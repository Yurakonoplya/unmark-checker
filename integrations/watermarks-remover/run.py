#!/usr/bin/env python3
"""Run guillaumemeyer/watermarks-remover on a marked sample and measure what came back.

One command, three steps, no model download:

    python3 integrations/watermarks-remover/run.py --checkout ~/watermarks-remover

    1. take a sample that carries a known mark (the bundled ones carry ours,
       and their key is public, so nothing has to be generated first);
    2. hand it to watermarks-remover, either through its HTTP service or by
       calling the scripts in a checkout;
    3. score what it returned with `unmark-checker check`.

Two ways in, and they measure different things:

    --service http://127.0.0.1:8765   POST /clean, the seam that project documents
                                      for other apps. For text it runs layer A and
                                      layer B, so the number covers the whole tool.
    --checkout /path/to/repo          calls service/scripts/clean_text.py (layer A)
                                      and, when a rewrite backend is configured,
                                      service/scripts/rewrite_text.py (layer B).

Layer A is a deterministic character scrub and needs nothing. Layer B rewrites the
text and needs a model of your own. A run that only got layer A is labelled as such
everywhere it is printed: on a statistical mark that is not a result about the tool,
it is a result about one of its two layers.

Stdlib only, on purpose: an integration that drags in dependencies is one more
reason not to try it.
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import os
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from contextlib import redirect_stdout
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DEFAULT_SAMPLE = REPO / "samples" / "UM-344F7E.txt"
# Printed in samples/README.md: the bundled samples are public and so is their key.
PUBLIC_SAMPLE_KEY = "unmark-checker-public-sample-key-v1"
DEFAULT_SERVICE = "http://127.0.0.1:8765"

LAYER_A = "layer A (character scrub)"
LAYER_AB = "layer A + layer B (character scrub, then rewrite)"


def _checker():
    """The checker itself, whether it is installed or just sitting in this tree."""
    try:
        from unmark_checker.cli import main
    except ModuleNotFoundError:
        sys.path.insert(0, str(REPO / "src"))
        from unmark_checker.cli import main
    return main


# --- their side ---------------------------------------------------------------


def clean_via_service(url: str, sample: Path, strategy: str | None) -> tuple[str, str, dict]:
    """POST /clean, the integration seam watermarks-remover documents for web apps."""
    options: dict[str, object] = {}
    if strategy:
        options["strategy"] = strategy
    payload = {
        "file": base64.b64encode(sample.read_bytes()).decode("ascii"),
        "name": sample.name,
    }
    if options:
        payload["options"] = options
    request = urllib.request.Request(
        url.rstrip("/") + "/clean",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    key = os.environ.get("WATERMARKS_SERVER_API_KEY")
    if key:
        request.add_header("Authorization", f"Bearer {key}")
    try:
        with urllib.request.urlopen(request, timeout=600) as response:
            answer = json.loads(response.read())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        message = detail
        try:
            message = json.loads(detail).get("error") or detail
        except json.JSONDecodeError:
            pass
        raise SystemExit(
            f"watermarks-remover refused the file ({exc.code}): {message}\n"
            "For text its /clean runs the rewrite layer as well, so it needs a model: "
            "set WATERMARKS_REWRITE_BACKEND (a local Ollama is enough) on the service, "
            "or measure the scrub alone with --checkout /path/to/repo."
        ) from exc
    except urllib.error.URLError as exc:
        raise SystemExit(
            f"no watermarks-remover service at {url}: {exc.reason}\n"
            "Start it (python3 service/scripts/server.py --port 8765) or pass "
            "--checkout /path/to/repo to call its scripts instead."
        ) from exc

    if not answer.get("ok"):
        raise SystemExit(f"watermarks-remover returned an error: {answer.get('error')}")
    cleaned = base64.b64decode(answer["cleaned"]).decode("utf-8")
    return cleaned, LAYER_AB, answer.get("report") or {}


def _script(checkout: Path, name: str) -> Path:
    path = checkout / "service" / "scripts" / name
    if not path.exists():
        raise SystemExit(
            f"{path} not found. --checkout expects a clone of "
            "https://github.com/guillaumemeyer/watermarks-remover"
        )
    return path


def clean_via_checkout(
    checkout: Path, sample: Path, layer_a_only: bool, strategy: str | None
) -> tuple[str, str, dict]:
    """Call their scripts directly: layer A always, layer B when a backend is set."""
    report: dict[str, object] = {}
    with tempfile.TemporaryDirectory() as tmp:
        scrubbed = Path(tmp) / "layer-a.txt"
        done = subprocess.run(
            [sys.executable, str(_script(checkout, "clean_text.py")),
             str(sample), "-o", str(scrubbed), "--stats"],
            capture_output=True, text=True,
        )
        if done.returncode != 0:
            raise SystemExit(f"clean_text.py failed:\n{done.stderr.strip()}")
        try:
            report["layer_a"] = json.loads(done.stderr)
        except json.JSONDecodeError:
            report["layer_a"] = {"stderr": done.stderr.strip()}

        backend = os.environ.get("WATERMARKS_REWRITE_BACKEND")
        if layer_a_only or not backend:
            return scrubbed.read_text(encoding="utf-8"), LAYER_A, report

        rewritten = Path(tmp) / "layer-b.txt"
        command = [sys.executable, str(_script(checkout, "rewrite_text.py")),
                   str(scrubbed), "-o", str(rewritten)]
        if strategy:
            command += ["--tactic", strategy]
        done = subprocess.run(command, capture_output=True, text=True)
        if done.returncode != 0:
            raise SystemExit(f"rewrite_text.py failed:\n{done.stderr.strip()}")
        report["layer_b"] = {"backend": backend, "stderr": done.stderr.strip()[-500:]}
        return rewritten.read_text(encoding="utf-8"), LAYER_AB, report


# --- our side -----------------------------------------------------------------


def measure(sample: Path, returned: Path, key: str, as_json: bool) -> dict | None:
    """Run `unmark-checker check` in process. Prints its own prose unless as_json."""
    argv = ["check", "--sample", str(sample), "--returned", str(returned), "--key", key]
    if not as_json:
        _checker()(argv)
        return None
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        _checker()(argv + ["--json"])
    return json.loads(buffer.getvalue())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run watermarks-remover on a marked sample and measure the result.",
    )
    parser.add_argument("--sample", default=str(DEFAULT_SAMPLE),
                        help=f"marked sample to hand over (default {DEFAULT_SAMPLE.name} "
                             "from samples/, whose key is public)")
    parser.add_argument("--service", nargs="?", const=DEFAULT_SERVICE, default=None,
                        help=f"call the HTTP service instead of a checkout "
                             f"(default {DEFAULT_SERVICE} when the flag is given bare)")
    parser.add_argument("--checkout", default=os.environ.get("WATERMARKS_REMOVER_DIR"),
                        help="clone of guillaumemeyer/watermarks-remover to call directly "
                             "(WATERMARKS_REMOVER_DIR)")
    parser.add_argument("--layer-a-only", action="store_true",
                        help="checkout mode: stop after the character scrub even if a "
                             "rewrite backend is configured")
    parser.add_argument("--strategy", default=None,
                        help="rewrite strategy passed through to their side: a "
                             "tactic@intensity list for the service, a tactic for a checkout")
    parser.add_argument("--out", default=None,
                        help="where to keep what came back (default <sample>.watermarks-remover.txt)")
    parser.add_argument("--key", default=os.environ.get("UNMARK_CHECKER_KEY"),
                        help="key the sample was generated with; the bundled samples "
                             "use the public one and need no key at all")
    parser.add_argument("--json", action="store_true",
                        help="print one machine-readable record instead of prose")
    args = parser.parse_args(argv)

    sample = Path(args.sample)
    if not sample.exists():
        raise SystemExit(f"no such sample: {sample}")

    key = args.key
    if not key:
        if sample.resolve().parent == (REPO / "samples").resolve():
            key = PUBLIC_SAMPLE_KEY
        else:
            raise SystemExit(
                "no key: this sample is not one of the bundled ones, so pass --key or set "
                "UNMARK_CHECKER_KEY to the key it was generated with."
            )

    if args.service and args.checkout:
        raise SystemExit("--service and --checkout are two ways to reach the same tool; pick one.")
    if not args.service and not args.checkout:
        raise SystemExit(
            "nothing to run: pass --checkout /path/to/watermarks-remover, or --service to "
            f"call a running one ({DEFAULT_SERVICE} by default)."
        )

    if args.service:
        where = args.service
        cleaned, layers, report = clean_via_service(args.service, sample, args.strategy)
    else:
        where = str(Path(args.checkout).expanduser())
        cleaned, layers, report = clean_via_checkout(
            Path(where), sample, args.layer_a_only, args.strategy
        )

    out = Path(args.out) if args.out else Path.cwd() / f"{sample.stem}.watermarks-remover.txt"
    out.write_text(cleaned, encoding="utf-8")

    if args.json:
        record = {
            "tool": "guillaumemeyer/watermarks-remover",
            "ran": where,
            "layers": layers,
            "sample": str(sample),
            "returned": str(out),
            "their_report": report,
            "measurement": measure(sample, out, key, as_json=True),
        }
        print(json.dumps(record, indent=2, ensure_ascii=False))
        return 0

    print(f"watermarks-remover, {layers}")
    print(f"  ran:      {where}")
    print(f"  sample:   {sample}")
    print(f"  returned: {out}")
    if report:
        print(f"  its own report: {json.dumps(report, ensure_ascii=False)[:400]}")
    if layers == LAYER_A:
        print(
            "  note: only the character scrub ran. It removes invisible characters and\n"
            "  look-alike spaces, which is not where a statistical mark lives, so read the\n"
            "  score below as a reading of that layer, not of the tool."
        )
    print("\nmeasured by unmark-checker:")
    measure(sample, out, key, as_json=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

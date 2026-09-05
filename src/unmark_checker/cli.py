"""Command line: generate samples, check what a tool returned, build the matrix.

Three commands, and the middle one is the point of the repository:

    unmark-checker generate --num 2 --words 100 --scheme shallow --out samples
    unmark-checker check --sample samples/UM-1A2B3C.txt --returned cleaned.txt
    unmark-checker matrix --dir results

The secret key never appears in this file and is never written to disk. Pass it
in `UNMARK_CHECKER_KEY` (preferred: it stays out of your shell history) or with
`--key`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

from . import thresholds
from .identify import is_same_text, overlap
from .schemes import (
    DEFAULT_SCHEME,
    PRESETS,
    LengthBucket,
    PROMPTS,
    build_scheme,
    key_fingerprint,
)

DEFAULT_MODEL = "gpt2"
MANIFEST_NAME = "manifest.json"
KEY_ENV = "UNMARK_CHECKER_KEY"


# --- helpers -----------------------------------------------------------------


def _secret(args) -> str:
    secret = args.key or os.environ.get(KEY_ENV, "")
    if not secret:
        raise SystemExit(
            f"no key: pass --key or set {KEY_ENV}. The key is yours; samples "
            "generated with it can only be scored with it."
        )
    return secret


def _sample_id(text: str) -> str:
    """Sample id derived from the text itself, so the same text is always the
    same sample and a renamed file is still recognisable."""
    return "UM-" + hashlib.sha256(text.encode("utf-8")).hexdigest()[:6].upper()


def _read(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    return Path(path).read_text(encoding="utf-8")


def _load_manifest(directory: Path) -> dict:
    path = directory / MANIFEST_NAME
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _manifest_entry(sample_path: Path) -> dict:
    """What we know about a sample file, if it sits next to its manifest."""
    manifest = _load_manifest(sample_path.parent)
    for entry in manifest.get("samples", []):
        if entry.get("file") == sample_path.name:
            return entry
    return {}


def _words(text: str) -> int:
    return len(text.split())


# --- generate ----------------------------------------------------------------


def cmd_generate(args) -> int:
    from .corpus import human_texts
    from .detector import KeyAwareDetector
    from .watermark import generate, load_lm

    secret = _secret(args)
    scheme = build_scheme(args.scheme, secret)
    bucket = LengthBucket(f"w{args.words}", args.words)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.control == "human":
        texts = human_texts(bucket, args.num)
        lm = None
    else:
        print(f"loading {args.model} on {args.device} (first run downloads it)", flush=True)
        lm = load_lm(args.model, device=args.device, num_threads=args.threads)

    detector_lm = lm
    if detector_lm is None:
        from .watermark import load_tokenizer
        detector_lm = load_tokenizer(args.model, device=args.device)
    detector = KeyAwareDetector(detector_lm, scheme)

    manifest = _load_manifest(out_dir)
    entries = manifest.get("samples", [])
    written = []
    planted = 0

    for i in range(args.num):
        started = time.time()
        if args.control == "human":
            text = texts[i]
        else:
            text = generate(
                lm,
                PROMPTS[(args.seed + i) % len(PROMPTS)],
                bucket,
                scheme=None if args.control == "model" else scheme,
                seed=args.seed + i,
            )
        took = time.time() - started
        detection = detector.score_text(text)
        sample_id = _sample_id(text)
        name = f"{sample_id}.txt"
        (out_dir / name).write_text(text, encoding="utf-8")
        entry = {
            "id": sample_id,
            "file": name,
            "scheme": args.scheme,
            "model": args.model if args.control != "human" else "human-corpus",
            "control": args.control or None,
            "words": _words(text),
            "z_at_build": round(detection.z, 3),
            "outcome": detection.outcome,
            "key_fingerprint": key_fingerprint(secret),
            "seconds": round(took, 1),
        }
        entries = [e for e in entries if e.get("file") != name] + [entry]
        written.append(entry)
        if detection.outcome == thresholds.MARK_PRESENT:
            planted += 1
        print(
            f"{sample_id}  {entry['words']:>5} words  z={detection.z:6.2f}  "
            f"{detection.outcome:<12} {took:5.1f}s  -> {out_dir / name}",
            flush=True,
        )

    manifest["samples"] = entries
    manifest["scheme_presets"] = {
        name: {"ngram_len": p.ngram_len, "depth": p.depth,
               "context_history_size": p.context_history_size}
        for name, p in PRESETS.items()
    }
    (out_dir / MANIFEST_NAME).write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"\nmanifest: {out_dir / MANIFEST_NAME} (no key is stored in it)")

    if args.control:
        print(
            "control texts carry no mark by construction: their scores are the "
            "baseline your 'the mark is gone' readings are read against."
        )
        return 0

    if planted == 0:
        print(
            "\nSTOP: the detector found no mark in any generated sample. Nothing "
            "measured on these texts means anything. Most often this is the "
            "generator (greedy decoding, a wrong transformers version, or a model "
            "whose sampling was overridden). Fix that before you check any tool.",
            file=sys.stderr,
        )
        return 2
    if planted < args.num:
        print(
            f"\nwarning: the mark planted in {planted} of {args.num} samples. Use "
            "only the samples above the detection line; short texts carry less "
            "evidence, so ask for more words if this repeats.",
            file=sys.stderr,
        )
    return 0


# --- check -------------------------------------------------------------------


def _describe(kpi_row: dict, sample_words: int, returned_words: int) -> str:
    z = kpi_row.get("z")
    outcome = kpi_row.get("outcome")
    lines = []
    if outcome == thresholds.MARK_PRESENT:
        lines.append(
            f"The mark is still there. Detector score {z:.2f}, at or above {thresholds.Z_DETECT}. "
            "Under the null case a clean text scores that high about three times in a hundred "
            "thousand, so this is not a coin flip: the tool did not take this mark out."
        )
    elif outcome == thresholds.UNCERTAIN:
        lines.append(
            f"In between. Detector score {z:.2f}, between {thresholds.Z_UNCERTAIN} and "
            f"{thresholds.Z_DETECT}. Marks of this class have a genuinely wide grey band, and "
            "rounding this to a yes or a no would be a lie in one direction or the other."
        )
    else:
        lines.append(
            f"The mark is gone. Detector score {z:.2f}, below {thresholds.Z_UNCERTAIN}. On this "
            "sample, on this run, the mark did not survive."
        )
    lines.append(
        f"Meaning kept: {kpi_row['similarity']:.2f} of 1.00. "
        f"Facts kept: {kpi_row['facts_preserved']} of {kpi_row['facts_total']}."
    )
    missing = kpi_row.get("facts_missing") or []
    if missing:
        lines.append("Facts lost: " + ", ".join(missing))
    lines.append(
        f"Longest verbatim run: {kpi_row['verbatim_longest_run']} words. "
        f"Words changed: {kpi_row['changed_share'] * 100:.0f}%. "
        f"Length: {kpi_row['length_ratio']:.2f}x ({sample_words} words in, {returned_words} out)."
    )
    if kpi_row["length_ratio"] < 0.7:
        lines.append(
            "Note: the result is much shorter than the sample. Removing a mark by "
            "deleting the text is not removing a mark."
        )
    if kpi_row["verbatim_longest_run"] >= 8 and kpi_row["outcome"] == thresholds.MARK_GONE:
        lines.append(
            "Note: long verbatim runs survived, yet the score fell. Worth a second run: "
            "a mark of this class lives exactly in runs like these."
        )
    return "\n".join(lines)


def cmd_check(args) -> int:
    from .detector import KeyAwareDetector
    from .kpi import compute
    from .watermark import load_tokenizer

    sample_text = _read(args.sample)
    returned_text = _read(args.returned)
    sample_path = Path(args.sample) if args.sample != "-" else None

    known = _manifest_entry(sample_path) if sample_path else {}
    scheme_name = args.scheme or known.get("scheme") or DEFAULT_SCHEME
    model_id = args.model or known.get("model") or DEFAULT_MODEL

    secret = _secret(args)
    if known.get("key_fingerprint") and known["key_fingerprint"] != key_fingerprint(secret):
        print(
            "warning: this sample was generated with a different key. The score below "
            "will be noise, not a measurement.",
            file=sys.stderr,
        )

    sample_words = _words(sample_text)
    returned_words = _words(returned_text)

    # Not our text, and the detector is not called: a score on material with no
    # known starting point says nothing, and this tool is not an oracle on
    # someone else's writing.
    if not is_same_text(returned_text, sample_text):
        row = {
            "outcome": thresholds.NOT_OUR_TEXT,
            "overlap": round(overlap(returned_text, sample_text), 3),
            "sample_words": sample_words,
            "returned_words": returned_words,
        }
        if args.json:
            print(json.dumps(row, indent=2, ensure_ascii=False))
        else:
            print(
                "Not the sample. Too few of the words in the returned text come from "
                f"the sample ({row['overlap']:.0%} of its content words, the line is 50%). "
                "Either the files do not belong together, or the text was rewritten past "
                "recognition. No score is reported: a score on a text that cannot be tied "
                "to a known starting point means nothing."
            )
        return 0

    lm = load_tokenizer(model_id)
    scheme = build_scheme(scheme_name, secret)
    detection = KeyAwareDetector(lm, scheme).score_text(returned_text)
    row = compute(sample_text, returned_text, detection.z, detection.outcome)

    if args.json:
        payload = dict(row)
        payload.update({
            "sample_id": known.get("id") or _sample_id(sample_text),
            "scheme": scheme_name,
            "model": model_id,
            "sample_words": sample_words,
            "returned_words": returned_words,
            "n_eff": detection.n_eff,
            "p_value": detection.p_value,
        })
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(_describe(row, sample_words, returned_words))
    return 0


# --- matrix ------------------------------------------------------------------


def cmd_matrix(args) -> int:
    from .matrix import build

    directory = Path(args.dir)
    if not directory.is_dir():
        raise SystemExit(f"not a directory: {directory}")
    text, problems = build(directory, Path(args.out) if args.out else None)
    if args.out:
        print(f"written: {args.out}")
    else:
        print(text)
    for problem in problems:
        print(f"warning: {problem}", file=sys.stderr)
    return 1 if problems else 0


# --- entry point -------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="unmark-checker",
        description=(
            "Plant a statistical text watermark of the SynthID-Text class with your own "
            "key, hand the text to any tool that claims to remove watermarks, and measure "
            "what came back."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("generate", help="write watermarked samples with your own key")
    gen.add_argument("--key", help=f"your secret; better set {KEY_ENV} instead")
    gen.add_argument("--num", type=int, default=2, help="how many samples (default 2)")
    gen.add_argument("--words", type=int, default=100, help="target length in words (default 100)")
    gen.add_argument("--scheme", default=DEFAULT_SCHEME, choices=sorted(PRESETS),
                     help=f"scheme configuration (default {DEFAULT_SCHEME})")
    gen.add_argument("--model", default=DEFAULT_MODEL,
                     help=f"open-weights generator (default {DEFAULT_MODEL})")
    gen.add_argument("--out", default="samples", help="output folder (default samples)")
    gen.add_argument("--seed", type=int, default=0, help="first seed; samples are seed-derived")
    gen.add_argument("--device", default="cpu", help="cpu or cuda (default cpu)")
    gen.add_argument("--threads", type=int, default=None, help="torch CPU threads")
    gen.add_argument("--control", choices=("model", "human"), default=None,
                     help="write control texts that carry no mark: unmarked output of the "
                          "same model, or bundled human prose")
    gen.set_defaults(func=cmd_generate)

    chk = sub.add_parser("check", help="measure what a tool returned")
    chk.add_argument("--sample", required=True, help="the sample you handed over ('-' for stdin)")
    chk.add_argument("--returned", required=True, help="what the tool gave back ('-' for stdin)")
    chk.add_argument("--key", help=f"your secret; better set {KEY_ENV} instead")
    chk.add_argument("--scheme", choices=sorted(PRESETS), default=None,
                     help="scheme the sample was generated with (read from the manifest if absent)")
    chk.add_argument("--model", default=None,
                     help="model whose tokenizer the sample was made with "
                          "(read from the manifest if absent)")
    chk.add_argument("--json", action="store_true", help="print the metric set as JSON")
    chk.set_defaults(func=cmd_check)

    mat = sub.add_parser("matrix", help="one table out of a folder of service files")
    mat.add_argument("--dir", required=True, help="folder of service JSON files")
    mat.add_argument("--out", default=None, help="write the table to this file")
    mat.set_defaults(func=cmd_matrix)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)

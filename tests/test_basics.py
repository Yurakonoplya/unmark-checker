"""Checks that need no model download: run them with `python tests/test_basics.py`.

They cover the parts where a silent change would corrupt published numbers: key
derivation, the frozen thresholds, the "is this still our sample" rule, and the
table builder.
"""

from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from unmark_checker import thresholds  # noqa: E402
from unmark_checker.cli import main  # noqa: E402
from unmark_checker.identify import is_same_text, overlap  # noqa: E402
from unmark_checker.matrix import build  # noqa: E402
from unmark_checker.schemes import PRESETS, build_scheme, derive_keys  # noqa: E402


def test_keys_are_stable_and_secret_specific() -> None:
    a = derive_keys("secret one", 20, "default")
    assert a == derive_keys("secret one", 20, "default"), "same secret must give same keys"
    assert a != derive_keys("secret two", 20, "default"), "different secrets must differ"
    assert a != derive_keys("secret one", 20, "deep"), "different presets must differ"
    assert len(set(a)) == 20, "keys must be distinct"
    assert all(1 <= k <= 65535 for k in a)


def test_presets_match_the_documented_grid() -> None:
    grid = {name: (p.ngram_len, p.depth, p.context_history_size) for name, p in PRESETS.items()}
    assert grid == {
        "shallow": (2, 10, 256),
        "default": (5, 20, 1024),
        "deep": (8, 30, 1024),
    }
    scheme = build_scheme("shallow", "secret")
    assert scheme.depth == 10 and scheme.kwargs()["ngram_len"] == 2


def test_thresholds_are_frozen() -> None:
    assert (thresholds.Z_DETECT, thresholds.Z_UNCERTAIN) == (4.0, 2.0)
    assert thresholds.classify(4.0) == thresholds.MARK_PRESENT
    assert thresholds.classify(3.99) == thresholds.UNCERTAIN
    assert thresholds.classify(1.99) == thresholds.MARK_GONE


def test_identification_rule() -> None:
    sample = "Beekeeping in Malacca began in 1994 with eleven hives and a borrowed smoker."
    assert is_same_text(sample, sample)
    assert is_same_text("In 1994 Malacca beekeeping started, eleven hives, one borrowed smoker.", sample)
    assert not is_same_text("Bicycle maintenance rewards patience and a torque wrench.", sample)
    assert overlap("", sample) == 0.0


def test_check_warns_when_the_manifest_says_the_mark_never_planted() -> None:
    """A sample whose mark never planted is still measured, but never silently.

    The pair below fails the identification rule on purpose, so `check` returns
    `not_our_text` before the detector is built: the warning has to be printed
    without loading any model.
    """
    sample = "Beekeeping in Malacca began in 1994 with eleven hives and a borrowed smoker."
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        (folder / "UM-000001.txt").write_text(sample, encoding="utf-8")
        (folder / "manifest.json").write_text(
            json.dumps({"samples": [{
                "id": "UM-000001", "file": "UM-000001.txt", "scheme": "shallow",
                "model": "gpt2", "outcome": thresholds.MARK_GONE,
            }]}),
            encoding="utf-8",
        )
        (folder / "returned.txt").write_text(
            "Bicycle maintenance rewards patience and a torque wrench.", encoding="utf-8"
        )
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main([
                "check",
                "--sample", str(folder / "UM-000001.txt"),
                "--returned", str(folder / "returned.txt"),
                "--key", "a key for the test only",
            ])
    assert code == 0, code
    assert "warning" in err.getvalue(), err.getvalue()
    assert thresholds.MARK_GONE in err.getvalue(), err.getvalue()
    assert "Not the sample" in out.getvalue(), out.getvalue()


def test_matrix_table() -> None:
    service = {
        "slug": "t", "name": "t.example.com", "url": "https://example.com", "kind": "rewriter",
        "runs": [{
            "id": "r1", "date": "2026-09-05", "by": "us", "sample_id": "UM-000001",
            "kpi": {"z": 1.0, "outcome": "mark_gone", "similarity": 0.9,
                    "facts_total": 4, "facts_preserved": 4, "verbatim_longest_run": 3,
                    "changed_share": 0.5, "length_ratio": 1.0, "kpi_version": 1},
        }],
    }
    with tempfile.TemporaryDirectory() as tmp:
        Path(tmp, "t.json").write_text(json.dumps(service), encoding="utf-8")
        table, problems = build(Path(tmp))
    assert not problems, problems
    assert "t.example.com" in table and "gone" in table and "4/4" in table


if __name__ == "__main__":
    failures = 0
    for name, func in sorted(globals().items()):
        if name.startswith("test_") and callable(func):
            try:
                func()
                print(f"ok   {name}")
            except AssertionError as exc:
                failures += 1
                print(f"FAIL {name}: {exc}")
    print("all good" if not failures else f"{failures} failed")
    sys.exit(1 if failures else 0)

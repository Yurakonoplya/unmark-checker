"""Build one summary table out of a folder of service files.

The input is the same data format the published pages are built from: one JSON
file per service, described in `docs/service-file.md`. The output is a Markdown
table you can paste anywhere, plus a list of services that could not be run,
because a tool that refuses a text is also a result.
"""

from __future__ import annotations

import json
from pathlib import Path

REQUIRED_SERVICE_FIELDS = ("slug", "name", "url", "kind")
REQUIRED_RUN_FIELDS = ("id", "date", "sample_id", "kpi")

OUTCOME_WORDS = {
    "mark_present": "still there",
    "uncertain": "in between",
    "mark_gone": "gone",
    "not_our_text": "not the sample",
}


def load_services(directory: Path) -> tuple[list[dict], list[str]]:
    """Read every *.json in `directory`. Returns services and complaints."""
    problems: list[str] = []
    services: list[dict] = []
    for path in sorted(directory.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            problems.append(f"{path.name}: unreadable ({exc})")
            continue
        missing = [f for f in REQUIRED_SERVICE_FIELDS if not data.get(f)]
        if missing:
            problems.append(f"{path.name}: missing {', '.join(missing)}")
            continue
        for run in data.get("runs", []):
            gaps = [f for f in REQUIRED_RUN_FIELDS if run.get(f) in (None, "")]
            if gaps:
                problems.append(f"{path.name}: run {run.get('id', '?')} missing {', '.join(gaps)}")
        services.append(data)
    return services, problems


def _fmt(value, digits: int = 2, suffix: str = "") -> str:
    if value is None:
        return "-"
    try:
        return f"{float(value):.{digits}f}{suffix}"
    except (TypeError, ValueError):
        return str(value)


def _run_row(service: dict, run: dict) -> list[str]:
    kpi = run.get("kpi") or {}
    total = kpi.get("facts_total")
    kept = kpi.get("facts_preserved")
    facts = f"{kept}/{total}" if total is not None and kept is not None else "-"
    changed = kpi.get("changed_share")
    return [
        service.get("name", service.get("slug", "?")),
        service.get("kind", "-"),
        run.get("date", "-"),
        run.get("sample_id", "-"),
        OUTCOME_WORDS.get(kpi.get("outcome", ""), kpi.get("outcome", "-")),
        _fmt(kpi.get("z")),
        _fmt(kpi.get("similarity")),
        facts,
        str(kpi.get("verbatim_longest_run", "-")),
        "-" if changed is None else f"{float(changed) * 100:.0f}%",
        _fmt(kpi.get("length_ratio"), suffix="x"),
        run.get("by", "-"),
    ]


HEADER = [
    "Service", "Kind", "Date", "Sample", "Mark", "z", "Meaning",
    "Facts kept", "Verbatim run", "Changed", "Length", "Run by",
]


def render(services: list[dict], source: str = "") -> str:
    rows = []
    not_run = []
    fixtures = []
    for service in sorted(services, key=lambda s: s.get("name", s.get("slug", ""))):
        if service.get("fixture"):
            fixtures.append(service.get("name", service.get("slug", "?")))
        runs = service.get("runs") or []
        if not runs:
            not_run.append(
                f"- **{service.get('name')}** ({service.get('url')}): "
                f"{service.get('not_run') or 'no run recorded'}"
            )
            continue
        for run in sorted(runs, key=lambda r: (r.get("date", ""), r.get("sample_id", ""))):
            rows.append(_run_row(service, run))

    out: list[str] = ["# Watermark removal: measured results", ""]
    if source:
        out += [f"Built from the service files in `{source}`.", ""]
    out += [
        "Every row is one run: one sample with a known key, handed to one tool, "
        "and the tool's output measured against the sample it came from. `z` is the "
        "key-aware detector score; at or above 4.0 the mark is still there, below "
        "2.0 it is gone, in between is the grey zone. The other columns say what the "
        "text cost: meaning similarity, facts kept, the longest run of words left "
        "verbatim, the share of words changed, and the length ratio.",
        "",
    ]
    if rows:
        out.append("| " + " | ".join(HEADER) + " |")
        out.append("|" + "|".join(["---"] * len(HEADER)) + "|")
        out += ["| " + " | ".join(r) + " |" for r in rows]
    else:
        out.append("*No runs recorded yet.*")
    if not_run:
        out += ["", "## Could not be run", ""] + not_run
    if fixtures:
        out += [
            "",
            "## Example data in this table",
            "",
            "These entries are marked `fixture` in their files: they are shape "
            "examples, not measurements. " + ", ".join(fixtures) + ".",
        ]
    out.append("")
    return "\n".join(out)


def build(directory: Path, out_path: Path | None = None) -> tuple[str, list[str]]:
    services, problems = load_services(directory)
    text = render(services, source=str(directory))
    if out_path is not None:
        out_path.write_text(text, encoding="utf-8")
    return text, problems

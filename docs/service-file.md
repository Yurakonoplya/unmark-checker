# The service file

One JSON file per tool. `unmark-checker matrix` reads a folder of these files and
prints one table; the published pages at https://unmarkclaude.io/check/services
are built from files of exactly this shape, so a table you build locally and the
table on the site are the same object.

```json
{
  "slug": "example-rewriter",
  "name": "example-rewriter.example.com",
  "url": "https://example.com/rewriter",
  "kind": "rewriter",
  "access": "Free, no sign-up, minimum 40 characters (read 5 September 2026).",
  "first_seen": "2026-09-05",
  "runs": [
    {
      "id": "2026-09-05-um-1a2b3c",
      "date": "2026-09-05",
      "by": "us",
      "sample_id": "UM-1A2B3C",
      "sample_words": 1250,
      "scheme": "shallow",
      "kpi": {
        "z": 1.23,
        "outcome": "mark_gone",
        "similarity": 0.81,
        "facts_total": 23,
        "facts_preserved": 21,
        "facts_missing": ["2019", "Malacca"],
        "verbatim_longest_run": 14,
        "changed_share": 0.58,
        "length_ratio": 0.97,
        "kpi_version": 1
      },
      "note": "Default mode; output pasted back unchanged.",
      "artifact": "results/2026-09-05/example-rewriter/UM-1A2B3C.txt"
    }
  ]
}
```

## Fields

| Field | Meaning |
|---|---|
| `slug` | latin letters, digits and dashes, taken from the domain or the name |
| `name`, `url` | how the tool calls itself, and where it lives |
| `kind` | `cleaner` (strips characters and metadata), `rewriter` (rewrites with a model), `humanizer` (general-purpose humanizer), `open-source` (code you run yourself), `assistant` (a chat assistant asked to rewrite), `ours` (our own pipeline) |
| `access` | a fact about free access, with the date it was read; no opinions |
| `first_seen` | the date the tool entered the list |
| `runs` | one entry per sample handed to this tool |
| `not_run` | why a tool could not be run (trial shorter than the sample, sign-up required, form refused the text), with a date. A tool that cannot be run is also a result, and gets a file with an empty `runs` |
| `fixture` | `true` marks a file that is a shape example, not a measurement |

## Fields of a run

| Field | Meaning |
|---|---|
| `id` | unique within the file: date, sample id, and a short suffix |
| `date` | the day the run happened |
| `by` | `us` or `reader` |
| `sample_id`, `sample_words`, `scheme` | which sample was handed over and how it was marked |
| `kpi` | the metric set, exactly as `unmark-checker check --json` prints it |
| `note` | what mode or settings were used, in one line |
| `artifact` | path to the saved output, so the row can be recomputed from disk |

## The metric set

`kpi` is what `check --json` produces, and every key is defined the same way for
every tool, for our own pipeline, and for a text a reader pastes into the hosted
checker:

| Key | What it is |
|---|---|
| `z` | key-aware detector score on the returned text |
| `outcome` | `mark_present` (z >= 4.0), `uncertain` (2.0 <= z < 4.0), `mark_gone` (z < 2.0), `not_our_text` |
| `similarity` | 0..1, how much of the meaning survived (mean over 120-word chunks of the sample, each matched to its closest chunk of the result) |
| `facts_total`, `facts_preserved`, `facts_missing` | numbers, dates, links, names and terms, checked deterministically; at most 20 missing ones are listed |
| `verbatim_longest_run` | longest run of words left verbatim |
| `changed_share` | 0..1, share of sample words in no matching block |
| `length_ratio` | words out divided by words in |
| `kpi_version` | version of this metric set; runs are comparable within one version |

A run with `outcome: "not_our_text"` carries no `kpi`: the returned text could not
be tied to the sample, and a score on it would say nothing.

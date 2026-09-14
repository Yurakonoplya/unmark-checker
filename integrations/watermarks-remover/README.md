# watermarks-remover, run and measured

[guillaumemeyer/watermarks-remover](https://github.com/guillaumemeyer/watermarks-remover)
strips watermarks; this repository measures what a strip actually did to a
statistical text mark. `run.py` joins the two: it hands a marked sample to
watermarks-remover, takes back what it returns, and scores it with
`unmark-checker check`.

```bash
# through the HTTP service it documents for other apps (layer A + layer B)
python3 service/scripts/server.py --port 8765      # in their checkout
python3 integrations/watermarks-remover/run.py --service

# or by calling the scripts in a checkout
python3 integrations/watermarks-remover/run.py --checkout ~/watermarks-remover
```

Nothing has to be generated first: the default sample is `samples/UM-344F7E.txt`,
one of the bundled marked texts, and their key is public. Scoring reads a
tokenizer and the key, never model weights, so the measurement itself takes
seconds.

## What each way in measures

| | reaches | covers |
| --- | --- | --- |
| `--service [url]` | `POST /clean` | layer A and layer B: their service runs the rewrite for text and refuses without a backend |
| `--checkout DIR` | `clean_text.py`, then `rewrite_text.py` | layer A always; layer B only when `WATERMARKS_REWRITE_BACKEND` is set |

Layer A is a deterministic character scrub: invisible codepoints, look-alike
spaces, bidi marks. Layer B rewrites the text with a model of your own.

That distinction is the whole reason this adapter labels every run. A statistical
mark of the SynthID-Text class lives in which words were chosen, not in the
characters they are spelled with, so layer A cannot move it and never claimed to.
A run that only got layer A is a reading of that layer, not a verdict on the tool,
and `run.py` prints it as such.

## A run, end to end

watermarks-remover v0.7.0 (commit 41ef353), sample `UM-344F7E` (1021 words),
14 September 2026, through `POST /clean` with their default strategy
(`paraphrase@0.8, mlm@0.2`) against an OpenAI-compatible endpoint on open
weights. Six minutes, most of it the rewrite:

```
watermarks-remover, layer A + layer B (character scrub, then rewrite)
  its own report: removed_count 0, replaced_count 0; layer_b paraphrase then mlm

measured by unmark-checker:
In between. Detector score 2.72, between 2.0 and 4.0. Marks of this class have a
genuinely wide grey band, and rounding this to a yes or a no would be a lie in one
direction or the other.
Meaning kept: 0.89 of 1.00. Facts kept: 42 of 48.
Longest verbatim run: 16 words. Words changed: 54%. Length: 0.84x (1021 in, 872 out).
```

The same tool on the same sample with layer A alone: score 36.11, `mark_present`,
meaning 1.00, nothing changed. Two honest numbers about two different layers.

One run on one sample is one run on one sample. `results/` holds the dated runs
this repository publishes, `unmark-checker matrix --dir results/services` builds
the table out of them, and the same numbers are on
<https://unmarkclaude.io/check/services>.

## Options

| | |
| --- | --- |
| `--sample PATH` | which marked sample to hand over (default `samples/UM-344F7E.txt`) |
| `--key`, `UNMARK_CHECKER_KEY` | key the sample was generated with; bundled samples need none |
| `--strategy` | passed through to their side: `tactic@intensity` list for the service, a tactic for a checkout |
| `--layer-a-only` | checkout mode: stop after the scrub even when a rewrite backend is set |
| `--out PATH` | where to keep what came back (default `<sample>.watermarks-remover.txt`) |
| `--json` | one record: what ran, their own report, and the full metric set |

`run.py` is stdlib only. `unmark-checker check` needs this package installed
(`pip install -e .`), and it finds it in this tree if it is not.

Not affiliated with watermarks-remover. It is run here as any user would run it,
from a clean checkout with default options, and its own report is printed next to
our measurement so the two can be told apart.

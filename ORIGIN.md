# Where this code came from, and how it stays in sync

Most modules here are copies of code that runs the hosted checker at
https://unmarkclaude.io/check. They are copies on purpose: the published
measurements and the measurements you make locally have to come from one
computation, and a repository that reimplements the metrics "in its own way"
would quietly stop being a check on anything.

**The rule: fix it in the source first, then port the fix here.** A patch that
lands only in this repository makes the two copies disagree, and the disagreement
would show up as a number nobody can reproduce. Issues and pull requests against
these files are welcome; they are applied upstream and land here in the next
release, which is why the table below carries a hash per file.

## What was copied, and from where

Source: the internal unmarkclaude.io repository, revision
`e58f0811c70ea2d64114c68d4cf80d827885ff03` (5 September 2026). Two of the copied
files were still uncommitted work at that revision, so the SHA-256 column,
not the revision, identifies the exact bytes each copy was made from.

| File here | Copied from | SHA-256 of the source (first 16) |
|---|---|---|
| `src/unmark_checker/detector.py` | `bench/unmark_bench/detector.py` | `a03dfd90d18f239d` |
| `src/unmark_checker/thresholds.py` | `bench/unmark_bench/thresholds.py` | `41401a4b2a8439fd` |
| `src/unmark_checker/watermark.py` | `bench/unmark_bench/watermark.py` | `54490406257022b2` |
| `src/unmark_checker/schemes.py` | `bench/unmark_bench/schemes.py` | `b2bec85fae805727` |
| `src/unmark_checker/corpus.py` | `bench/unmark_bench/corpus.py` | `707b724b75907a96` |
| `src/unmark_checker/data/human_corpus.txt` | `bench/data/human_corpus.txt` | `4a10031be840fb23` |
| `src/unmark_checker/kpi.py` | `core/unmark_core/kpi.py` | `ea6d973afebe799f` |
| `src/unmark_checker/embed.py` | `core/unmark_core/embed.py` | `2335e73d7f5dcecc` |
| `src/unmark_checker/entities.py` | `core/unmark_core/entities.py` | `992b05bb63a55b67` |
| `METHODOLOGY.md` | `bench/METHODOLOGY.md` | `04614e7a42fb38b6` |

`kpi.py`, `embed.py` and `entities.py` are byte-for-byte the same code as the
source: only comments and docstrings were translated into English, and this was
checked mechanically (the parsed syntax trees are identical once docstrings are
removed). If you find a difference in behaviour, that is a bug in the port.

## Where the copies deliberately differ

Four changes, each one because the source runs a service and this runs on your
machine:

1. **No keys.** The internal copy of `schemes.py` carries the keys of our own
   sample pool. Here the presets carry only the public shape of a scheme
   (context window, tournament depth, repetition history) and the keys are
   derived from your secret in `derive_keys()`. Nothing in this repository can
   score our published samples, and nothing in it lets a tool recognise them.
2. **Outcome names.** The internal detector labels its three outcomes
   `detected` / `uncertain` / `not_detected`; the site and its published pages
   say `mark_present` / `uncertain` / `mark_gone`. This copy uses the published
   names, so a local run and a run on the site read the same. The two thresholds
   and the arithmetic behind them are untouched.
3. **A tokenizer-only loading path** (`watermark.load_tokenizer`). Scoring a text
   needs the tokenizer and the key, never the model weights; skipping the weights
   turns `check` from a minute into a second.
4. **Generation returns text, not token ids.** The internal stand keeps ids
   around for its own bookkeeping; here every text goes through the same
   text -> tokenizer -> detector path, which is also what the methodology
   requires of every group.

## What was deliberately not copied

Nothing that removes a mark. This repository checks; it does not clean. The
pipeline that removes watermarks, the sample pool of the hosted checker and its
keys, and everything belonging to the service (accounts, payments, storage) stay
out of it entirely. That boundary is the reason the code here can be open at all.

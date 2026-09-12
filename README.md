# unmark-checker

Plant a statistical text watermark of the SynthID-Text class in a text **with your
own key**, hand that text to any tool that claims to remove watermarks, and
measure what came back: is the mark still there, and what did the text cost.

Nobody can tell you whether a given text still carries a *vendor's* watermark:
the key that shaped it belongs to the vendor. But you can hold a key of your own.
Mark a text with it, and you know exactly what went in, so you can say exactly
what is left, and a detector that knows the key is the strongest detector that
can exist for that text. That is the trick this repository is built on, and it is
the only honest way to test these tools.

## Who this is for

- anyone deciding whether a "watermark remover" or "humanizer" does anything at
  all, before paying for it;
- anyone comparing several such tools on one ruler, with results others can
  reproduce;
- developers and writers who will not paste their own text into someone else's
  website to find out.

## Without installing anything

The same check runs in a browser at **https://unmarkclaude.io/check**, on a
sample marked with that site's key: paste what a tool returned and get the same
numbers. Results measured that way are published, tool by tool, at
**https://unmarkclaude.io/check/services**, in exactly the file format
`unmark-checker matrix` reads, so you can rebuild that table yourself or add
rows of your own.

Install this if you want the key to be yours, the sample to be yours, and the
text to stay on your machine.

## Install (CPU, Python 3.10 or newer)

```bash
git clone https://github.com/Yurakonoplya/unmark-checker && cd unmark-checker
python3 -m venv .venv
source .venv/bin/activate
# torch from the CPU index, otherwise pip pulls the multi-gigabyte CUDA build:
pip install --index-url https://download.pytorch.org/whl/cpu torch
pip install -e .
```

There is no package on PyPI: installing from a clone is the only
supported way, so what you run is the code you can read.

No GPU is needed. The first run downloads a small open-weights model (about 500
MB for `gpt2`) and the embedding model used for meaning similarity (about 90 MB).

Your key is a string you choose. Keep it in the environment so it stays out of
your shell history:

```bash
export UNMARK_CHECKER_KEY='a secret only you have'
```

Everything derives from it: the same secret always reproduces the same samples
and the same scores, and no one without it can score your samples or recognise
them.

## Check a tool in one minute, without generating anything

`samples/` holds ready-made marked samples of about a thousand words each, and
their key is printed in `samples/README.md` in plain sight. Hand one of them to
the tool you want to test, save what it returns, and run:

```bash
export UNMARK_CHECKER_KEY='unmark-checker-public-sample-key-v1'
unmark-checker check --sample samples/UM-344F7E.txt --returned cleaned.txt
```

That is the whole check. It needs no model download and finishes in seconds,
because scoring reads the tokenizer and the key, never the weights.

The key of those samples is public on purpose, and that is also their one
weakness: a tool could recognise these exact texts and treat them specially. For
a test nobody can anticipate, generate your own with your own key, as below. The
published samples are the fast path; your own samples are the strict one.

## Three commands

### 1. `generate`: samples that carry your mark

```bash
unmark-checker generate --num 2 --words 100 --scheme shallow --out my-samples
```

```
UM-A1C410    151 words  z=  8.84  mark_present 297.0s  -> my-samples/UM-A1C410.txt
UM-796705    161 words  z=  9.44  mark_present 238.6s  -> my-samples/UM-796705.txt

manifest: my-samples/manifest.json (no key is stored in it)
```

Every sample is scored as it is written, and that is not decoration: if the mark
did not plant, nothing measured on these texts means anything, so the command
says so and exits with code 2. The manifest remembers which scheme and model each
sample came from, so `check` does not have to be told twice; it holds no key.

### 2. `check`: what a tool did to a sample

Give the tool a sample, save exactly what it returned, then:

```bash
unmark-checker check --sample my-samples/UM-A1C410.txt --returned cleaned.txt
```

Here is a real answer, on the sample above against a version of itself with every
sentence moved to a new place. Shuffling is what a lot of "humanizers" mostly do,
and this is what it achieves:

```
The mark is still there. Detector score 6.86, at or above 4.0. Under the null
case a clean text scores that high about three times in a hundred thousand, so
this is not a coin flip: the tool did not take this mark out.
Meaning kept: 0.88 of 1.00. Facts kept: 9 of 9.
Longest verbatim run: 34 words. Words changed: 41%. Length: 1.00x (151 words in,
151 out).
```

Two things are worth reading twice there. The score barely moved, because a mark
of this class does not live in sentence order: it lives in the runs of words left
untouched, and a 34-word run was left untouched. And "41% of words changed" did
not help at all, which is why that column is reported next to the score and never
instead of it.

Add `--json` for the same run as a record you can store or publish:

```json
{
  "z": 6.864930642568267,
  "outcome": "mark_present",
  "similarity": 0.8812106606223327,
  "facts_total": 9, "facts_preserved": 9, "facts_missing": [],
  "verbatim_longest_run": 34,
  "changed_share": 0.41025641025641024,
  "length_ratio": 1.0,
  "kpi_version": 1,
  "sample_id": "UM-A1C410", "scheme": "shallow", "model": "gpt2",
  "sample_words": 151, "returned_words": 151,
  "n_eff": 990, "p_value": 3.3261782887586806e-12
}
```

Four outcomes, and the two thresholds behind them were fixed before any run of
ours and are not tuned to results:

| Outcome | Condition | What it means |
|---|---|---|
| `mark_present` | z >= 4.0 | A clean text scores that high about three times in a hundred thousand. The tool did not take this mark out. |
| `uncertain` | 2.0 <= z < 4.0 | The grey zone, and it is genuinely wide for marks of this class. Reported as its own answer rather than rounded to a yes or a no. |
| `mark_gone` | z < 2.0 | On this sample, on this run, the mark did not survive. |
| `not_our_text` | fewer than half the returned text's content words come from the sample | No score at all: a score on a text with no known starting point means nothing. |

The other columns are what the removal cost, and they matter as much as the
score: removing a mark by shortening or mangling the text is easy and worthless.

### 3. `matrix`: one table out of many runs

```bash
unmark-checker matrix --dir examples/services            # try it on the two examples
unmark-checker matrix --dir my-runs --out my-runs/matrix.md
```

Reads a folder of service files (one JSON per tool, format in
`docs/service-file.md`) and writes one Markdown table, plus a list of tools that
could not be run at all, because a tool that refuses the text is also a result.
Our own runs land in `results/` in the same format, so a table of yours and a
table of ours are comparable line by line.

## What a run claims, and what it does not

- **Claims:** on a reproduced scheme of this class, with a detector that knows
  the key, this tool left the mark in place or took it out, on this sample, at
  this length, at this cost in meaning and facts.
- **Does not claim:** anything about a specific vendor's watermark. A vendor uses
  a different model and unpublished scheme parameters, and no experiment without
  their key can test their detector, this one included.
- One direction does carry: a tool that **leaves this mark in place** is very
  unlikely to remove a vendor's mark either, because both live in the same place,
  which words got chosen. The reverse does not carry: clearing this mark is not
  evidence of clearing anyone else's, and "undetectable" is not a word this tool
  will ever print.
- One run on one sample is a measurement, not a verdict on a product. Run several
  samples, several lengths, and all three scheme presets before saying anything
  general.

The full experiment, including the traps that quietly break this kind of
measurement, is in [METHODOLOGY.md](METHODOLOGY.md).

## Speed, and which model to generate with

Planting the mark is the slow part: the processor hashes a context window and
runs a tournament over the key layers at every token, and on a CPU that costs
roughly half a second per token no matter how small the model is. Measured on an
ordinary 4-core cloud machine with no GPU:

| Model | One 100-word sample | Reads as |
|---|---|---|
| `sshleifer/tiny-gpt2` | 1 to 2 minutes (measured: 72 s and 121 s) | random tokens, not English |
| `gpt2` (default) | 4 to 5 minutes (measured: 297 s and 239 s) | plain, slightly rambling English |

Use `--model sshleifer/tiny-gpt2` to check that the whole pipeline works in a
couple of minutes; the mark and the detector behave the same on it, only the
prose does not. Use the default when the sample has to look like real writing,
for instance because it is going into a web form. With a GPU, add
`--device cuda` and a bigger open-weights model (`--model facebook/opt-1.3b`)
and it takes seconds.

Longer samples carry more evidence: the mark is statistical, and 100 words is
about the shortest length worth trusting. If you can wait, generate 300.

## Controls: what the detector says on text that carries no mark

```bash
unmark-checker generate --control human --words 150 --out my-control   # bundled human prose
unmark-checker generate --control model --words 150 --out my-control   # same model, no mark
```

"The mark is gone" is only meaningful against a baseline of how often the
detector fires on nothing. These two commands produce that baseline on your
machine, with your key.

## In an editor or an agent

- **Claude Code:** copy `skills/verify-watermark-removal/` into `.claude/skills/`
  of your project (or your personal `~/.claude/skills/`). The skill runs the
  three commands above and reports the outcome with its cost. `SKILL.md` is a
  plain Agent Skill (frontmatter plus instructions, no paths outside its own
  folder), so the same file drops unchanged into any agent or collection that
  reads that format.
- **Cursor:** copy `integrations/cursor/verify-watermark-removal.mdc` into
  `.cursor/rules/`. It is `alwaysApply: false`: the rule attaches when the
  question is about checking a removal, not on every request.

Both do one thing: when a tool claims a text was cleaned, they check the claim
instead of repeating it.

## What is in here

```
src/unmark_checker/    the library: scheme, generator, detector, metrics, matrix
docs/service-file.md   the data format results are recorded and published in
examples/services/     two example service files, marked as examples
results/               our own runs, with the output every number came from
skills/, integrations/ the editor and agent wrappers
METHODOLOGY.md         the experiment, its thresholds and its caveats
ORIGIN.md              which files are copies of the hosted checker's code
```

This repository **checks**; it does not remove anything. There is no cleaner, no
paraphraser and no service code in it, and that boundary is why it can be open.

## Contributing

Bug reports with both texts attached (the sample and what came back) are the most
useful thing you can send: a number of ours that you cannot reproduce is a
problem worth fixing. Note that several modules here are copies of the code that
runs the hosted checker, so a fix lands upstream first and is ported here;
[ORIGIN.md](ORIGIN.md) says which files those are and why.

## License

MIT. See [LICENSE](LICENSE).

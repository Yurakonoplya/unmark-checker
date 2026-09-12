---
name: verify-watermark-removal
description: Verify that a watermark-removal or "humanizer" step actually removed a statistical text watermark, by measuring a sample whose key you hold. Use after any tool, script or service claims to have cleaned a text, or when the user asks whether such a tool works, which one to trust, or how to test one. Reports a detector score against fixed thresholds plus what the tool cost in meaning, facts, verbatim overlap and length. Not for removing marks: this skill only measures.
---

# Verify watermark removal

A tool says it removed a watermark. This skill checks whether it did, on a text
whose mark was planted with a key the user holds, and reports what the text cost
on the way. It never claims anything about a specific vendor's watermark, and it
never removes anything.

## Setup, once

```bash
git clone https://github.com/Yurakonoplya/unmark-checker && cd unmark-checker
pip install --index-url https://download.pytorch.org/whl/cpu torch
pip install -e .                            # no PyPI package: install from the clone
export UNMARK_CHECKER_KEY='a secret only the user has'
```

The key is the whole basis of the check: a sample marked with it can only be
scored with it, so no tool can recognise the sample or tune its output to it.
Keep the key in the environment, never in a file or in a command that gets
logged.

## Workflow

1. **Get a marked sample.** If the user has none, make two (about two minutes
   each on a CPU with the small model):

   ```bash
   unmark-checker generate --num 2 --words 100 --scheme shallow \
       --model sshleifer/tiny-gpt2 --out my-samples
   ```

   Use `--model gpt2` instead when the sample must read as English, for example
   when it is going into a web form that rejects nonsense. Every sample is scored
   as it is written: if the mark did not plant, the command says so and exits
   with code 2, and nothing measured on those texts means anything.

2. **Run the tool under test on the sample** and save exactly what came back,
   unedited, to a file.

3. **Measure, one command:**

   ```bash
   unmark-checker check --sample my-samples/UM-XXXXXX.txt --returned cleaned.txt
   ```

   Add `--json` when the numbers are going into a table or a report.

4. **Report what the run says, and only that.** The outcome is one of four:

   | Outcome | What it means |
   |---|---|
   | `mark_present` | score at or above 4.0; the tool did not take this mark out |
   | `uncertain` | score between 2.0 and 4.0, the grey zone; do not round it to a yes or a no |
   | `mark_gone` | score below 2.0; on this sample, on this run, the mark did not survive |
   | `not_our_text` | the returned text is not recognisably the sample; no score is reported |

   Always report the cost columns next to the outcome: meaning similarity, facts
   kept, longest verbatim run, share of words changed, length ratio. A mark that
   disappeared together with half the text is not a result the user wants.

## What the answer supports, and what it does not

- A tool that **leaves this mark in place** is very unlikely to remove a vendor's
  mark either: both live in the same place, which words were chosen. That
  direction holds.
- A tool that **removes this mark** has not been shown to remove anyone else's.
  Different key, different scheme parameters, different model. Say so; do not let
  a passing run turn into "the text is now undetectable".
- One run on one sample is one measurement, not a verdict on a product. For a
  claim worth repeating, run several samples at several lengths and across the
  three scheme presets (`shallow`, `default`, `deep`).

## Comparing tools

Record each run as a service file and build one table:

```bash
unmark-checker matrix --dir my-runs --out my-runs/matrix.md
```

The file format is in `docs/service-file.md`. Published results in the same
format: https://unmarkclaude.io/check/services

## Without installing anything

The same check runs in a browser at https://unmarkclaude.io/check on a sample
whose key that site holds. Use it when the user wants an answer in a minute
rather than a local setup; use this skill when the text must not leave the
machine, or when the key has to be the user's own.

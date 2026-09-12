# How this check works, and what it is allowed to conclude

This document describes the experiment the code in this repository performs. It
measures whether a statistical text watermark of the SynthID-Text class survives
a tool that claims to remove watermarks, and what that tool did to the text on
the way. Every parameter and threshold is stated here, and none of them was
chosen after seeing a result.

## What is being measured, in one paragraph

Several vendors mark model output with a statistical watermark: a secret key
biases which of several near-equivalent tokens gets sampled, and a detector that
knows the key can later test for that bias. The scheme class (SynthID-Text,
published by DeepMind in Nature, 2024) is open and implemented in Hugging Face
`transformers`; the vendors' keys are not. So this code reproduces the *scheme*
with **your** key on an open-weights model, plants the mark, lets a tool process
the text, and asks the strongest possible detector, one that knows the key,
whether the mark is still there. That is exactly the position a vendor is in with
respect to its own text; any third-party detector is strictly weaker.

## What this experiment can and cannot claim

**Can claim:** on a reproduced scheme of this class, with a detector that knows
the key, this tool left the mark in place / took it out, on this sample, at this
length, while meaning similarity and fact survival were the numbers printed in
the same run.

**Cannot claim:** anything about a specific vendor's watermark. A vendor uses a
different model and unpublished scheme parameters (context depth, tournament
layers, key count). No experiment without their key can test their detector, this
one included. This is stated plainly because several services imply the opposite;
the formulation above is the only one the experiment supports.

There is one direction that does carry, and it is the useful one:

- A tool that **leaves this mark in place** is very unlikely to remove a vendor's
  mark either, because both live in the same place: which words were chosen.
- A tool that **removes this mark** has not thereby been shown to remove anyone
  else's. Different key, different scheme parameters, different model.

**A further honest caveat:** the generator here is a small open model, not a
frontier one. That is acceptable because the object under measurement is the
scheme's statistical mark, which the sampling processor plants per token
regardless of model quality; the detector reads token identities only. Model
choice affects how natural the sample reads, and therefore how a rewriting tool
behaves on it, which is why the quality columns are reported from the same run
and never separately.

## Verify that the mark planted, before you interpret anything

This sounds obvious and is easy to skip, so it is a step. On our first pilot a
rented GPU silently produced unwatermarked text: the untouched group scored a
median z of about 0.1 against a threshold of 4.0. The texts were fluent and long
and nothing looked wrong. The identical configuration (same model, scheme, dtype,
batch size, image and library versions) scored z of about 7 on a *different*
machine. Rented hardware is not homogeneous, and a silently wrong machine is
indistinguishable from a good one except by measuring. Had the untouched texts
not been checked, the run would have reported "detection fell from 0% to 0%", a
broken experiment wearing the costume of a result.

`generate` therefore scores every sample it writes and refuses to end well if the
detector cannot find the mark in any of them (exit code 2). Keep that gate if you
reproduce this work. An untouched sample is not a formality: it is the control
that tells you whether the experiment happened at all.

Two related traps, both already handled in the code and both worth knowing if you
port it:

- **The g-value table is built on CPU and moved to the device.** Torch's RNG
  differs between CPU and CUDA for the same seed, so a processor built on a GPU
  marks against a different table than one built on a CPU. A mark planted on the
  GPU was invisible to the local detector: the GPU saw its own texts at 100%, the
  local re-score at 0%.
- **Text is always tokenized with `add_special_tokens=False`.** Some tokenizers
  prepend a BOS token equal to eos, and the detector's eos mask then zeroes every
  position, so any text scores exactly z = 0.0. A flat zero on every text is the
  signature of that bug, not of a weak mark.

## Detector and frozen thresholds

The detector is the key-only mean-g-value test from the SynthID paper: for each
position past the first `ngram_len - 1` tokens, and each tournament layer, the
scheme defines a g-value in {0,1}; without the watermark each g-value is a fair
coin. The score is z = (mean_g - 0.5) / (0.5 / sqrt(n_eff)) over valid positions
times layers, with the same masking the reference `transformers` detector uses.

Outcomes, frozen in `thresholds.py` and never adjusted afterwards:

| outcome | condition | one-sided p under the null |
|---|---|---|
| `mark_present` | z >= 4.0 | about 3.2 x 10^-5 |
| `uncertain` | 2.0 <= z < 4.0 | grey zone |
| `mark_gone` | z < 2.0 | |

Why thresholds can be fixed before any run, independent of model and scheme:
under the null hypothesis every g-value is Bernoulli(0.5) for any model and any
scheme parameters, so the null distribution of z is standard normal for all
configurations, and the line is set by the false-positive rate one is willing to
accept. Three outcomes are counted separately and never collapsed into yes/no:
this class of mark has a genuinely wide grey band, and an independent AIES 2026
study found 8 of 10 untouched watermarked texts landing in it.

An honest caveat on the null: g-values across layers and positions are only
approximately independent (the hash chain and repeated-context suppression
introduce mild correlation), so the empirical spread on unmarked text can be
slightly wider than the theory. Measure it rather than assume it:
`generate --control model` and `generate --control human` write texts that carry
no mark, and their scores are the baseline. If the measured false-positive rate
exceeds the theoretical one, that is a finding to report, never a reason to move
the thresholds.

## A fourth outcome: not the sample

Before anything is scored, the returned text is compared to the sample by
content-word overlap (words of four letters or more, function words dropped).
Below 50% the pair is reported as `not_our_text` and no score is computed. A
detector score on material with no known starting point is not a weak
measurement, it is not a measurement: the code refuses to print one rather than
hand you a number that looks like evidence.

## Axes worth varying

- **Text length**, never averaged: about 100, 300 and 1000 words. The mark is
  statistical, so short texts carry less evidence, and a single averaged number
  overstates the result for the short ones.
- **Scheme configuration**, as a separate axis: `shallow` / `default` / `deep`
  vary the hash context window (`ngram_len` 2/5/8), tournament depth (10/20/30
  keys) and repeated-context suppression (256/1024). Vendor parameters are
  unpublished; running the grid lets a conclusion read "across all tested
  configurations" instead of "at the one point we picked".
- **Enough samples.** One run on one sample is an anecdote and is honest as such.
  For a number worth publishing, tens of samples per cell; at 100 observations
  the error bar is still roughly ten percentage points.

## Quality is measured in the same table

Removing a mark by destroying the text is trivial and worthless, so every check
carries, from the same run: meaning similarity to the sample (per 120-word chunk,
model `all-MiniLM-L6-v2`, each chunk of the sample matched to its closest chunk
of the result, which makes the number indifferent to reordering), a deterministic
check that every number, date, URL, proper name and technical term survived, the
longest run of words left verbatim, the share of words changed, and the length
ratio. A tool that returns 40% of the text with the mark gone has not done what a
reader wanted.

## Why long verbatim runs are the thing to watch

A mark of this class lives only where a full window of consecutive source tokens
survives verbatim: the g-value at a position is a deterministic function of the
previous few tokens and the token itself. Break every window and the score
collapses to the unmarked baseline. Measured on our own pilot data, leaving no
verbatim run longer than about three words drops detection to zero across all
three configurations at every length, whereas "40% of words changed on average"
does not: the mark rides the long runs left intact. This is why
`verbatim_longest_run` is reported next to the score, and why a `mark_gone` with
a long surviving run deserves a second run rather than a headline.

## Reproducing this

```bash
pip install --index-url https://download.pytorch.org/whl/cpu torch
pip install -e .

read -rs UNMARK_CHECKER_KEY && export UNMARK_CHECKER_KEY   # nothing echoed, nothing in the history
unmark-checker generate --num 3 --words 300 --scheme shallow --out my-samples
# hand my-samples/UM-XXXXXX.txt to the tool, save what it returns
unmark-checker check --sample my-samples/UM-XXXXXX.txt --returned cleaned.txt --json
```

Everything is deterministic given your key and the seeds: the same secret and the
same seed reproduce the same samples, and the same pair of texts reproduces the
same metrics. If your numbers disagree with ours on the same tool, that is worth
an issue with both texts attached; measurement, not the table, is the point of
publishing the code.

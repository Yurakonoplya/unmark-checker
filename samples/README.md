# Ready-made samples, and their key

These texts carry a watermark of the SynthID-Text class, planted by us with the
key below. The key is public on purpose: without it you could not score the
sample, and then the sample would be useless to you.

```
UNMARK_CHECKER_KEY=unmark-checker-public-sample-key-v1
```

Hand a sample to the tool you want to test, save exactly what it returns, then:

```bash
export UNMARK_CHECKER_KEY='unmark-checker-public-sample-key-v1'
unmark-checker check --sample samples/UM-344F7E.txt --returned cleaned.txt
```

The scheme and the model are read from `manifest.json` next to the texts, so
nothing else has to be typed. Scoring takes seconds: it needs the tokenizer and
the key, never the model weights.

## What is here

One sample is enough for a check: `UM-344F7E.txt` is the one every published
run uses, so a number measured on it compares directly with the published
table. The other two are spares, marked with the same key and the same scheme,
for anyone who wants a second run on a different text:

| Sample | Words | Scheme | Model | z when it was made |
|---|---|---|---|---|
| `UM-344F7E.txt` | 1021 | `default` (window 5, 20 tournament layers) | `facebook/opt-1.3b` | 36.11 |
| `UM-D20A72.txt` | 1047 | `default` | `facebook/opt-1.3b` | 29.60 |
| `UM-F54983.txt` | 777 | `default` | `facebook/opt-1.3b` | 29.94 |

Every one of them starts far above the detection line of 4.0, which is what
makes them worth handing to a tool: whatever the score is afterwards, the mark
was unmistakably there before.

`manifest.json` carries the same facts in machine-readable form, plus the
fingerprint of the key (a hash, not the key itself, so the file format is the
same for your own private samples).

Verify any of them for yourself before trusting a run made on it:

```bash
unmark-checker check --sample samples/UM-344F7E.txt --returned samples/UM-344F7E.txt
```

A sample compared to itself must come back `mark_present` with meaning 1.00 and
every fact kept. If it does not, something in your installation is wrong and no
measurement made with it means anything.

## The honest weakness of a public key

Because this key is published, a tool could recognise these exact texts and treat
them differently from everything else it is given. Nothing stops it. That is the
price of a sample anyone can use in one minute, and it is why these samples are
the fast path rather than the strict one.

For a test nobody can anticipate, make your own:

```bash
read -rs UNMARK_CHECKER_KEY && export UNMARK_CHECKER_KEY   # nothing echoed, nothing in the history
unmark-checker generate --num 2 --words 800 --scheme default \
    --model facebook/opt-1.3b --dtype bfloat16 --out my-samples
```

That is how these were made: about ten minutes per sample on an ordinary
four-core machine with no GPU.

## Do not edit these files

A statistical mark lives in which words were chosen, so any edit is a change to
the thing being measured. Fixing a typo, normalising a dash, re-wrapping the
lines: all of it moves the score. The texts are raw model output, published
exactly as the generator produced them, punctuation quirks included. If you want
a different text, generate one.

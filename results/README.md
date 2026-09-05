# results

Our own runs live here: one folder per date, one service file per tool, and the
saved output of every run next to it, so any row of the published table can be
recomputed from disk rather than believed.

```
results/
  services/                      one JSON file per tool (docs/service-file.md)
  2026-09-05/                    artifacts of the runs made that day
    example-rewriter/
      UM-1A2B3C.txt              exactly what the tool returned
```

Rebuild the table from whatever is here (the folder appears with the first run;
until then, `examples/services` shows the same command working):

```bash
unmark-checker matrix --dir results/services --out results/matrix.md
```

## First run: 5 September 2026

Fifteen free tools, three samples of ours (one per scheme depth), every output saved
next to its service file. Seven tools returned a result: five returned the text with
the mark still found; two returned it with the mark no longer found on any sample, and
both lost facts on the way. Eight did not return a result (four cap free input below
the sample length, four accepted the text and returned nothing); their service files
carry the reason. Our own processing is measured on the same samples with the same
ruler and sits in the same table. Scores use kpi_version 2. Rebuild `matrix.md` from
this folder with the command above; it is the same table the site publishes.

The published table lives at https://unmarkclaude.io/check/services. When a run
lands there it lands here too, with the date it was made and the output it was
computed from.

## If you run your own

Point `matrix` at your own folder and you get your own table in the same shape.
That is deliberate: a result of ours and a result of yours are then comparable
line by line, and disagreement is a thing to look at rather than a matter of who
is trusted.

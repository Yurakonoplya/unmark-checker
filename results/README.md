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

## Nothing measured is published here yet

This folder holds the format and no numbers. The table is published together
with the first run, and every row it will hold is a run of ours on a sample of
ours: the same three commands this repository ships, on tools anyone can reach.
Until then, the shape is visible in `examples/services/`, and those two files are
marked `fixture` precisely so nobody mistakes an example for a measurement.

The published table lives at https://unmarkclaude.io/check/services. When a run
lands there it lands here too, with the date it was made and the output it was
computed from.

## If you run your own

Point `matrix` at your own folder and you get your own table in the same shape.
That is deliberate: a result of ours and a result of yours are then comparable
line by line, and disagreement is a thing to look at rather than a matter of who
is trusted.

# Watermark removal: measured results

Built from the service files in `results/services`.

Every row is one run: one sample with a known key, handed to one tool, and the tool's output measured against the sample it came from. `z` is the key-aware detector score; at or above 4.0 the mark is still there, below 2.0 it is gone, in between is the grey zone. The other columns say what the text cost: meaning similarity, facts kept, the longest run of words left verbatim, the share of words changed, and the length ratio.

| Service | Kind | Date | Sample | Mark | z | Meaning | Facts kept | Verbatim run | Changed | Length | Run by |
|---|---|---|---|---|---|---|---|---|---|---|---|
| claudewatermark.com | cleaner | 2026-09-05 | UM-8B2588 | still there | 35.31 | 1.00 | 8/8 | 1006 | 0% | 1.00x | us |
| claudewatermark.com | cleaner | 2026-09-05 | UM-A85AAA | still there | 19.55 | 1.00 | 32/32 | 1065 | 0% | 1.00x | us |
| claudewatermark.com | cleaner | 2026-09-05 | UM-D150B2 | still there | 37.96 | 1.00 | 3/3 | 1025 | 0% | 1.00x | us |
| claudewatermarkremover.app | rewriter | 2026-09-05 | UM-8B2588 | still there | 35.31 | 1.00 | 8/8 | 1006 | 0% | 1.00x | us |
| claudewatermarkremover.app | rewriter | 2026-09-05 | UM-A85AAA | still there | 19.55 | 1.00 | 32/32 | 1065 | 0% | 1.00x | us |
| claudewatermarkremover.app | rewriter | 2026-09-05 | UM-D150B2 | still there | 37.96 | 1.00 | 3/3 | 1025 | 0% | 1.00x | us |
| favtutor.com | rewriter | 2026-09-05 | UM-8B2588 | gone | -0.19 | 0.89 | 8/8 | 9 | 61% | 0.78x | us |
| favtutor.com | rewriter | 2026-09-05 | UM-A85AAA | in between | 3.87 | 0.92 | 31/32 | 11 | 60% | 0.79x | us |
| favtutor.com | rewriter | 2026-09-05 | UM-D150B2 | gone | -0.96 | 0.80 | 1/3 | 7 | 81% | 0.79x | us |
| gptcleanup.com | cleaner | 2026-09-05 | UM-8B2588 | still there | 35.31 | 1.00 | 8/8 | 1006 | 0% | 1.00x | us |
| gptcleanup.com | cleaner | 2026-09-05 | UM-A85AAA | still there | 19.55 | 1.00 | 32/32 | 1065 | 0% | 1.00x | us |
| gptcleanup.com | cleaner | 2026-09-05 | UM-D150B2 | still there | 37.96 | 1.00 | 3/3 | 1025 | 0% | 1.00x | us |
| guillaumemeyer/watermarks-remover, character cleaning | open-source | 2026-09-05 | UM-8B2588 | still there | 35.31 | 1.00 | 8/8 | 1006 | 0% | 1.00x | us |
| guillaumemeyer/watermarks-remover, character cleaning | open-source | 2026-09-05 | UM-A85AAA | still there | 19.55 | 1.00 | 32/32 | 1065 | 0% | 1.00x | us |
| guillaumemeyer/watermarks-remover, character cleaning | open-source | 2026-09-05 | UM-D150B2 | still there | 37.96 | 1.00 | 3/3 | 1025 | 0% | 1.00x | us |
| guillaumemeyer/watermarks-remover, rewrite layer | open-source | 2026-09-05 | UM-8B2588 | gone | -0.24 | 0.87 | 7/8 | 6 | 72% | 0.68x | us |
| guillaumemeyer/watermarks-remover, rewrite layer | open-source | 2026-09-05 | UM-A85AAA | in between | 3.91 | 0.84 | 28/32 | 34 | 56% | 0.77x | us |
| guillaumemeyer/watermarks-remover, rewrite layer | open-source | 2026-09-05 | UM-D150B2 | gone | -1.13 | 0.79 | 1/3 | 6 | 77% | 0.64x | us |
| removeclaudewatermark.com | rewriter | 2026-09-05 | UM-A85AAA | still there | 11.55 | 0.97 | 30/32 | 173 | 23% | 0.91x | us |
| unmarkclaude.io | ours | 2026-09-05 | UM-8B2588 | gone | 1.12 | 0.81 | 8/8 | 23 | 85% | 0.89x | us |
| unmarkclaude.io | ours | 2026-09-05 | UM-A85AAA | in between | 2.35 | 0.89 | 32/32 | 21 | 71% | 0.92x | us |
| unmarkclaude.io | ours | 2026-09-05 | UM-D150B2 | gone | 0.83 | 0.74 | 3/3 | 10 | 91% | 0.92x | us |

## Could not be run

- **Duck.ai** (https://duck.ai/): Not run on 5 September 2026. The message with the sample went through, but the chat answered "Duck.ai is temporarily unavailable" instead of a rewrite, on all three samples, with 425 seconds of waiting each. The other free assistants ask for an account, and we do not open accounts.
- **Ninja Humanizer** (https://ninjahumanizer.com/claude-watermark-remover): Not run on 5 September 2026: the free counter stops at 200 of 200 words and the sample is 1029 words.
- **Overchat AI** (https://overchat.ai/text/claude-watermark-remover): Not run on 5 September 2026: the button on the tool page started nothing. The result area stayed empty for 300 seconds and the page sent no network request, on our sample and on the site own sample alike, over three attempts.
- **WriteHuman** (https://writehuman.ai/): Not run on 5 September 2026: pasting the sample produced the message "Text trimmed to 250 words", four times shorter than the sample.
- **gpt-watermark-remover.com** (https://gpt-watermark-remover.com/): Not run on 5 September 2026: the free input is capped at 500 characters and the samples are 5281 to 5909 characters long. The remove button is also locked until a detect run is made.
- **proofreaderpro.ai** (https://proofreaderpro.ai/claude-watermark-remover): Not run on 5 September 2026: the free limit is 500 words and the samples are 992 to 1029 words.
- **removeclaudewatermark.org** (https://removeclaudewatermark.org/): The form accepted the sample and passed the site security check, but the rewrite endpoint answered "Service busy, try again in a moment." on twelve attempts across three samples between 20:35 and 21:45 on 5 September 2026.
- **un-claude.com** (https://un-claude.com/): Not run on 5 September 2026. The free scan works and reports no hidden characters found and the statistical watermark as presumed present. Starting the clean shows a notice that about 48 percent of the document will come back exactly as sent, and after confirming, the page showed no result within 500 seconds on two attempts.

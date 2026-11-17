# Experiment B: paired median prompts

24 pairs, identical odd-length value lists (7 values), same expected stats_median call. Direct prompt says `median`; natural prompt says `middle value` after sorting and does not name the operation. Diagnostic only; not sealed and not used by the controller.

## Per-seed results

| seed | state | direct joint | natural joint | gap | direct answer | natural answer | direct tool | natural tool |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 20261108 | start | 1.000 | 1.000 | +0.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| 20261108 | midpoint | 1.000 | 0.958 | +0.042 | 1.000 | 0.958 | 1.000 | 1.000 |
| 20261108 | end | 1.000 | 0.500 | +0.500 | 1.000 | 0.583 | 1.000 | 0.500 |
| 20261109 | start | 1.000 | 1.000 | +0.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| 20261109 | midpoint | 1.000 | 1.000 | +0.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| 20261109 | end | 1.000 | 1.000 | +0.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| 20261110 | start | 1.000 | 1.000 | +0.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| 20261110 | midpoint | 1.000 | 0.958 | +0.042 | 1.000 | 1.000 | 1.000 | 1.000 |
| 20261110 | end | 1.000 | 0.792 | +0.208 | 1.000 | 0.958 | 1.000 | 1.000 |

## Aggregate across seeds

| state | metric | direct | natural | gap |
| --- | --- | --- | --- | --- |
| start | joint | 1.000 | 1.000 | 0.000 |
| start | answer | 1.000 | 1.000 | 0.000 |
| start | tool | 1.000 | 1.000 | 0.000 |
| start | argument | 1.000 | 1.000 | 0.000 |
| midpoint | joint | 1.000 | 0.972±0.024 | 0.028 |
| midpoint | answer | 1.000 | 0.986±0.024 | 0.014 |
| midpoint | tool | 1.000 | 1.000 | 0.000 |
| midpoint | argument | 1.000 | 0.972±0.024 | 0.028 |
| end | joint | 1.000 | 0.764±0.251 | 0.236 |
| end | answer | 1.000 | 0.847±0.229 | 0.153 |
| end | tool | 1.000 | 0.833±0.289 | 0.167 |
| end | argument | 1.000 | 0.931±0.120 | 0.069 |

## Natural-prompt tool confusions

| seed | state | predicted tool | count |
| --- | --- | --- | --- |
| 20261108 | end | stats_sorted | 12 |

## Reading

A positive gap means the direct wording is easier than the natural wording. The gap is small at start and midpoint and only becomes material at the end (natural joint 0.764±0.251 vs direct 1.000). The effect is heterogeneous: seed 20261109 stays at 1.000, while seed 20261108 falls to 0.500. In this run the natural-prompt errors are tool-selection errors to `stats_sorted` (12 items), not the historical `stats_mean` confusion; the exact confusion depends on wording. The monitor must therefore include multiple indirect wordings, and 24 pairs are underpowered for a stable estimate.

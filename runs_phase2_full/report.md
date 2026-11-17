# FAC-TinyAgent Phase 2 Full-Test Re-Evaluation

- Final adapters from the Phase 2 sequential sweep
- Test set: all available test episodes per family (30 in `data_phase2`)
- Runs: 9
- Orders: A, B, C
- Seeds: 20261108, 20261109, 20261110
- No retraining; old checkpoints and subset evaluations are untouched

## Final capability (full test set)

| order | calendar | database | file | python | mean across families |
| --- | --- | --- | --- | --- | --- |
| A | 0.633±0.088 | 0.600±0.033 | 0.489±0.019 | 0.933±0.033 | 0.664±0.027 |
| B | 0.633±0.260 | 0.689±0.019 | 0.600 | 0.933±0.088 | 0.714±0.084 |
| C | 0.089±0.019 | 0.567±0.203 | 0.467 | 0.789±0.171 | 0.478±0.090 |

### Per family

| family | mean final | runs |
| --- | --- | --- |
| python | 0.885±0.121 | 9 |
| database | 0.619±0.117 | 9 |
| file | 0.519±0.063 | 9 |
| calendar | 0.452±0.305 | 9 |

### Per run

| run | calendar | database | file | python |
| --- | --- | --- | --- | --- |
| A_seed20261108 | 0.667 | 0.600 | 0.500 | 0.933 |
| A_seed20261109 | 0.700 | 0.633 | 0.500 | 0.900 |
| A_seed20261110 | 0.533 | 0.567 | 0.467 | 0.967 |
| B_seed20261108 | 0.800 | 0.667 | 0.600 | 1.000 |
| B_seed20261109 | 0.333 | 0.700 | 0.600 | 0.833 |
| B_seed20261110 | 0.767 | 0.700 | 0.600 | 0.967 |
| C_seed20261108 | 0.067 | 0.700 | 0.467 | 0.833 |
| C_seed20261109 | 0.100 | 0.667 | 0.467 | 0.933 |
| C_seed20261110 | 0.100 | 0.333 | 0.467 | 0.600 |

## Comparison with the 6-item subset

| order | family | 6-item subset | full | full - subset | runs |
| --- | --- | --- | --- | --- | --- |
| A | calendar | 0.556±0.192 | 0.633±0.088 | 0.078±0.107 | 3 |
| A | database | 0.611±0.096 | 0.600±0.033 | -0.011±0.069 | 3 |
| A | file | 0.500 | 0.489±0.019 | -0.011±0.019 | 3 |
| A | python | 0.833 | 0.933±0.033 | 0.100±0.033 | 3 |
| B | calendar | 0.556±0.192 | 0.633±0.260 | 0.078±0.069 | 3 |
| B | database | 0.778±0.096 | 0.689±0.019 | -0.089±0.077 | 3 |
| B | file | 0.667 | 0.600 | -0.067 | 3 |
| B | python | 0.889±0.096 | 0.933±0.088 | 0.044±0.077 | 3 |
| C | calendar | 0.000 | 0.089±0.019 | 0.089±0.019 | 3 |
| C | database | 0.722±0.192 | 0.567±0.203 | -0.156±0.019 | 3 |
| C | file | 0.500 | 0.467 | -0.033 | 3 |
| C | python | 0.778±0.096 | 0.789±0.171 | 0.011±0.084 | 3 |

Across 36 run-family cells, the full test changes the score by 0.003±0.092 on average (full minus subset).

## Key findings

- Best order on the full test set: B (0.714±0.084); worst: C (0.478±0.090).
- Final capability by family: python 0.885±0.121; database 0.619±0.117; file 0.519±0.063; calendar 0.452±0.305.
- Lowest order-family cell: C/calendar 0.089±0.019; highest: A/python 0.933±0.033.
  The 6-item subset reported 0.000 for this cell; the full 30-item test gives 0.089±0.019. The collapse is real, but the exact zero was a small-sample artifact.
- Across 36 cells, full minus subset is 0.003±0.092 on average; individual cells shift by up to 0.200. The largest shift is A_seed20261110/calendar 0.333 -> 0.533.

## Limitations

- Only the final adapter is re-evaluated; intermediate-stage matrices still use the 6-item subset.
- Three seeds and one model; no formal significance test.
- Full evaluation measures final retention, not the shape of forgetting during the sequence.

## Output

- Per-run results: `runs_phase2_full/<run>/<family>/`

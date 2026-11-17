# FAC-TinyAgent Phase 2 Report

- Model: `/home/egret/models/Qwen3-0.6B`
- Tool families: calendar, database, file, python
- Learning orders: A, B, C
- Seeds: 20261108, 20261109, 20261110
- Completed runs: 9
- Capability evaluation: all families at every stage; test subset per family = 6
- Method: sequential QLoRA SFT, natural forgetting, no replay

## Complete capability matrix

### Order A
| stage | calendar | database | file | python |
| --- | --- | --- | --- | --- |
| stage_00_base | 0.000 | 0.000 | 0.000 | 0.333 |
| stage_01_file | 0.222±0.192 | 0.278±0.096 | 0.444±0.096 | 0.778±0.096 |
| stage_02_database | 0.333 | 0.611±0.096 | 0.556±0.096 | 0.778±0.096 |
| stage_03_python | 0.056±0.096 | 0.556±0.096 | 0.500 | 1.000 |
| stage_04_calendar | 0.556±0.192 | 0.611±0.096 | 0.500 | 0.833 |

### Order B
| stage | calendar | database | file | python |
| --- | --- | --- | --- | --- |
| stage_00_base | 0.000 | 0.000 | 0.000 | 0.333 |
| stage_01_calendar | 0.333 | 0.278±0.096 | 0.333 | 0.611±0.096 |
| stage_02_python | 0.333 | 0.278±0.096 | 0.444±0.096 | 0.889±0.096 |
| stage_03_database | 0.667 | 0.833 | 0.500 | 0.889±0.096 |
| stage_04_file | 0.556±0.192 | 0.778±0.096 | 0.667 | 0.889±0.096 |

### Order C
| stage | calendar | database | file | python |
| --- | --- | --- | --- | --- |
| stage_00_base | 0.000 | 0.000 | 0.000 | 0.333 |
| stage_01_database | 0.111±0.192 | 0.667 | 0.389±0.096 | 0.444±0.096 |
| stage_02_file | 0.111±0.192 | 0.778±0.096 | 0.667 | 0.611±0.096 |
| stage_03_calendar | 0.222±0.192 | 0.722±0.096 | 0.500 | 0.611±0.096 |
| stage_04_python | 0.000 | 0.722±0.192 | 0.500 | 0.778±0.096 |

### Pooled across orders and seeds
| stage | calendar | database | file | python |
| --- | --- | --- | --- | --- |
| stage_00 | 0.000 | 0.000 | 0.000 | 0.333 |
| stage_01 | 0.222±0.167 | 0.407±0.206 | 0.389±0.083 | 0.611±0.167 |
| stage_02 | 0.259±0.147 | 0.556±0.236 | 0.556±0.118 | 0.759±0.147 |
| stage_03 | 0.315±0.294 | 0.704±0.139 | 0.500 | 0.833±0.186 |
| stage_04 | 0.370±0.309 | 0.704±0.139 | 0.556±0.083 | 0.833±0.083 |

### Acquisition vs retention

`peak` is the best observed value after the family was learned and before the final stage; `final` is the final-stage value; `forgetting` is the per-run max(0, peak - final), averaged over seeds. The family learned last has no later re-evaluation, so its peak and forgetting are `-`, but its final capability is still shown.

| order | family | peak | final | forgetting | runs with forgetting |
| --- | --- | --- | --- | --- | --- |
| A | calendar | - | 0.556±0.192 | - | 0 |
| A | database | 0.611±0.096 | 0.611±0.096 | 0.056±0.096 | 3 |
| A | file | 0.556±0.096 | 0.500 | 0.056±0.096 | 3 |
| A | python | 1.000 | 0.833 | 0.167 | 3 |
| B | calendar | 0.667 | 0.556±0.192 | 0.111±0.192 | 3 |
| B | database | 0.833 | 0.778±0.096 | 0.056±0.096 | 3 |
| B | file | - | 0.667 | - | 0 |
| B | python | 0.889±0.096 | 0.889±0.096 | 0.000 | 3 |
| C | calendar | 0.222±0.192 | 0.000 | 0.222±0.192 | 3 |
| C | database | 0.778±0.096 | 0.722±0.192 | 0.111±0.192 | 3 |
| C | file | 0.667 | 0.500 | 0.167 | 3 |
| C | python | - | 0.778±0.096 | - | 0 |

### Final capability by family (all orders)

| family | mean final | runs |
| --- | --- | --- |
| python | 0.833±0.083 | 9 |
| database | 0.704±0.139 | 9 |
| file | 0.556±0.083 | 9 |
| calendar | 0.370±0.309 | 9 |

## Forgetting

| order | family-mean forgetting | runs |
| --- | --- | --- |
| A | 0.093±0.032 | 3 |
| B | 0.056±0.056 | 3 |
| C | 0.167±0.111 | 3 |

Each order mean covers the three families that were re-evaluated after a later stage; the last-learned family has no forgetting estimate, so the family sets differ across orders.

| family | order A | order B | order C | overall |
| --- | --- | --- | --- | --- |
| calendar | fourth - | first 0.111±0.192 | third 0.222±0.192 | 0.167±0.183 |
| database | second 0.056±0.096 | third 0.056±0.096 | first 0.111±0.192 | 0.074±0.121 |
| file | first 0.056±0.096 | fourth - | second 0.167 | 0.111±0.086 |
| python | third 0.167 | second 0.000 | fourth - | 0.083±0.091 |

### Learning position

| position | mean forgetting | observations |
| --- | --- | --- |
| first | 0.093±0.147 | 9 |
| second | 0.074±0.088 | 9 |
| third | 0.148±0.130 | 9 |
| fourth | - (no later stage) | 0 |

### Family complexity (descriptive)

| family | complexity | mean forgetting | observations |
| --- | --- | --- | --- |
| calendar | 2 | 0.167±0.183 | 6 |
| database | 3 | 0.074±0.121 | 9 |
| file | 1 | 0.111±0.086 | 6 |
| python | 2 | 0.083±0.091 | 6 |

### Skill-level forgetting (weighted by n)

| family | skill | mean forgetting | total n | runs |
| --- | --- | --- | --- | --- |
| file | file_search | 0.500 | 12 | 6 |
| file | line_index | 0.500 | 12 | 6 |
| python | stat_median | 0.500 | 6 | 6 |
| calendar | calendar_attendees | 0.333 | 12 | 6 |
| calendar | calendar_count | 0.333 | 12 | 6 |
| python | stat_regression | 0.167 | 6 | 6 |
| calendar | calendar_free | 0.167 | 12 | 6 |
| calendar | calendar_time | 0.167 | 12 | 6 |
| database | sql_filter | 0.148 | 27 | 9 |
| database | sql_aggregation | 0.111 | 27 | 9 |
| database | sql_order | 0.111 | 9 | 9 |
| python | numeric_input | 0.083 | 36 | 6 |
| file | character_count | 0.000 | 6 | 6 |
| file | counting | 0.000 | 6 | 6 |
| file | file_list | 0.000 | 12 | 6 |

## Key findings

- Mean final capability across the four families by order: B 0.722±0.048; A 0.625±0.072; C 0.500±0.072. The best order is B, the worst is C.
- Mean final capability by family: python 0.833±0.083; database 0.704±0.139; file 0.556±0.083; calendar 0.370±0.309.
- Largest order-dependent final-capability gap for one family: calendar, 0.556 in order A versus 0.000 in order C.
  The low cell is 0.000 on the 6-item subset; the full 30-item test gives 0.089±0.019, so the exact zero was a small-sample artifact, but the gap remains.
  The forgetting statistic must be read together with the absolute final value.
- Training the first family also raises the untrained families by 0.272±0.147 on average at the next stage (positive transfer), likely shared tool-call/output-format learning; capability changes are net of this transfer.
- Forgetting is estimated only for families re-evaluated after a later stage; the fourth family in each order has no forgetting estimate. Position and family are therefore partly confounded.

## Answers to the Phase 2 questions

### 1. Is forgetting consistent across orders and seeds?
Family-level final forgetting (mean±std across runs): calendar 0.167±0.183; database 0.074±0.121; file 0.111±0.086; python 0.083±0.091.
Families with positive mean forgetting: calendar, database, file, python.

### 2. Which tools are forgotten most?
calendar 0.167±0.183; file 0.111±0.086; python 0.083±0.091; database 0.074±0.121

### 3. Which skills are forgotten most?
file/file_search 0.500 (n=12); file/line_index 0.500 (n=12); python/stat_median 0.500 (n=6); calendar/calendar_attendees 0.333 (n=12); calendar/calendar_count 0.333 (n=12); python/stat_regression 0.167 (n=6); calendar/calendar_free 0.167 (n=12); calendar/calendar_time 0.167 (n=12); database/sql_filter 0.148 (n=27); database/sql_aggregation 0.111 (n=27)

### 4. Order, schema and argument complexity
The family-by-order table above crosses each family with different learning positions. The position table is descriptive: position and family are partly confounded because each order contains each family once. The complexity table is also descriptive with four families. Treat order/complexity effects as hypotheses, not causal estimates.

## Appendix: per-run final capability

| run | calendar | database | file | python |
| --- | --- | --- | --- | --- |
| A_seed20261108 | 0.667 | 0.667 | 0.500 | 0.833 |
| A_seed20261109 | 0.667 | 0.667 | 0.500 | 0.833 |
| A_seed20261110 | 0.333 | 0.500 | 0.500 | 0.833 |
| B_seed20261108 | 0.667 | 0.667 | 0.667 | 1.000 |
| B_seed20261109 | 0.333 | 0.833 | 0.667 | 0.833 |
| B_seed20261110 | 0.667 | 0.833 | 0.667 | 0.833 |
| C_seed20261108 | 0.000 | 0.833 | 0.500 | 0.833 |
| C_seed20261109 | 0.000 | 0.833 | 0.500 | 0.833 |
| C_seed20261110 | 0.000 | 0.500 | 0.500 | 0.667 |

## Full 30-item final re-evaluation

The final adapters were re-evaluated on all 30 test items per family (no retraining). Across 36 run-family cells, full minus subset is 0.003±0.092 on average; individual cells shift by up to 0.200.

| order | calendar | database | file | python | mean across families |
| --- | --- | --- | --- | --- | --- |
| A | 0.633±0.088 | 0.600±0.033 | 0.489±0.019 | 0.933±0.033 | 0.664±0.027 |
| B | 0.633±0.260 | 0.689±0.019 | 0.600 | 0.933±0.088 | 0.714±0.084 |
| C | 0.089±0.019 | 0.567±0.203 | 0.467 | 0.789±0.171 | 0.478±0.090 |

Per-family full-test means: python 0.885±0.121; database 0.619±0.117; file 0.519±0.063; calendar 0.452±0.305.

Full report: `runs_phase2_full/report.md`.

## Limitations

- The stage-by-stage capability matrix uses a test subset per family (6); only the final adapters were re-evaluated on all 30 items. Intermediate-stage scores are noisier than Phase 1.
- A small number of orders/seeds; no formal significance test.
- One model (Qwen3-0.6B); validation losses in Phase 1 were near zero, so overfitting remains a concern.
- Skill-level n is small; the skill ranking is exploratory.
- Natural forgetting only; no replay or adaptive review is implemented.

## Phase 3 implications

- Use the per-family/per-skill estimates to seed a forgetting-aware monitor; replay should target the families and structural skills with the highest estimated forgetting.
- Add more orders and seeds before fixing the monitor thresholds; the current order effect is not separable from family difficulty.
- The next algorithmic step is a forgetting estimator plus a budgeted replay controller, not a larger fixed replay buffer.

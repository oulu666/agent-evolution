# FAC-TinyAgent Phase 1 Report

- Run: `A_seed20261108`
- Created: 2026-11-10T13:42:53+08:00
- Model: `/home/egret/models/Qwen3-1.7B`
- Seed: 20261108
- Method: sequential QLoRA SFT, no replay (natural forgetting)
- Training: 2 epochs, LR 0.0001, LoRA r=8 alpha=16, max length 1024

## Data
| family | train | val | test |
| --- | --- | --- | --- |
| file | 8 | 2 | 6 |
| database | 8 | 2 | 6 |
| python | 8 | 2 | 6 |
| calendar | 8 | 2 | 6 |

## Training

| stage | train | val | epochs | steps | tokens | val_loss | peak_gpu_gb | seconds |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| stage_01_file | 8 | 2 | 2 | 16 | 5786 | 1.14628 | 3.474 | 14.35 |
| stage_02_database | 8 | 2 | 2 | 16 | 4816 | 0.996529 | 3.261 | 17.02 |
| stage_03_python | 8 | 2 | 2 | 16 | 5986 | 0.137253 | 3.515 | 11.54 |
| stage_04_calendar | 8 | 2 | 2 | 16 | 7326 | 0.0441046 | 4.013 | 12.37 |

## Capability matrix (final task success)

| stage | calendar | database | file | python |
| --- | --- | --- | --- | --- |
| stage_00_base | 0.000 | 0.000 | 0.333 | 0.000 |
| stage_01_file | 0.000 | 0.000 | 0.667 | 0.333 |
| stage_02_database | 0.000 | 0.000 | 0.667 | 0.333 |
| stage_03_python | 0.000 | 0.000 | 0.667 | 0.667 |
| stage_04_calendar | 0.000 | 0.667 | 0.667 | 1.000 |

## Forgetting by metric

| stage | tool_selection_accuracy | argument_accuracy | execution_success_rate | final_task_success_rate |
| --- | --- | --- | --- | --- |
| 2 | 0.000 | 0.000 | 0.000 | 0.000 |
| 3 | 0.000 | 0.000 | 0.000 | 0.000 |
| 4 | 0.000 | 0.000 | 0.000 | 0.000 |

## Key findings

- File final success: stage 1 0.667 -> stage 2 0.667 -> stage 3 0.667.
- Database final success: stage 2 0.000 -> stage 3 0.000.
- Python final success after its own stage: 0.667.
- Stage 2 average forgetting was 0.000; the measurable drop appears only after the final (Python) stage.
- Largest skill-level drops (final task success): file/counting 0.000; file/file_list 0.000; file/file_read 0.000; file/file_search 0.000; file/final_formatting 0.000; file/line_index 0.000. Skill-level n is small; treat this ranking as a hypothesis.

## Answers to the Phase 1 questions

### 1. Does continual learning cause old-skill decline?
Final-stage average forgetting by family: file=0.000, database=0.000, python=0.000.
No positive forgetting was observed in this run; the test sets may be at a floor.

### 2. Which tools are forgotten most?
file (0.000); database (0.000); python (0.000)

### 3. Which skills are forgotten most?
file/counting (0.000); file/file_list (0.000); file/file_read (0.000); file/file_search (0.000); file/final_formatting (0.000); file/line_index (0.000); database/sql_aggregation (0.000); database/sql_filter (0.000); database/sql_group (0.000); database/sql_order (0.000)

### 4. Schema, argument complexity, and order
The three families differ in schema complexity (file < statistics < SQL) and learning order (file -> database -> python). With one run and three families these factors are confounded; use multiple orders/seeds and within-family complexity levels in Phase 2 before making a causal claim.

## Limitations

- One model (Qwen3-0.6B) and one seed; no confidence intervals.
- Test templates are held out, but the absolute scores can be near floor.
- Natural forgetting only; no replay or adaptive review is implemented.
- The data split is template-based plus entity-based, not a fully independent domain.
- Validation losses are near zero (0.025, 0.00036, 9e-5); each 80-example stage is likely overfit. Forgetting is still a behavioral signal, but absolute scores should not be read as broad generalization.
- The Python test reaches 1.0 while Database starts lower; difficulty is not matched across families, so cross-family forgetting magnitudes are only indicative.


## Phase 2 implications

- Forgetting is concentrated after the final tool stage; a forgetting-aware replay trigger should target File/Database structural skills when a new family is learned.
- Add multiple tool orders and seeds; the current order confounds recency with domain similarity.
- Match test difficulty across families, and add within-family complexity levels before making a causal claim about schema or argument complexity.
- Monitor tool_selection, execution and schema_reading; these show the largest drops, while argument accuracy of Database did not decline.

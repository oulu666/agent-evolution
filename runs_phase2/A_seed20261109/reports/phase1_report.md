# FAC-TinyAgent Phase 1 Report

- Run: `A_seed20261109`
- Created: 2026-11-09T00:40:00+08:00
- Model: `/home/egret/models/Qwen3-0.6B`
- Seed: 20261109
- Method: sequential QLoRA SFT, no replay (natural forgetting)
- Training: 2 epochs, LR 0.0001, LoRA r=8 alpha=16, max length 1024

## Data
| family | train | val | test |
| --- | --- | --- | --- |
| file | 80 | 20 | 30 |
| database | 80 | 20 | 30 |
| python | 80 | 20 | 30 |
| calendar | 80 | 20 | 30 |

## Training

| stage | train | val | epochs | steps | tokens | val_loss | peak_gpu_gb | seconds |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| stage_01_file | 80 | 20 | 2 | 160 | 54894 | 0.0242367 | 2.095 | 104.57 |
| stage_02_database | 80 | 20 | 2 | 160 | 48950 | 0.000635303 | 1.855 | 108.37 |
| stage_03_python | 80 | 20 | 2 | 160 | 61094 | 4.4562e-05 | 2.095 | 112.13 |
| stage_04_calendar | 80 | 20 | 2 | 160 | 74944 | 0.0214121 | 2.608 | 115.61 |

## Capability matrix (final task success)

| stage | calendar | database | file | python |
| --- | --- | --- | --- | --- |
| stage_00_base | 0.000 | 0.000 | 0.000 | 0.333 |
| stage_01_file | 0.000 | 0.167 | 0.333 | 0.833 |
| stage_02_database | 0.333 | 0.667 | 0.500 | 0.833 |
| stage_03_python | 0.000 | 0.667 | 0.500 | 1.000 |
| stage_04_calendar | 0.667 | 0.667 | 0.500 | 0.833 |

## Forgetting by metric

| stage | tool_selection_accuracy | argument_accuracy | execution_success_rate | final_task_success_rate |
| --- | --- | --- | --- | --- |
| 2 | 0.167 | 0.167 | 0.167 | 0.000 |
| 3 | 0.000 | 0.083 | 0.000 | 0.000 |
| 4 | 0.056 | 0.056 | 0.056 | 0.056 |

## Key findings

- File final success: stage 1 0.333 -> stage 2 0.500 -> stage 3 0.500.
- Database final success: stage 2 0.667 -> stage 3 0.667.
- Python final success after its own stage: 1.000.
- Stage 2 average forgetting was 0.000; the measurable drop appears only after the final (Python) stage.
- Largest skill-level drops (final task success): python/stat_median 1.000; file/file_search 0.500; file/line_index 0.500; python/numeric_input 0.167; file/character_count 0.000; file/counting 0.000. Skill-level n is small; treat this ranking as a hypothesis.

## Answers to the Phase 1 questions

### 1. Does continual learning cause old-skill decline?
Final-stage average forgetting by family: python=0.167, file=0.000, database=0.000.
Yes, at least one previously learned family degraded after later training.

### 2. Which tools are forgotten most?
python (0.167); file (0.000); database (0.000)

### 3. Which skills are forgotten most?
python/stat_median (1.000); file/file_search (0.500); file/line_index (0.500); python/numeric_input (0.167); file/character_count (0.000); file/counting (0.000); file/file_list (0.000); file/file_read (0.000); file/file_write (0.000); file/final_formatting (0.000)

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

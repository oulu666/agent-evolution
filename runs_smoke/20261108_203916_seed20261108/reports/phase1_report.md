# FAC-TinyAgent Phase 1 Report

- Run: `20261108_203916_seed20261108`
- Created: 2026-11-08T20:45:05+08:00
- Model: `/home/egret/models/Qwen3-0.6B`
- Seed: 20261108
- Method: sequential QLoRA SFT, no replay (natural forgetting)
- Training: 2 epochs, LR 0.0001, LoRA r=8 alpha=16, max length 1024

## Data
| family | train | val | test |
| --- | --- | --- | --- |
| file | 8 | 2 | 6 |
| database | 8 | 2 | 6 |
| python | 8 | 2 | 6 |

## Capability matrix (final task success)

| stage | database | file | python |
| --- | --- | --- | --- |
| stage_00_base | 0.000 | 0.000 | 0.333 |
| stage_01_file | - | 0.167 | - |
| stage_02_database | 0.000 | 0.167 | - |
| stage_03_python | 0.167 | 0.333 | 0.833 |

## Forgetting by metric

| stage | tool_selection_accuracy | argument_accuracy | execution_success_rate | final_task_success_rate |
| --- | --- | --- | --- | --- |
| 2 | 0.167 | 0.167 | 0.167 | 0.000 |
| 3 | 0.000 | 0.000 | 0.000 | 0.000 |

## Answers to the Phase 1 questions

### 1. Does continual learning cause old-skill decline?
Final-stage average forgetting by family: file=0.000, database=0.000.
No positive forgetting was observed in this run; the test sets may be at a floor.

### 2. Which tools are forgotten most?
file (0.000); database (0.000)

### 3. Which skills are forgotten most?
file/character_count (0.000); file/counting (0.000); file/file_list (0.000); file/file_read (0.000); file/file_search (0.000); file/file_write (0.000); file/final_formatting (0.000); file/line_index (0.000); database/counting (0.000); database/schema_reading (0.000)

### 4. Schema, argument complexity, and order
The three families differ in schema complexity (file < statistics < SQL) and learning order (file -> database -> python). With one run and three families these factors are confounded; use multiple orders/seeds and within-family complexity levels in Phase 2 before making a causal claim.

## Limitations

- One model (Qwen3-0.6B) and one seed; no confidence intervals.
- Test templates are held out, but the absolute scores can be near floor.
- Natural forgetting only; no replay or adaptive review is implemented.
- The data split is template-based plus entity-based, not a fully independent domain.

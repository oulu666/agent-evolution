# Experiment A: cross-evaluation of models and task suites

Two final models: historical A-order stage-4 and v2 no-replay stage-4. Two suites: historical test (30/family) and current probe (24/family). All old-tool cells use batch 32; joint success requires tool, arguments, execution and answer.

## Macro old-tool joint success

| model × suite | mean over seeds | seeds |
| --- | --- | --- |
| historical_on_test | 0.596±0.006 | 3 |
| historical_on_probe | 0.551±0.040 | 3 |
| v2none_on_test | 0.600±0.029 | 3 |
| v2none_on_probe | 0.519±0.016 | 3 |

## Per-family detail

| model × suite | family | joint | answer | seeds |
| --- | --- | --- | --- | --- |
| historical_on_test | file | 0.489±0.019 | 0.489±0.019 | 3 |
| historical_on_test | database | 0.400±0.033 | 0.600±0.033 | 3 |
| historical_on_test | python | 0.900±0.033 | 0.911±0.019 | 3 |
| historical_on_probe | file | 0.292±0.072 | 0.292±0.072 | 3 |
| historical_on_probe | database | 0.361±0.048 | 0.556±0.064 | 3 |
| historical_on_probe | python | 1.000 | 1.000 | 3 |
| v2none_on_test | file | 0.511±0.051 | 0.511±0.051 | 3 |
| v2none_on_test | database | 0.389±0.038 | 0.589±0.038 | 3 |
| v2none_on_test | python | 0.900±0.067 | 0.922±0.051 | 3 |
| v2none_on_probe | file | 0.194±0.048 | 0.194±0.048 | 3 |
| v2none_on_probe | database | 0.361±0.048 | 0.556±0.064 | 3 |
| v2none_on_probe | python | 1.000 | 1.000 | 3 |

## Start-state reference

| model × suite | mean old joint | seeds |
| --- | --- | --- |
| start_on_test | 0.648±0.028 | 3 |
| start_on_probe | 0.500 | 3 |

## Change from start

| suite | model | family | start | final | delta |
| --- | --- | --- | --- | --- | --- |
| test | historical | file | 0.500±0.058 | 0.489±0.019 | -0.0111 |
| test | historical | database | 0.444±0.038 | 0.400±0.033 | -0.0444 |
| test | historical | python | 1.000 | 0.900±0.033 | -0.1000 |
| test | v2none | file | 0.500±0.058 | 0.511±0.051 | +0.0111 |
| test | v2none | database | 0.444±0.038 | 0.389±0.038 | -0.0556 |
| test | v2none | python | 1.000 | 0.900±0.067 | -0.1000 |
| probe | historical | file | 0.167 | 0.292±0.072 | +0.1250 |
| probe | historical | database | 0.333 | 0.361±0.048 | +0.0278 |
| probe | historical | python | 1.000 | 1.000 | +0.0000 |
| probe | v2none | file | 0.167 | 0.194±0.048 | +0.0278 |
| probe | v2none | database | 0.333 | 0.361±0.048 | +0.0278 |
| probe | v2none | python | 1.000 | 1.000 | +0.0000 |

## Reading

The same historical model falls from 0.648 to 0.596 on the historical test (-5.2pp), but rises from 0.500 to 0.551 on the probe (+5.1pp). The v2 no-replay model shows the same pattern (0.648 -> 0.600 on test; 0.500 -> 0.519 on probe). On the historical test database and python fall; on the probe they hold or improve. This is a task-coverage/wording difference, not a different training trajectory. Absolute probe scores are lower for file/database, so compare within-suite changes, not raw cross-suite levels.

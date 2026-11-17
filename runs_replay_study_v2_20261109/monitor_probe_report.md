# Monitor probe diagnosis

Order A; no-replay branch; probe start/midpoint/end; no training.

## Probe scores

| Seed | Tool | Start joint | Midpoint joint | End joint | Start answer | Midpoint answer | End answer |
|---|---|---|---|---|---|---|---|
| 20261108 | file | 0.167 | 0.292 | 0.167 | 0.167 | 0.292 | 0.167 |
| 20261108 | database | 0.333 | 0.333 | 0.333 | 0.375 | 0.625 | 0.500 |
| 20261108 | python | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| 20261109 | file | 0.167 | 0.333 | 0.167 | 0.167 | 0.333 | 0.167 |
| 20261109 | database | 0.333 | 0.333 | 0.417 | 0.417 | 0.583 | 0.625 |
| 20261109 | python | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| 20261110 | file | 0.167 | 0.375 | 0.250 | 0.167 | 0.375 | 0.250 |
| 20261110 | database | 0.333 | 0.333 | 0.333 | 0.458 | 0.625 | 0.542 |
| 20261110 | python | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |

## Historical per-template drops

| Seed | Tool | Template | Before | After | n |
|---|---|---|---|---|---|
| 20261108 | python | stats_median_prose | 1.000 | 0.400 | 5 |
| 20261109 | database | db_filter_top | 0.500 | 0.333 | 6 |
| 20261109 | python | stats_median_prose | 1.000 | 0.200 | 5 |
| 20261110 | file | file_last_match | 0.500 | 0.000 | 8 |
| 20261110 | database | db_filter_top | 0.500 | 0.000 | 6 |
| 20261110 | python | stats_median_prose | 1.000 | 0.600 | 5 |

## Coverage check

Historical drop templates: db_filter_top, file_last_match, stats_median_prose.
Probe template coverage: study_correlation, study_filter_count, study_filter_mean, study_first_match, study_group_count, study_last_match, study_line_count, study_list, study_mean, study_median, study_percentile, study_rank, study_regression, study_schema, study_std, study_tables, study_word_count, study_write.
Exact template overlap: none.

The probe uses `study_*` templates and explicit tool wording; the historical drops occur on different test templates. A zero overlap means the monitor's null signal is a coverage result, not evidence that old skills are retained.

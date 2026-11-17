# Monitor v1 vs v2 offline validation

Units: scenario x seed x old family = 15 (A: 9, C: 6). Decision at stage midpoint; gold = independent natural final at end of the no-replay arm (File re-scored).

| detector | gold | IE policy | recall | FPR | TP/FN/FP/TN | IE |
|---|---|---|---|---|---|---|
| V1_drop>0_rawlabels | G_drop | IE=neg | 0.67 | 0.33 | 2/1/4/8 | 0 |
| V1_drop>0_rawlabels | G_drop | IE=flag | 0.67 | 0.33 | 2/1/4/8 | 0 |
| V1_drop>0_rawlabels | G_need | IE=neg | 0.45 | 0.25 | 5/6/1/3 | 0 |
| V1_drop>0_rawlabels | G_need | IE=flag | 0.45 | 0.25 | 5/6/1/3 | 0 |
| V1_drop>0_rawlabels | G_cum | IE=neg | 0.75 | 0.27 | 3/1/3/8 | 0 |
| V1_drop>0_rawlabels | G_cum | IE=flag | 0.75 | 0.27 | 3/1/3/8 | 0 |
| V1_drop>0_fixedlabels | G_drop | IE=neg | 1.00 | 0.25 | 3/0/3/9 | 0 |
| V1_drop>0_fixedlabels | G_drop | IE=flag | 1.00 | 0.25 | 3/0/3/9 | 0 |
| V1_drop>0_fixedlabels | G_need | IE=neg | 0.36 | 0.50 | 4/7/2/2 | 0 |
| V1_drop>0_fixedlabels | G_need | IE=flag | 0.36 | 0.50 | 4/7/2/2 | 0 |
| V1_drop>0_fixedlabels | G_cum | IE=neg | 0.75 | 0.27 | 3/1/3/8 | 0 |
| V1_drop>0_fixedlabels | G_cum | IE=flag | 0.75 | 0.27 | 3/1/3/8 | 0 |
| V1probes+rule2 | G_drop | IE=neg | 1.00 | 0.67 | 3/0/8/4 | 2 |
| V1probes+rule2 | G_drop | IE=flag | 1.00 | 0.83 | 3/0/10/2 | 2 |
| V1probes+rule2 | G_need | IE=neg | 0.82 | 0.50 | 9/2/2/2 | 2 |
| V1probes+rule2 | G_need | IE=flag | 1.00 | 0.50 | 11/0/2/2 | 2 |
| V1probes+rule2 | G_cum | IE=neg | 1.00 | 0.64 | 4/0/7/4 | 2 |
| V1probes+rule2 | G_cum | IE=flag | 1.00 | 0.82 | 4/0/9/2 | 2 |
| V1probes+rule2[DEGRADED-only] | G_drop | IE=neg | 0.67 | 0.00 | 2/1/0/12 | 2 |
| V1probes+rule2[DEGRADED-only] | G_drop | IE=flag | 0.67 | 0.17 | 2/1/2/10 | 2 |
| V1probes+rule2[DEGRADED-only] | G_need | IE=neg | 0.09 | 0.25 | 1/10/1/3 | 2 |
| V1probes+rule2[DEGRADED-only] | G_need | IE=flag | 0.27 | 0.25 | 3/8/1/3 | 2 |
| V1probes+rule2[DEGRADED-only] | G_cum | IE=neg | 0.50 | 0.00 | 2/2/0/11 | 2 |
| V1probes+rule2[DEGRADED-only] | G_cum | IE=flag | 0.50 | 0.18 | 2/2/2/9 | 2 |
| V2probes_drop>0 | G_drop | IE=neg | 1.00 | 0.25 | 3/0/3/9 | 0 |
| V2probes_drop>0 | G_drop | IE=flag | 1.00 | 0.25 | 3/0/3/9 | 0 |
| V2probes_drop>0 | G_need | IE=neg | 0.36 | 0.50 | 4/7/2/2 | 0 |
| V2probes_drop>0 | G_need | IE=flag | 0.36 | 0.50 | 4/7/2/2 | 0 |
| V2probes_drop>0 | G_cum | IE=neg | 0.75 | 0.27 | 3/1/3/8 | 0 |
| V2probes_drop>0 | G_cum | IE=flag | 0.75 | 0.27 | 3/1/3/8 | 0 |
| V2probes+rule2_pooled | G_drop | IE=neg | 1.00 | 1.00 | 3/0/12/0 | 0 |
| V2probes+rule2_pooled | G_drop | IE=flag | 1.00 | 1.00 | 3/0/12/0 | 0 |
| V2probes+rule2_pooled | G_need | IE=neg | 1.00 | 1.00 | 11/0/4/0 | 0 |
| V2probes+rule2_pooled | G_need | IE=flag | 1.00 | 1.00 | 11/0/4/0 | 0 |
| V2probes+rule2_pooled | G_cum | IE=neg | 1.00 | 1.00 | 4/0/11/0 | 0 |
| V2probes+rule2_pooled | G_cum | IE=flag | 1.00 | 1.00 | 4/0/11/0 | 0 |
| V2probes+rule2_pooled[DEGRADED-only] | G_drop | IE=neg | 0.33 | 0.00 | 1/2/0/12 | 0 |
| V2probes+rule2_pooled[DEGRADED-only] | G_drop | IE=flag | 0.33 | 0.00 | 1/2/0/12 | 0 |
| V2probes+rule2_pooled[DEGRADED-only] | G_need | IE=neg | 0.09 | 0.00 | 1/10/0/4 | 0 |
| V2probes+rule2_pooled[DEGRADED-only] | G_need | IE=flag | 0.09 | 0.00 | 1/10/0/4 | 0 |
| V2probes+rule2_pooled[DEGRADED-only] | G_cum | IE=neg | 0.25 | 0.00 | 1/3/0/11 | 0 |
| V2probes+rule2_pooled[DEGRADED-only] | G_cum | IE=flag | 0.25 | 0.00 | 1/3/0/11 | 0 |
| V2probes+rule2_subsetmax | G_drop | IE=neg | 1.00 | 1.00 | 3/0/12/0 | 0 |
| V2probes+rule2_subsetmax | G_drop | IE=flag | 1.00 | 1.00 | 3/0/12/0 | 0 |
| V2probes+rule2_subsetmax | G_need | IE=neg | 1.00 | 1.00 | 11/0/4/0 | 0 |
| V2probes+rule2_subsetmax | G_need | IE=flag | 1.00 | 1.00 | 11/0/4/0 | 0 |
| V2probes+rule2_subsetmax | G_cum | IE=neg | 1.00 | 1.00 | 4/0/11/0 | 0 |
| V2probes+rule2_subsetmax | G_cum | IE=flag | 1.00 | 1.00 | 4/0/11/0 | 0 |
| V2probes+rule2_subsetmax[DEGRADED-only] | G_drop | IE=neg | 0.33 | 0.00 | 1/2/0/12 | 0 |
| V2probes+rule2_subsetmax[DEGRADED-only] | G_drop | IE=flag | 0.33 | 0.00 | 1/2/0/12 | 0 |
| V2probes+rule2_subsetmax[DEGRADED-only] | G_need | IE=neg | 0.09 | 0.00 | 1/10/0/4 | 0 |
| V2probes+rule2_subsetmax[DEGRADED-only] | G_need | IE=flag | 0.09 | 0.00 | 1/10/0/4 | 0 |
| V2probes+rule2_subsetmax[DEGRADED-only] | G_cum | IE=neg | 0.25 | 0.00 | 1/3/0/11 | 0 |
| V2probes+rule2_subsetmax[DEGRADED-only] | G_cum | IE=flag | 0.25 | 0.00 | 1/3/0/11 | 0 |

## V1 with raw labels for both monitor and gold (what Round 2 saw)

```
{
 "G_drop": {
  "tp": 5,
  "fn": 0,
  "fp": 1,
  "tn": 9,
  "ie": 0,
  "recall": 1.0,
  "fpr": 0.1,
  "n": 15
 },
 "G_need": {
  "tp": 5,
  "fn": 8,
  "fp": 1,
  "tn": 1,
  "ie": 0,
  "recall": 0.38461538461538464,
  "fpr": 0.5,
  "n": 15
 },
 "G_cum": {
  "tp": 2,
  "fn": 0,
  "fp": 4,
  "tn": 9,
  "ie": 0,
  "recall": 1.0,
  "fpr": 0.3076923076923077,
  "n": 15
 }
}
```

## Round-2 natural final re-scored (File last-match label fix)

```
{
 "A|start": {
  "old_macro_raw": 0.48148148148148145,
  "old_macro_fixed": 0.40740740740740744,
  "file_fixed": 0.22222222222222224,
  "file_fixed_by_seed": [
   0.13333333333333333,
   0.13333333333333333,
   0.4
  ]
 },
 "A|none": {
  "old_macro_raw": 0.2111111111111111,
  "old_macro_fixed": 0.34074074074074073,
  "file_fixed": 0.3888888888888889,
  "file_fixed_by_seed": [
   0.06666666666666667,
   0.43333333333333335,
   0.6666666666666666
  ]
 },
 "A|uniform": {
  "old_macro_raw": 0.2037037037037037,
  "old_macro_fixed": 0.35185185185185186,
  "file_fixed": 0.4444444444444444,
  "file_fixed_by_seed": [
   0.3333333333333333,
   0.26666666666666666,
   0.7333333333333333
  ]
 },
 "A|targeted": {
  "old_macro_raw": 0.6407407407407407,
  "old_macro_fixed": 0.8222222222222222,
  "file_fixed": 0.5444444444444445,
  "file_fixed_by_seed": [
   0.8333333333333334,
   0.3333333333333333,
   0.4666666666666667
  ]
 },
 "A|adaptive": {
  "old_macro_raw": 0.362962962962963,
  "old_macro_fixed": 0.5,
  "file_fixed": 0.4222222222222222,
  "file_fixed_by_seed": [
   0.7333333333333333,
   0.03333333333333333,
   0.5
  ]
 },
 "C|start": {
  "old_macro_raw": 0.14444444444444443,
  "old_macro_fixed": 0.5388888888888889,
  "file_fixed": 0.788888888888889,
  "file_fixed_by_seed": [
   0.7666666666666667,
   0.8,
   0.8
  ]
 },
 "C|none": {
  "old_macro_raw": 0.16666666666666666,
  "old_macro_fixed": 0.5111111111111112,
  "file_fixed": 0.6888888888888889,
  "file_fixed_by_seed": [
   0.8333333333333334,
   0.4,
   0.8333333333333334
  ]
 },
 "C|uniform": {
  "old_macro_raw": 0.3055555555555556,
  "old_macro_fixed": 0.6,
  "file_fixed": 0.5888888888888889,
  "file_fixed_by_seed": [
   0.8333333333333334,
   0.23333333333333334,
   0.7
  ]
 },
 "C|targeted": {
  "old_macro_raw": 0.5277777777777778,
  "old_macro_fixed": 0.6388888888888888,
  "file_fixed": 0.2777777777777778,
  "file_fixed_by_seed": [
   0.26666666666666666,
   0.36666666666666664,
   0.2
  ]
 },
 "C|adaptive": {
  "old_macro_raw": 0.3055555555555556,
  "old_macro_fixed": 0.6,
  "file_fixed": 0.5888888888888889,
  "file_fixed_by_seed": [
   0.8,
   0.23333333333333334,
   0.7333333333333333
  ]
 }
}
```

## Costs (per monitoring check, all old families)

```
{
 "v1": {
  "episodes": 720,
  "input_tokens": 409796,
  "output_tokens": 37925,
  "seconds": 419.27999999999986,
  "checks": 12,
  "per_check": {
   "episodes": 60.0,
   "input_tokens": 34149.666666666664,
   "output_tokens": 3160.4166666666665,
   "seconds": 34.93999999999999
  }
 },
 "v2": {
  "episodes": 960,
  "input_tokens": 557542,
  "output_tokens": 53789,
  "seconds": 420.84,
  "checks": 12,
  "per_check": {
   "episodes": 80.0,
   "input_tokens": 46461.833333333336,
   "output_tokens": 4482.416666666667,
   "seconds": 35.07
  }
 }
}
```

## Units

- A seed20261108 file gold_fixed={'start': 0.133, 'end_none': 0.067, 'ref': 0.633} gold_raw={'start': 0.567, 'end_none': 0.0, 'ref': 0.0} labels={'G_drop': False, 'G_need': True, 'G_cum': True} | {'V1_drop>0_rawlabels': 'DEGRADED', 'V1_drop>0_fixedlabels': 'OK', 'V1probes+rule2': 'DEFICIENT', 'V2probes_drop>0': 'OK', 'V2probes+rule2_pooled': 'DEFICIENT', 'V2probes+rule2_subsetmax': 'DEFICIENT', 'V1probes+rule2[DEGRADED-only]': 'OK', 'V2probes+rule2_pooled[DEGRADED-only]': 'OK', 'V2probes+rule2_subsetmax[DEGRADED-only]': 'OK'}
- A seed20261108 database gold_fixed={'start': 0.0, 'end_none': 0.0, 'ref': 0.0} gold_raw={'start': 0.0, 'end_none': 0.0, 'ref': 0.0} labels={'G_drop': False, 'G_need': True, 'G_cum': False} | {'V1_drop>0_rawlabels': 'OK', 'V1_drop>0_fixedlabels': 'OK', 'V1probes+rule2': 'DEFICIENT', 'V2probes_drop>0': 'OK', 'V2probes+rule2_pooled': 'DEFICIENT', 'V2probes+rule2_subsetmax': 'DEFICIENT', 'V1probes+rule2[DEGRADED-only]': 'OK', 'V2probes+rule2_pooled[DEGRADED-only]': 'OK', 'V2probes+rule2_subsetmax[DEGRADED-only]': 'OK'}
- A seed20261108 python gold_fixed={'start': 0.967, 'end_none': 0.1, 'ref': 0.967} gold_raw={'start': 0.967, 'end_none': 0.1, 'ref': 0.967} labels={'G_drop': True, 'G_need': True, 'G_cum': True} | {'V1_drop>0_rawlabels': 'DEGRADED', 'V1_drop>0_fixedlabels': 'DEGRADED', 'V1probes+rule2': 'DEGRADED', 'V2probes_drop>0': 'DEGRADED', 'V2probes+rule2_pooled': 'DEFICIENT', 'V2probes+rule2_subsetmax': 'DEFICIENT', 'V1probes+rule2[DEGRADED-only]': 'DEGRADED', 'V2probes+rule2_pooled[DEGRADED-only]': 'OK', 'V2probes+rule2_subsetmax[DEGRADED-only]': 'OK'}
- A seed20261109 file gold_fixed={'start': 0.133, 'end_none': 0.433, 'ref': 0.5} gold_raw={'start': 0.533, 'end_none': 0.0, 'ref': 0.0} labels={'G_drop': False, 'G_need': True, 'G_cum': False} | {'V1_drop>0_rawlabels': 'DEGRADED', 'V1_drop>0_fixedlabels': 'DEGRADED', 'V1probes+rule2': 'DEFICIENT', 'V2probes_drop>0': 'OK', 'V2probes+rule2_pooled': 'DEFICIENT', 'V2probes+rule2_subsetmax': 'DEFICIENT', 'V1probes+rule2[DEGRADED-only]': 'OK', 'V2probes+rule2_pooled[DEGRADED-only]': 'OK', 'V2probes+rule2_subsetmax[DEGRADED-only]': 'OK'}
- A seed20261109 database gold_fixed={'start': 0.033, 'end_none': 0.0, 'ref': 0.0} gold_raw={'start': 0.033, 'end_none': 0.0, 'ref': 0.0} labels={'G_drop': False, 'G_need': True, 'G_cum': False} | {'V1_drop>0_rawlabels': 'OK', 'V1_drop>0_fixedlabels': 'OK', 'V1probes+rule2': 'DEFICIENT', 'V2probes_drop>0': 'DEGRADED', 'V2probes+rule2_pooled': 'DEFICIENT', 'V2probes+rule2_subsetmax': 'DEFICIENT', 'V1probes+rule2[DEGRADED-only]': 'OK', 'V2probes+rule2_pooled[DEGRADED-only]': 'OK', 'V2probes+rule2_subsetmax[DEGRADED-only]': 'OK'}
- A seed20261109 python gold_fixed={'start': 1.0, 'end_none': 1.0, 'ref': 1.0} gold_raw={'start': 1.0, 'end_none': 1.0, 'ref': 1.0} labels={'G_drop': False, 'G_need': False, 'G_cum': False} | {'V1_drop>0_rawlabels': 'OK', 'V1_drop>0_fixedlabels': 'OK', 'V1probes+rule2': 'OK', 'V2probes_drop>0': 'OK', 'V2probes+rule2_pooled': 'DEFICIENT', 'V2probes+rule2_subsetmax': 'DEFICIENT', 'V1probes+rule2[DEGRADED-only]': 'OK', 'V2probes+rule2_pooled[DEGRADED-only]': 'OK', 'V2probes+rule2_subsetmax[DEGRADED-only]': 'OK'}
- A seed20261110 file gold_fixed={'start': 0.4, 'end_none': 0.667, 'ref': 0.467} gold_raw={'start': 0.233, 'end_none': 0.0, 'ref': 0.0} labels={'G_drop': False, 'G_need': True, 'G_cum': False} | {'V1_drop>0_rawlabels': 'DEGRADED', 'V1_drop>0_fixedlabels': 'OK', 'V1probes+rule2': 'INSUFFICIENT_EVIDENCE', 'V2probes_drop>0': 'OK', 'V2probes+rule2_pooled': 'DEFICIENT', 'V2probes+rule2_subsetmax': 'DEFICIENT', 'V1probes+rule2[DEGRADED-only]': 'INSUFFICIENT_EVIDENCE', 'V2probes+rule2_pooled[DEGRADED-only]': 'OK', 'V2probes+rule2_subsetmax[DEGRADED-only]': 'OK'}
- A seed20261110 database gold_fixed={'start': 0.033, 'end_none': 0.0, 'ref': 0.0} gold_raw={'start': 0.033, 'end_none': 0.0, 'ref': 0.0} labels={'G_drop': False, 'G_need': True, 'G_cum': False} | {'V1_drop>0_rawlabels': 'DEGRADED', 'V1_drop>0_fixedlabels': 'DEGRADED', 'V1probes+rule2': 'DEFICIENT', 'V2probes_drop>0': 'DEGRADED', 'V2probes+rule2_pooled': 'DEFICIENT', 'V2probes+rule2_subsetmax': 'DEFICIENT', 'V1probes+rule2[DEGRADED-only]': 'OK', 'V2probes+rule2_pooled[DEGRADED-only]': 'OK', 'V2probes+rule2_subsetmax[DEGRADED-only]': 'OK'}
- A seed20261110 python gold_fixed={'start': 0.967, 'end_none': 0.8, 'ref': 0.967} gold_raw={'start': 0.967, 'end_none': 0.8, 'ref': 0.967} labels={'G_drop': True, 'G_need': False, 'G_cum': True} | {'V1_drop>0_rawlabels': 'DEGRADED', 'V1_drop>0_fixedlabels': 'DEGRADED', 'V1probes+rule2': 'DEGRADED', 'V2probes_drop>0': 'DEGRADED', 'V2probes+rule2_pooled': 'DEFICIENT', 'V2probes+rule2_subsetmax': 'DEFICIENT', 'V1probes+rule2[DEGRADED-only]': 'DEGRADED', 'V2probes+rule2_pooled[DEGRADED-only]': 'OK', 'V2probes+rule2_subsetmax[DEGRADED-only]': 'OK'}
- C seed20261108 file gold_fixed={'start': 0.767, 'end_none': 0.833, 'ref': 0.767} gold_raw={'start': 0.0, 'end_none': 0.0, 'ref': 0.0} labels={'G_drop': False, 'G_need': False, 'G_cum': False} | {'V1_drop>0_rawlabels': 'OK', 'V1_drop>0_fixedlabels': 'OK', 'V1probes+rule2': 'OK', 'V2probes_drop>0': 'OK', 'V2probes+rule2_pooled': 'DEFICIENT', 'V2probes+rule2_subsetmax': 'DEFICIENT', 'V1probes+rule2[DEGRADED-only]': 'OK', 'V2probes+rule2_pooled[DEGRADED-only]': 'OK', 'V2probes+rule2_subsetmax[DEGRADED-only]': 'OK'}
- C seed20261108 database gold_fixed={'start': 0.233, 'end_none': 0.267, 'ref': 0.033} gold_raw={'start': 0.233, 'end_none': 0.267, 'ref': 0.033} labels={'G_drop': False, 'G_need': True, 'G_cum': False} | {'V1_drop>0_rawlabels': 'OK', 'V1_drop>0_fixedlabels': 'OK', 'V1probes+rule2': 'DEFICIENT', 'V2probes_drop>0': 'OK', 'V2probes+rule2_pooled': 'DEFICIENT', 'V2probes+rule2_subsetmax': 'DEFICIENT', 'V1probes+rule2[DEGRADED-only]': 'OK', 'V2probes+rule2_pooled[DEGRADED-only]': 'OK', 'V2probes+rule2_subsetmax[DEGRADED-only]': 'OK'}
- C seed20261109 file gold_fixed={'start': 0.8, 'end_none': 0.4, 'ref': 0.8} gold_raw={'start': 0.0, 'end_none': 0.0, 'ref': 0.0} labels={'G_drop': True, 'G_need': True, 'G_cum': True} | {'V1_drop>0_rawlabels': 'OK', 'V1_drop>0_fixedlabels': 'DEGRADED', 'V1probes+rule2': 'DEFICIENT', 'V2probes_drop>0': 'DEGRADED', 'V2probes+rule2_pooled': 'DEGRADED', 'V2probes+rule2_subsetmax': 'DEGRADED', 'V1probes+rule2[DEGRADED-only]': 'OK', 'V2probes+rule2_pooled[DEGRADED-only]': 'DEGRADED', 'V2probes+rule2_subsetmax[DEGRADED-only]': 'DEGRADED'}
- C seed20261109 database gold_fixed={'start': 0.3, 'end_none': 0.333, 'ref': 0.067} gold_raw={'start': 0.3, 'end_none': 0.333, 'ref': 0.067} labels={'G_drop': False, 'G_need': True, 'G_cum': False} | {'V1_drop>0_rawlabels': 'OK', 'V1_drop>0_fixedlabels': 'OK', 'V1probes+rule2': 'DEFICIENT', 'V2probes_drop>0': 'OK', 'V2probes+rule2_pooled': 'DEFICIENT', 'V2probes+rule2_subsetmax': 'DEFICIENT', 'V1probes+rule2[DEGRADED-only]': 'OK', 'V2probes+rule2_pooled[DEGRADED-only]': 'OK', 'V2probes+rule2_subsetmax[DEGRADED-only]': 'OK'}
- C seed20261110 file gold_fixed={'start': 0.8, 'end_none': 0.833, 'ref': 0.8} gold_raw={'start': 0.0, 'end_none': 0.0, 'ref': 0.0} labels={'G_drop': False, 'G_need': False, 'G_cum': False} | {'V1_drop>0_rawlabels': 'OK', 'V1_drop>0_fixedlabels': 'DEGRADED', 'V1probes+rule2': 'DEFICIENT', 'V2probes_drop>0': 'DEGRADED', 'V2probes+rule2_pooled': 'DEFICIENT', 'V2probes+rule2_subsetmax': 'DEFICIENT', 'V1probes+rule2[DEGRADED-only]': 'OK', 'V2probes+rule2_pooled[DEGRADED-only]': 'OK', 'V2probes+rule2_subsetmax[DEGRADED-only]': 'OK'}
- C seed20261110 database gold_fixed={'start': 0.333, 'end_none': 0.4, 'ref': 0.133} gold_raw={'start': 0.333, 'end_none': 0.4, 'ref': 0.133} labels={'G_drop': False, 'G_need': True, 'G_cum': False} | {'V1_drop>0_rawlabels': 'OK', 'V1_drop>0_fixedlabels': 'OK', 'V1probes+rule2': 'INSUFFICIENT_EVIDENCE', 'V2probes_drop>0': 'OK', 'V2probes+rule2_pooled': 'DEFICIENT', 'V2probes+rule2_subsetmax': 'DEFICIENT', 'V1probes+rule2[DEGRADED-only]': 'INSUFFICIENT_EVIDENCE', 'V2probes+rule2_pooled[DEGRADED-only]': 'OK', 'V2probes+rule2_subsetmax[DEGRADED-only]': 'OK'}

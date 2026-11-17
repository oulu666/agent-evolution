# Monitor v2 离线校准（CPU，只读）

生成于 2026-11-11 13:28:34（Asia/Shanghai）。15 个离线单元（A 9 + C 6），特征只用 v2 探针（File 用修正判分）。金标准来自独立自然语言期末（无复习臂末端）。n=15，所有数字只作描述；概率阈值固定 0.5，未在验证折上调。

## 1. 为什么 τ=0.8 把所有单元判成不足（刻度漂移）

- 15 个单元在决策时刻的 v2 探针分数最高只有 **0.656**；n=32 时 Wilson 90% 上界要 ≥0.8，探针分至少要 0.688。所以 rule2 的“上界 < τ → DEFICIENT”对每个单元都成立。
- 同一个 checkpoint 上，自然语言期末比 v2 探针平均高 0.210（起点）/ 0.230（各工具刚学完时）。v2 探针含改写/自然表述子集，比期末难，分数被整体压低：τ=0.8 是按期末刻度定的，却用在探针刻度上。
- 例：A/20261109/python 期末起点 1.000、末端 1.000（完全没忘），探针只有 0.625 → 仍被判 DEFICIENT。

| 单元 | 探针 p0 | 期末起点 | 探针 p1(决策) | 期末末端(none) | 探针 ref | 期末 ref | Wilson 上界(p1) |
|---|---|---|---|---|---|---|---|
| A/20261108/file | 0.031 | 0.133 | 0.031 | 0.067 | 0.062 | 0.633 | 0.129 |
| A/20261108/database | 0.250 | 0.000 | 0.250 | 0.000 | 0.188 | 0.000 | 0.392 |
| A/20261108/python | 0.719 | 0.967 | 0.656 | 0.100 | 0.719 | 0.967 | 0.777 |
| A/20261109/file | 0.031 | 0.133 | 0.031 | 0.433 | 0.125 | 0.500 | 0.129 |
| A/20261109/database | 0.250 | 0.033 | 0.219 | 0.000 | 0.250 | 0.000 | 0.358 |
| A/20261109/python | 0.625 | 1.000 | 0.625 | 1.000 | 0.625 | 1.000 | 0.751 |
| A/20261110/file | 0.000 | 0.400 | 0.188 | 0.667 | 0.062 | 0.467 | 0.324 |
| A/20261110/database | 0.250 | 0.033 | 0.219 | 0.000 | 0.219 | 0.000 | 0.358 |
| A/20261110/python | 0.656 | 0.967 | 0.625 | 0.800 | 0.656 | 0.967 | 0.751 |
| C/20261108/file | 0.375 | 0.767 | 0.438 | 0.833 | 0.375 | 0.767 | 0.581 |
| C/20261108/database | 0.094 | 0.233 | 0.156 | 0.267 | 0.031 | 0.033 | 0.288 |
| C/20261109/file | 0.125 | 0.800 | 0.000 | 0.400 | 0.125 | 0.800 | 0.078 |
| C/20261109/database | 0.094 | 0.300 | 0.188 | 0.333 | 0.062 | 0.067 | 0.324 |
| C/20261110/file | 0.156 | 0.800 | 0.094 | 0.833 | 0.156 | 0.800 | 0.213 |
| C/20261110/database | 0.094 | 0.333 | 0.156 | 0.400 | 0.031 | 0.133 | 0.288 |

## 2. 预测 G_need（阳性 11/15）

| 方法 | 验证 | recall | FPR | TP/FN/FP/TN | Brier | ECE(5 箱) | AUC |
|---|---|---|---|---|---|---|---|
| baseline rule2 (v2 pooled) | in_sample | 1.00 | 1.00 | 11/0/4/0 | 0.267 | 0.267 | 0.50 |
| baseline rule2 subset-max | in_sample | 1.00 | 1.00 | 11/0/4/0 | 0.267 | 0.267 | 0.50 |
| baseline fixed p1<0.8 | in_sample | 1.00 | 1.00 | 11/0/4/0 | 0.267 | 0.267 | 0.50 |
| baseline Wilson-upper(p1)<0.8 | in_sample | 1.00 | 1.00 | 11/0/4/0 | 0.267 | 0.267 | 0.50 |
| baseline prevalence (constant) | in_sample | 1.00 | 1.00 | 11/0/4/0 | 0.196 | 0.000 | 0.50 |
| logit(p1) | LOSO_seed | 0.91 | 1.00 | 10/1/4/0 | 0.173 | 0.230 | 0.70 |
| logit(p1) | LOSO_scenario | 0.91 | 0.50 | 10/1/2/2 | 0.184 | 0.102 | 0.61 |
| logit(p1) | in_sample_optimistic | 0.91 | 0.50 | 10/1/2/2 | 0.151 | 0.141 | 0.75 |
| logit(p1, p0-p1) | LOSO_seed | 0.91 | 1.00 | 10/1/4/0 | 0.215 | 0.086 | 0.61 |
| logit(p1, p0-p1) | LOSO_scenario | 0.91 | 0.50 | 10/1/2/2 | 0.199 | 0.236 | 0.64 |
| logit(p1, p0-p1) | in_sample_optimistic | 0.91 | 0.50 | 10/1/2/2 | 0.150 | 0.045 | 0.84 |
| logit(p1, pref-p1) | LOSO_seed | 0.91 | 1.00 | 10/1/4/0 | 0.203 | 0.114 | 0.66 |
| logit(p1, pref-p1) | LOSO_scenario | 0.82 | 0.50 | 9/2/2/2 | 0.208 | 0.192 | 0.61 |
| logit(p1, pref-p1) | in_sample_optimistic | 0.91 | 0.50 | 10/1/2/2 | 0.146 | 0.206 | 0.84 |
| isotonic(p1) | LOSO_seed | 0.91 | 0.25 | 10/1/1/3 | 0.151 | 0.150 | 0.80 |
| isotonic(p1) | LOSO_scenario | 0.91 | 0.50 | 10/1/2/2 | 0.178 | 0.142 | 0.73 |
| isotonic(p1) | in_sample_optimistic | 0.91 | 0.25 | 10/1/1/3 | 0.134 | 0.133 | 0.80 |

## 2. 预测 G_cum（阳性 4/15）

| 方法 | 验证 | recall | FPR | TP/FN/FP/TN | Brier | ECE(5 箱) | AUC |
|---|---|---|---|---|---|---|---|
| baseline rule2 (v2 pooled) | in_sample | 1.00 | 1.00 | 4/0/11/0 | 0.733 | 0.733 | 0.50 |
| baseline rule2 subset-max | in_sample | 1.00 | 1.00 | 4/0/11/0 | 0.733 | 0.733 | 0.50 |
| baseline fixed p1<0.8 | in_sample | 1.00 | 1.00 | 4/0/11/0 | 0.733 | 0.733 | 0.50 |
| baseline Wilson-upper(p1)<0.8 | in_sample | 1.00 | 1.00 | 4/0/11/0 | 0.733 | 0.733 | 0.50 |
| baseline prevalence (constant) | in_sample | 0.00 | 0.00 | 0/4/0/11 | 0.196 | 0.000 | 0.50 |
| logit(p1) | LOSO_seed | 0.00 | 0.00 | 0/4/0/11 | 0.234 | 0.235 | 0.14 |
| logit(p1) | LOSO_scenario | 0.00 | 0.00 | 0/4/0/11 | 0.240 | 0.149 | 0.36 |
| logit(p1) | in_sample_optimistic | 0.00 | 0.00 | 0/4/0/11 | 0.195 | 0.000 | 0.50 |
| logit(p1, p0-p1) | LOSO_seed | 0.00 | 0.09 | 0/4/1/10 | 0.187 | 0.068 | 0.66 |
| logit(p1, p0-p1) | LOSO_scenario | 0.25 | 0.00 | 1/3/0/11 | 0.206 | 0.116 | 0.56 |
| logit(p1, p0-p1) | in_sample_optimistic | 0.25 | 0.00 | 1/3/0/11 | 0.138 | 0.058 | 0.85 |
| logit(p1, pref-p1) | LOSO_seed | 0.25 | 0.09 | 1/3/1/10 | 0.183 | 0.242 | 0.70 |
| logit(p1, pref-p1) | LOSO_scenario | 0.00 | 0.00 | 0/4/0/11 | 0.201 | 0.097 | 0.50 |
| logit(p1, pref-p1) | in_sample_optimistic | 0.25 | 0.00 | 1/3/0/11 | 0.136 | 0.067 | 0.86 |
| isotonic(p1) | LOSO_seed | 0.50 | 0.36 | 2/2/4/7 | 0.262 | 0.300 | 0.50 |
| isotonic(p1) | LOSO_scenario | 0.50 | 0.45 | 2/2/5/6 | 0.228 | 0.149 | 0.58 |
| isotonic(p1) | in_sample_optimistic | 0.50 | 0.09 | 2/2/1/10 | 0.201 | 0.293 | 0.53 |

## 3. 外部复现单元（E4 + E2 的 none 臂，A 场景，Database/Python，模型用全部 15 单元拟合）

注意：与离线单元同起点、同种子，只是重新训练的中点与末端，不是独立种子。

G_need：

| 方法 | recall | FPR | TP/FN/FP/TN | Brier | ECE | AUC |
|---|---|---|---|---|---|---|
| baseline fixed p1<0.8 | 1.00 | 1.00 | 10/0/2/0 | 0.167 | 0.167 | 0.50 |
| baseline Wilson-upper(p1)<0.8 | 0.90 | 1.00 | 9/1/2/0 | 0.250 | 0.250 | 0.45 |
| logit(p1) | 0.60 | 0.00 | 6/4/0/2 | 0.168 | 0.227 | 0.70 |
| logit(p1, p0-p1) | 0.60 | 0.00 | 6/4/0/2 | 0.188 | 0.252 | 0.60 |
| logit(p1, pref-p1) | 0.60 | 0.00 | 6/4/0/2 | 0.190 | 0.254 | 0.60 |
| isotonic(p1) | 0.60 | 0.00 | 6/4/0/2 | 0.209 | 0.307 | 0.80 |

G_cum：

| 方法 | recall | FPR | TP/FN/FP/TN | Brier | ECE | AUC |
|---|---|---|---|---|---|---|
| baseline fixed p1<0.8 | 1.00 | 1.00 | 4/0/8/0 | 0.667 | 0.667 | 0.50 |
| baseline Wilson-upper(p1)<0.8 | 0.75 | 1.00 | 3/1/8/0 | 0.750 | 0.750 | 0.38 |
| logit(p1) | 0.00 | 0.00 | 0/4/0/8 | 0.235 | 0.079 | 0.06 |
| logit(p1, p0-p1) | 0.00 | 0.00 | 0/4/0/8 | 0.188 | 0.080 | 1.00 |
| logit(p1, pref-p1) | 0.00 | 0.00 | 0/4/0/8 | 0.162 | 0.070 | 1.00 |
| isotonic(p1) | 0.00 | 0.00 | 0/4/0/8 | 0.276 | 0.399 | 0.12 |

外部单元明细：

- E4 seed20261108 database: p0=0.250 p1=0.250 pref=0.188 end=0.000 ref=0.000 gold={'G_need': True, 'G_cum': False}
- E4 seed20261108 python: p0=0.719 p1=0.688 pref=0.719 end=0.600 ref=0.967 gold={'G_need': True, 'G_cum': True}
- E4 seed20261109 database: p0=0.250 p1=0.219 pref=0.250 end=0.000 ref=0.000 gold={'G_need': True, 'G_cum': False}
- E4 seed20261109 python: p0=0.625 p1=0.625 pref=0.625 end=1.000 ref=1.000 gold={'G_need': False, 'G_cum': False}
- E4 seed20261110 database: p0=0.250 p1=0.219 pref=0.219 end=0.000 ref=0.000 gold={'G_need': True, 'G_cum': False}
- E4 seed20261110 python: p0=0.656 p1=0.625 pref=0.656 end=0.767 ref=0.967 gold={'G_need': True, 'G_cum': True}
- E2 seed20261108 database: p0=0.250 p1=0.250 pref=0.188 end=0.000 ref=0.000 gold={'G_need': True, 'G_cum': False}
- E2 seed20261108 python: p0=0.719 p1=0.656 pref=0.719 end=0.267 ref=0.967 gold={'G_need': True, 'G_cum': True}
- E2 seed20261109 database: p0=0.250 p1=0.219 pref=0.250 end=0.000 ref=0.000 gold={'G_need': True, 'G_cum': False}
- E2 seed20261109 python: p0=0.625 p1=0.625 pref=0.625 end=1.000 ref=1.000 gold={'G_need': False, 'G_cum': False}
- E2 seed20261110 database: p0=0.250 p1=0.219 pref=0.219 end=0.000 ref=0.000 gold={'G_need': True, 'G_cum': False}
- E2 seed20261110 python: p0=0.656 p1=0.625 pref=0.656 end=0.767 ref=0.967 gold={'G_need': True, 'G_cum': True}

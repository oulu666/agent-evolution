# Round 2 A-scenario: replay content comparison

Four arms, order A stage 3 -> 4 (Calendar new; File/Database/Python old). Shared prefix, 10% replay budget, targeted/adaptive half uniform + half targeted. Historical test and independent natural final are separate suites.

## Historical test (old families macro / Calendar)

| mode | seeds | old joint | old answer | new joint |
| --- | --- | --- | --- | --- |
| start | 3 | 0.648±0.028 | 0.715±0.028 | 0.000 |
| none | 3 | 0.600±0.011 | 0.670±0.013 | 0.667±0.115 |
| uniform | 3 | 0.637±0.034 | 0.663±0.006 | 0.644±0.102 |
| targeted | 3 | 0.626±0.028 | 0.674±0.013 | 0.456±0.168 |
| adaptive | 3 | 0.615±0.028 | 0.663±0.013 | 0.322±0.184 |

## Independent natural final (old families macro)

| mode | seeds | joint | answer |
| --- | --- | --- | --- |
| start | 3 | 0.481±0.061 | 0.522±0.029 |
| none | 3 | 0.211±0.158 | 0.352±0.152 |
| uniform | 3 | 0.204±0.170 | 0.333±0.194 |
| targeted | 3 | 0.641±0.017 | 0.652±0.017 |
| adaptive | 3 | 0.363±0.034 | 0.452±0.023 |

## Paired differences

| seed | uniform-none hist | targeted-uniform hist | adaptive-uniform hist | targeted-uniform natural | adaptive-uniform natural |
| --- | --- | --- | --- | --- | --- |
| 20261108 | +0.0556 | -0.0444 | -0.0556 | +0.6333 | +0.3222 |
| 20261109 | +0.0444 | +0.0111 | +0.0000 | +0.3222 | +0.0222 |
| 20261110 | +0.0111 | -0.0000 | -0.0111 | +0.3556 | +0.1333 |

## Replay plan / cost

| seed | mode | replay input | target fraction | adaptive triggered | target samples | actual branch s |
| --- | --- | --- | --- | --- | --- | --- |
| 20261108 | none | 0 | 0.0 | False | {} | 182.1 |
| 20261108 | uniform | 7494 | 0.0 | False | {} | 65.8 |
| 20261108 | targeted | 7494 | 0.5 | False | {'database': 5, 'file': 3, 'python': 1} | 59.8 |
| 20261108 | adaptive | 7494 | 0.5 | True | {'database': 0, 'file': 4, 'python': 4} | 61.9 |
| 20261109 | none | 0 | 0.0 | False | {} | 194.8 |
| 20261109 | uniform | 7493 | 0.0 | False | {} | 62.6 |
| 20261109 | targeted | 7494 | 0.5 | False | {'database': 3, 'file': 3, 'python': 2} | 60.8 |
| 20261109 | adaptive | 7494 | 0.5 | True | {'database': 0, 'file': 8, 'python': 0} | 56.3 |
| 20261110 | none | 0 | 0.0 | False | {} | 216.4 |
| 20261110 | uniform | 7494 | 0.0 | False | {} | 58.1 |
| 20261110 | targeted | 7472 | 0.5 | False | {'database': 3, 'file': 4, 'python': 2} | 64.4 |
| 20261110 | adaptive | 7440 | 0.5 | True | {'database': 1, 'file': 5, 'python': 4} | 77.6 |

## Reading

The historical test is the direct old-tool outcome. The natural final is independent and tests whether the targeted content transfers to unseen natural wording. The key comparison is targeted vs uniform; adaptive vs uniform is interpretable only when adaptive_triggered is true.

# Round 2 C-scenario: replay content comparison

Four arms, order C stage 2 -> 3 (Calendar new; File/Database old). Shared prefix, 10% replay budget, targeted/adaptive half uniform + half targeted. Historical test and independent natural final are separate suites.

## Historical test (old families macro / Calendar)

| mode | seeds | old joint | old answer | new joint |
| --- | --- | --- | --- | --- |
| start | 3 | 0.450 | 0.650 | 0.078±0.069 |
| none | 3 | 0.400±0.029 | 0.594±0.035 | 0.289±0.150 |
| uniform | 3 | 0.439±0.111 | 0.511±0.063 | 0.300±0.153 |
| targeted | 3 | 0.411±0.111 | 0.500±0.109 | 0.233±0.173 |
| adaptive | 3 | 0.439±0.111 | 0.511±0.063 | 0.322±0.164 |

## Independent natural final (old families macro)

| mode | seeds | joint | answer |
| --- | --- | --- | --- |
| start | 3 | 0.144±0.025 | 0.244±0.063 |
| none | 3 | 0.167±0.033 | 0.283±0.029 |
| uniform | 3 | 0.306±0.113 | 0.372±0.098 |
| targeted | 3 | 0.528±0.048 | 0.528±0.048 |
| adaptive | 3 | 0.306±0.086 | 0.378±0.079 |

## Paired differences

| seed | uniform-none hist | targeted-uniform hist | adaptive-uniform hist | targeted-uniform natural | adaptive-uniform natural |
| --- | --- | --- | --- | --- | --- |
| 20261108 | +0.1333 | -0.0333 | +0.0000 | +0.3667 | +0.0167 |
| 20261109 | -0.0167 | +0.0167 | +0.0000 | +0.0667 | -0.0333 |
| 20261110 | +0.0000 | -0.0667 | +0.0000 | +0.2333 | +0.0167 |

## Replay plan / cost

| seed | mode | replay input | target fraction | adaptive triggered | target samples | actual branch s |
| --- | --- | --- | --- | --- | --- | --- |
| 20261108 | none | 0 | 0.0 | False | {} | 231.1 |
| 20261108 | uniform | 7494 | 0.0 | False | {} | 60.8 |
| 20261108 | targeted | 7494 | 0.5 | False | {'database': 7, 'file': 3} | 62.6 |
| 20261108 | adaptive | 7494 | 0.0 | False | {} | 65.1 |
| 20261109 | none | 0 | 0.0 | False | {} | 154.7 |
| 20261109 | uniform | 7491 | 0.0 | False | {} | 72.7 |
| 20261109 | targeted | 7494 | 0.5 | False | {'database': 5, 'file': 3} | 73.1 |
| 20261109 | adaptive | 7491 | 0.0 | False | {} | 64.1 |
| 20261110 | none | 0 | 0.0 | False | {} | 183.8 |
| 20261110 | uniform | 7494 | 0.0 | False | {} | 66.0 |
| 20261110 | targeted | 7494 | 0.5 | False | {'database': 6, 'file': 3} | 70.5 |
| 20261110 | adaptive | 7494 | 0.0 | False | {} | 72.7 |

## Reading

The historical test is the direct old-tool outcome. The natural final is independent and tests whether the targeted content transfers to unseen natural wording. The key comparison is targeted vs uniform; adaptive vs uniform is interpretable only when adaptive_triggered is true.

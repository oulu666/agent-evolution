# Round 2 A-scenario: replay content comparison

Four arms, order A stage 3 -> 4 (Calendar new; File/Database/Python old). Shared prefix, 10% replay budget, targeted/adaptive half uniform + half targeted. Historical test and independent natural final are separate suites.

## Historical test (old families macro / Calendar)

| mode | seeds | old joint | old answer | new joint |
| --- | --- | --- | --- | --- |
| start | 1 | 0.622 | 0.689 | 0.000 |
| none | 1 | 0.600 | 0.667 | 0.600 |
| targeted | 1 | 0.633 | 0.700 | 0.367 |

## Independent natural final (old families macro)

| mode | seeds | joint | answer |
| --- | --- | --- | --- |
| start | 1 | 0.511 | 0.533 |
| none | 1 | 0.233 | 0.422 |
| targeted | 1 | 0.656 | 0.667 |

## Paired differences

| seed | uniform-none hist | targeted-uniform hist | adaptive-uniform hist | targeted-uniform natural | adaptive-uniform natural |
| --- | --- | --- | --- | --- | --- |

## Replay plan / cost

| seed | mode | replay input | target fraction | adaptive triggered | target samples | actual branch s |
| --- | --- | --- | --- | --- | --- | --- |
| 20261108 | none | 0 | 0.0 | False | {} | 212.7 |
| 20261108 | targeted | 5752 | 0.5 | False | {'database': 7, 'file': 3, 'python': 1} | 70.5 |

## Reading

The historical test is the direct old-tool outcome. The natural final is independent and tests whether the targeted content transfers to unseen natural wording. The key comparison is targeted vs uniform; adaptive vs uniform is interpretable only when adaptive_triggered is true.

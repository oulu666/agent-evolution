# H2: transaction-scoped semantic rebuild admission
**Decision: do not promote to a core algorithm.** Endpoint coalescing helps controlled batches with frequent inverse writes, but does not pass the preregistered cross-workload threshold, loses to fixed SQL dependency invalidation on three of four confirmation profiles, and is matched by ordinary SQL first/last endpoint grouping.

Reproduce from this directory (Python standard library only): `sha256sum -c LOCK.sha256`; run `python -B run.py | python -B summarize.py` for the primary arm; add `--confirm` or `--endpoint` after `run.py` for the two validation arms. Compare workload aggregates, excluding runtime columns `ms` and `applicability_ms` from deterministic replay checks. The repository contains only workload aggregates. Milliseconds are local diagnostics, not comparable across runs or portable performance estimates.

## Mechanism
A real SQLite trigger records absolute old/new row values at each write. For any staged batch, the candidate coalesces journal rows by record ID and treats each row as either no contribution (unpublished) or (region, SKU, price × qty, qty). The dirty set is the union of regions of old/new unequal contributions. The endpoint test is sound in this scoped algebra: each projection is a sorted set of group sums, so a region not in the dirty set has identical contributed tuples. A projection hash still gates deterministic CSV serialization and gzip. The controls share exactly the same writes and trigger. Every method is checked against a full externally recomputed build after each batch; the oracle tests scheduling/invalidation, not the underlying SQL's correctness.

## Results, original seed block
Median exact SQL projections and total tested stage milliseconds per 36-batch history:
| Profile | Source hashed DAG | Canonical projection cutoff | Coalescer |
|---|---:|---:|---:|
| Metadata only | 576 / 39.583 | 576 / 15.466 | 0 / 1.893 |
| Inverse edits | 384 / 37.295 | 576 / 17.541 | 35 / 4.855 |
| Sparse substantive | 576 / 47.685 | 576 / 23.374 | 270 / 15.787 |
| Dense substantive | 576 / 63.757 | 576 / 39.771 | 576 / 58.751 |

## Confirmation seed block, stronger same-information journal control
| Profile | Canonical projection cutoff | SQL dirty-region filter | Coalescer |
|---|---:|---:|---:|
| Metadata only | 576 / 15.927 | 0 / 1.438 | 0 / 1.957 |
| Inverse edits | 576 / 17.050 | 292.5 / 11.168 | 33 / 5.287 |
| Sparse substantive | 576 / 24.517 | 272.5 / 17.336 | 272.5 / 18.054 |
| Dense substantive | 576 / 43.258 | 576 / 49.574 | 576 / 65.776 |

All methods and workloads produced zero stale regional outputs on the first two seed blocks, with identical gzip build counts within each history. The candidate's narrow confirmation speedup is 52.7% on inverse edits; elsewhere it is slower. On dense updates, it spends 17.607ms reading/coalescing/applying the journal, vs 3.578ms for the fixed SQL filter, without reducing projection/gzip counts.


## Additional independent seed block, direct SQL endpoint comparator
Fixed SQL computes first/last journal row per record with GROUP BY and then runs the same contribution and dirty-region predicates in SQLite. On all 24 histories it exactly matches candidate projection and gzip counts per seed and yields zero stale output. Median end-to-end milliseconds for (fixed dirty-region SQL / Python candidate / first-last SQL) are metadata 1.399 / 1.887 / 1.930, inverse edits 10.245 / 4.794 / 4.743, sparse 17.627 / 18.752 / 18.241, dense 46.443 / 60.631 / 56.157. Candidate does not beat direct SQL coalescing by 15% on any profile; the apparent inverse-edit gain is not specific to the proposed implementation.

Limitations: fixture workloads with in-memory SQLite and gzip bytes held in memory; assumes a known fixed additive report, update-only complete journal, numeric non-null fields, and no cross-batch/concurrent writes. No crash/recovery, historical production, bandwidth, persistent transaction, timestamp, or I/O conclusions. Cross-row cancellation is not recognized by the candidate; only a fundamentally different angle than direct SQL coalescing would warrant another exploratory test.

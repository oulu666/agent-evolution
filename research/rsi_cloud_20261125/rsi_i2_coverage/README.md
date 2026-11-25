# I2: coverage-gap triage with two output pixels
**Do not promote.** Standard predictive-entropy probing exactly ties category information gain on actionable escalation and impossible escalations in all six profile-by-budget cells. Coverage gating is still a useful diagnostic, distinct from a scoring improvement.

The observed artifact is a real Pillow RGB operation on controlled 8×8 images. Exact full rendering of each source under every declared operation assigns the oracle label: target in base (selection error only if identity fails), target only in larger menu (recoverable menu gap), or no attainable output under the full declared finite affordance. Each strategy may compute the same source-only candidate outputs; it only receives one or two target pixels. Reference images and labels stay out of query selection/ranking. Each strategy queries 1,440 target pixels total at the two-pixel budget, and each selects 72 of 240 tasks per domain. All 15 primitive renderings per input are shared and not budgeted as target observations; this is not an end-to-end cost reduction claim.

| Domain | Exact base / recoverable gap / impossible | Selection errors if identity is used | Recoverable among 72 escalated: random / random pixels + menu ranking / entropy / candidate | Impossible among entropy and candidate escalations |
|---|---|---:|---|---:|
| Color | 80 / 80 / 80 | 80 | 26 / 62 / 62 / 62 | 10 |
| Symmetric | 108 / 52 / 80 | 58 | 17 / 48 / 52 / 52 | 12 |
| Sparse | 81 / 79 / 80 | 81 | 25 / 42 / 60 / 60 | 12 |

At two probes, entropy and candidate each escalate 174/216 actionable items (80.6% precision) and 34/216 genuinely impossible tasks. Profile-balanced budget's oracle ceiling is 196/216. One probe scores 62/45/60 for both. Many nominal extended transformations on near-grayscale symmetric images collapse to an existing output; exact audit prevents 28 of those tasks inflating the count of genuine menu gaps in that profile. An exact gap does not imply a real teacher can repair it; no teacher was called. Conversely, some out-of-affordance targets coincide with known actions at both observed pixels, so a residual can reject a catalog but finite sampled agreement cannot prove representability.

The frozen protocol's phrase “calibrated ranking” denotes deterministic compatibility tiers, not fitting empirical probabilities. The candidate uses mutual information under a uniform prior over compatible distinct images, not a learned probability. Impossibility is exhaustive only for specified single operations; composition, parametric variants, and arbitrary code are out of scope. No historical releases, business benefit, paid teacher, or model improvement tested.

Replay with Pillow 13.0.0: `python run.py > aggregate.json`; check freeze with `sha256sum -c PROTOCOL.sha256`.

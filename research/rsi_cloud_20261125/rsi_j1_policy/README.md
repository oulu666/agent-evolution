# J1: learned sequential repair on held-out image compositions
**Decision: do not promote.** A trained ExtraTrees policy composes real Pillow operations on entirely unseen 3-factor combinations when source statistics match training, but does not improve on direct factoring and generalizes poorly to unseen artifact families.

## Protocol and mechanisms
The policy emits one primitive at a time from seven square-image orientation transforms, RGB inversion and two cyclic RGB shifts, or stops. A true primitive execution counts against the common three-action cap. The exact target is represented to each policy by the same nine anchor pixels; no policy receives oracle feedback in rollout. Each candidate geometry/hypothesis may read source pixels corresponding to those same anchors; no full-image trial/apply is concealed outside the action cap. Exact mode, dimensions and the entire RGB pixel byte buffer, including pixels not sampled by the policy, determine success after rollout. All single actions occur among the 2,707 supervised labeled states. Training has 800 color artifacts and uses only one-/two-factor corruption combinations; 14 canonical three-factor test combos do not overlap training. The two shifted artifact families were entirely absent from training.

Direct factorization minimizes RGB anchor distance over the finite 8×2×3 geometry/inversion/channel group, applies the first nonidentity component to the live image, and then re-observes. One-step greedy uses only a primitive's individual anchor distance; 1-NN retrieves from the same training feature vectors; the shuffled tree preserves class counts, but its policy collapses to the stop action (a weak null, not a competitive baseline).

## Original 320 tasks per family
| Family | Proposed policy | Direct factorization | Greedy | Retrieval | Shuffled |
|---|---:|---:|---:|---:|---:|
| Random-color | 320 | 320 | 21 | 318 | 0 |
| Sparse color impulses | 15 | 129 | 71 | 2 | 0 |
| Gray horizontal symmetry | 217 | 238 | 167 | 215 | 0 |

Held-out color needs all three operations on every example; candidate and native each executed 960. In sparse impulse, 115 artifacts succeed with native only and one with candidate only; in grayscale symmetry 21 are native-only and none candidate-only. Some images are non-identifiable from nine anchors (e.g. different sparse artifact arrangements that match all sampled anchors), but this protocol does not quantify that ceiling. Action count is reported separately, not treated as efficiency without success.

A fresh composition-balanced set of 20 cases for each of 14 test triples per family reproduced the pattern: candidate/native 280/280 vs 280/280 (color), 16/280 vs 109/280 (impulse), and 200/280 vs 212/280 (gray symmetry). Across all 840 balanced pairs, there were no candidate-only successes against native and 105 native-only successes.

Reproduce with Python, Pillow 13.0.0, scikit-learn 1.8.0 and numpy 2.3.5: `LOKY_MAX_CPU_COUNT=1 python run.py > aggregate.json`; use `--balanced` to repeat the fresh 20-per-composition sensitivity. `PROTOCOL.md` is frozen; `BALANCED.md` documents the 32-vs-33 manifest count typo and balanced extension. This is a closed-label behavioral-cloning pilot: no self-updating policy, model training beyond small ExtraTrees, production images, or tool-family extrapolation.

Compatibility: the preserved primary aggregate predates the explicit JSON `balanced` field. On replay, treat missing as `balanced=false`; all other values must match.

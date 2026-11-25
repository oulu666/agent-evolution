# L1: strict benign numeric historical supplement
**One strict NumPy regression admitted.** Two newer issues were screened and executed before the preregistered backup. Neither newer issue qualified as a strict historical regression in this environment. All fixtures are ordinary numeric arrays and have independent contract-based or algebraic expected outputs.

| Candidate | Prior checked → affected checked → fixed checked | Default correct, /12 per wheel | Public alternative correct, /12 per wheel | Admission |
|---|---|---|---|---|
| [#33155: mixed missing/finite quantile precision](https://github.com/numpy/numpy/pull/33155) | 2.5.3 → 2.5.4 → 2.5.5 | 6 → 6 → 12 | 12 → 12 → 12 | Reproduced old functional defect; no prior-good wheel documented or observed |
| [#33179: large complex square root](https://github.com/numpy/numpy/pull/33179) | 2.5.3 → 2.5.4 → 2.5.5 | 12 → 12 → 12 | 12 → 12 → 12 | No reproduction on tested Linux wheels; report cites fallback implementation, not forced |
| [#31453: Boolean conjugation dtype](https://github.com/numpy/numpy/pull/31453) | 2.4.4 → 2.4.5 → 2.4.6 | 12 → 0 → 12 | 12 → 12 → 12 | Strict prior-good, affected-bad, fixed-good |

### Contract and workaround
- Quantile: Python standard arithmetic computes linear interpolation on each finite slice while yielding NaN for all-missing slices; the independently specified mixed float32 task expects order-invariant float64 results with an array of quantiles. Newer wheel passes; older defaults silently return invalid output type on missing-first fixtures. Explicit float64 input casting solves the measured task. All-missing across every slice and other quantile estimators are out of scope.
- Complex square root: the real and signed imaginary parts of principal root of a pure imaginary number follow ±sqrt(|imaginary part|/2). The baseline normalizes squared scaling then rescales. We do not force a nonstandard build or claim the platform-specific defect did not exist.
- Boolean conjugate: values, shape, bool dtype, and source preservation are checked independently. Identity copy is the public same-information workaround for this read-only value contract. It deliberately does not claim matching upstream output identity, memory aliasing, or allocation cost. All affected errors were wrong outputs, not exceptions.

### Screening and replay
Started at [2.5.5](https://numpy.org/devdocs/release/2.5.5-notes.html), skipped compatibility and build work, float finfo cache startup, and non-math resource/crash/leak entries; selected the first two ordinary numerical candidates. [#32832](https://github.com/numpy/numpy/issues/32832) documents that the quantile issue is also present in 2.4.6, not a previously working case. The [2.5.4–2.5.1](https://numpy.org/devdocs/release.html) notes were skimmed for documented onset; maintenance/typing, new behavior, and unsafe/resource-related cases were excluded. The [2.4.6 notes](https://numpy.org/devdocs/release/2.4.6-notes.html) explicitly identify a 2.4.5 regression and list #31453, the bounded replacement; stopped at three tested issues. SciPy was not screened further. This is a qualification cohort, not representative prevalence or algorithm improvement. Multiple inputs to one issue are not independent historical regressions.

All six official CPython 3.12 Linux wheels installed into distinct local targets. Results contain grouped outcome counts only; no per-fixture vectors are generated.
```bash
d=/tmp/l1-versions
for v in 2.5.3 2.5.4 2.5.5 2.4.4 2.4.5 2.4.6; do
  python -m pip install --no-deps --target "$d/$v" "numpy==$v"
done
python run.py "$d" > aggregate.json
sha256sum -c PROTOCOL.sha256 CASES.sha256
```

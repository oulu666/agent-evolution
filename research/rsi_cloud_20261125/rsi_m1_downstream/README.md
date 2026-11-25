# M1: pre-issue downstream obligation and workaround audit
**Initial bounded search: 0/4 independently eligible. Optional evidence-guided extension: 1 eligible downstream repository.** This is a downstream confirmation and a strong negative case for *novel repair synthesis*, not a measured gain by an RSI method.

## Initial screening corpus
- [NumPy #31452 / #31453](https://github.com/numpy/numpy/issues/31452), Boolean ndarray conjugate: the official issue/PR and targeted exact searches turned up NumPy-only cases and array implementations using different dispatch (e.g. JAX), not a pinned independent same-trigger data path with a dtype-dependent obligation. Exact downstream impact not verified.
- [pandas #71769](https://github.com/pandas-dev/pandas/issues/71769), CSV and LocalPath: the report contains a temporary pytest reproducer and public path/string workaround dated 2026-10-29. Searching historical `tmpdir.join` / `pd.read_csv` calling patterns exposed no verified pinned project meeting the full direct-LocalPath and independent obligation test. A string from `os.path.join` is not that trigger. The upstream report itself is not a preexisting downstream test.
- [pandas #71567](https://github.com/pandas-dev/pandas/issues/71567), datetime series map then write: the report mentions pvlib in an environment path and gives public `transform` on 2026-10-25. Primary project searches did not establish a preissue pvlib call site performing that exact operation and subsequent write; related Pandas/NumPy copy-on-write failures are different triggers.
- [pandas #71743](https://github.com/pandas-dev/pandas/issues/71743), timestamp-arrow conversion mutates source: exact-method searches yielded Pandas internals/tests, separate timezone problems, and public conversion examples without a verified predating readback of the *source* after conversion. No pinned independent production/test outcome, no claim of absence. These four negative results are access/search-bounded.

## Optional extension: exact downstream scope and test
[NumPy #31754](https://github.com/numpy/numpy/issues/31754) and [numpy-quaternion #270](https://github.com/moble/quaternion/issues/270) document that NumPy 2.5.0's ndarray method regressed for legacy registered dtypes, but the ufunc still worked. Their direct examples are upstream witnesses, not the downstream oracle.

In independent project QuatIca, immutable commit [e946411c6a347e6ec1e5be0d2bef95706ac965e0, 2026-02-26](https://github.com/vleplat/QuatIca/commit/e946411c6a347e6ec1e5be0d2bef95706ac965e0) contains production `quatica.optiQ.qadj` calling ndarray method conjugation, and `inner_real` transitively invoking it. [Existing ADMM test](https://github.com/vleplat/QuatIca/blob/e946411c6a347e6ec1e5be0d2bef95706ac965e0/tests/unit/test_optiQ_admm.py#L59-L73) defines an independent application obligation: the canonical quaternion basis Gram matrix must be identity for the original n=3/seed=0 and n=5/seed=1 test inputs. Our harness exercises the actual pinned production functions and basis constructor and asserts this same identity/tolerance. It does **not** run or claim the full ADMM convergence suite. Three simple rectangular adjoint inputs additionally check sign/transposition by independent arithmetic and preserve source arrays.

| NumPy | Unchanged adjoint | Unchanged canonical Gram | Native existing helper, combined |
|---|---:|---:|---:|
| 2.4.6 before | 3/3 | 2/2 | 5/5 |
| 2.5.0 affected | 0/3 | 0/2 | 5/5 |
| 2.5.2 fixed | 3/3 | 2/2 | 5/5 |

The native substitution swaps only the public conjugation operation on the affected caller. A separate direct ufunc wrapper produced identical outcomes. Public workaround evidence does **not** begin when the bug was reported June 25, 2026: the same February commit already provided [`quat_hermitian`](https://github.com/vleplat/QuatIca/blob/e946411c6a347e6ec1e5be0d2bef95706ac965e0/quatica/utils.py#L88-L113), which uses ufunc conjugation on the same dense matrices. That code is earlier known *availability*, not a report that a specific downstream maintainer applied it at that time. Jun 25 is dated public evidence of applicability to the exact regression; the [NumPy 2.5.2 release notes](https://numpy.org/devdocs/release/2.5.2-notes.html) document the released restoration. Scope is this case, not causal or statistical generalization.

## Replay
Requires Python 3.12 plus QuatIca's import dependencies (SciPy, matplotlib, numba); observed with SciPy 1.17.0. Run original archive from a temporary directory, not from a mutable checkout.
```bash
d=/tmp/m1
mkdir -p "$d/qipre"
rev=e946411c6a347e6ec1e5be0d2bef95706ac965e0
curl -fsSL "https://codeload.github.com/vleplat/QuatIca/tar.gz/$rev" -o "$d/repo.tar.gz"
tar -xf "$d/repo.tar.gz" -C "$d/qipre" --strip-components=1
for v in 2.4.6 2.5.0 2.5.2; do
  python -m pip install --no-deps --target "$d/numpy-$v" "numpy==$v"
done
python -m pip install --no-deps --target "$d/quaternion" numpy-quaternion==2024.0.12
python run.py "$d" "$d/qipre" "$d/numpy-2.4.6" > aggregate.json
sha256sum -c PROTOCOL.sha256 EXTENSION.sha256
```

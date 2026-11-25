# K1: bounded historical functional admission
Results from actual isolated public wheels, with independent Python/date, CSV round-trip, and membership oracles. On four independently documented issues from two libraries, old ordinary behavior passed 7/24 fixture variations; old native wrappers and new ordinary API passed all 24/24. There are **three strict regressions, all from pandas**, and one historical defect from packaging; the goal of strict regressions across two libraries did not pass. Fixture variants are not independent historical issues. This is a qualification cohort, not algorithm validation or a prevalence estimate.

| Primary record | Wheel transition | Old default | Old native workaround | New default |
|---|---|---:|---:|---:|
| [pandas #71743](https://github.com/pandas-dev/pandas/issues/71743), datetime source must keep missing values | 3.1.0→3.1.1 | 2/6 | 6/6, deep-copy before converting | 6/6 |
| [pandas #71567](https://github.com/pandas-dev/pandas/issues/71567), map then assign an actual changed timestamp | 3.1.0→3.1.1 | 0/6 | 6/6, public transform for this scalar operation | 6/6 |
| [pandas #71769](https://github.com/pandas-dev/pandas/issues/71769), path object with read/write convenience methods | 3.1.0→3.1.1 | 2/6 | 6/6, os.fspath before CSV API | 6/6 |
| [packaging #1511](https://github.com/pypa/packaging/pull/1511), range union preserves explicitly listed prerelease | 26.3→26.4 | 3/6 | 6/6, union outputs of two public filters on this finite list | 6/6 |

On #71743 the oracle reads both converted and original records; old failures are wrong state, not exceptions, and both no-null controls pass. On #71567 it checks the edited series and unchanged original. On #71769 it checks the exact complete CSV and parsed rows; a local structural PathLike reproduces the publicly documented class of behavior, not a claim of running the exact original py.path.local sample. Installing the optional legacy py package timed out; the structural path uses only a temp local file. On #1511 companions distinguish a named prerelease inside/outside the interval and a distinct spelling; the wrapper is for this finite-list task, not an implementation of general VersionRange union. No extra permissions were used; extra copies/calls are not equal computational cost.

## Screening and bounded stop
- [pandas 3.1.1 release notes](https://pandas.pydata.org/docs/whatsnew/v3.1.1.html): first three entries under “Fixed regressions” qualified, in order. Later entries and second release pair not executed once three strict same-library items had been gathered; #63920 was excluded a priori.
- [packaging changelog](https://packaging.pypa.io/en/stable/changelog.html): skip Python support drop/new APIs, formatting-only marker presentation, object storage change, and a new-method unknown-argument validation. Skip #1485 (old documentation required parsed specifiers, so raw-string list support is a widened input contract); skip #1430/#1384 (malformed input validation). #1511 is the first applied companion. It is not a previously working release regression because public VersionRange itself entered in 26.3. Other changelog fixes and older pair were not executed under this timebox.
- [attrs changelog](https://www.attrs.org/en/stable/changelog.html): existing workspace already studied #1427; excluded. Newest notes include explicitly labeled breaking alias resolution, typing, new accepted inputs, and validator context nesting; no additional strict candidate was established here. [lxml 6.1 notes](https://lxml.de/6.1/changes-6.1.1.html): newest fix entries are security-linked, excluded; older pairs unscreened at stop. Neither library was executed. This release search is not exhaustive.

## Replay
On CPython 3.12 use NumPy 2.3.5 and standard pandas runtime dependencies. Install each version in a separate target directory; the exact versions are verified in every subprocess.
```bash
d=/tmp/k1-versions
for spec in pandas:3.1.0 pandas:3.1.1 packaging:26.3 packaging:26.4 pyarrow:22.0.0; do
  name=${spec%:*}; version=${spec#*:}
  python -m pip install --no-deps --target "$d/$name-$version" "$name==$version"
done
python -B run.py "$d" | python -B summarize.py | diff -u summary.json -
sha256sum -c LOCK.sha256 PROTOCOL.sha256 CASES.sha256
```

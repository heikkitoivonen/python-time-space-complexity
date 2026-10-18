# Skill recall: haiku

- Model claude-haiku-5-5
- Started 2026-10-17T23:09:11+00:00; Claude Code 2.1.302; judge sonnet
- Skill 0.4.0 at 968d9fff4ec4d1ad812850409957efdc301fc4ea-dirty, files digest 58dd1238699f
- 100 items, 3 runs per arm, questions asked about CPython 3.14
- Cost $31.97; 0 runs ended in an error
- Not compared (no key, or no graded run in one arm): none
- Key changed since the run, so only exact matches count: sorted-with-key, sum-of-lists

A bound passes when it matches the key exactly, as one of the spellings items.yaml accepts, or by the judge's ruling on any other spelling; `both` counts a run only when its time and space bounds both pass. Each arm's score is the mean over items of the fraction of runs that pass. Δ is the mean per-item difference, with a bootstrap 95% interval that resamples items. McNemar's test compares items, each counted as passing in an arm when most of its runs there pass.

## Summary

| Stratum | Items | Bound | Without skill | With skill | Δ | 95% CI | McNemar p |
|---|---|---|---|---|---|---|---|
| common | 61 | time | 95% | 99% | +4% | +0% to +10% | 0.250 |
| common | 61 | space | 97% | 99% | +2% | +0% to +5% | 1.000 |
| common | 61 | both | 93% | 98% | +5% | +1% to +11% | 0.250 |
| tail | 39 | time | 92% | 98% | +6% | +0% to +14% | 0.500 |
| tail | 39 | space | 92% | 100% | +8% | +1% to +16% | 0.250 |
| tail | 39 | both | 90% | 98% | +9% | +2% to +17% | 0.250 |
| all | 100 | time | 94% | 99% | +5% | +1% to +10% | 0.062 |
| all | 100 | space | 95% | 99% | +4% | +1% to +8% | 0.125 |
| all | 100 | both | 92% | 98% | +7% | +3% to +11% | 0.031 |

The skill fired in 300 of 300 with-skill runs. Mean cost per run: $0.051 without, $0.056 with.

## Items

| Item | Stratum | Key time | Key space | Without: time | Without: space | With: time | With: space |
|---|---|---|---|---|---|---|---|
| `any-all-falsy` | common | O(n) | O(1) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) |
| `bisect-insort-list` | tail | O(n) | O(1) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) |
| `bool-of-list` | common | O(1) | O(1) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) |
| `bytes-decode` | common | O(n) | O(n) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) |
| `bytesio-from-bytes` | common | O(1) | O(1) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) |
| `chainmap-getitem` | tail | O(i) | O(1) | ✓ O(i)<br>✓ O(i)<br>✓ O(i) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) | ✓ O(i)<br>✓ O(i)<br>✓ O(i) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) |
| `chainmap-len` | tail | O(n + N) | O(n + N) | ✓ O(n + N)<br>✓ O(n + N)<br>✓ O(n + N) | ✓ O(n + N)<br>✓ O(n + N)<br>✓ O(n + N) | ✓ O(n + N)<br>✓ O(n + N)<br>✓ O(n + N) | ✓ O(n + N)<br>✓ O(n + N)<br>✓ O(n + N) |
| `chainmap-to-dict` | tail | O(n + N·n) | O(N) | ✓ O(n·N)<br>✓ O(N·n)<br>✓ O(n·N) | ✓ O(N)<br>✓ O(N)<br>✓ O(N) | ✓ O(n + N·n)<br>✓ O(n + N·n)<br>✓ O(n + nN) | ✓ O(N)<br>✓ O(N)<br>✓ O(N) |
| `copy-copy-list` | common | O(n) | O(n) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) |
| `copy-copy-tuple` | tail | O(1) | O(1) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) |
| `counter-from-list` | tail | O(t) | O(u) | ✓ O(t)<br>✓ O(t)<br>✓ O(t) | ✓ O(u)<br>✓ O(u)<br>✓ O(u) | ✓ O(t)<br>✓ O(t)<br>✓ O(t) | ✓ O(u)<br>✓ O(u)<br>✓ O(u) |
| `counter-most-common-k` | tail | O(n log k) | O(k) | ✓ O(n log k)<br>✓ O(n log k)<br>✓ O(n log k) | ✓ O(k)<br>✓ O(k)<br>✓ O(k) | ✓ O(n log k)<br>✓ O(n log k)<br>✓ O(n log k) | ✓ O(k)<br>✓ O(k)<br>✓ O(k) |
| `decimal-from-int` | tail | O(n²) | O(n) | ✓ O(n^2)<br>✓ O(n^2)<br>✓ O(n^2) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) | ✓ O(n^2)<br>✓ O(n²)<br>✓ O(n^2) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) |
| `decimal-from-str` | tail | O(n) | O(n) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) |
| `deepcopy` | common | O(v + e) | O(v + e) | ✓ O(v + e)<br>✓ O(v + e)<br>✓ O(v + e) | ✓ O(v + e)<br>✓ O(v + e)<br>✓ O(v + e) | ✓ O(v + e)<br>✓ O(v + e)<br>✗ O(3^(e/3)) | ✓ O(v + e)<br>✓ O(v + e)<br>✓ O(v + e) |
| `defaultdict-missing-key` | common | O(1) | O(1) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) |
| `deque-index` | tail | O(n) | O(1) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) |
| `deque-popleft` | common | O(1) | O(1) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) |
| `deque-rotate` | tail | O(min(s, n - s)) | O(1) | ✗ O(n)<br>✗ O(n)<br>✗ O(n) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) | ✓ O(min(s, n - s))<br>✗ O(n)<br>✗ O(n) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) |
| `dict-copy` | common | O(n) | O(n) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) |
| `dict-from-pairs` | common | O(n) | O(n) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) |
| `dict-get` | common | O(1) | O(1) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) |
| `dict-items-view` | common | O(1) | O(1) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) |
| `dict-merge-operator` | tail | O(n + m) | O(n + m) | ✓ O(n + m)<br>✓ O(n + m)<br>✓ O(n + m) | ✓ O(n + m)<br>✓ O(n + m)<br>✓ O(n + m) | ✓ O(n + m)<br>✓ O(n + m)<br>✓ O(n + m) | ✓ O(n + m)<br>✓ O(n + m)<br>✓ O(n + m) |
| `dict-setdefault` | common | O(1) | O(1) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) |
| `dict-update` | common | O(m) | O(m) | ✓ O(m)<br>✓ O(m)<br>✓ O(m) | ✗ O(n + m)<br>✗ O(n + m)<br>✓ O(m) | ✓ O(m)<br>✓ O(m)<br>✓ O(m) | ✗ O(n + m)<br>✗ O(n + m)<br>✓ O(m) |
| `dict-values-membership` | tail | O(n) | O(1) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) |
| `enumerate-create` | common | O(1) | O(1) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) |
| `getattr-literal-name` | common | O(1) | O(1) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) |
| `getattr-runtime-name` | tail | O(d) | O(1) | ✓ O(d)<br>✓ O(d)<br>✓ O(d) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) | ✓ O(d)<br>✓ O(d)<br>✓ O(d) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) |
| `heapq-heapify` | tail | O(n) | O(1) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) |
| `heapq-merge-consume` | tail | O(r + m log r) | O(r) | ✓ O(m log r)<br>✓ O(m log r)<br>✓ O(m log r) | ✓ O(r)<br>✓ O(r)<br>✓ O(r) | ✓ O(m log r)<br>✓ O(r + m log r)<br>✓ O(m log r) | ✓ O(r)<br>✓ O(r)<br>✓ O(r) |
| `heapq-nlargest` | tail | O(m log k) | O(k) | ✓ O(m log k)<br>✓ O(m log k)<br>✓ O(m log k) | ✓ O(k)<br>✓ O(k)<br>✓ O(k) | ✓ O(m log k)<br>✓ O(m log k)<br>✓ O(m log k) | ✓ O(k)<br>✓ O(k)<br>✓ O(k) |
| `isinstance-plain-class` | common | O(d) | O(1) | ✓ O(d)<br>✓ O(d)<br>✓ O(d) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) | ✓ O(d)<br>✓ O(d)<br>✓ O(d) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) |
| `isinstance-tuple` | tail | O(k·d) | O(1) | ✓ O(k·d)<br>✓ O(k·d)<br>✓ O(k·d) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) | ✓ O(k·d)<br>✓ O(k*d)<br>✓ O(k·d) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) |
| `iter-list` | common | O(1) | O(1) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) |
| `json-loads` | common | O(n) | O(n) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) |
| `len-list` | common | O(1) | O(1) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) |
| `list-append` | common | O(1) | O(1) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) |
| `list-clear` | common | O(n) | O(1) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) |
| `list-count` | common | O(n) | O(1) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) |
| `list-del-slice` | tail | O(n - i) | O(j - i) | ✗ O(n)<br>✗ O(n)<br>✗ O(n) | ✗ O(n)<br>✗ O(n)<br>✗ O(n) | ✓ O(n-i)<br>✓ O(n-i)<br>✓ O(n-i) | ✓ O(j-i)<br>✓ O(j-i)<br>✓ O(j-i) |
| `list-eq-different-lengths` | tail | O(1) | O(1) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) |
| `list-extend` | common | O(k) | O(k) | ✓ O(k)<br>✓ O(k)<br>✓ O(k) | ✓ O(k)<br>✗ O(n+k)<br>✓ O(k) | ✓ O(k)<br>✓ O(k)<br>✓ O(k) | ✓ O(k)<br>✓ O(k)<br>✓ O(k) |
| `list-from-iterator` | common | O(n) | O(n) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) |
| `list-index` | common | O(1) | O(1) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) |
| `list-insert-front` | common | O(n) | O(1) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) |
| `list-membership` | common | O(n) | O(1) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) |
| `list-pop-front` | common | O(n) | O(1) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) | ✓ O(1)<br>✓ O(1)<br>✗ O(n) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) |
| `list-remove` | common | O(n) | O(1) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) |
| `list-reverse` | common | O(n) | O(1) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) |
| `list-slice` | common | O(j - i) | O(j - i) | ✗ O(n)<br>✓ O(j - i)<br>✗ O(n) | ✗ O(n)<br>✓ O(j - i)<br>✗ O(n) | ✓ O(j-i)<br>✓ O(j - i)<br>✓ O(j - i) | ✓ O(j-i)<br>✓ O(j - i)<br>✓ O(j - i) |
| `list-slice-assign` | tail | O(n - i + k) | O(j - i + k) | ✗ O(n + k)<br>✗ O(n+k)<br>✗ O(n + k) | ✗ O(n + k)<br>✗ O(n+k)<br>✗ O(n + k) | ✓ O(n - i + k)<br>✓ O(n-i+k)<br>✓ O(n - i + k) | ✓ O(j - i + k)<br>✓ O(j-i+k)<br>✓ O(j - i + k) |
| `list-sort` | common | O(n log n) | O(n) | ✓ O(n log n)<br>✓ O(n log n)<br>✓ O(n log n) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) | ✓ O(n log n)<br>✓ O(n log n)<br>✓ O(n log n) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) |
| `lru-cache-hit` | common | O(a + m) | O(a + m) | ✓ O(a + m)<br>✓ O(a + m)<br>✓ O(a + m) | ✓ O(a + m)<br>✓ O(a + m)<br>✓ O(a + m) | ✓ O(a + m)<br>✓ O(a + m)<br>✓ O(a + m) | ✓ O(a + m)<br>✓ O(a + m)<br>✓ O(a + m) |
| `map-create` | common | O(1) | O(1) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) |
| `max-list` | common | O(n) | O(1) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) |
| `max-with-key` | tail | O(n·k) | O(1) | ✓ O(nk)<br>✓ O(n·k)<br>✓ O(n·k) | ✗ O(k)<br>✓ O(1)<br>✗ O(k) | ✓ O(nk)<br>✓ O(n·k)<br>✓ O(n·k) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) |
| `namedtuple-class` | common | O(f) | O(f) | ✓ O(f)<br>✓ O(f)<br>✓ O(f) | ✓ O(f)<br>✓ O(f)<br>✓ O(f) | ✓ O(f)<br>✓ O(f)<br>✓ O(f) | ✓ O(f)<br>✓ O(f)<br>✓ O(f) |
| `ordereddict-move-to-end` | tail | O(1) | O(1) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) |
| `os-environ-get` | common | O(k + v) | O(k + v) | ✓ O(k + v)<br>✓ O(k + v)<br>✓ O(k + v) | ✓ O(k + v)<br>✓ O(k + v)<br>✓ O(k + v) | ✓ O(k + v)<br>✓ O(k + v)<br>✓ O(k + v) | ✓ O(k + v)<br>✓ O(k + v)<br>✓ O(k + v) |
| `os-path-join` | common | O(n + L) | O(L) | ✗ O(n·L)<br>✗ O(n·L)<br>✗ O(n·L) | ✓ O(L)<br>✓ O(L)<br>✓ O(L) | ✓ O(L)<br>✓ O(n + L)<br>✓ O(L) | ✓ O(L)<br>✓ O(L)<br>✓ O(L) |
| `product-create` | tail | O(p + q) | O(p + q) | ✓ O(p + q)<br>✓ O(p + q)<br>✓ O(p + q) | ✓ O(p + q)<br>✓ O(p + q)<br>✓ O(p + q) | ✓ O(p + q)<br>✓ O(p + q)<br>✓ O(p + q) | ✓ O(p + q)<br>✓ O(p + q)<br>✓ O(p + q) |
| `random-sample` | tail | O(k) | O(k) | ✓ O(k)<br>✓ O(k)<br>✓ O(k) | ✓ O(k)<br>✓ O(k)<br>✓ O(k) | ✓ O(k)<br>✓ O(k)<br>✓ O(k) | ✓ O(k)<br>✓ O(k)<br>✓ O(k) |
| `range-contains-float` | tail | O(n) | O(1) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) |
| `range-contains-int` | tail | O(1) | O(1) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) |
| `range-create` | common | O(1) | O(1) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) |
| `re-compile` | common | O(n) | O(n) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) |
| `reduce-concat-str` | tail | O(n²) | O(n) | ✓ O(n^2)<br>✓ O(n^2)<br>✓ O(n^2) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) | ✓ O(n²)<br>✓ O(n²)<br>✓ O(n^2) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) |
| `reversed-list` | common | O(1) | O(1) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) |
| `sequencematcher-create` | tail | O(B) | O(B) | ✓ O(B)<br>✓ O(B)<br>✓ O(B) | ✓ O(B)<br>✓ O(B)<br>✓ O(B) | ✓ O(B)<br>✓ O(B)<br>✓ O(B) | ✓ O(B)<br>✓ O(B)<br>✓ O(B) |
| `set-add` | common | O(1) | O(1) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) |
| `set-difference` | tail | O(n) | O(n) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) |
| `set-discard` | common | O(1) | O(1) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) |
| `set-from-list` | common | O(n) | O(n) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) |
| `set-intersection` | tail | O(min(n, m)) | O(min(n, m)) | ✓ O(min(n, m))<br>✓ O(min(n, m))<br>✓ O(min(n, m)) | ✓ O(min(n, m))<br>✓ O(min(n, m))<br>✓ O(min(n, m)) | ✓ O(min(n,m))<br>✓ O(min(n,m))<br>✓ O(min(n,m)) | ✓ O(min(n,m))<br>✓ O(min(n,m))<br>✓ O(min(n,m)) |
| `setattr-literal-name` | common | O(1) | O(1) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) |
| `sorted-list` | common | O(n log n) | O(n) | ✓ O(n log n)<br>✓ O(n log n)<br>✓ O(n log n) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) | ✓ O(n log n)<br>✓ O(n log n)<br>✓ O(n log n) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) |
| `sorted-presorted` | tail | O(n) | O(n) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) |
| `sorted-with-key` | tail | O(n log n + n·k) | O(n) | ✓ O(n·k + n log n)<br>✓ O(n(k + log n))<br>✓ O(n(k + log n)) | ✗ O(n + k)<br>✓ O(n)<br>✓ O(n) | ✓ O(n(log n + k))<br>✓ O(n(k + log n))<br>✓ O(n log n + nk) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) |
| `statistics-median` | tail | O(n log n) | O(n) | ✓ O(n log n)<br>✓ O(n log n)<br>✓ O(n log n) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) | ✓ O(n log n)<br>✓ O(n log n)<br>✓ O(n log n) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) |
| `statistics-mode` | tail | O(n) | O(u) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) | ✓ O(u)<br>✓ O(u)<br>✓ O(u) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) | ✓ O(u)<br>✓ O(u)<br>✓ O(u) |
| `str-contains` | common | O(n) | O(1) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) |
| `str-encode` | common | O(n) | O(n) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) |
| `str-find` | common | O(n) | O(1) | ✗ O(n*m)<br>✗ O(n·m)<br>✗ O(n·m) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) |
| `str-hash-first-call` | tail | O(n) | O(1) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) |
| `str-join` | common | O(r) | O(r) | ✓ O(r)<br>✓ O(p + r)<br>✓ O(p + r) | ✓ O(r)<br>✓ O(r)<br>✓ O(r) | ✓ O(r)<br>✓ O(r)<br>✓ O(r) | ✓ O(r)<br>✓ O(r)<br>✓ O(r) |
| `str-lower` | common | O(n) | O(n) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) |
| `str-of-str` | common | O(1) | O(1) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) |
| `str-partition` | common | O(n) | O(n) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) |
| `str-replace` | common | O(n + r) | O(r) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) | ✓ O(r)<br>✓ O(r)<br>✓ O(r) | ✓ O(n + r)<br>✓ O(n + r)<br>✓ O(n + r) | ✓ O(r)<br>✓ O(r)<br>✓ O(r) |
| `str-rfind` | tail | O(n·m) | O(1) | ✓ O(n·m)<br>✓ O(n·m)<br>✓ O(n*m) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) | ✓ O(n·m)<br>✓ O(n·m)<br>✓ O(n·m) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) |
| `str-rsplit` | common | O(n·m) | O(n) | ✓ O(n*m)<br>✗ O(n)<br>✓ O(n*m) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) | ✓ O(n·m)<br>✓ O(n·m)<br>✓ O(n·m) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) |
| `str-split` | common | O(n) | O(n) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) |
| `str-startswith` | common | O(m) | O(1) | ✓ O(m)<br>✓ O(m)<br>✓ O(m) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) | ✓ O(m)<br>✓ O(m)<br>✓ O(m) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) |
| `sum-of-lists` | tail | O(n·N) | O(N) | ✓ O(n·N)<br>✓ O(n(N+1))<br>✓ O(n·N) | ✓ O(N)<br>✓ O(N)<br>✓ O(N) | ✓ O(n·(N+1))<br>✓ O(n·N)<br>✓ O(n·N) | ✓ O(N+1)<br>✓ O(N)<br>✓ O(N) |
| `sum-small-ints` | common | O(n) | O(1) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) |
| `tee-leading-iterator` | tail | O(k) | O(k) | ✓ O(k)<br>✓ O(k)<br>✓ O(k) | ✓ O(k)<br>✓ O(k)<br>✓ O(k) | ✓ O(k)<br>✓ O(k)<br>✓ O(k) | ✓ O(k)<br>✓ O(k)<br>✓ O(k) |
| `tuple-from-list` | common | O(n) | O(n) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) | ✓ O(n)<br>✓ O(n)<br>✓ O(n) |
| `type-of-object` | common | O(1) | O(1) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) | ✓ O(1)<br>✓ O(1)<br>✓ O(1) |

## Worse with the skill

- `deepcopy` time: 100% without, 67% with

## Judge rulings to review

Bounds the judge accepted although they are not a listed spelling of the key, and exact matches the judge rejected (scored as passes).

- `dict-copy` without run 0 time: O(n) - judge fail, key O(n)
- `dict-items-view` without run 2 time: O(1) - judge fail, key O(1)
- `json-loads` with run 2 time: O(n) - judge fail, key O(n)
- `len-list` without run 2 time: O(1) - judge fail, key O(1)
- `lru-cache-hit` without run 1 time: O(a + m) - judge fail, key O(a + m)
- `str-lower` without run 0 time: O(n) - judge fail, key O(n)
- `str-partition` without run 2 time: O(n) - judge fail, key O(n)
- `type-of-object` without run 0 time: O(1) - judge fail, key O(1)

# Eval run run-20261125-0339

## Tasks

| model | category | pass | median TTFT (s) | median gen tok/s | median reasoning tok |
|---|---|---|---|---|---|
| qwen27b | code | 2/3 | 0.3 | 47.6 | - |
| qwen27b | domain | 0/1 | 0.3 | 47.1 | - |
| qwen27b | instruction | 1/1 | 0.3 | 47.5 | - |
| qwen27b | reasoning | 2/2 | 0.3 | 47.6 | - |
| qwen27b | **all** | 5/7 | 0.3 | 47.5 | - |
| inkling | code | 3/3 | 0.2 | 66.1 | - |
| inkling | domain | 1/1 | 0.2 | 65.4 | - |
| inkling | instruction | 1/1 | 0.2 | 66.2 | - |
| inkling | reasoning | 2/2 | 0.2 | 66.3 | - |
| inkling | **all** | 7/7 | 0.2 | 66.2 | - |
| flash | code | 3/3 | 1.8 | 44.9 | 137 |
| flash | domain | 1/1 | 1.8 | 67.9 | 712 |
| flash | instruction | 1/1 | 2.5 | 39.8 | 78 |
| flash | reasoning | 2/2 | 2.0 | 46.8 | 159 |
| flash | **all** | 7/7 | 1.8 | 44.9 | 137 |

## Long-context recall (needle in a haystack)

Cell = pass/fail and time to first token.

### qwen27b

| length | 10% | 50% | 90% | prefill tok/s |
|---|---|---|---|---|
| 8K | ✅ 2.7s | ✅ 2.7s | ✅ 2.8s | 3047 |
| 32K | ✅ 11.1s | ✅ 11.3s | ✅ 11.3s | 2893 |
| 64K | ✅ 25.2s | ✅ 25.4s | ✅ 25.4s | 2563 |
| 128K | ✅ 62.6s | ✅ 63.1s | ✅ 63.1s | 2045 |
| 190K | ✅ 111.3s | ✅ 111.7s | ✅ 111.7s | 1707 |

### inkling

| length | 10% | 50% | 90% | prefill tok/s |
|---|---|---|---|---|
| 8K | ✅ 7.3s | ✅ 7.2s | ✅ 7.3s | 1133 |
| 32K | ✅ 38.5s | ✅ 38.8s | ✅ 38.7s | 839 |
| 64K | ✅ 103.9s | ✅ 104.0s | ✅ 104.1s | 623 |
| 128K | ✅ 312.5s | ✅ 313.3s | ❌ 312.9s | 412 |
| 190K | ✅ 622.7s | ✅ 622.3s | ✅ 623.1s | 307 |

### flash

| length | 10% | 50% | 90% | prefill tok/s |
|---|---|---|---|---|
| 8K | ✅ 11.6s | ✅ 10.6s | ✅ 10.0s | 757 |
| 32K | ✅ 23.9s | ✅ 18.1s | ✅ 18.7s | 1700 |
| 64K | ✅ 34.0s | ✅ 39.0s | ✅ 40.1s | 1631 |
| 128K | ✅ 68.7s | ✅ 73.3s | ✅ 73.4s | 1729 |
| 190K | ✅ 107.3s | ✅ 109.6s | ✅ 121.1s | 1714 |

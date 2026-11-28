# Eval run run-20261127-2238

## Tasks

Pass counts are over every sample (tasks × repeats); truncated = hit
the token budget (`finish_reason=length`).

| model | category | pass | truncated | median TTFT (s) | median gen tok/s | median reasoning tok |
|---|---|---|---|---|---|---|
| inkling | code | 16/21 | 4 | 0.3 | 65.3 | - |
| inkling | domain | 12/15 | 3 | 0.2 | 65.5 | - |
| inkling | instruction | 9/9 | 0 | 0.2 | 66.1 | - |
| inkling | reasoning | 18/18 | 0 | 0.2 | 66.0 | - |
| inkling | **all** | 55/63 | 7 | 0.2 | 65.9 | - |
| inkling-iq3s | code | 17/21 | 4 | 0.3 | 71.4 | - |
| inkling-iq3s | domain | 11/15 | 4 | 0.2 | 71.5 | - |
| inkling-iq3s | instruction | 9/9 | 0 | 0.2 | 72.3 | - |
| inkling-iq3s | reasoning | 18/18 | 0 | 0.2 | 72.2 | - |
| inkling-iq3s | **all** | 55/63 | 8 | 0.2 | 72.0 | - |

### Per task

Cell = passes / samples, `Lk` = k samples truncated.

| task | category | inkling | inkling-iq3s |
|---|---|---|---|
| code-merge-intervals | code | 3/3 | 3/3 |
| code-balanced-brackets | code | 3/3 | 3/3 |
| code-lru-cache | code | 3/3 | 3/3 |
| math-arith | reasoning | 3/3 | 3/3 |
| logic-widgets | reasoning | 3/3 | 3/3 |
| nuclear-decay | domain | 3/3 | 2/3 L1 |
| follow-format | instruction | 3/3 | 3/3 |
| code-expr-eval | code | 0/3 L2 | 0/3 L3 |
| code-lcs-diff | code | 3/3 | 3/3 |
| code-fix-csv | code | 2/3 L1 | 3/3 |
| code-calendar-ii | code | 2/3 L1 | 2/3 L1 |
| reasoning-inclusion | reasoning | 3/3 | 3/3 |
| reasoning-dice-race | reasoning | 3/3 | 3/3 |
| reasoning-seating | reasoning | 3/3 | 3/3 |
| reasoning-dates | reasoning | 3/3 | 3/3 |
| finance-mortgage-payment | domain | 3/3 | 3/3 |
| finance-remaining-balance | domain | 0/3 L3 | 0/3 L3 |
| health-steady-state | domain | 3/3 | 3/3 |
| health-creatinine-clearance | domain | 3/3 | 3/3 |
| instruction-json | instruction | 3/3 | 3/3 |
| instruction-word-counts | instruction | 3/3 | 3/3 |

## Long-context aggregation

Sum one vendor's 8 invoices scattered through a haystack that also
holds 16 invoices from 3 other vendors. Cell = exact totals / samples,
median TTFT.

| length | inkling | inkling-iq3s |
|---|---|---|
| 32K | 1/3, 40.0s | 0/3, 40.5s |
| 128K | 0/3, 315.9s | 0/3, 318.3s |

## Long-context recall (needle in a haystack)

Cell = pass/fail and time to first token.

### inkling

| length | 10% | 50% | 90% | prefill tok/s |
|---|---|---|---|---|
| 8K | ✅ 7.4s | ✅ 7.4s | ✅ 7.3s | 1133 |
| 32K | ✅ 38.5s | ✅ 38.8s | ✅ 38.9s | 839 |
| 64K | ✅ 104.0s | ✅ 103.9s | ✅ 104.2s | 623 |
| 128K | ✅ 312.6s | ✅ 313.0s | ✅ 313.1s | 412 |
| 190K | ✅ 622.8s | ✅ 622.5s | ✅ 623.0s | 307 |

### inkling-iq3s

| length | 10% | 50% | 90% | prefill tok/s |
|---|---|---|---|---|
| 8K | ✅ 7.5s | ✅ 7.5s | ✅ 7.4s | 1110 |
| 32K | ✅ 39.0s | ✅ 39.3s | ✅ 39.4s | 828 |
| 64K | ✅ 105.1s | ✅ 105.0s | ✅ 105.3s | 616 |
| 128K | ✅ 314.9s | ✅ 315.6s | ✅ 315.5s | 409 |
| 190K | ✅ 626.3s | ✅ 626.1s | ✅ 626.9s | 306 |

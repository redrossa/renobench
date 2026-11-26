# Eval run run-20261126-0621

## Tasks

Pass counts are over every sample (tasks × repeats); truncated = hit
the token budget (`finish_reason=length`).

| model | category | pass | truncated | median TTFT (s) | median gen tok/s | median reasoning tok |
|---|---|---|---|---|---|---|
| flash-iq3s | code | 19/21 | 0 | 3.9 | 44.7 | 12305 |
| flash-iq3s | domain | 12/15 | 0 | 5.4 | 62.3 | 2363 |
| flash-iq3s | instruction | 9/9 | 0 | 4.6 | 36.7 | 253 |
| flash-iq3s | reasoning | 18/18 | 0 | 6.9 | 41.5 | 472 |
| flash-iq3s | **all** | 58/63 | 0 | 4.8 | 44.7 | 636 |

### Per task

Cell = passes / samples, `Lk` = k samples truncated.

| task | category | flash-iq3s |
|---|---|---|
| code-merge-intervals | code | 3/3 |
| code-balanced-brackets | code | 3/3 |
| code-lru-cache | code | 3/3 |
| math-arith | reasoning | 3/3 |
| logic-widgets | reasoning | 3/3 |
| nuclear-decay | domain | 3/3 |
| follow-format | instruction | 3/3 |
| code-expr-eval | code | 2/3 |
| code-lcs-diff | code | 3/3 |
| code-fix-csv | code | 3/3 |
| code-calendar-ii | code | 2/3 |
| reasoning-inclusion | reasoning | 3/3 |
| reasoning-dice-race | reasoning | 3/3 |
| reasoning-seating | reasoning | 3/3 |
| reasoning-dates | reasoning | 3/3 |
| finance-mortgage-payment | domain | 3/3 |
| finance-remaining-balance | domain | 0/3 |
| health-steady-state | domain | 3/3 |
| health-creatinine-clearance | domain | 3/3 |
| instruction-json | instruction | 3/3 |
| instruction-word-counts | instruction | 3/3 |

## Long-context aggregation

Sum one vendor's 8 invoices scattered through a haystack that also
holds 16 invoices from 3 other vendors. Cell = exact totals / samples,
median TTFT.

| length | flash-iq3s |
|---|---|
| 32K | 3/3, 31.9s |
| 128K | 3/3, 93.6s |

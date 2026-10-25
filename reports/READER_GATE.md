# The five readers, scored against the hand-read check set

Gate: a reader runs on all 450 RHPs only at **precision >= 95.0%** on the values it produces. Precision is measured on what it said, not on what it withheld: silence is useless, a confident wrong value is corrupting.

## Per field

| field | truth rows | produced | withheld | correct | precision | right line | recall | gate |
|---|---|---|---|---|---|---|---|---|
| `depreciation_amortisation` | 2 | 1 | 1 | 0 | **0.0%** | 0.0% | 0.0% | **FAIL** |
| `finance_costs` | 3 | 1 | 2 | 0 | **0.0%** | 0.0% | 0.0% | **FAIL** |
| `net_worth` | 3 | 1 | 2 | 1 | **100.0%** | 100.0% | 33.3% | PASS |
| `shares_outstanding_pre_issue` | 4 | 3 | 1 | 3 | **100.0%** | 100.0% | 75.0% | PASS |
| `tax_expense` | 2 | 0 | 2 | 0 | **nan%** | nan% | 0.0% | **FAIL** |

`right line` is the share of produced values that match SOME year the document prints for that field; `precision` is the share that match the year the anchor should have picked. The gap between them is the column error, which is the expensive one: a correct figure filed against the wrong year corrupts every ratio built on it.

## Every wrong value

| RHP | field | got | wanted | right line? | line |
|---|---|---|---|---|---|
| Polycab India Ltd | `finance_costs` | 36.8 | 936.8 | NO | `Finance costs - - - - 9 36.80 - - - - 659.49 - - - - 1 ,473.52` |
| Polycab India Ltd | `depreciation_amortisation` | 1244.55 | 1329.5 | NO | `Depreciation & Amortisation expenses 1,244.55 74.71 10.24 - 1,329.50 1` |

## Withheld (8), with the reason

| RHP | field | reason |
|---|---|---|
| Polycab India Ltd | `tax_expense` | row not present on the page |
| Prince Pipes and Fittings Ltd | `net_worth` | two columns of the same profit-and-loss page match a stated EPS (columns 2 and 0), so the period is not identified and nothing is read |
| Prince Pipes and Fittings Ltd | `tax_expense` | two columns of the same profit-and-loss page match a stated EPS (columns 2 and 0), so the period is not identified and nothing is read |
| Prince Pipes and Fittings Ltd | `finance_costs` | two columns of the same profit-and-loss page match a stated EPS (columns 2 and 0), so the period is not identified and nothing is read |
| Prince Pipes and Fittings Ltd | `depreciation_amortisation` | two columns of the same profit-and-loss page match a stated EPS (columns 2 and 0), so the period is not identified and nothing is read |
| Likhitha Infrastructure Ltd | `net_worth` | no pre-issue share count, so neither the EPS nor the NAV anchor can be applied |
| Likhitha Infrastructure Ltd | `finance_costs` | no pre-issue share count, so neither the EPS nor the NAV anchor can be applied |
| Likhitha Infrastructure Ltd | `shares_outstanding_pre_issue` | no ISSUED, SUBSCRIBED ... BEFORE THE OFFER line with an Equity Shares count |

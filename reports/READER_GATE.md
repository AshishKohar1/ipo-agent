# The five readers, scored against the hand-read check set

Gate: a reader runs on all 450 RHPs only at **precision >= 95.0%** on the values it produces. Precision is measured on what it said, not on what it withheld: silence is useless, a confident wrong value is corrupting.

## Per field

| field | truth rows | produced | withheld | correct | precision | right line | recall | gate |
|---|---|---|---|---|---|---|---|---|
| `depreciation_amortisation` | 2 | 1 | 1 | 0 | **0.0%** | 0.0% | 0.0% | **FAIL** |
| `finance_costs` | 3 | 1 | 2 | 0 | **0.0%** | 0.0% | 0.0% | **FAIL** |
| `net_worth` | 3 | 1 | 2 | 1 | **100.0%** | 100.0% | 33.3% | PASS |
| `shares_outstanding_pre_issue` | 4 | 3 | 1 | 3 | **100.0%** | 100.0% | 75.0% | PASS |
| `tax_expense` | 2 | 1 | 1 | 0 | **0.0%** | 0.0% | 0.0% | **FAIL** |

`right line` is the share of produced values that match SOME year the document prints for that field; `precision` is the share that match the year the anchor should have picked. The gap between them is the column error, which is the expensive one: a correct figure filed against the wrong year corrupts every ratio built on it.

## Every wrong value

| RHP | field | got | wanted | right line? | line |
|---|---|---|---|---|---|
| Polycab India Ltd | `tax_expense` | 763.86 | 2055.96 | NO | `Total tax expense 763.86 531.53` |
| Polycab India Ltd | `finance_costs` | 1084.6 | 936.8 | NO | `Finance costs 1,084.60 937.95` |
| Polycab India Ltd | `depreciation_amortisation` | 975.34 | 1329.5 | NO | `Depreciation and amortisation expense 975.34 708.66` |

## Withheld (7), with the reason

| RHP | field | reason |
|---|---|---|
| Prince Pipes and Fittings Ltd | `net_worth` | no balance-sheet column reproduces any stated NAV within 0.6% - the page, the column or the unit is wrong, so nothing is read |
| Prince Pipes and Fittings Ltd | `tax_expense` | no balance-sheet column reproduces any stated NAV within 0.6% - the page, the column or the unit is wrong, so nothing is read |
| Prince Pipes and Fittings Ltd | `finance_costs` | no balance-sheet column reproduces any stated NAV within 0.6% - the page, the column or the unit is wrong, so nothing is read |
| Prince Pipes and Fittings Ltd | `depreciation_amortisation` | no balance-sheet column reproduces any stated NAV within 0.6% - the page, the column or the unit is wrong, so nothing is read |
| Likhitha Infrastructure Ltd | `net_worth` | no share count or no stated NAV to anchor on |
| Likhitha Infrastructure Ltd | `finance_costs` | no share count or no stated NAV to anchor on |
| Likhitha Infrastructure Ltd | `shares_outstanding_pre_issue` | no ISSUED, SUBSCRIBED ... BEFORE THE OFFER line with an Equity Shares count |

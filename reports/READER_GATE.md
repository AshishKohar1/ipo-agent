# The five readers, scored against the hand-read check set

Gate (H55): a reader runs on all documents only at **precision >= 95.0%** on the values it produces **and at least 10 correct values**. Precision is measured on what it said, not on what it withheld: silence is useless, a confident wrong value is corrupting. Below the minimum sample the verdict is **INSUFFICIENT** - the reader has not been measured, which is a fact about the check set and not about the reader. 100% of one value is a coin landing heads.

## Per field

| field | truth rows | produced | withheld | correct | precision | right line | recall | verdict (needs >=95.0% and >=10 correct) |
|---|---|---|---|---|---|---|---|---|
| `depreciation_amortisation` | 4 | 1 | 3 | 0 | **0.0%** | 0.0% | 0.0% | **INSUFFICIENT** |
| `finance_costs` | 5 | 2 | 3 | 1 | **50.0%** | 50.0% | 20.0% | **INSUFFICIENT** |
| `net_worth` | 4 | 1 | 3 | 1 | **100.0%** | 100.0% | 25.0% | **INSUFFICIENT** |
| `shares_outstanding_pre_issue` | 6 | 5 | 1 | 5 | **100.0%** | 100.0% | 83.3% | **INSUFFICIENT** |
| `tax_expense` | 2 | 1 | 1 | 1 | **100.0%** | 100.0% | 50.0% | **INSUFFICIENT** |

`right line` is the share of produced values that match SOME year the document prints for that field; `precision` is the share that match the year the anchor should have picked. The gap between them is the column error, which is the expensive one: a correct figure filed against the wrong year corrupts every ratio built on it.

## Every wrong value

| RHP | field | got | wanted | right line? | line |
|---|---|---|---|---|---|
| Polycab India Ltd | `finance_costs` | 36.8 | 936.8 | NO | `Finance costs - - - - 9 36.80 - - - - 659.49 - - - - 1 ,473.52` |
| Polycab India Ltd | `depreciation_amortisation` | 1244.55 | 1329.5 | NO | `Depreciation & Amortisation expenses 1,244.55 74.71 10.24 - 1,329.50 1` |

## Withheld (11), with the reason

| RHP | field | reason |
|---|---|---|
| Prince Pipes and Fittings Ltd | `net_worth` | two columns of the same profit-and-loss page match a stated EPS (columns 2 and 0), so the period is not identified and nothing is read |
| Prince Pipes and Fittings Ltd | `tax_expense` | two columns of the same profit-and-loss page match a stated EPS (columns 2 and 0), so the period is not identified and nothing is read |
| Prince Pipes and Fittings Ltd | `finance_costs` | two columns of the same profit-and-loss page match a stated EPS (columns 2 and 0), so the period is not identified and nothing is read |
| Prince Pipes and Fittings Ltd | `depreciation_amortisation` | two columns of the same profit-and-loss page match a stated EPS (columns 2 and 0), so the period is not identified and nothing is read |
| Likhitha Infrastructure Ltd | `net_worth` | no pre-issue share count, so neither the EPS nor the NAV anchor can be applied |
| Likhitha Infrastructure Ltd | `finance_costs` | no pre-issue share count, so neither the EPS nor the NAV anchor can be applied |
| Likhitha Infrastructure Ltd | `shares_outstanding_pre_issue` | no ISSUED, SUBSCRIBED ... BEFORE THE OFFER line with an Equity Shares count |
| Craftsman Automation Limited | `depreciation_amortisation` | row not present on the page |
| Global Health Limited | `net_worth` | no dated row survives as a full fiscal year |
| Global Health Limited | `finance_costs` | no dated row survives as a full fiscal year |
| Global Health Limited | `depreciation_amortisation` | no dated row survives as a full fiscal year |

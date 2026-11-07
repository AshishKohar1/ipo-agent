# The five readers, scored against the hand-read check set

Gate (H55): a reader runs on all documents only at **precision >= 95.0%** on the values it produces **and at least 10 correct values**. Precision is measured on what it said, not on what it withheld: silence is useless, a confident wrong value is corrupting. Below the minimum sample the verdict is **INSUFFICIENT** - the reader has not been measured, which is a fact about the check set and not about the reader. 100% of one value is a coin landing heads.

## Per field

| field | truth rows | produced | withheld | correct | precision | right line | recall | verdict (needs >=95.0% and >=10 correct) |
|---|---|---|---|---|---|---|---|---|
| `depreciation_amortisation` | 15 | 2 | 13 | 1 | **50.0%** | 50.0% | 6.7% | **INSUFFICIENT** |
| `finance_costs` | 17 | 4 | 13 | 3 | **75.0%** | 75.0% | 17.6% | **INSUFFICIENT** |
| `net_worth` | 16 | 3 | 13 | 2 | **66.7%** | 66.7% | 12.5% | **INSUFFICIENT** |
| `shares_outstanding_pre_issue` | 13 | 12 | 1 | 12 | **100.0%** | 100.0% | 92.3% | PASS |
| `tax_expense` | 12 | 3 | 9 | 3 | **100.0%** | 100.0% | 25.0% | **INSUFFICIENT** |

`right line` is the share of produced values that match SOME year the document prints for that field; `precision` is the share that match the year the anchor should have picked. The gap between them is the column error, which is the expensive one: a correct figure filed against the wrong year corrupts every ratio built on it.

## Every wrong value

| RHP | field | got | wanted | right line? | line |
|---|---|---|---|---|---|
| Polycab India Ltd | `finance_costs` | 36.8 | 936.8 | NO | `Finance costs - - - - 9 36.80 - - - - 659.49 - - - - 1 ,473.52` |
| Polycab India Ltd | `depreciation_amortisation` | 1244.55 | 1329.5 | NO | `Depreciation & Amortisation expenses 1,244.55 74.71 10.24 - 1,329.50 1` |
| Route Mobile Ltd | `net_worth` | 2681.94 | 2703.65 | NO | `Total equity 2,946.92 2,681.94 2,099.01 1,601.93` |

## Withheld (49), with the reason

| RHP | field | reason |
|---|---|---|
| Prince Pipes and Fittings Ltd | `net_worth` | two columns of the same profit-and-loss page match a stated EPS (columns 2 and 0), so the period is not identified and nothing is read |
| Prince Pipes and Fittings Ltd | `tax_expense` | two columns of the same profit-and-loss page match a stated EPS (columns 2 and 0), so the period is not identified and nothing is read |
| Prince Pipes and Fittings Ltd | `finance_costs` | two columns of the same profit-and-loss page match a stated EPS (columns 2 and 0), so the period is not identified and nothing is read |
| Prince Pipes and Fittings Ltd | `depreciation_amortisation` | two columns of the same profit-and-loss page match a stated EPS (columns 2 and 0), so the period is not identified and nothing is read |
| Likhitha Infrastructure Ltd | `net_worth` | no pre-issue share count, so neither the EPS nor the NAV anchor can be applied |
| Likhitha Infrastructure Ltd | `finance_costs` | no pre-issue share count, so neither the EPS nor the NAV anchor can be applied |
| Likhitha Infrastructure Ltd | `shares_outstanding_pre_issue` | no ISSUED, SUBSCRIBED ... BEFORE THE OFFER line with an Equity Shares count |
| Antony Waste Handling Cell Ltd | `tax_expense` | no profit-and-loss column reproduces a stated EPS within 3.0% on the pre-issue share count, so the period cannot be identified and nothing i |
| Antony Waste Handling Cell Ltd | `finance_costs` | no profit-and-loss column reproduces a stated EPS within 3.0% on the pre-issue share count, so the period cannot be identified and nothing i |
| CarTrade Tech Limited | `net_worth` | no profit-and-loss column reproduces a stated EPS within 3.0% on the pre-issue share count, so the period cannot be identified and nothing i |
| CarTrade Tech Limited | `tax_expense` | no profit-and-loss column reproduces a stated EPS within 3.0% on the pre-issue share count, so the period cannot be identified and nothing i |
| CarTrade Tech Limited | `finance_costs` | no profit-and-loss column reproduces a stated EPS within 3.0% on the pre-issue share count, so the period cannot be identified and nothing i |
| CarTrade Tech Limited | `depreciation_amortisation` | no profit-and-loss column reproduces a stated EPS within 3.0% on the pre-issue share count, so the period cannot be identified and nothing i |
| Craftsman Automation Limited | `depreciation_amortisation` | row not present on the page |
| AGS Transact Technologies Limited | `net_worth` | no pre-issue share count, so neither the EPS nor the NAV anchor can be applied |
| AGS Transact Technologies Limited | `tax_expense` | no pre-issue share count, so neither the EPS nor the NAV anchor can be applied |
| AGS Transact Technologies Limited | `finance_costs` | no pre-issue share count, so neither the EPS nor the NAV anchor can be applied |
| AGS Transact Technologies Limited | `depreciation_amortisation` | no pre-issue share count, so neither the EPS nor the NAV anchor can be applied |
| Delhivery Limited | `net_worth` | no profit-and-loss column reproduces a stated EPS within 3.0% on the pre-issue share count, so the period cannot be identified and nothing i |
| Global Health Limited | `net_worth` | no dated row survives as a full fiscal year |
| Global Health Limited | `finance_costs` | no dated row survives as a full fiscal year |
| Global Health Limited | `depreciation_amortisation` | no dated row survives as a full fiscal year |
| Cello World Limited | `net_worth` | no profit-and-loss column reproduces a stated EPS within 3.0% on the pre-issue share count, so the period cannot be identified and nothing i |
| Cello World Limited | `tax_expense` | no profit-and-loss column reproduces a stated EPS within 3.0% on the pre-issue share count, so the period cannot be identified and nothing i |
| Cello World Limited | `finance_costs` | no profit-and-loss column reproduces a stated EPS within 3.0% on the pre-issue share count, so the period cannot be identified and nothing i |
| Cello World Limited | `depreciation_amortisation` | no profit-and-loss column reproduces a stated EPS within 3.0% on the pre-issue share count, so the period cannot be identified and nothing i |
| IRM Energy Limited | `depreciation_amortisation` | row not present on the page |
| Signature Global India Limited | `net_worth` | no profit-and-loss column reproduces a stated EPS within 3.0% on the pre-issue share count, so the period cannot be identified and nothing i |
| Signature Global India Limited | `tax_expense` | no profit-and-loss column reproduces a stated EPS within 3.0% on the pre-issue share count, so the period cannot be identified and nothing i |
| Signature Global India Limited | `finance_costs` | no profit-and-loss column reproduces a stated EPS within 3.0% on the pre-issue share count, so the period cannot be identified and nothing i |
| Signature Global India Limited | `depreciation_amortisation` | no profit-and-loss column reproduces a stated EPS within 3.0% on the pre-issue share count, so the period cannot be identified and nothing i |
| ACME Solar Holdings Limited | `net_worth` | no profit-and-loss column reproduces a stated EPS within 3.0% on the pre-issue share count, so the period cannot be identified and nothing i |
| ACME Solar Holdings Limited | `finance_costs` | no profit-and-loss column reproduces a stated EPS within 3.0% on the pre-issue share count, so the period cannot be identified and nothing i |
| ACME Solar Holdings Limited | `depreciation_amortisation` | no profit-and-loss column reproduces a stated EPS within 3.0% on the pre-issue share count, so the period cannot be identified and nothing i |
| Bansal Wire Industries Limited | `net_worth` | no profit-and-loss column reproduces a stated EPS within 3.0% on the pre-issue share count, so the period cannot be identified and nothing i |
| Bansal Wire Industries Limited | `tax_expense` | no profit-and-loss column reproduces a stated EPS within 3.0% on the pre-issue share count, so the period cannot be identified and nothing i |
| Bansal Wire Industries Limited | `finance_costs` | no profit-and-loss column reproduces a stated EPS within 3.0% on the pre-issue share count, so the period cannot be identified and nothing i |
| Bansal Wire Industries Limited | `depreciation_amortisation` | no profit-and-loss column reproduces a stated EPS within 3.0% on the pre-issue share count, so the period cannot be identified and nothing i |
| Godavari Biorefineries Limited | `net_worth` | no profit-and-loss column reproduces a stated EPS within 3.0% on the pre-issue share count, so the period cannot be identified and nothing i |
| Godavari Biorefineries Limited | `finance_costs` | no profit-and-loss column reproduces a stated EPS within 3.0% on the pre-issue share count, so the period cannot be identified and nothing i |
| Godavari Biorefineries Limited | `depreciation_amortisation` | no profit-and-loss column reproduces a stated EPS within 3.0% on the pre-issue share count, so the period cannot be identified and nothing i |
| Borana Weaves Limited | `net_worth` | no dated Basis row for EPS or NAV, so the latest fiscal year cannot be named |
| Borana Weaves Limited | `tax_expense` | no dated Basis row for EPS or NAV, so the latest fiscal year cannot be named |
| Borana Weaves Limited | `finance_costs` | no dated Basis row for EPS or NAV, so the latest fiscal year cannot be named |
| Borana Weaves Limited | `depreciation_amortisation` | no dated Basis row for EPS or NAV, so the latest fiscal year cannot be named |
| GNG Electronics Limited | `net_worth` | no profit-and-loss column reproduces a stated EPS within 3.0% on the pre-issue share count, so the period cannot be identified and nothing i |
| GNG Electronics Limited | `tax_expense` | no profit-and-loss column reproduces a stated EPS within 3.0% on the pre-issue share count, so the period cannot be identified and nothing i |
| GNG Electronics Limited | `finance_costs` | no profit-and-loss column reproduces a stated EPS within 3.0% on the pre-issue share count, so the period cannot be identified and nothing i |
| GNG Electronics Limited | `depreciation_amortisation` | no profit-and-loss column reproduces a stated EPS within 3.0% on the pre-issue share count, so the period cannot be identified and nothing i |

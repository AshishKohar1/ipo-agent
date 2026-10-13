# HDFIRE intraday test — Task 9

Does NSE's `ipo-active-category` publish during the bidding day, or only at 19:00? Subjects: **HDFIRE** (EQ, mainboard) and **RAVITA** (SME, control), both bidding 2026-10-13 to 2026-10-15, confirmed from NSE's own calendar.

`16` rows recorded.

## Every poll, as recorded

| trading date | polled at (real) | slot | symbol | source | Total | QIB | HNI | RII | NSE updateTime | gate |
|---|---|---|---|---|---|---|---|---|---|---|
| 2026-10-13 | 2026-10-13 01:37:37 | 0145-manual | HDFIRE | nse_active_category | 0.00x | — | — | — | Updated as on null | False |
| 2026-10-13 | 2026-10-13 01:37:37 | 0145-manual | HDFIRE | chittorgarh | — | — | — | — | nan | nan |
| 2026-10-13 | 2026-10-13 01:37:37 | 0145-manual | RAVITA | nse_active_category | 0.00x | — | — | — | Updated as on null | False |
| 2026-10-13 | 2026-10-13 01:37:37 | 0145-manual | RAVITA | chittorgarh | — | — | — | — | nan | nan |
| 2026-10-13 | 2026-10-13 11:01:29 | 1101 | HDFIRE | nse_active_category | 0.76x | 0.00x | 2.11x | 0.82x | Updated as on 13-Oct-2026 10:57:00 | True |
| 2026-10-13 | 2026-10-13 11:01:29 | 1101 | HDFIRE | chittorgarh | — | — | — | — | nan | nan |
| 2026-10-13 | 2026-10-13 11:01:29 | 1101 | RAVITA | nse_active_category | 0.00x | — | — | — | Updated as on null | False |
| 2026-10-13 | 2026-10-13 11:01:29 | 1101 | RAVITA | chittorgarh | — | — | — | — | nan | nan |
| 2026-10-13 | 2026-10-13 13:01:32 | 1301 | HDFIRE | nse_active_category | 2.00x | 0.00x | 5.76x | 2.03x | Updated as on 13-Oct-2026 12:57:00 | True |
| 2026-10-13 | 2026-10-13 13:01:32 | 1301 | HDFIRE | chittorgarh | 1.37x | — | 3.01x | 1.46x | nan | nan |
| 2026-10-13 | 2026-10-13 13:01:32 | 1301 | RAVITA | nse_active_category | 0.00x | — | — | — | Updated as on null | False |
| 2026-10-13 | 2026-10-13 13:01:32 | 1301 | RAVITA | chittorgarh | — | — | — | — | nan | nan |
| 2026-10-13 | 2026-10-13 15:01:47 | 1501 | HDFIRE | nse_active_category | 3.66x | 1.01x | 9.76x | 3.08x | Updated as on 13-Oct-2026 14:57:00 | True |
| 2026-10-13 | 2026-10-13 15:01:47 | 1501 | HDFIRE | chittorgarh | 2.02x | — | 4.63x | 2.06x | nan | nan |
| 2026-10-13 | 2026-10-13 15:01:47 | 1501 | RAVITA | nse_active_category | 0.00x | — | — | — | Updated as on null | False |
| 2026-10-13 | 2026-10-13 15:01:47 | 1501 | RAVITA | chittorgarh | — | — | — | — | nan | nan |

## Did NSE's updateTime advance within a day?

This is the whole test. An advancing `updateTime` means NSE publishes intraday and can carry the 15:00 decision; a single pinned value means it cannot.

| trading date | symbol | distinct NSE updateTimes | values |
|---|---|---|---|
| 2026-10-13 | HDFIRE | **4** | Updated as on null; Updated as on 13-Oct-2026 10:57:00; Updated as on 13-Oct-2026 12:57:00; Updated as on 13-Oct-2026 14:57:00 |
| 2026-10-13 | RAVITA | **1** | Updated as on null |

## NSE versus Chittorgarh, per poll

| trading date | slot | symbol | NSE Total | Chittorgarh Total | difference |
|---|---|---|---|---|---|
| 2026-10-13 | 0145-manual | HDFIRE | 0.00x | — | — |
| 2026-10-13 | 0145-manual | RAVITA | 0.00x | — | — |
| 2026-10-13 | 1101 | HDFIRE | 0.76x | — | — |
| 2026-10-13 | 1101 | RAVITA | 0.00x | — | — |
| 2026-10-13 | 1301 | HDFIRE | 2.00x | 1.37x | +0.63x (+46.0%) |
| 2026-10-13 | 1301 | RAVITA | 0.00x | — | — |
| 2026-10-13 | 1501 | HDFIRE | 3.66x | 2.02x | +1.64x (+81.2%) |
| 2026-10-13 | 1501 | RAVITA | 0.00x | — | — |

## 15:00 to final growth (H23's unmeasured quantity)

| trading date | symbol | 15:00 Total | last poll Total | growth |
|---|---|---|---|---|
| 2026-10-13 | HDFIRE | — | 3.66x | — |
| 2026-10-13 | RAVITA | — | 0.00x | — |

## Verdict on H22

**Not yet decided — this is filled in after 15 October.** The decision rule: if `updateTime` advances within a bidding day on HDFIRE, confirm H22 and let NSE carry the live 15:00 decision. If it does not, H22 is reduced to an archival and verification role and Chittorgarh stays primary for the live figure. The freshness gate already makes either outcome safe.


# NSE data-access request — draft for Ashish to complete and submit

**Status: drafted WITHOUT having seen the form.** Read the next section before using this.

## What I could and could not do

| | |
|---|---|
| Asked for | NSE's research/data-access form, its mandatory fields, and truthful draft answers |
| **Could not** | **Locate the form.** The Browser pane is denied for `nseindia.com` in this session, `curl` receives NSE's single-page-app shell rather than rendered content, and the four URLs I tried returned 404 |
| Did not | Guess further URLs. Yesterday I guessed at NSE's and SEBI's terms pages, got two 404s, and said I would rather report a gap than assert a page I had not read. The same applies here |
| Sitemap search | `https://www.nseindia.com/sitemap.xml` (1,619 URLs) has a research section — working papers, events, publications, and a page announcing **"NSE Data Room"**, a cloud-based research facility. That page 404s to `curl`, so I could not read what it asks for |

**So the field list below is what a request of this kind asks for, not a transcription of
NSE's form.** Where NSE asks something I have not anticipated, the answers here still give
you the substance; nothing below is invented about *you* — every personal field is left
blank.

**To find the real form:** open `https://www.nseindia.com` in your own browser, and look
under **Resources → Research → NSE Data Room**, or **Contact Us** for the data-services
address. If the form differs from this, tell me what it asks and I will redraft.

---

## Draft answers

Blanks marked `________` are yours. I have filled nothing about your identity.

### Applicant

| Field | Answer |
|---|---|
| Applicant type | **Individual** |
| Name | `________` |
| Address | `________` |
| City / State / PIN | `________` |
| Country | India |
| Email | `________` |
| Phone | `________` |
| Government ID / PAN (if asked) | `________` |
| Organisation / Institution | **None. This is a personal request, not made on behalf of any employer, university or firm.** |
| Designation | `________` (state your actual job title if the form requires one; do not describe it as a research post) |

### Purpose

| Field | Answer |
|---|---|
| Purpose of request | Personal, non-commercial research into the listing-day performance of Indian IPOs — whether figures published before a bid closes carry any information about the outcome after listing. |
| Is this academic or educational? | **No.** This is personal research by an individual investor. It is not affiliated with any university, not for a degree or course, and not for publication in an academic venue. |
| Is this commercial? | **No.** Nothing is sold, licensed, or offered as a service, and no fee is charged to anyone. |
| Will the data be redistributed? | **No.** The raw data is stored in a private repository, is never published, shared or passed to a third party, and is not offered for download. Only **aggregate results and conclusions** — summary statistics, model accuracy figures, written findings — would ever be shared, and those contain no NSE data records. |
| Intended output | A personal decision aid for the applicant's own IPO applications, and written summaries of what the analysis shows. |

### Data requested

| Field | Answer |
|---|---|
| Data items | 1. IPO subscription figures by investor category, for issues currently open for bidding.<br>2. Past public issues: company, symbol, series, issue open and close dates, issue price, listing date.<br>3. Daily equity bhavcopy (end-of-day open/close per scrip) for specific listing dates.<br>4. Index history: Nifty 50 and sectoral index closes, the Nifty 50 Total Return Index, and index P/E–P/B history.<br>5. The trading-holiday calendar for the capital-market segment. |
| Period covered | Historical: 2010 to date for index and bhavcopy history; 2016 to date for past-issue records. Ongoing: current issues as they open. |
| Delivery preference | Whatever NSE prefers. The existing public web endpoints are entirely sufficient; no feed, file transfer or API key is being requested. |

### Frequency and volume

| Field | Answer |
|---|---|
| Access frequency | A few requests per trading day — in practice fewer than ten, on a fixed schedule: one around 14:15–15:00 IST when an IPO is open for bidding, and one after market close. |
| Peak volume | Under 50 requests on any day, including the occasional backfill of historical dates. |
| Automated? | **Yes, and stated plainly.** The requests are made by a scheduled script rather than by hand. This is the reason for this application: NSE's terms of use prohibit systematic or automated collection without written consent, and the applicant would rather hold that consent than rely on an interpretation. |
| Rate limiting observed | At least 3 seconds between requests to any one host. Results are cached on disk and re-used; the same date is never downloaded twice. |
| Response to a block | If NSE returns 403 or refuses a connection, the script stops asking NSE for that run and uses another source. It does not retry, change its User-Agent, or route around the refusal. |

### Declarations

| Field | Answer |
|---|---|
| Data will not be redistributed | Agreed. |
| Data will not be used commercially | Agreed. |
| Attribution | Any shared conclusion will state that the underlying data came from NSE. |
| Storage | A private repository on the applicant's own machine and private GitHub account. Not shared with anyone. |
| Deletion on request | The applicant will delete the stored NSE data if NSE asks. |

---

## Notes for you before you send it

1. **Do not describe this as academic or educational.** You told me not to, and it would
   also be untrue — there is no institution behind it. "Personal, non-commercial research
   by an individual investor" is accurate and is what the draft says throughout.
2. **The automated-access answer is deliberately plain.** Softening it would defeat the
   point: the consent being sought is precisely consent to automate.
3. **If NSE declines or does not reply**, nothing here changes — H47 already records your
   decision to continue under its six conditions, and condition 6 keeps this application
   open rather than treating silence as permission.
4. Nothing has been submitted. This file is a draft only.

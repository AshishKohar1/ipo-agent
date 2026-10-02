# EMAIL_SETUP — the daily IPO decision email

Two secrets to create, once. Ten minutes. After that the email arrives every weekday.

---

## Step 1 — create a Gmail app password

An app password is a 16-character key that lets one program send mail as you, without your
real password and without disabling anything on your account. It can be revoked on its own.

1. Your Google account needs **2-Step Verification** on. If it is not:
   <https://myaccount.google.com/signinoptions/two-step-verification> → turn it on.
   App passwords do not exist as an option until 2-Step is enabled.
2. Go to <https://myaccount.google.com/apppasswords>
3. In **App name** type `ipo-agent` and press **Create**.
4. Google shows a 16-character password in four blocks, e.g. `abcd efgh ijkl mnop`.
   **Copy it now — it is never shown again.** Spaces do not matter; the code strips them.

If `/apppasswords` says the option is unavailable, it is almost always because 2-Step is off,
or because the account is a Workspace account whose admin has disabled app passwords.

---

## Step 2 — add both secrets to the repository

1. <https://github.com/AshishKohar1/ipo-agent/settings/secrets/actions>
2. **New repository secret**, twice:

| Name | Value |
|---|---|
| `GMAIL_ADDRESS` | `ashishkohar4@gmail.com` |
| `GMAIL_APP_PASSWORD` | the 16 characters from step 1 |

The names must match exactly — they are read by those names and nothing guesses at
alternatives.

**Use repository secrets, not environment secrets or variables.** A *variable* is visible in
logs; a secret is masked. Do not commit the password to a file in the repo — the workflow
reads it from the secret store and never writes it anywhere.

---

## Step 3 — prove it works before Monday

GitHub → **Actions** → **Model L live** → **Run workflow** → mode **`email`** → **Run**.

An email should arrive within about a minute, from you to you, subject beginning
`IPO decision — `.

If it does not, open the run log. The failure is deliberately loud, and there are only a few:

| In the log | Cause | Fix |
|---|---|---|
| `missing repo secret(s): …` | a secret is absent or misnamed | re-check step 2's exact names |
| `535 … Username and Password not accepted` | the app password is wrong, or you used your real password | regenerate the app password |
| `534 … Please log in with your web browser` | 2-Step is off, so it is not a real app password | enable 2-Step, regenerate |
| `Chittorgarh robots.txt no longer permits…` | **the source has withdrawn permission** | stop; this is not a bug to work around |

---

## What arrives, and what it deliberately does not

Subject: `IPO decision — 12 open, 9 closes today`. It always begins with exactly
`IPO decision — ` so you can filter on it.

**A verdict appears only where the model supports one.** Model L is trained on final-day
subscription, and an IPO sitting at 3× on day 1 can close at 150×. So:

- **closing today, mainboard** → full L1/L2 BID or NO against their thresholds
- **not closing today** → subscription figures and nothing else
- **SME, any day** → `PROVISIONAL — SME model not validated for bid decisions`

There is no provisional, indicative or estimated verdict anywhere in the code for a
non-final day. That is intentional: a number the model cannot support is worse than a blank,
because you would act on it.

**Thresholds in the email read 90% (L1) and 80% (L2).** The format you sketched showed 85%
for L2; the model's actual validated promise is 80%, which is what the threshold was derived
against, so the email prints 80%. Changing the figure printed without re-deriving the
threshold would be a false claim.

**Category figures (QIB / HNI / Retail) are display-only**, marked as such on every line.
Per decision H2 they are not model inputs and cannot move a verdict. The demand-profile
label is display-only too (H3). The GMP field is blank for you to fill in by hand (D1).

**You will get an email on a day with no open IPO**, saying so. Silence must always mean
something broke.

---

## The one caveat that matters

Every email carries:

> Subscription from a single source — verify on your broker app.

This is not boilerplate. NSE times out for this client and BSE returns 403 even on its own
`robots.txt`, so Chittorgarh is the only permitted source publishing subscription during
bidding (decision H14). Rule 2 normally requires two sources precisely because a wrong Total
corrupts the **only** input Model L has — and with one source, nothing in the pipeline can
catch such an error. **The check is you, in the thirty seconds before you bid.**

If NSE or BSE grant access later they become the primary pair and Chittorgarh drops to
corroborator, at which point the caveat can go.

---

## Schedule

| Job | Time IST | What |
|---|---|---|
| score + capture + **email** | 15:00 weekdays | resolve open IPOs, read subscription, score the ones closing today, send |
| final capture | 17:30 weekdays | re-read the same IPOs after close — builds the 3pm-vs-close dataset |

15:00 rather than 15:30 because GitHub's scheduler drifts 5–15 minutes; even a 15-minute
drift lands 45 minutes before the 4:00 PM cutoff. The jobs are idempotent, so a drifted
retry or a manual run on top of a scheduled one costs nothing.

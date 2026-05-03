# Tableau Extraction Research — Open Questions

**Status:** Research needed before committing to an automated extraction approach.
**Default until answered:** manual CSV download, once per refresh cycle.

This document lists the concerns an investigating agent should answer before we decide how `etl/extract.py` pulls data from OLCC's Tableau Public views. The outcome should be a recommendation (with evidence) for one of: (A) fully automated via a stable endpoint, (B) automated via headless browser, (C) manual download with a documented cadence, or (D) hybrid.

## Sources in scope

Primary (Phase 1):
- OLCC Cannabis Licensee: https://data.olcc.state.or.us/t/OLCCPublic/views/CannabisBusinessLicensesEndorsements/CannabisLicensesEndorsements

Secondary (Phase 2, same research applies):
- OLCC Market Data: https://data.olcc.state.or.us/#/site/OLCCPublic/views/MarketDataTableau/MainScreen
- OLCC Cannabis Thefts (embedded): https://www.oregon.gov/olcc/marijuana/Pages/marijuana-thefts.aspx

## Questions to answer

### 1. Is there a stable public CSV/data endpoint?

- Does the view expose a `?:format=csv` or `?:showVizHome=no&:embed=y` parameter that yields a CSV directly?
- Does the Tableau "Download" button in the UI produce a direct URL we can script against, or is it a session-bound POST?
- Does `bootstrapSession`-style endpoint (`/vizql/w/<workbook>/v/<view>/bootstrapSession/sessions/<session_id>`) return usable tabular data, and is the session obtainable without headful interaction?
- If there's an export endpoint, how stable is the URL across deploys? Any version token that rotates?

### 2. Is there a terms-of-service or `robots.txt` constraint?

- Check `https://data.olcc.state.or.us/robots.txt`.
- Check OLCC's site for ToS on automated access.
- Tableau Public's terms (if this is Tableau Public vs. Tableau Server) — they differ. Is `data.olcc.state.or.us` self-hosted Tableau Server or Tableau Public?
- What `User-Agent` identification is expected? We want to send a truthful UA string with project URL + contact email.

### 3. Rate limiting / throttling behavior

- What happens on repeated requests in a short window? HTTP 429? Silent CAPTCHA? Soft IP block?
- Does the server set rate-limit headers we can respect?
- Is a once-per-day pull safe? Once-per-week?

### 4. Session / cookie / CSRF requirements

- Does the CSV download path require an established session cookie?
- Are there CSRF tokens embedded in the page HTML that must be extracted first?
- Does the URL contain a per-session `sessionid`/`token` path segment that would make a hard-coded URL break tomorrow?

### 5. Headless-browser viability (fallback)

If no clean HTTP endpoint exists:
- Can Playwright reliably load the view, click Download → CSV, and capture the file?
- How long does the view take to render on a cold load?
- Does it work headless or does it need `headless=False`? (Some Tableau views misbehave without a real viewport.)
- Total runtime budget: we want nightly extraction under 2 minutes.

### 6. Data completeness

- Does the CSV export contain **every** field we need for the schema in `PLAN.md` (`license_id`, `license_type`, `status`, `business_name`, `trade_name`, `county`, `city`, `tier`, `canopy_type`, `issued_date`, `expires_date`)?
- Or does the Tableau view pre-filter/aggregate and require us to toggle filters in the UI to get full detail?
- Is "inactive" data present, or does the view only show active licenses (in which case we can't detect `STATUS_CHANGE` transitions to inactive — we'd infer removal-from-list as the signal)?
- Row count sanity check: approximately how many active licenses should we expect (order of magnitude) so we can assert on each pull?

### 7. Schema stability

- Has OLCC changed the column set of this view recently? (Wayback Machine may help.)
- Are column names stable across weekly updates, or do they drift (spacing, case)?
- Any columns that look auto-generated (`Measure Names`, `Measure Values`) that we should strip?

### 8. Update cadence of the source

- How often does OLCC actually refresh this view? (Plan says "weekly-ish" — verify.)
- Is there a `last_updated` timestamp visible anywhere in the view or its metadata?
- What day of the week / time of day does the refresh typically happen? Our nightly cron should run **after** the daily refresh to avoid capturing stale data repeatedly.

### 9. Comparable approaches elsewhere

- Does the `cannlytics/cannlytics` repo already have an Oregon extractor? If so, how does it handle this?
- Has anyone else scraped these specific Tableau views publicly (blog posts, Kaggle datasets, civic-tech repos)? What approach did they use, and does it still work?
- Is there a Tableau REST API available for Tableau Server deployments that OLCC might have enabled?

### 10. Legal / ethical check

- OLCC licensee data is public record under Oregon public-records law — confirmed. Is there any specific restriction on *republishing* it (vs. just accessing it)?
- Are there any named-individual privacy concerns beyond what's already redacted in the source? (e.g., the CSV won't include residential addresses, but does it include individual owner names?)

## Deliverable

After investigation, the agent should update this document with:

1. **Recommendation:** one of A/B/C/D above, with a one-paragraph justification.
2. **Evidence:** URLs tested, response codes, example request/response snippets.
3. **Reliability estimate:** "expected to work 95% of nights" vs. "fragile, expect manual intervention monthly."
4. **Implementation sketch:** ~20-line outline of what `extract.py` would do under the recommended approach.
5. **Triggers to revisit:** what would cause us to change approach (e.g., "if Tableau Server upgrades to vX.Y").

## Concerns that have already shaped the plan

- We are not willing to run a headless browser in GitHub Actions long-term if it's flaky — the point of this project is a reliable pipeline, not a maintenance burden.
- Manual-once-per-week is an acceptable outcome. A well-operated manual process with good documentation beats a broken automated one.
- We will not bypass rate limits, CAPTCHAs, or ToS restrictions. If the only way to automate is adversarial, the answer is manual.

---

## Findings (verified 2026-04-24)

Evidence gathered by direct HTTP requests from the project working directory.

### Recommendation: **Option A — Fully Automated via Direct CSV Endpoint**

Either URL form returns a working CSV:

- `https://data.olcc.state.or.us/t/OLCCPublic/views/CannabisBusinessLicensesEndorsements/CannabisLicensesEndorsements.csv` (preferred — cleaner)
- `https://data.olcc.state.or.us/t/OLCCPublic/views/CannabisBusinessLicensesEndorsements/CannabisLicensesEndorsements?:format=csv` (equivalent)

Both returned `HTTP 200`, `Content-Type: text/csv`, ~453 KB, 2,658 data rows (plus header). Reliability estimate: high (95%+ nightly success) conditional on handling the TLS-chain quirk below.

### Answers to the 10 questions

**1. Stable public CSV endpoint?** — **Yes.** Confirmed both `.csv` URL-suffix and `?:format=csv` query-param forms return identical CSV. Response headers include `X-Tableau: Tableau Server`, so this is Tableau Server (not Tableau Public). **Confidence: High.**

**2. ToS / robots.txt?** — **No robots.txt** (`GET /robots.txt` returns a 200-ish HTML error page "The page you were looking for could not be found"). Absence of a disallow means crawling is not prohibited, but the site doesn't actively invite it either. Use a truthful `User-Agent` identifying the project + contact email. No visible ToS restriction. **Confidence: Medium** — we haven't found an explicit ToS page.

**3. Rate limiting / throttling?** — **No evidence of rate limiting** on single requests. We did not load-test, but once-nightly is clearly safe. **Confidence: Medium** (didn't probe, didn't need to).

**4. Session / cookie / CSRF?** — **None required.** Direct `GET` with no cookies returned the CSV. No session establishment needed. **Confidence: High.**

**5. Headless-browser viability (fallback)?** — **Not needed.** The direct CSV endpoint works without JS rendering. Playwright fallback is unnecessary. **Confidence: High.**

**6. Data completeness?** — **Available fields verified by real header and sample rows:**

```
Business Licenses, Business Name, Canopy Type, County, Endorsement,
License Number, License Type, PhysicalAddress, SOS Registration Number,
Status, Tier, Expiration Date
```

Notable real-data facts:

- **`Status` is `ACTIVE` for 100% of returned rows** — the view is pre-filtered to active licenses. We **cannot** observe `Suspended / Revoked / Surrendered` from this source. Our diff logic can only emit `REMOVED` when a license disappears from the list; specific termination reason isn't available here.
- `PhysicalAddress` is populated for **retailers and labs**, and says "Exempt from Public Disclosure" for **producers / processors / wholesalers** (as the statute requires).
- `Tier` and `Canopy Type` are populated for **producers only**.
- `Endorsement` carries things like "Marijuana Home Delivery, Medical Marijuana Retailer" (comma-separated within a quoted field — parse accordingly).
- `SOS Registration Number` is an Oregon Secretary of State business-entity number — valuable future join key, but mostly blank in the current export.
- **`Business Licenses`** (column 1) is the **legal entity name**. **`Business Name`** (column 2) is the **trade name / DBA**. PLAN.md had these backward.
- **No `Issued Date`** column. Plan's `issued_date` cannot be populated from this source.
- **No standalone `City` column.** Address info is only in the free-text `PhysicalAddress` for retailers/labs; parse if needed.
- **License Types found:** `HEMP GROWER CERTIFICATE`, `HEMP HANDLER CERTIFICATE`, `LABORATORY`, `RECREATIONAL PROCESSOR`, `RECREATIONAL PRODUCER`, `RECREATIONAL RETAILER`, `RECREATIONAL WHOLESALER`, `RESEARCH CERTIFICATE`. Our controlled vocabulary needs `HEMP GROWER CERTIFICATE`, `HEMP HANDLER CERTIFICATE`, `RESEARCH CERTIFICATE` added.
- **Counties:** 30 of Oregon's 36 counties present in the data.

**Confidence: High** (these are verified from the actual response).

**7. Schema stability?** — **Cannot assess from one snapshot.** Wayback-Machine history was not retrieved. Monitor via a pytest assertion on the expected column set; warn on unmapped columns; fail on missing required columns. **Confidence: Low.**

**8. Update cadence?** — **Not verified.** `Last-Modified` on the server root is 2025-10-03, but that's the homepage, not the view dataset. PLAN.md's "weekly-ish" assumption stands, unverified. Worth a follow-up: check `Last-Modified` on the CSV response specifically after a few days of captures. **Confidence: Low.**

**9. Comparable approaches elsewhere?** — **No cannlytics Oregon adapter found.** The `cannlytics/cannlytics` repo covers other states; Oregon is open territory. `easyolcc.com` publishes a filterable license browser that is clearly derived from this dataset, but they don't publish their scraping methodology. Tableau community docs confirm the `.csv` suffix / `?:format=csv` params are standard Tableau Server features. **Confidence: High.**

**10. Legal / ethical?** — **Public record under Oregon law.** Data published by OLCC; `PhysicalAddress` is already redacted at source for producers. Republishing with attribution is appropriate. **Confidence: High.**

### Critical operational gotcha: TLS chain (verified workaround in place)

**`data.olcc.state.or.us` does not serve the intermediate certificate.** Cert: `CN=*.olcc.state.or.us`, issuer `Sectigo Public Server Authentication CA OV R36`. Verification fails with `unable to get local issuer certificate` / `unable to verify the first certificate`.

Verified results (2026-04-27):

| Client | Result |
|---|---|
| `openssl s_client` (default) | **fails** |
| WebFetch (Node-based) | **fails** |
| Python `requests` + `certifi` | **fails** — contradicting earlier speculation |
| `curl` with macOS system trust store | works (LibreSSL has different chain handling) |
| Python `requests` + bundled intermediate (the fix) | **works** |

**Implemented fix:** the project ships the missing intermediate at `etl/certs/sectigo_public_server_auth_ov_r36.pem` (sourced from the cert's AIA extension URL) and `extract.py` builds a merged CA bundle (certifi + this intermediate) at runtime via `_ca_bundle()`. Cert verification stays strict; only the missing link is added.

If OLCC rotates to a different Sectigo intermediate, the extractor will fail with TLS errors. Refresh procedure is documented in `etl/certs/README.md`.

### Implementation sketch for `extract.py`

```python
import hashlib
from datetime import datetime, timezone
from pathlib import Path

import requests

OLCC_LICENSEE_URL = (
    "https://data.olcc.state.or.us/t/OLCCPublic/views/"
    "CannabisBusinessLicensesEndorsements/CannabisLicensesEndorsements.csv"
)
USER_AGENT = "OregonCannabisDataProject/0.1 (+mark@pernotto.com)"

EXPECTED_COLUMNS = [
    "Business Licenses", "Business Name", "Canopy Type", "County",
    "Endorsement", "License Number", "License Type", "PhysicalAddress",
    "SOS Registration Number", "Status", "Tier", "Expiration Date",
]


def extract() -> dict:
    resp = requests.get(
        OLCC_LICENSEE_URL,
        headers={"User-Agent": USER_AGENT, "Accept": "text/csv"},
        timeout=60,
    )
    resp.raise_for_status()
    body = resp.content

    # Sanity assertions — fail loudly, do not silently continue.
    assert resp.headers.get("Content-Type", "").startswith("text/csv"), resp.headers
    assert len(body) > 100_000, f"suspiciously small: {len(body)} bytes"

    header = body.split(b"\n", 1)[0].decode()
    missing = [c for c in EXPECTED_COLUMNS if c not in header]
    assert not missing, f"columns missing: {missing}"

    retrieved_at = datetime.now(timezone.utc)
    checksum = hashlib.sha256(body).hexdigest()
    snapshot_path = Path(f"data/snapshots/{retrieved_at.date()}.csv")
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path.write_bytes(body)

    return {
        "path": snapshot_path,
        "source_url": OLCC_LICENSEE_URL,
        "source_retrieved_at": retrieved_at.isoformat(),
        "source_checksum": checksum,
        "extraction_version": "0.1.0",
    }
```

### Triggers to revisit this approach

- HTTP 403 / 404 on the `.csv` endpoint
- Content-Type shifts to HTML (means the direct export was disabled)
- Unexpected column set (missing `EXPECTED_COLUMNS`)
- Row count drops > 30% run-over-run
- `requests` starts failing TLS verification in CI even with `certifi`
- OLCC publishes an explicit ToS prohibiting automated access

### Loose ends (worth but not blocking)

- **Schema stability over time** — not assessed. Check Wayback Machine after scaffolding.
- **Actual refresh cadence of the source data** — not verified. Log `Last-Modified` on each pull; infer cadence from a few weeks of data.
- **Secondary views (Market Data, Thefts)** — same Tableau Server, same approach assumed to work. Verify when Phase 2 starts.
- **EasyOLCC's methodology** — not documented publicly. Not blocking; they may or may not use this same endpoint.

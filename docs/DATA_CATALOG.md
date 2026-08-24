# Data Catalog

One entry per dataset ingested by this project. Modeled after the
[Frictionless Data](https://frictionlessdata.io/) data-package conventions.

---

## olcc-cannabis-licensees

| Field | Value |
|---|---|
| **Title** | OLCC Cannabis Business Licenses & Endorsements |
| **Publisher** | Oregon Liquor and Cannabis Commission (OLCC), via the Oregon Open Data Portal |
| **Source URL** | https://data.oregon.gov/d/q32u-cmam |
| **Extraction URL** | `https://data.oregon.gov/resource/q32u-cmam.csv?$limit=50000&$order=:id` |
| **Format** | CSV over Socrata SODA 2.1 |
| **License (source)** | Public record under Oregon law (ORS 192.311 et seq.) |
| **License (this republication)** | CC0 1.0 — see [LICENSE-DATA](../LICENSE-DATA) |
| **Update cadence** | Daily |
| **Coverage** | Oregon cannabis and hemp licensees, all license types, active and closed |
| **Grain** | One row per license *term*; collapsed to one row per license on load |
| **Row count (2026-08-24)** | 3,760 source rows / 3,666 licenses (2,726 active) |
| **Verified** | 2026-08-24 |
| **History** | [docs/SOURCE_HISTORY.md](SOURCE_HISTORY.md) — this replaced a Tableau Server export retired 2026-08 |

### Fields

| Source column | Target field | Notes |
|---|---|---|
| `business_licenses` | `legal_name` | Legal entity name |
| `business_name` | `trade_name` | DBA |
| `license_number` | `license_number` | Primary key; prefix encodes type |
| `license_type` | `license_type` | See [vocabularies/license_type.yaml](../vocabularies/license_type.yaml) |
| `license_expired` + `inactive_date` | `status` | Derived; see [vocabularies/status.yaml](../vocabularies/status.yaml) |
| `county` | `county` | 30 of 36 Oregon counties present |
| `physical_address` | `physical_address` | Retailers + labs only; redacted for others |
| `canopy_type` | `canopy_type` | Producers only |
| `tier` | `tier` | Producers only (Tier I / Tier II) |
| `endorsement` | `endorsements` | Parsed comma-separated to array |
| `sos_registration_number` | `sos_registration` | OR Secretary of State entity number |
| `effective_date` | `effective_date` | ISO; start of the license term |
| `expiration_date` | `expiration_date` | ISO; end of the license term |
| `inactive_date` | `inactive_date` | Set when a license ended before its term ran out |

### Known issues

- **No status column.** `status` is derived from `license_expired` and
  `inactive_date`. `INACTIVE` covers surrender, revocation, and early
  non-renewal alike — the source does not publish the reason.
- **`license_expired` is not derivable from the dates.** 177 licenses are
  flagged active while past their printed `expiration_date`, because OLCC
  keeps a license active during renewal. Trust the flag, not the arithmetic.
- **One row per license term.** 94 licenses publish a current term and a
  renewal already on file. `etl.transform` keeps the term in effect on the
  snapshot date; the raw rows remain in `data/snapshots/`.
- `physical_address` is redacted by statute for producers, processors, and
  wholesalers — the cell contains the literal string "Exempt from Public
  Disclosure" for those license types.
- **Coverage gap 2026-08-10 .. 2026-08-23**, from the source migration. The
  portal publishes current state only, so it cannot be backfilled.

### Citation

> Oregon Liquor and Cannabis Commission, *Cannabis Business Licenses &
> Endorsements*. Retrieved via the Oregon Open Data Portal
> (`data.oregon.gov/d/q32u-cmam`) on `YYYY-MM-DD`.

# Data Catalog

One entry per dataset ingested by this project. Modeled after the
[Frictionless Data](https://frictionlessdata.io/) data-package conventions.

---

## olcc-cannabis-licensees

| Field | Value |
|---|---|
| **Title** | OLCC Cannabis Licensee Public Report |
| **Publisher** | Oregon Liquor and Cannabis Commission (OLCC) |
| **Source URL** | https://data.olcc.state.or.us/t/OLCCPublic/views/CannabisBusinessLicensesEndorsements/CannabisLicensesEndorsements |
| **Extraction URL** | https://data.olcc.state.or.us/t/OLCCPublic/views/CannabisBusinessLicensesEndorsements/CannabisLicensesEndorsements.csv |
| **Format** | CSV (Tableau Server direct export) |
| **License (source)** | Public record under Oregon law (ORS 192.311 et seq.) |
| **License (this republication)** | CC0 1.0 — see [LICENSE-DATA](../LICENSE-DATA) |
| **Update cadence** | Weekly-ish (verify over time; not officially documented) |
| **Coverage** | Active Oregon cannabis and hemp licensees, all license types |
| **Row count (2026-04-24)** | 2,658 |
| **Verified** | 2026-04-24 |
| **Research** | [docs/TABLEAU_RESEARCH.md](TABLEAU_RESEARCH.md) |

### Fields

| Source column | Target field | Notes |
|---|---|---|
| Business Licenses | `legal_name` | Legal entity name |
| Business Name | `trade_name` | DBA |
| License Number | `license_number` | Primary key; prefix encodes type |
| License Type | `license_type` | See [vocabularies/license_type.yaml](../vocabularies/license_type.yaml) |
| Status | `status` | Source view filters to ACTIVE only |
| County | `county` | 30 of 36 Oregon counties present |
| PhysicalAddress | `physical_address` | Retailers + labs only; redacted for others |
| Canopy Type | `canopy_type` | Producers only |
| Tier | `tier` | Producers only (Tier I / Tier II) |
| Endorsement | `endorsements` | Parsed comma-separated to array |
| SOS Registration Number | `sos_registration` | OR Secretary of State entity number |
| Expiration Date | `expiration_date` | MM/DD/YYYY in source |

### Known issues

- `Status` is always `ACTIVE` — the source pre-filters. De-activations are
  inferred from REMOVED diff events, without a specific termination reason.
- `PhysicalAddress` is redacted by statute for producers, processors, and
  wholesalers — the cell contains the literal string "Exempt from Public
  Disclosure" for those license types.
- No `Issued Date` field. Historical issuance dates are not available from
  this source.
- The OLCC TLS cert chain does not include the Sectigo intermediate; use an
  HTTP client with a Mozilla-derived trust store (Python `requests` +
  `certifi`).

### Citation

> Oregon Liquor and Cannabis Commission, *Cannabis Licensee Public Report*.
> Retrieved via `data.olcc.state.or.us` on `YYYY-MM-DD`.

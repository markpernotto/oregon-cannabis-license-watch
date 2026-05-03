# Privacy

This project republishes public records from Oregon state agencies. It does not
collect, store, or analyze any personal information about visitors to the
published data or site.

## What the dataset contains

Business-entity information from the Oregon Liquor and Cannabis Commission
(OLCC) licensee public report, which is a public record under Oregon law
(ORS 192.311 et seq., ORS 475C). Specifically:

- Legal entity names and trade names of licensed cannabis businesses
- License numbers, types, and status
- Expiration dates
- County of operation
- For retailers and laboratories only: physical street address (producers,
  processors, and wholesalers have their addresses redacted at source under
  ORS 475C.185)
- Producer canopy tier and canopy type
- Secretary of State business-registration numbers (where published by OLCC)

## What the dataset does not contain

The project does not add information beyond what OLCC already publishes. It
does not include:

- Residential addresses of license holders or their employees
- Individual personnel or owner names (except as embedded in legal entity
  names, which is public business registration data)
- Financial records, tax filings, or sales figures tied to named licensees
- Security plans, inventory, or transactional METRC data (these are
  statutorily exempt from disclosure)

## Correction requests

If you are a licensee and believe the published data contains an error, the
authoritative source is OLCC's Cannabis Licensing program. We republish what
OLCC publishes; corrections applied at the source will flow through on the
next nightly snapshot. If you believe this project has introduced an error
during processing, open an issue in the project repository and we'll
investigate.

## Snapshots and change history

The project retains historical snapshots of OLCC's public license data and
derives a change feed from them. This is a public-interest archival function;
the historical record shows the same facts OLCC published at each point in
time.

## Principles

These rules govern what this project will and will not do with public data.
They are commitments, not aspirations. See [CONTRIBUTING.md](CONTRIBUTING.md)
for how they apply to contributors.

1. **Republish, don't enrich.** We mirror what the publishing agency releases.
   We do not join public licensing data against other sources (residential
   property records, voter rolls, social profiles, court filings) to
   reconstruct information the agency chose not to publish. If OLCC redacted
   a field, that redaction stands.

2. **Mirror corrections.** When the agency corrects or removes a record, the
   current published view of this project reflects that correction on the next
   snapshot. The historical archive may retain the prior state as an archival
   record of what the agency published when, but the canonical "current" view
   is always the latest source state.

3. **Honor takedown requests for derived errors.** If a licensee identifies
   an error introduced by this project's processing — not by the source — we
   investigate and fix promptly. Errors in the source are routed to the
   source agency.

4. **Aggregate-only for any health-related data.** Any future ingestion of
   medical-program data (e.g. OHA OMMP statistics) uses only aggregated
   counts as the agency publishes them. Patient-level medical data is out of
   scope, full stop.

5. **No scoring, ranking, or editorializing.** The project presents what
   agencies publish. It does not produce "shadiest licensees" rankings, risk
   scores, theft heatmaps that imply causation, or any other derived rating
   that could function as defamation. Neutral facts; visible attribution.

6. **No reidentification.** If aggregated data is published with small cells
   or k-anonymity protections, we do not attempt to reverse those protections
   by joining against other sources.

7. **No automated harassment surfaces.** No personal contact information, no
   "where is this person now" tools, no enrichment that turns a regulatory
   record into a person-search lookup.

# Data Sources

Public Oregon data sources tracked or planned for this project. Full catalog
entries live in [DATA_CATALOG.md](DATA_CATALOG.md) as each source is ingested.

## Phase 1

| Source | Agency | Format | Status |
|---|---|---|---|
| [Cannabis Licensee Public Report](https://data.olcc.state.or.us/t/OLCCPublic/views/CannabisBusinessLicensesEndorsements/CannabisLicensesEndorsements) | OLCC | Tableau Server CSV | Verified 2026-04-24 |

## Phase 2 (planned)

| Source | Agency | Format |
|---|---|---|
| [Market Data Tableau](https://data.olcc.state.or.us/#/site/OLCCPublic/views/MarketDataTableau/MainScreen) | OLCC | Tableau Server CSV |
| [Cannabis Thefts](https://www.oregon.gov/olcc/marijuana/Pages/marijuana-thefts.aspx) | OLCC | Tableau (embedded) |
| [Monthly Marijuana Tax Distribution](https://www.oregon.gov/dor/programs/businesses/Documents/Marjuana_monthly_financial_reporting_distributions_public.pdf) | OR DOR | PDF |
| [OHA OMMP Statistics](https://www.oregon.gov/oha/ph/DiseasesConditions/ChronicDisease/MedicalMarijuanaProgram/Pages/data.aspx) | OHA | PDF (quarterly) |
| [Cannabis Pesticide Guide](https://data.oregon.gov/d/b8ki-p9ef) | ODA via Socrata | SODA API |
| [Portland Cannabis Program](https://www.portland.gov/ppd/cannabis/statistics) | City of Portland | HTML/PDF |

## Not available (do not pursue)

- **METRC raw transaction data** — legally exempt under ORS 475C.517
- **Producer / processor / wholesaler physical addresses** — redacted at source
- **Licensee-specific inventory, security plans** — statutorily exempt

## Access conventions

- Identify the project in `User-Agent`:
  `OregonCannabisDataProject/<version> (+mark@pernotto.com)`
- Pull on a human cadence (nightly is the ceiling; weekly or monthly where
  appropriate).
- Never bypass rate limits, CAPTCHAs, or ToS restrictions.
- Attribute the publishing agency in all derived artifacts.

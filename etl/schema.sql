-- Idempotent DDL for the Oregon Cannabis Data project.
-- Apply with: psql "$DATABASE_URL" -f etl/schema.sql

CREATE TABLE IF NOT EXISTS licensees_snapshots (
    snapshot_date          DATE        NOT NULL,
    license_number         TEXT        NOT NULL,
    license_type           TEXT        NOT NULL,
    status                 TEXT        NOT NULL,
    legal_name             TEXT,
    trade_name             TEXT,
    endorsements           TEXT[],
    county                 TEXT,
    physical_address       TEXT,
    tier                   TEXT,
    canopy_type            TEXT,
    sos_registration       TEXT,
    expiration_date        DATE,
    raw_row                JSONB       NOT NULL,
    source_url             TEXT        NOT NULL,
    source_retrieved_at    TIMESTAMPTZ NOT NULL,
    source_checksum        TEXT        NOT NULL,
    extraction_version     TEXT        NOT NULL,
    PRIMARY KEY (snapshot_date, license_number)
);

CREATE INDEX IF NOT EXISTS licensees_snapshots_license_number_idx
    ON licensees_snapshots (license_number);

CREATE TABLE IF NOT EXISTS license_changes (
    change_id              BIGSERIAL   PRIMARY KEY,
    observed_at            TIMESTAMPTZ NOT NULL,
    license_number         TEXT        NOT NULL,
    change_type            TEXT        NOT NULL,
    field_name             TEXT,
    prev_value             JSONB,
    new_value              JSONB,
    diff_summary           TEXT,
    source_snapshot_date   DATE        NOT NULL,
    CONSTRAINT license_changes_change_type_check
        CHECK (change_type IN ('NEW', 'REMOVED', 'FIELD_CHANGE')),
    CONSTRAINT license_changes_field_name_requires_field_change
        CHECK (
            (change_type = 'FIELD_CHANGE' AND field_name IS NOT NULL)
            OR (change_type IN ('NEW', 'REMOVED') AND field_name IS NULL)
        )
);

CREATE INDEX IF NOT EXISTS license_changes_observed_at_idx
    ON license_changes (observed_at DESC);
CREATE INDEX IF NOT EXISTS license_changes_license_number_idx
    ON license_changes (license_number);
CREATE INDEX IF NOT EXISTS license_changes_change_type_idx
    ON license_changes (change_type);

-- Idempotency anchor: re-running diff on the same snapshot pair must not
-- duplicate change rows. NULLS NOT DISTINCT (Postgres 15+) treats NULL
-- field_name as equal to NULL field_name for uniqueness purposes.
CREATE UNIQUE INDEX IF NOT EXISTS license_changes_unique_observation_idx
    ON license_changes (source_snapshot_date, license_number, change_type, field_name)
    NULLS NOT DISTINCT;

-- "Current" means: present in the most recent overall snapshot. A license
-- that was removed today should not appear here, even though we still have
-- its prior snapshot rows in licensees_snapshots.
CREATE OR REPLACE VIEW licensees_current AS
SELECT *
FROM licensees_snapshots
WHERE snapshot_date = (SELECT MAX(snapshot_date) FROM licensees_snapshots);

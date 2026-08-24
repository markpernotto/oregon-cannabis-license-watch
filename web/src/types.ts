export type ChangeType = "NEW" | "REMOVED" | "FIELD_CHANGE";

export interface Change {
  change_id: number;
  observed_at: string;
  snapshot_date: string;
  license_number: string;
  license_type: string | null;
  legal_name: string | null;
  trade_name: string | null;
  county: string | null;
  change_type: ChangeType;
  field_name: string | null;
  prev_value: unknown;
  new_value: unknown;
  summary: string;
}

export interface CoverageGap {
  /** First missing day, inclusive. */
  start: string;
  /** Last missing day, inclusive. */
  end: string;
  days: number;
}

export interface ChangesPayload {
  generated_at: string;
  source: string;
  source_url: string;
  window_days: number;
  total_changes: number;
  freshness_sla_hours: number;
  /** Start of history. Unlike `consecutive_since`, a gap does not move it. */
  first_snapshot_date: string | null;
  latest_snapshot_date: string | null;
  /** Start of the current unbroken daily run. */
  consecutive_since: string | null;
  coverage_gaps: CoverageGap[];
  changes: Change[];
}

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

export interface ChangesPayload {
  generated_at: string;
  source: string;
  source_url: string;
  window_days: number;
  total_changes: number;
  freshness_sla_hours: number;
  changes: Change[];
}

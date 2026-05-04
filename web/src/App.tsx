import { useEffect, useMemo, useState } from "react";
import type { Change, ChangesPayload } from "./types";

const ALL = "__all__";

export default function App() {
  const [data, setData] = useState<ChangesPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [licenseTypeFilter, setLicenseTypeFilter] = useState(ALL);
  const [changeTypeFilter, setChangeTypeFilter] = useState(ALL);
  const [search, setSearch] = useState("");

  useEffect(() => {
    fetch("/changes.json")
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json() as Promise<ChangesPayload>;
      })
      .then(setData)
      .catch((e) => setError(String(e)));
  }, []);

  const licenseTypes = useMemo(() => {
    if (!data) return [];
    const set = new Set<string>();
    for (const c of data.changes) {
      const lt = guessLicenseTypeFromNumber(c.license_number);
      if (lt) set.add(lt);
    }
    return Array.from(set).sort();
  }, [data]);

  const changeTypes = useMemo(() => {
    if (!data) return [];
    const set = new Set(data.changes.map((c) => c.change_type));
    return Array.from(set).sort();
  }, [data]);

  const filtered = useMemo(() => {
    if (!data) return [];
    const needle = search.trim().toLowerCase();
    return data.changes.filter((c) => {
      if (changeTypeFilter !== ALL && c.change_type !== changeTypeFilter) return false;
      if (licenseTypeFilter !== ALL) {
        const lt = guessLicenseTypeFromNumber(c.license_number);
        if (lt !== licenseTypeFilter) return false;
      }
      if (needle && !c.summary.toLowerCase().includes(needle)) return false;
      return true;
    });
  }, [data, changeTypeFilter, licenseTypeFilter, search]);

  return (
    <main>
      <header>
        <h1>Oregon Cannabis License Watch</h1>
        <p>
          Daily change feed derived from the OLCC Cannabis Licensee public report.
        </p>
        {data && (
          <div className="meta">
            <span>
              <strong>{data.total_changes}</strong> changes in last {data.window_days} days
            </span>
            <span>
              Updated {formatRelative(data.generated_at)}
            </span>
            <span>
              Freshness SLO: ≤ {data.freshness_sla_hours}h
            </span>
            <span>
              <a href="/rss.xml">RSS</a> · <a href="/changes.json">JSON</a>
            </span>
          </div>
        )}
      </header>

      {!data && !error && <div className="loading">Loading…</div>}
      {error && <div className="error">Failed to load changes: {error}</div>}

      {data && (
        <>
          <div className="filters">
            <div>
              <label htmlFor="license-type">License type</label>
              <select
                id="license-type"
                value={licenseTypeFilter}
                onChange={(e) => setLicenseTypeFilter(e.target.value)}
              >
                <option value={ALL}>All</option>
                {licenseTypes.map((t) => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </select>
            </div>
            <div>
              <label htmlFor="change-type">Change type</label>
              <select
                id="change-type"
                value={changeTypeFilter}
                onChange={(e) => setChangeTypeFilter(e.target.value)}
              >
                <option value={ALL}>All</option>
                {changeTypes.map((t) => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </select>
            </div>
            <div>
              <label htmlFor="search">Search</label>
              <input
                id="search"
                type="search"
                placeholder="License number or text…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>
          </div>

          <p className="summary">
            Showing {filtered.length} of {data.total_changes} changes
          </p>

          {filtered.length === 0 ? (
            <div className="empty">No changes match the current filters.</div>
          ) : (
            <ul className="change-list">
              {filtered.map((c) => (
                <ChangeRow key={c.change_id} change={c} />
              ))}
            </ul>
          )}
        </>
      )}

      <footer>
        Data from the{" "}
        <a href="https://www.oregon.gov/olcc" target="_blank" rel="noopener noreferrer">
          Oregon Liquor and Cannabis Commission
        </a>
        . Republished under{" "}
        <a href="https://creativecommons.org/publicdomain/zero/1.0/" target="_blank" rel="noopener noreferrer">
          CC0
        </a>
        .{" "}
        <a href="https://github.com/markpernotto/oregon-cannabis-license-watch" target="_blank" rel="noopener noreferrer">
          Source on GitHub
        </a>
        .
      </footer>
    </main>
  );
}

function ChangeRow({ change }: { change: Change }) {
  const cls = change.change_type.toLowerCase();
  return (
    <li className="change-card">
      <span className={`change-type ${cls}`}>{change.change_type}</span>
      <div className="change-summary">
        <code>{change.license_number}</code>
        {change.field_name ? (
          <>
            {" "}— {change.field_name}: {formatValue(change.prev_value)} → {formatValue(change.new_value)}
          </>
        ) : (
          renderNewRemovedSummary(change)
        )}
      </div>
      <span className="change-date">{change.snapshot_date}</span>
    </li>
  );
}

function renderNewRemovedSummary(c: Change): React.ReactNode {
  // Strip the leading "NEW <type>: " or "REMOVED: " from diff_summary so we
  // don't repeat the badge text in the line. Falls back to the raw summary.
  const stripped = c.summary
    .replace(/^NEW [A-Z_]+:\s*/, "")
    .replace(/^REMOVED:\s*/, "")
    .replace(new RegExp(`\\s*\\(${escapeRegex(c.license_number)}\\)\\s*$`), "");
  return stripped ? <> — {stripped}</> : null;
}

function escapeRegex(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function formatValue(v: unknown): string {
  if (v === null || v === undefined) return "(empty)";
  if (Array.isArray(v)) return v.length ? v.join(", ") : "(empty)";
  return String(v);
}

function formatRelative(iso: string): string {
  const then = new Date(iso).getTime();
  const now = Date.now();
  const seconds = Math.max(0, (now - then) / 1000);
  if (seconds < 60) return "just now";
  if (seconds < 3600) return `${Math.floor(seconds / 60)} min ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)} h ago`;
  return `${Math.floor(seconds / 86400)} d ago`;
}

// License number prefix encodes the broad license type in OLCC's scheme.
// 010 = Lab, 020 = Producer, 030 = Processor, 040 = Wholesaler,
// 050 = Retailer, 060 = (variant), 330 = Hemp.
function guessLicenseTypeFromNumber(n: string): string {
  const prefix = n.slice(0, 3);
  switch (prefix) {
    case "010": return "Laboratory";
    case "020": return "Producer";
    case "030": return "Processor";
    case "040": return "Wholesaler";
    case "050": return "Retailer";
    case "060": return "Wholesaler/Other";
    case "330": return "Hemp";
    default: return "Other";
  }
}

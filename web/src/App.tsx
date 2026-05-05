import { useEffect, useMemo, useState } from "react";
import type { Change, ChangesPayload } from "./types";

const ALL = "__all__";
const VALID_WINDOWS = [30, 90, 180] as const;
type WindowDays = (typeof VALID_WINDOWS)[number];

const REPO_URL = "https://github.com/markpernotto/oregon-cannabis-license-watch";
const SITE_URL = "https://oregon-cannabis-license-watch.vercel.app";
const SNAPSHOT_BASE = `${REPO_URL}/blob/main/data/snapshots`;
void SITE_URL; // available if we want canonical-URL meta later

function readWindowFromUrl(): WindowDays {
  if (typeof window === "undefined") return 30;
  const params = new URLSearchParams(window.location.search);
  const v = Number(params.get("window"));
  return (VALID_WINDOWS as readonly number[]).includes(v) ? (v as WindowDays) : 30;
}

function writeWindowToUrl(w: WindowDays) {
  const params = new URLSearchParams(window.location.search);
  params.set("window", String(w));
  window.history.replaceState({}, "", `?${params.toString()}${window.location.hash}`);
}

export default function App() {
  const [data, setData] = useState<ChangesPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [licenseTypeFilter, setLicenseTypeFilter] = useState(ALL);
  const [changeTypeFilter, setChangeTypeFilter] = useState(ALL);
  const [search, setSearch] = useState("");
  const [windowDays, setWindowDays] = useState<WindowDays>(readWindowFromUrl);

  useEffect(() => {
    fetch("/changes.json")
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json() as Promise<ChangesPayload>;
      })
      .then(setData)
      .catch((e) => setError(String(e)));
  }, []);

  const cutoffMs = useMemo(
    () => Date.now() - windowDays * 86_400_000,
    [windowDays],
  );

  const inWindow = useMemo(() => {
    if (!data) return [];
    return data.changes.filter(
      (c) => new Date(c.observed_at).getTime() >= cutoffMs,
    );
  }, [data, cutoffMs]);

  const licenseTypes = useMemo(() => {
    const set = new Set<string>();
    for (const c of inWindow) {
      const lt = guessLicenseTypeFromNumber(c.license_number);
      if (lt) set.add(lt);
    }
    return Array.from(set).sort();
  }, [inWindow]);

  const changeTypes = useMemo(() => {
    const set = new Set(inWindow.map((c) => c.change_type));
    return Array.from(set).sort();
  }, [inWindow]);

  const filtered = useMemo(() => {
    const needle = search.trim().toLowerCase();
    return inWindow.filter((c) => {
      if (changeTypeFilter !== ALL && c.change_type !== changeTypeFilter) return false;
      if (licenseTypeFilter !== ALL) {
        const lt = guessLicenseTypeFromNumber(c.license_number);
        if (lt !== licenseTypeFilter) return false;
      }
      if (needle && !c.summary.toLowerCase().includes(needle)) return false;
      return true;
    });
  }, [inWindow, changeTypeFilter, licenseTypeFilter, search]);

  const handleWindowChange = (w: WindowDays) => {
    setWindowDays(w);
    writeWindowToUrl(w);
  };

  return (
    <main>
      <header>
        <h1>Oregon Cannabis License Watch</h1>
        <p>Daily change feed from the OLCC Cannabis Licensee public report.</p>

        <details className="about">
          <summary>What is this?</summary>
          <p>
            Oregon publishes a list of every business licensed to grow, process,
            sell, or test cannabis. The list shows what's true <em>right now</em>;
            it doesn't keep history. This project takes a snapshot every night,
            compares it to yesterday's, and publishes what changed — new
            licenses, removed licenses, name updates, expiration renewals.
          </p>
          <p>
            Each row below is one change. Every change carries provenance
            (which snapshot it came from, when, with a checksum) so you can
            verify it independently. The same data is available as{" "}
            <a href={REPO_URL}>open-source code</a>, raw{" "}
            <a href="/changes.json">JSON</a>, and an{" "}
            <a href="/rss.xml">RSS feed</a>.
          </p>
        </details>

        {data && (
          <div className="meta">
            <a className="rss-cta" href="/rss.xml" title="Subscribe in any RSS reader (Feedly, Inoreader, NetNewsWire, etc.)">
              <span aria-hidden="true">📡</span> Subscribe via RSS
            </a>
            <span title={`Source pulled at ${data.generated_at}`}>
              Data is {formatStaleness(data.generated_at)} old
            </span>
            <span>
              <a href="/changes.json">JSON</a>
              {" · "}
              <a href={REPO_URL}>Source on GitHub</a>
            </span>
          </div>
        )}
      </header>

      {!data && !error && <div className="loading">Loading…</div>}
      {error && <div className="error">Failed to load changes: {error}</div>}

      {data && (
        <>
          <div className="window-toggle">
            <span className="window-toggle-label">Window:</span>
            {VALID_WINDOWS.map((w) => (
              <button
                key={w}
                type="button"
                onClick={() => handleWindowChange(w)}
                className={w === windowDays ? "active" : ""}
                aria-pressed={w === windowDays}
              >
                {w} days
              </button>
            ))}
          </div>

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
            Showing <strong>{filtered.length}</strong> of {inWindow.length} changes
            in the last {windowDays} days
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
        <p>
          Data from the{" "}
          <a href="https://www.oregon.gov/olcc" target="_blank" rel="noopener noreferrer">
            Oregon Liquor and Cannabis Commission
          </a>
          . Republished under{" "}
          <a href="https://creativecommons.org/publicdomain/zero/1.0/" target="_blank" rel="noopener noreferrer">
            CC0
          </a>
          .{" "}
          <a href={REPO_URL} target="_blank" rel="noopener noreferrer">
            Source on GitHub
          </a>
          .
        </p>
        <p>
          Need history beyond 180 days?{" "}
          <a href={`${REPO_URL}/issues/new`} target="_blank" rel="noopener noreferrer">
            Open an issue
          </a>{" "}
          — the underlying database keeps everything; the public window is
          just the rolling view.
        </p>
      </footer>
    </main>
  );
}

function ChangeRow({ change }: { change: Change }) {
  const cls = change.change_type.toLowerCase();
  const sourceUrl = `${SNAPSHOT_BASE}/${change.snapshot_date}.csv`;
  const displayName = change.trade_name || change.legal_name;
  return (
    <li className="change-card">
      <span className={`change-type ${cls}`}>{change.change_type}</span>
      <div className="change-summary">
        {displayName && <span className="change-name">{displayName}</span>}
        <span className="change-detail">
          {change.legal_name && change.trade_name && change.legal_name !== change.trade_name && (
            <span className="change-legal" title="Legal entity name">
              {change.legal_name}
              {" · "}
            </span>
          )}
          {change.county && <span>{change.county} County · </span>}
          <code>{change.license_number}</code>
          {change.field_name ? (
            <>
              {" "}— {change.field_name}: {formatValue(change.prev_value)} → {formatValue(change.new_value)}
            </>
          ) : (
            renderNewRemovedSummary(change)
          )}
        </span>
      </div>
      <div className="change-meta">
        <span className="change-date">{change.snapshot_date}</span>
        <a
          className="change-source"
          href={sourceUrl}
          target="_blank"
          rel="noopener noreferrer"
          title={`View the source CSV for ${change.snapshot_date} on GitHub`}
        >
          source
        </a>
      </div>
    </li>
  );
}

function renderNewRemovedSummary(c: Change): React.ReactNode {
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

function formatStaleness(iso: string): string {
  const then = new Date(iso).getTime();
  const now = Date.now();
  const seconds = Math.max(0, (now - then) / 1000);
  if (seconds < 60) return "less than a minute";
  if (seconds < 3600) return `${Math.floor(seconds / 60)} min`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)} h`;
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  return hours ? `${days} d ${hours} h` : `${days} d`;
}

// License number prefix encodes the broad license type in OLCC's scheme.
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

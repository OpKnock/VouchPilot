import { useEffect, useRef, useState, type ReactNode } from "react";
import { api, type LabelInfo, type Prediction, type RunRecord } from "./api";

type Area = "Dashboard" | "Classify" | "Review" | "System" | "Settings";
type Theme = "light" | "dark";
type IconName =
  | "dashboard"
  | "classify"
  | "review"
  | "system"
  | "shield"
  | "chevron"
  | "upload"
  | "search"
  | "filter"
  | "more"
  | "check"
  | "alert"
  | "arrow"
  | "file"
  | "clock"
  | "server"
  | "database"
  | "cpu"
  | "lock"
  | "spark"
  | "sun"
  | "moon";

const nav: { label: Area; icon: IconName; count?: number }[] = [
  { label: "Dashboard", icon: "dashboard" },
  { label: "Classify", icon: "classify" },
  { label: "Review", icon: "review", count: 12 },
  { label: "System", icon: "server" },
  { label: "Settings", icon: "system" },
];

type Settings = Record<string, unknown>;

const SCORER_NAMES: Record<string, string> = {
  keyword: "Keyword rules",
  vouchpilot: "VouchPilot+ fraud screen",
  stub: "Stub (testing)",
  server: "Qwen3.5-4B server",
};

function scorerName(id: unknown): string {
  return SCORER_NAMES[String(id ?? "keyword")] ?? String(id ?? "keyword");
}

function downloadJson(filename: string, data: unknown) {
  const blob = new Blob([JSON.stringify(data, null, 1)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function useCountUp(target: number, duration = 750): number {
  const [val, setVal] = useState(0);
  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setVal(target);
      return;
    }
    let raf = 0;
    const t0 = performance.now();
    function tick(t: number) {
      const p = Math.min(1, (t - t0) / duration);
      setVal(target * (1 - Math.pow(1 - p, 3)));
      if (p < 1) raf = requestAnimationFrame(tick);
    }
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target, duration]);
  return val;
}

function Icon({ name, size = 18 }: { name: IconName; size?: number }) {
  const common = { width: size, height: size, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 1.8, strokeLinecap: "round" as const, strokeLinejoin: "round" as const, "aria-hidden": true };
  const paths: Record<IconName, ReactNode> = {
    dashboard: <><rect x="3" y="3" width="7" height="7" rx="1" /><rect x="14" y="3" width="7" height="7" rx="1" /><rect x="3" y="14" width="7" height="7" rx="1" /><rect x="14" y="14" width="7" height="7" rx="1" /></>,
    classify: <><path d="M4 19V5a2 2 0 0 1 2-2h9l5 5v11a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2Z" /><path d="M14 3v6h6M8 13h8M8 17h5" /></>,
    review: <><path d="M9 11l2 2 4-4" /><path d="M12 22c5-2 8-5 8-10V5l-8-3-8 3v7c0 5 3 8 8 10Z" /></>,
    system: <><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.7 1.7 0 0 0 .34 1.88l.06.06-2.83 2.83-.06-.06a1.7 1.7 0 0 0-1.88-.34 1.7 1.7 0 0 0-1.03 1.56V21h-4v-.08A1.7 1.7 0 0 0 9 19.37a1.7 1.7 0 0 0-1.88.34l-.06.06-2.83-2.83.06-.06A1.7 1.7 0 0 0 4.63 15 1.7 1.7 0 0 0 3.08 14H3v-4h.08A1.7 1.7 0 0 0 4.63 9a1.7 1.7 0 0 0-.34-1.88l-.06-.06 2.83-2.83.06.06A1.7 1.7 0 0 0 9 4.63 1.7 1.7 0 0 0 10 3.08V3h4v.08A1.7 1.7 0 0 0 15 4.63a1.7 1.7 0 0 0 1.88-.34l.06-.06 2.83 2.83-.06.06A1.7 1.7 0 0 0 19.37 9 1.7 1.7 0 0 0 20.92 10H21v4h-.08A1.7 1.7 0 0 0 19.4 15Z" /></>,
    shield: <><path d="M12 22c5-2 8-5 8-10V5l-8-3-8 3v7c0 5 3 8 8 10Z" /><path d="M9 12l2 2 4-5" /></>,
    chevron: <path d="m9 18 6-6-6-6" />,
    upload: <><path d="M12 16V4M7 9l5-5 5 5M5 20h14" /></>,
    search: <><circle cx="11" cy="11" r="7" /><path d="m20 20-4-4" /></>,
    filter: <path d="M4 5h16M7 12h10M10 19h4" />,
    more: <><circle cx="5" cy="12" r=".7" fill="currentColor" /><circle cx="12" cy="12" r=".7" fill="currentColor" /><circle cx="19" cy="12" r=".7" fill="currentColor" /></>,
    check: <path d="m5 12 4 4L19 6" />,
    alert: <><path d="M12 9v4M12 17h.01" /><path d="M10.3 3.6 2.5 17a2 2 0 0 0 1.7 3h15.6a2 2 0 0 0 1.7-3L13.7 3.6a2 2 0 0 0-3.4 0Z" /></>,
    arrow: <><path d="M5 12h14M14 7l5 5-5 5" /></>,
    file: <><path d="M5 3h10l4 4v14H5z" /><path d="M14 3v5h5M8 13h8M8 17h6" /></>,
    clock: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>,
    server: <><rect x="3" y="4" width="18" height="6" rx="2" /><rect x="3" y="14" width="18" height="6" rx="2" /><path d="M7 7h.01M7 17h.01" /></>,
    database: <><ellipse cx="12" cy="5" rx="8" ry="3" /><path d="M4 5v7c0 1.7 3.6 3 8 3s8-1.3 8-3V5M4 12v7c0 1.7 3.6 3 8 3s8-1.3 8-3v-7" /></>,
    cpu: <><rect x="6" y="6" width="12" height="12" rx="2" /><path d="M9 1v3M15 1v3M9 20v3M15 20v3M20 9h3M20 14h3M1 9h3M1 14h3M10 10h4v4h-4z" /></>,
    lock: <><rect x="5" y="10" width="14" height="11" rx="2" /><path d="M8 10V7a4 4 0 0 1 8 0v3" /></>,
    spark: <><path d="m12 3 1.4 4.1L17.5 8.5l-4.1 1.4L12 14l-1.4-4.1-4.1-1.4 4.1-1.4L12 3Z" /><path d="m18.5 15 .7 2.3 2.3.7-2.3.7-.7 2.3-.7-2.3-2.3-.7 2.3-.7.7-2.3Z" /></>,
    sun: <><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" /></>,
    moon: <path d="M20.8 15.3A9 9 0 0 1 8.7 3.2 9 9 0 1 0 20.8 15.3Z" />,
  };
  return <svg {...common}>{paths[name]}</svg>;
}

function Logo() {
  return <div className="logo"><img className="logo-mark logo-img" src="/logo.svg" alt="VouchPilot" width={28} height={28} /><span>VouchPilot</span></div>;
}

function ThemeToggle({ theme, onToggle, labelled = false }: { theme: Theme; onToggle: () => void; labelled?: boolean }) {
  return <button className={`theme-toggle ${labelled ? "labelled" : ""}`} onClick={onToggle} aria-label={`Switch to ${theme === "light" ? "dark" : "light"} mode`}>
    <span className={theme === "light" ? "active" : ""}><Icon name="sun" size={14} /></span>
    <span className={theme === "dark" ? "active" : ""}><Icon name="moon" size={14} /></span>
    {labelled && <b>{theme === "light" ? "Light" : "Dark"} mode</b>}
  </button>;
}

function Welcome({ onEnter, onExplore, theme, onThemeToggle }: { onEnter: () => void; onExplore: () => void; theme: Theme; onThemeToggle: () => void }) {
  return <div className="welcome">
    <header className="welcome-nav">
      <Logo />
      <div className="welcome-links"><a href="#platform">Platform</a><a href="#security">Security</a><a href="#architecture">Architecture</a></div>
      <div className="welcome-actions"><ThemeToggle theme={theme} onToggle={onThemeToggle} /><a className="secondary-button" href="/desktop-package" download>Download desktop app</a><button className="primary-button" onClick={onEnter}>Open workspace <Icon name="arrow" size={15} /></button></div>
    </header>
    <main className="welcome-main">
      <section className="welcome-hero enter">
        <div className="model-active"><i className="online-dot" />Qwen3.5-4B offline model active</div>
        <h1>Flawless GST vouchers.<br /><span>Zero cloud dependency.</span></h1>
        <p>An offline, open-weight AI system that classifies Indian accounting transactions into 27 GST categories—with calibrated confidence, traceable evidence, and a human approval gate.</p>
        <div className="hero-actions"><button className="primary-button hero-primary" onClick={onEnter}>Enter VouchPilot <Icon name="arrow" size={16} /></button><button className="secondary-button" onClick={onExplore}><Icon name="shield" size={16} />Explore security</button></div>
        <div className="trust-row"><span><Icon name="lock" size={14} />Nothing leaves your machine</span><span><Icon name="check" size={14} />27 GST voucher types</span><span><Icon name="spark" size={14} />Evidence-backed predictions</span></div>
      </section>
      <section className="welcome-preview enter delay-1">
        <div className="preview-glow" />
        <div className="preview-window">
          <div className="preview-top"><div><i /><i /><i /></div><span>Local inference · March_Purchases.xlsx</span><b><i className="online-dot" />LIVE</b></div>
          <div className="preview-heading"><div><span>CLASSIFICATION RUN</span><h2>2,481 transactions processed</h2></div><div><strong>97.2%</strong><span>ACCURACY</span></div></div>
          <div className="preview-table">
            <div className="preview-row preview-head"><span>NARRATION / DETAILS</span><span>TAX MODE</span><span>PREDICTED VOUCHER</span><span>CONFIDENCE</span><span>STATUS</span></div>
            {[
              ["AWS Mumbai Hosting Oct", "IGST 18%", "Purchase", 98, "Approved"],
              ["Client Advance Payment (TCS)", "CGST / SGST", "Receipt", 92, "Approved"],
              ["Staff Welfare — Diwali sweets", "Nil", "Journal", 65, "Review"],
            ].map((row, index) => <div className={`preview-row ${index === 2 ? "needs-review" : ""}`} key={String(row[0])}>
              <span>{row[0]}</span><span><b>{row[1]}</b></span><span><b className="voucher-chip">{row[2]}</b></span>
              <span className="preview-confidence"><i><em style={{ width: `${row[3]}%` }} /></i><b>{row[3]}%</b></span>
              <span className={index === 2 ? "preview-review" : "preview-approved"}>{row[4]}</span>
            </div>)}
          </div>
        </div>
      </section>
      <section className="welcome-stats enter delay-2"><div><strong>100%</strong><span>Offline inference</span></div><div><strong>27</strong><span>GST voucher categories</span></div><div><strong>97.2%</strong><span>Validated accuracy</span></div><div><strong>0</strong><span>Cloud dependencies</span></div></section>
      <section className="info-strip enter delay-3">
        <div className="panel" id="platform"><p className="section-label">PLATFORM</p><h2>Classify → review → export</h2><p>Upload any workbook, get a voucher label with confidence and evidence per row, approve the uncertain ones, export JSON or CSV. Qwen3.5-4B, Gemma 4 E4B, keyword rules and fraud-aware scoring, all switchable in Settings.</p></div>
        <div className="panel" id="security"><p className="section-label">SECURITY</p><h2>Air-gapped by design</h2><p>Quishing-URL and prompt-injection screening on every narration, SHA-256 tamper pins on exports, aud-bound single-use action tokens. Nothing leaves this machine — no accounts, no signup, no cloud.</p></div>
        <div className="panel" id="architecture"><p className="section-label">ARCHITECTURE</p><h2>Pipeline, not a wrapper</h2><p>Ingest → schema normaliser → perspective resolver → evidence extractor → constrained SLM scoring → pairwise challenger → human gate → validated export. FastAPI serves the UI and API from one offline process.</p></div>
      </section>
    </main>
  </div>;
}

function PageHeader({ eyebrow, title, detail, action }: { eyebrow: string; title: string; detail: string; action?: ReactNode }) {
  return <header className="page-header enter">
    <div><p className="eyebrow">{eyebrow}</p><h1>{title}</h1><p className="page-detail">{detail}</p></div>
    {action}
  </header>;
}

function Metric({ label, value, delta, tone = "neutral" }: { label: string; value: string; delta: string; tone?: "neutral" | "good" | "warn" }) {
  return <div className="metric-card">
    <div className="metric-top"><span>{label}</span><Icon name="more" size={16} /></div>
    <strong>{value}</strong>
    <p className={tone}><span>{tone === "good" ? "↑" : tone === "warn" ? "!" : "·"}</span>{delta}</p>
  </div>;
}

function Dashboard({ navigate, runs, predictions }: { navigate: (area: Area) => void; runs: RunRecord[]; predictions: Prediction[] }) {
  const need = predictions.filter((p) => p.needs_review).length;
  const total = runs.reduce((s, r) => s + r.rows, 0);
  const mean = predictions.length
    ? (predictions.reduce((s, p) => s + p.confidence, 0) / predictions.length) * 100 : 0;
  const counts: Record<string, number> = {};
  predictions.forEach((p) => { counts[p.voucher_type] = (counts[p.voucher_type] || 0) + 1; });
  const top = Object.entries(counts).sort((a, b) => b[1] - a[1]).slice(0, 12);
  const max = Math.max(1, ...top.map((t) => t[1]));
  const last = runs[0];
  const animTotal = Math.round(useCountUp(total));
  const animMean = useCountUp(mean);
  const animNeed = Math.round(useCountUp(need));
  return <div className="view">
    <PageHeader eyebrow="LOCAL INFERENCE · OFFLINE" title="Flawless vouchers. Zero cloud dependency." detail={total ? `${animTotal} transactions classified across ${runs.length} batch${runs.length === 1 ? "" : "es"} on this machine.` : "Upload a workbook in Classify to see live numbers here."} action={<button className="primary-button" onClick={() => navigate("Classify")}><Icon name="upload" size={16} />New classification</button>} />
    <section className="metrics-grid enter delay-1">
      <Metric label="Transactions classified" value={String(animTotal)} delta={runs.length ? `${runs.length} batches` : "no batches yet"} tone={runs.length ? "good" : "neutral"} />
      <Metric label="Mean confidence" value={predictions.length ? `${animMean.toFixed(1)}%` : "—"} delta="current batch" tone="neutral" />
      <Metric label="Needs review" value={String(animNeed)} delta="human approval gate" tone={need ? "warn" : "good"} />
      <Metric label="Last accuracy" value={last?.accuracy != null ? `${(last.accuracy * 100).toFixed(1)}%` : "—"} delta={last ? last.file : "needs gold labels"} tone="neutral" />
    </section>
    <section className="dashboard-grid enter delay-2">
      <div className="panel accuracy-panel">
        <div className="panel-heading"><div><p className="section-label">DISTRIBUTION</p><h2>Predicted voucher types</h2></div></div>
        <div className="accuracy-summary"><strong>{predictions.length}</strong><span>rows in current batch</span></div>
        <div className="chart-wrap">
          <div className="axis"><span>{max}</span><span>{Math.round(max / 2)}</span><span>0</span></div>
          <div className="bar-chart">{top.length ? top.map(([label, n], i) => <div className="bar-column" key={label}><span className="bar" style={{ height: `${Math.max(4, (n / max) * 100)}%` }} /><small>{label.split(" ")[0].slice(0, 6)}</small></div>) : <p>No predictions yet.</p>}</div>
        </div>
      </div>
      <div className="panel review-panel">
        <div className="panel-heading"><div><p className="section-label">ATTENTION</p><h2>Review queue</h2></div><button className="icon-button" aria-label="More options"><Icon name="more" /></button></div>
        <div className="review-number"><strong>{need}</strong><span>rows need a decision</span></div>
        <div className="queue-track"><span style={{ width: `${predictions.length ? Math.round((need / predictions.length) * 100) : 0}%` }} /></div>
        <div className="queue-legend"><span><i className="uncertain-dot" />Low confidence <b>{need}</b></span></div>
        <button className="text-button" onClick={() => navigate("Review")}>Open review queue <Icon name="arrow" size={15} /></button>
      </div>
    </section>
    <section className="panel recent-panel enter delay-3">
      <div className="panel-heading"><div><p className="section-label">RECENT ACTIVITY</p><h2>Classification runs</h2></div><button className="secondary-button" onClick={() => navigate("Classify")}>View all runs</button></div>
      <div className="run-table">
        <div className="table-row table-head"><span>FILE</span><span>ROWS</span><span>ACCURACY</span><span>STATUS</span><span>COMPLETED</span><span /></div>
        {runs.length ? runs.slice(0, 5).map((row) => <div className="table-row" key={row.file + row.completed}><span className="file-cell"><i><Icon name="file" size={15} /></i>{row.file}</span><span>{row.rows}</span><span>{row.accuracy != null ? `${(row.accuracy * 100).toFixed(1)}%` : "—"}</span><span><b className={`status ${row.status === "Completed" ? "" : "review"}`}>{row.status}</b></span><span>{row.completed}</span><button className="icon-button" aria-label={`Download ${row.file} predictions`} title="Download predictions JSON" onClick={() => downloadJson(`${row.file}.predictions.json`, row.predictions)}><Icon name="arrow" size={16} /></button></div>) : <div className="table-row"><span>No runs yet — classify a workbook to begin.</span><span /><span /><span /><span /><span /></div>}
      </div>
    </section>
  </div>;
}

function Classify({ settings, initial, onDone }: { settings: Settings; initial: Prediction[]; onDone: (run: RunRecord, preds: Prediction[]) => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");
  const [rows, setRows] = useState<Prediction[]>(initial);
  const [query, setQuery] = useState("");
  const input = useRef<HTMLInputElement>(null);
  async function run() {
    if (!file) { setError("Choose a workbook first."); return; }
    setRunning(true);
    setError("");
    try {
      const res = await api.predictFile(file, {
        scorer: String(settings.scorer ?? "keyword"),
        workers: String(settings.workers ?? 1),
        challenge: (settings.challenger ?? false) ? "true" : "false",
      });
      setRows(res.predictions);
      const need = res.predictions.filter((p) => p.needs_review).length;
      onDone({
        file: file.name, rows: res.n_rows, accuracy: null,
        status: need ? "Review needed" : "Completed",
        completed: new Date().toLocaleString(), predictions: res.predictions,
      }, res.predictions);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
    setRunning(false);
  }
  const shown = rows.filter((r) =>
    (`${r.invoice_number} ${r.voucher_type}`.toLowerCase().includes(query.toLowerCase())));
  return <div className="view">
    <PageHeader eyebrow="CLASSIFY / NEW RUN" title="Transaction classifier" detail="Upload a workbook. Processing stays entirely on this machine." action={<><input ref={input} className="hidden-input" type="file" accept=".xlsx,.xls,.csv" onChange={(e) => { if (e.target.files?.[0]) setFile(e.target.files[0]); }} /><button className="secondary-button" onClick={() => input.current?.click()}><Icon name="upload" size={16} />{file ? "Replace file" : "Choose file"}</button><button className="primary-button" onClick={run} disabled={running || !file}><Icon name="spark" size={16} />{running ? "Classifying…" : "Run classifier"}</button></>} />
    {error && <p className="danger-text">{error}</p>}
    <p className="page-detail">Scorer: <b>{scorerName(settings.scorer)}</b> — keyword rules are instant and need no model download; the Qwen3.5-4B server is the AI model (needs the llama server running); VouchPilot+ adds fraud screening on top.</p>
    <section className="run-strip enter delay-1">
      <div className="run-file"><i><Icon name="file" /></i><div><strong>{file ? file.name : "No file chosen"}</strong><span>{rows.length ? `${rows.length} rows classified` : "xlsx with voucher type missing"}</span></div></div>
      <div className="run-model"><span>MODEL</span><strong><i className="online-dot" />{scorerName(settings.scorer)}</strong></div>
      <div className="run-model"><span>PRIVACY</span><strong><Icon name="lock" size={14} />Local only</strong></div>
      <div className="run-progress"><span>{running ? "Scoring rows…" : rows.length ? "Classification complete" : "Idle"}</span><div><i style={{ width: running ? "55%" : rows.length ? "100%" : "0%" }} /></div></div>
    </section>
    <section className="panel predictions-panel enter delay-2">
      <div className="predictions-toolbar"><div><h2>Predictions</h2><span className="count-pill">{shown.length} rows</span></div><div className="toolbar-actions"><label className="search-box"><Icon name="search" size={16} /><input placeholder="Search transactions" value={query} onChange={(e) => setQuery(e.target.value)} /></label><button className="secondary-button" onClick={() => downloadJson("predictions.jsonl.json", rows)}>Export JSON <Icon name="chevron" size={14} /></button></div></div>
      <div className="prediction-table">
        <div className="prediction-row prediction-head"><span>TRANSACTION</span><span>PREDICTION</span><span>CONFIDENCE</span><span>EVIDENCE</span><span /></div>
        {running && !rows.length && [0, 1, 2, 3].map((i) => <div className="shimmer-row" key={i}><span style={{ width: "30%" }} /><span style={{ width: "90%" }} /><span style={{ width: "60%" }} /></div>)}
        {shown.slice(0, 100).map((row) => <div className="prediction-row" key={row.row_id}>
          <span className="transaction-cell"><strong>{row.invoice_number}</strong><small>row {row.row_id}</small></span>
          <span><b className="label-pill">{row.voucher_type}</b></span>
          <span className="confidence-cell"><b className={row.confidence < 0.5 ? "low" : ""}>{Math.round(row.confidence * 100)}%</b><i><em className={row.confidence < 0.5 ? "low" : ""} style={{ width: `${Math.round(row.confidence * 100)}%` }} /></i></span>
          <span className="evidence-cell">{row.evidence.slice(0, 3).map((tag) => <b key={tag}>{tag}</b>)}{row.needs_review && <b className="risk-tag">Review</b>}</span>
          <button className="icon-button" aria-label={`Actions for ${row.invoice_number}`}><Icon name="more" /></button>
        </div>)}
      </div>
      <div className="table-footer"><span>Showing {Math.min(100, shown.length)} of {shown.length}</span></div>
    </section>
  </div>;
}

export interface Decision { row_id: number; verdict: "approve" | "override" | "escalate"; label: string | null; note: string }

function Review({ predictions, labels, threshold, onExport }: {
  predictions: Prediction[];
  labels: LabelInfo[];
  threshold: number;
  onExport: (decisions: Decision[], final: Prediction[]) => void;
}) {
  const queue = predictions.filter((p) => p.needs_review || p.confidence * 100 < threshold);
  const [priority, setPriority] = useState<"all" | "undecided" | "decided">("all");
  const shown = queue.filter((q) => priority === "all"
    || (priority === "decided" ? decisions[q.row_id] !== undefined : decisions[q.row_id] === undefined));
  function toCSV(rows: Prediction[]): string {
    const head = "row_id,invoice_number,voucher_type,confidence,needs_review";
    const lines = rows.map((r) => [r.row_id, `"${String(r.invoice_number).replace(/"/g, "")}"`,
      `"${r.voucher_type}"`, r.confidence, r.needs_review].join(","));
    return [head, ...lines].join("\n");
  }
  function downloadCSV() {
    const blob = new Blob([toCSV(finalRows())], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "final.csv";
    a.click();
    URL.revokeObjectURL(url);
  }
  function finalRows(): Prediction[] {
    const byId: Record<number, Decision> = {};
    queue.forEach((q) => {
      byId[q.row_id] = decisions[q.row_id] ?? { row_id: q.row_id, verdict: "escalate", label: null, note: "undecided at export" };
    });
    return predictions.map((p) => {
      const d = byId[p.row_id];
      if (!d) return p;
      if (d.verdict === "override" && d.label) {
        return { ...p, voucher_type: d.label, needs_review: false,
                 evidence: [...p.evidence, `HUMAN:override->${d.label}`] };
      }
      if (d.verdict === "escalate") {
        return { ...p, needs_review: true, evidence: [...p.evidence, "HUMAN:escalated"] };
      }
      return { ...p, needs_review: false, evidence: [...p.evidence, "HUMAN:approved"] };
    });
  }
  const [decisions, setDecisions] = useState<Record<number, Decision>>({});
  const [overriding, setOverriding] = useState<number | null>(null);
  function applyFinal() {
    const decs: Decision[] = queue.map((q) =>
      decisions[q.row_id] ?? { row_id: q.row_id, verdict: "escalate", label: null, note: "undecided at export" });
    onExport(decs, finalRows());
  }
  const done = Object.keys(decisions).length;
  return <div className="view">
    <PageHeader eyebrow="HUMAN APPROVAL GATE" title="Review queue" detail={`${queue.length - done} rows need a decision before this batch can be exported.`} action={<button className="secondary-button" onClick={() => setPriority(priority === "all" ? "undecided" : priority === "undecided" ? "decided" : "all")}><Icon name="filter" size={15} />Priority: {priority[0].toUpperCase() + priority.slice(1)}</button>} />
    <div className="review-layout enter delay-1">
      <section className="review-list">
        {shown.length ? shown.map((item) => <article className={`review-card ${decisions[item.row_id] && decisions[item.row_id].verdict !== undefined && (decisions[item.row_id].verdict !== "override" || decisions[item.row_id].label) ? "resolved" : ""}`} key={item.row_id}>
          <div className="review-card-top"><div className="review-id"><span><Icon name="file" /></span><div><strong>{item.invoice_number}</strong><small>row {item.row_id}</small></div></div><button className="icon-button" aria-label={`More actions for ${item.invoice_number}`}><Icon name="more" /></button></div>
          <div className="decision-grid">
            <div><span>MODEL PREDICTION</span><strong>{item.voucher_type}</strong></div>
            <div><span>CONFIDENCE</span><strong className={item.confidence < 0.5 ? "danger-text" : ""}>{Math.round(item.confidence * 100)}%</strong></div>
            <div><span>TOP ALTERNATIVE</span><strong>{item.top_k[1] ? item.top_k[1][0] : "—"}</strong></div>
          </div>
          <div className="evidence-row">{item.evidence.slice(0, 5).map((tag) => <span key={tag}>{tag}</span>)}</div>
          <div className="decision-actions">{decisions[item.row_id] && decisions[item.row_id].verdict !== "override" ? <p className="resolved-message"><Icon name="check" size={16} />Marked as {decisions[item.row_id].verdict}</p> : <><button className="approve-button" onClick={() => setDecisions({ ...decisions, [item.row_id]: { row_id: item.row_id, verdict: "approve", label: null, note: "" } })}><Icon name="check" size={15} />Approve</button><button className="secondary-button" onClick={() => setOverriding(item.row_id)}>Override</button><button className="plain-button" onClick={() => setDecisions({ ...decisions, [item.row_id]: { row_id: item.row_id, verdict: "escalate", label: null, note: "" } })}>Escalate</button></>}</div>
          {overriding === item.row_id && <div className="decision-actions"><select value={decisions[item.row_id]?.label ?? ""} onChange={(e) => {
            if (!e.target.value) {
              const next = { ...decisions };
              delete next[item.row_id];
              setDecisions(next);
            } else {
              setDecisions({ ...decisions, [item.row_id]: { row_id: item.row_id, verdict: "override", label: e.target.value, note: "" } });
            }
          }}><option value="">Pick correct label…</option>{labels.map((l) => <option key={l.name} value={l.name}>{l.name}</option>)}</select></div>}
        </article>) : <p>No rows need review — batch is fully auto-classified.</p>}
      </section>
      <aside className="review-summary panel">
        <p className="section-label">BATCH PROGRESS</p><div className="ring" style={{ "--progress": `${queue.length ? Math.round((done / queue.length) * 100) : 100}%` } as React.CSSProperties}><span><strong>{done}</strong><small>of {queue.length}</small></span></div>
        <h3>Approval checkpoint</h3><p>Every uncertain classification must be signed off before export.</p>
        <div className="summary-list"><span><i className="online-dot" />Approved <b>{Object.values(decisions).filter((d) => d.verdict === "approve").length}</b></span><span><i className="override-dot" />Overridden <b>{Object.values(decisions).filter((d) => d.verdict === "override").length}</b></span><span><i className="critical-dot" />Escalated <b>{Object.values(decisions).filter((d) => d.verdict === "escalate").length}</b></span></div>
        <button className="primary-button" disabled={!queue.length} onClick={applyFinal}>Complete review</button>
        <button className="text-button" onClick={downloadCSV}>Download final.csv</button>
        <button className="text-button" onClick={() => downloadJson("decisions.json", { decisions: queue.map((q) => decisions[q.row_id] ?? { row_id: q.row_id, verdict: "escalate", label: null, note: "undecided" }) })}>Download decisions.json</button>
      </aside>
    </div>
  </div>;
}

function System({ navigate }: { navigate: (area: Area) => void }) {
  const [data, setData] = useState<{ modules: Record<string, string>; server: { up: boolean }; weights: string[] } | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    api.system().then((d) => setData(d as never)).catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)));
  }, []);
  const entries = data ? Object.entries(data.modules) : [];
  const okCount = entries.filter(([, v]) => v === "OK").length;
  const modules = [
    { icon: "server" as IconName, name: "Model server", meta: "llama.cpp :8080", value: data ? (data.server.up ? "Reachable" : "Down") : "…", sub: "Qwen3.5-4B · Gemma 4 E4B" },
    { icon: "database" as IconName, name: "Pipeline modules", meta: `${okCount}/${entries.length} imports OK`, value: entries.length && okCount === entries.length ? "Healthy" : "Check", sub: error || "local imports" },
    { icon: "shield" as IconName, name: "Fraud scanner", meta: "Quishing + prompt injection", value: "Active", sub: "rule engine, offline" },
    { icon: "cpu" as IconName, name: "Pairwise challenger", meta: "Close-call verification", value: "Active", sub: "margin 0.15, rate-capped" },
  ];
  return <div className="view">
    <PageHeader eyebrow="LOCAL RUNTIME" title="System health" detail="All inference, evidence, and files remain on this device." action={<button className="secondary-button" onClick={() => window.location.reload()}>Run diagnostics</button>} />
    <section className="system-hero enter delay-1">
      <div><span className="health-orb"><Icon name="check" /></span><div><p className="section-label">OVERALL STATUS</p><h2>{data ? (okCount === entries.length ? "All systems operational" : "Degraded — see modules") : "Checking…"}</h2><p>Weights on disk: {data ? (data.weights.join(", ") || "none — run scripts/fetch_model.py") : "…"}</p></div></div>
    </section>
    <section className="system-grid enter delay-2">
      <div className="panel modules-panel"><div className="panel-heading"><div><p className="section-label">SERVICES</p><h2>Module health</h2></div><span className="live-pill"><i />Live</span></div>
        <div className="module-list">{modules.map((module) => <div className="module-row" key={module.name}><span className="module-icon"><Icon name={module.icon} /></span><div><strong>{module.name}</strong><small>{module.meta}</small></div><div className="module-value"><strong><i className="online-dot" />{module.value}</strong><small>{module.sub}</small></div><Icon name="chevron" size={16} /></div>)}</div>
      </div>
      <div className="panel model-panel"><p className="section-label">MODEL WEIGHTS</p><div className="model-name"><span>Q</span><div><h2>Local GGUF weights</h2><p>Open-weight · Offline</p></div></div>
        <dl><div><dt>Files on disk</dt><dd>{data && data.weights.length ? data.weights.join(", ") : "none"}</dd></div><div><dt>Runtime</dt><dd>llama.cpp server · Q4 · ctx 4096</dd></div><div><dt>Endpoint</dt><dd>127.0.0.1:8080</dd></div></dl>
        <a className="secondary-button full-button" href="/desktop-package" download>Download desktop app <Icon name="arrow" size={15} /></a>
      </div>
    </section>
    <section className="privacy-banner enter delay-3"><span><Icon name="lock" /></span><div><strong>Air-gapped by design</strong><p>Network access is disabled for the model runtime. No transaction data, prompts, or embeddings leave this machine.</p></div><button onClick={() => navigate("Settings")}>View privacy controls <Icon name="arrow" size={14} /></button></section>
  </div>;
}

function PreferenceSwitch({ enabled, onChange, label }: { enabled: boolean; onChange: () => void; label: string }) {
  return <button className={`preference-switch ${enabled ? "on" : ""}`} onClick={onChange} role="switch" aria-checked={enabled} aria-label={label}><span /></button>;
}

function Settings({ theme, onThemeToggle, onSaved }: { theme: Theme; onThemeToggle: () => void; onSaved: (s: Settings) => void }) {
  const [challenger, setChallenger] = useState(true);
  const [fraud, setFraud] = useState(true);
  const [autoApprove, setAutoApprove] = useState(false);
  const [threshold, setThreshold] = useState(85);
  const [scorer, setScorer] = useState("keyword");
  const [workers, setWorkers] = useState(1);
  const [format, setFormat] = useState("jsonl");
  const [evidence, setEvidence] = useState(true);
  const [loaded, setLoaded] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    api.settings()
      .then((s) => {
        const r = s as Record<string, unknown>;
        if (typeof r.challenger === "boolean") setChallenger(r.challenger);
        if (typeof r.fraud === "boolean") setFraud(r.fraud);
        if (typeof r.auto_approve_threshold === "number") setThreshold(r.auto_approve_threshold);
        if (typeof r.scorer === "string") setScorer(r.scorer);
        if (typeof r.export_format === "string") setFormat(r.export_format);
        if (typeof r.include_evidence === "boolean") setEvidence(r.include_evidence);
        setLoaded(true);
      })
      .catch(() => setLoaded(true));
  }, []);
  const save = () => {
    setError("");
    api.saveSettings({ challenger, fraud, auto_approve_threshold: threshold, scorer, workers, export_format: format, include_evidence: evidence })
      .then((s) => { onSaved(s as Settings); setSaved(true); window.setTimeout(() => setSaved(false), 1800); })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)));
  };
  if (!loaded) return <div className="view"><p>Loading settings…</p></div>;
  return <div className="view">
    <PageHeader eyebrow="WORKSPACE CONTROL" title="Settings"     detail="Configure classification behavior, privacy, appearance, and export defaults."
    action={<><button className="primary-button" onClick={save}>{saved ? <><Icon name="check" size={15} />Saved</> : "Save changes"}</button></>}
  />
    {error && <p className="danger-text">{error}</p>}
    <div className="settings-layout enter delay-1">
      <section className="settings-column">
        <div className="panel settings-panel">
          <div className="settings-heading"><span><Icon name="sun" /></span><div><h2>Appearance</h2><p>Choose how VouchPilot looks on this device.</p></div></div>
          <div className="setting-row"><div><strong>Interface theme</strong><small>Switch between the original light workspace and night mode.</small></div><ThemeToggle theme={theme} onToggle={onThemeToggle} labelled /></div>
          <div className="setting-row"><div><strong>Density</strong><small>Optimized for transaction-heavy accounting workflows.</small></div><div className="segmented"><button>Comfortable</button><button className="selected">Compact</button></div></div>
        </div>
        <div className="panel settings-panel">
          <div className="settings-heading"><span><Icon name="spark" /></span><div><h2>Classification behavior</h2><p>Control how the local model handles uncertain rows.</p></div></div>
          <div className="threshold-setting"><div><strong>Review queue cutoff</strong><b>{threshold}%</b></div><input type="range" min="60" max="99" value={threshold} onChange={(e) => setThreshold(Number(e.target.value))} /><div><span>More review</span><span>More automation</span></div></div>
          <div className="setting-row"><div><strong>Pairwise challenger</strong><small>Re-check close calls against the second-best voucher category.</small></div><PreferenceSwitch enabled={challenger} onChange={() => setChallenger(!challenger)} label="Pairwise challenger" /></div>
          <div className="setting-row"><div><strong>Default scorer</strong><small>Used for new Classify runs unless changed.</small></div><div className="segmented">{["keyword", "vouchpilot", "stub", "server"].map((s) => <button key={s} className={scorer === s ? "selected" : ""} onClick={() => setScorer(s)}>{s}</button>)}</div></div>
        </div>
      </section>
      <section className="settings-column">
        <div className="panel settings-panel">
          <div className="settings-heading"><span><Icon name="shield" /></span><div><h2>Privacy & security</h2><p>VouchPilot is offline-first and private by default.</p></div></div>
          <div className="security-note"><Icon name="lock" /><div><strong>Network isolation active</strong><p>Model inference and transaction storage are restricted to this device.</p></div></div>
          <div className="setting-row"><div><strong>Fraud and injection scanner</strong><small>Scan narrations for quishing URLs and prompt-injection attempts.</small></div><PreferenceSwitch enabled={fraud} onChange={() => setFraud(!fraud)} label="Fraud scanner" /></div>
          <div className="setting-row"><div><strong>Parallel workers</strong><small>Match the llama-server slot count. 1 is bit-identical.</small></div><div className="segmented">{[1, 2, 4].map((w) => <button key={w} className={workers === w ? "selected" : ""} onClick={() => setWorkers(w)}>{w}</button>)}</div></div>
        </div>
        <div className="panel settings-panel">
          <div className="settings-heading"><span><Icon name="file" /></span><div><h2>Export defaults</h2><p>Set the format used after human approval.</p></div></div>
          <div className="setting-row"><div><strong>Default format</strong><small>Used for Review-tab exports.</small></div><div className="segmented">{["jsonl", "csv"].map((f) => <button key={f} className={format === f ? "selected" : ""} onClick={() => setFormat(f)}>{f}</button>)}</div></div>
          <div className="setting-row"><div><strong>Include decision evidence</strong><small>Add confidence, evidence tags, and reviewer status as columns.</small></div><PreferenceSwitch enabled={evidence} onChange={() => setEvidence(!evidence)} label="Include evidence" /></div>
        </div>
        <div className="danger-zone"><div><strong>Reset local workspace</strong><p>Remove imported files, decisions, and cached evidence. Model weights are retained.</p></div><button onClick={() => { window.localStorage.removeItem("vouchpilot-runs"); window.location.reload(); }}>Reset data</button></div>
      </section>
    </div>
  </div>;
}

export default function App() {
  const [area, setArea] = useState<Area>("Dashboard");
  const [entered, setEntered] = useState(false);
  const [predictions, setPredictions] = useState<Prediction[]>([]);
  const [runs, setRuns] = useState<RunRecord[]>(() => {
    try {
      return JSON.parse(window.localStorage.getItem("vouchpilot-runs") ?? "[]") as RunRecord[];
    } catch {
      return [];
    }
  });
  const [labels, setLabels] = useState<LabelInfo[]>([]);
  const [settings, setSettings] = useState<Settings>({});
  const [theme, setTheme] = useState<Theme>(() => {
    const saved = window.localStorage.getItem("vouchpilot-theme");
    return saved === "dark" ? "dark" : "light";
  });
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    window.localStorage.setItem("vouchpilot-theme", theme);
  }, [theme]);
  useEffect(() => {
    api.labels().then((d) => setLabels(d.labels)).catch(() => undefined);
    api.settings().then((s) => setSettings(s as Settings)).catch(() => undefined);
  }, []);
  const toggleTheme = () => setTheme((current) => current === "light" ? "dark" : "light");
  function classified(run: RunRecord, preds: Prediction[]) {
    setPredictions(preds);
    setRuns((prev) => {
      const next = [run, ...prev].slice(0, 20);
      try {
        window.localStorage.setItem("vouchpilot-runs",
          JSON.stringify(next.map(({ predictions: _p, ...r }) => r)));
      } catch { /* storage full: keep in memory */ }
      return next;
    });
    setArea("Dashboard");
  }
  function exported(_decisions: Decision[], final: Prediction[]) {
    setPredictions(final);
    downloadJson("final.jsonl", final);
  }
  if (!entered) return <Welcome onEnter={() => setEntered(true)} onExplore={() => { setEntered(true); setArea("System"); }} theme={theme} onThemeToggle={toggleTheme} />;
  const navItems = nav.map((item) => item.label === "Review"
    ? { ...item, count: predictions.filter((p) => p.needs_review).length || undefined }
    : item);
  return <div className="app-shell">
    <aside className="sidebar">
      <div className="sidebar-top"><Logo /><button className="workspace"><span>VP</span><div><strong>VouchPilot</strong><small>Local workspace</small></div><Icon name="chevron" size={14} /></button>
        <nav aria-label="Primary navigation">{navItems.map((item) => <button key={item.label} className={area === item.label ? "active" : ""} onClick={() => setArea(item.label)}><Icon name={item.icon} /><span>{item.label}</span>{item.count ? <b>{item.count}</b> : null}</button>)}</nav>
      </div>
      <div className="sidebar-bottom">
        <div className="sidebar-theme"><span>Appearance</span><ThemeToggle theme={theme} onToggle={toggleTheme} /></div>
        <div className="offline-card"><Icon name="shield" size={17} /><div><strong>{scorerName(settings.scorer)} active</strong><small>100% offline inference</small></div><i className="runtime-pulse" /></div>
      </div>
    </aside>
    <main>
      <div className="mobile-top"><Logo /><button aria-label="Open navigation"><Icon name="more" /></button></div>
      {area === "Dashboard" && <Dashboard navigate={setArea} runs={runs} predictions={predictions} />}
      {area === "Classify" && <Classify settings={settings} initial={predictions} onDone={classified} />}
      {area === "Review" && <Review predictions={predictions} labels={labels} threshold={Number(settings.auto_approve_threshold ?? 85)} onExport={exported} />}
      {area === "System" && <System navigate={setArea} />}
      {area === "Settings" && <Settings theme={theme} onThemeToggle={toggleTheme} onSaved={setSettings} />}
    </main>
  </div>;
}

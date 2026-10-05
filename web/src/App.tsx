import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type ReactNode,
} from "react";
import { api, type LabelInfo, type Prediction, type RunRecord } from "./api";
import { loadRuns, saveRuns, THEME_KEY } from "./storage";
import { applyReviewToRuns } from "./review";
import { exportablePredictions, predictionsToCsv } from "./export";

type Area =
  | "Dashboard"
  | "Classify"
  | "Review"
  | "System"
  | "Settings"
  | "Privacy"
  | "Terms"
  | "Cookies"
  | "Refunds";
type Theme = "light" | "dark";
type Settings = Record<string, unknown>;

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

const NAV: { label: Area; icon: IconName }[] = [
  { label: "Dashboard", icon: "dashboard" },
  { label: "Classify", icon: "classify" },
  { label: "Review", icon: "review" },
  { label: "System", icon: "server" },
  { label: "Settings", icon: "system" },
];

const SCORER_NAMES: Record<string, string> = {
  keyword: "Instant rules",
  vouchpilot: "VouchPilot+",
  stub: "Demo scorer",
  server: "Local Qwen model",
};

const FILE_TYPES = ".xlsx,.xlsm,.csv,.pdf,.png,.jpg,.jpeg,.tiff,.bmp,.webp";

function scorerName(id: unknown): string {
  return SCORER_NAMES[String(id ?? "keyword")] ?? String(id ?? "keyword");
}

function downloadBlob(filename: string, data: BlobPart, type: string) {
  const blob = new Blob([data], { type });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 250);
}

function downloadJson(filename: string, data: unknown) {
  downloadBlob(filename, JSON.stringify(data, null, 2), "application/json");
}

function downloadJsonl(filename: string, rows: unknown[]) {
  downloadBlob(
    filename,
    rows.map((row) => JSON.stringify(row)).join("\n") + "\n",
    "application/x-ndjson",
  );
}

function useCountUp(target: number, duration = 650): number {
  const [value, setValue] = useState(target);
  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setValue(target);
      return;
    }
    const from = value;
    const start = performance.now();
    let raf = 0;
    const tick = (now: number) => {
      const progress = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - progress, 3);
      setValue(from + (target - from) * eased);
      if (progress < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target, duration]);
  return value;
}

function Icon({ name, size = 18 }: { name: IconName; size?: number }) {
  const common = {
    width: size,
    height: size,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.8,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    "aria-hidden": true,
  };
  const paths: Record<IconName, ReactNode> = {
    dashboard: (
      <>
        <rect x="3" y="3" width="7" height="7" rx="1" />
        <rect x="14" y="3" width="7" height="7" rx="1" />
        <rect x="3" y="14" width="7" height="7" rx="1" />
        <rect x="14" y="14" width="7" height="7" rx="1" />
      </>
    ),
    classify: (
      <>
        <path d="M4 19V5a2 2 0 0 1 2-2h9l5 5v11a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2Z" />
        <path d="M14 3v6h6M8 13h8M8 17h5" />
      </>
    ),
    review: (
      <>
        <path d="M9 11l2 2 4-4" />
        <path d="M12 22c5-2 8-5 8-10V5l-8-3-8 3v7c0 5 3 8 8 10Z" />
      </>
    ),
    system: (
      <>
        <circle cx="12" cy="12" r="3" />
        <path d="M19.4 15a1.7 1.7 0 0 0 .34 1.88l.06.06-2.83 2.83-.06-.06a1.7 1.7 0 0 0-1.88-.34 1.7 1.7 0 0 0-1.03 1.56V21h-4v-.08A1.7 1.7 0 0 0 9 19.37a1.7 1.7 0 0 0-1.88.34l-.06.06-2.83-2.83.06-.06A1.7 1.7 0 0 0 4.63 15 1.7 1.7 0 0 0 3.08 14H3v-4h.08A1.7 1.7 0 0 0 4.63 9a1.7 1.7 0 0 0-.34-1.88l-.06-.06 2.83-2.83.06.06A1.7 1.7 0 0 0 9 4.63 1.7 1.7 0 0 0 10 3.08V3h4v.08A1.7 1.7 0 0 0 15 4.63a1.7 1.7 0 0 0 1.88-.34l.06-.06 2.83 2.83-.06.06A1.7 1.7 0 0 0 19.37 9 1.7 1.7 0 0 0 20.92 10H21v4h-.08A1.7 1.7 0 0 0 19.4 15Z" />
      </>
    ),
    shield: (
      <>
        <path d="M12 22c5-2 8-5 8-10V5l-8-3-8 3v7c0 5 3 8 8 10Z" />
        <path d="M9 12l2 2 4-5" />
      </>
    ),
    chevron: <path d="m9 18 6-6-6-6" />,
    upload: (
      <>
        <path d="M12 16V4M7 9l5-5 5 5M5 20h14" />
      </>
    ),
    search: (
      <>
        <circle cx="11" cy="11" r="7" />
        <path d="m20 20-4-4" />
      </>
    ),
    filter: <path d="M4 5h16M7 12h10M10 19h4" />,
    more: (
      <>
        <circle cx="5" cy="12" r=".8" fill="currentColor" />
        <circle cx="12" cy="12" r=".8" fill="currentColor" />
        <circle cx="19" cy="12" r=".8" fill="currentColor" />
      </>
    ),
    check: <path d="m5 12 4 4L19 6" />,
    alert: (
      <>
        <path d="M12 9v4M12 17h.01" />
        <path d="M10.3 3.6 2.5 17a2 2 0 0 0 1.7 3h15.6a2 2 0 0 0 1.7-3L13.7 3.6a2 2 0 0 0-3.4 0Z" />
      </>
    ),
    arrow: (
      <>
        <path d="M5 12h14M14 7l5 5-5 5" />
      </>
    ),
    file: (
      <>
        <path d="M5 3h10l4 4v14H5z" />
        <path d="M14 3v5h5M8 13h8M8 17h6" />
      </>
    ),
    clock: (
      <>
        <circle cx="12" cy="12" r="9" />
        <path d="M12 7v5l3 2" />
      </>
    ),
    server: (
      <>
        <rect x="3" y="4" width="18" height="6" rx="2" />
        <rect x="3" y="14" width="18" height="6" rx="2" />
        <path d="M7 7h.01M7 17h.01" />
      </>
    ),
    database: (
      <>
        <ellipse cx="12" cy="5" rx="8" ry="3" />
        <path d="M4 5v7c0 1.7 3.6 3 8 3s8-1.3 8-3V5M4 12v7c0 1.7 3.6 3 8 3s8-1.3 8-3v-7" />
      </>
    ),
    cpu: (
      <>
        <rect x="6" y="6" width="12" height="12" rx="2" />
        <path d="M9 1v3M15 1v3M9 20v3M15 20v3M20 9h3M20 14h3M1 9h3M1 14h3M10 10h4v4h-4z" />
      </>
    ),
    lock: (
      <>
        <rect x="5" y="10" width="14" height="11" rx="2" />
        <path d="M8 10V7a4 4 0 0 1 8 0v3" />
      </>
    ),
    spark: (
      <>
        <path d="m12 3 1.4 4.1L17.5 8.5l-4.1 1.4L12 14l-1.4-4.1-4.1-1.4 4.1-1.4L12 3Z" />
        <path d="m18.5 15 .7 2.3 2.3.7-2.3.7-.7 2.3-.7-2.3-2.3-.7 2.3-.7.7-2.3Z" />
      </>
    ),
    sun: (
      <>
        <circle cx="12" cy="12" r="4" />
        <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
      </>
    ),
    moon: <path d="M20.8 15.3A9 9 0 0 1 8.7 3.2 9 9 0 1 0 20.8 15.3Z" />,
  };
  return <svg {...common}>{paths[name]}</svg>;
}

function Logo({ compact = false }: { compact?: boolean }) {
  return (
    <div className={`brand ${compact ? "brand-compact" : ""}`}>
      <img src="/logo.png" alt="" width={28} height={28} />
      <span>VouchPilot</span>
    </div>
  );
}

function ThemeToggle({
  theme,
  onToggle,
}: {
  theme: Theme;
  onToggle: () => void;
}) {
  return (
    <button
      className="theme-switch"
      onClick={onToggle}
      aria-label={`Switch to ${theme === "light" ? "dark" : "light"} mode`}
    >
      <span className={theme === "light" ? "active" : ""}>
        <Icon name="sun" size={14} />
      </span>
      <span className={theme === "dark" ? "active" : ""}>
        <Icon name="moon" size={14} />
      </span>
    </button>
  );
}

function StatusDot({ tone = "good" }: { tone?: "good" | "warn" | "bad" }) {
  return <i className={`status-dot ${tone}`} aria-hidden="true" />;
}

function PrimaryButton({
  children,
  onClick,
  disabled,
  type = "button",
  className = "",
}: {
  children: ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  type?: "button" | "submit";
  className?: string;
}) {
  return (
    <button
      type={type}
      className={`btn btn-primary ${className}`}
      onClick={onClick}
      disabled={disabled}
    >
      {children}
    </button>
  );
}

function SecondaryButton({
  children,
  onClick,
  disabled,
  className = "",
}: {
  children: ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  className?: string;
}) {
  return (
    <button
      className={`btn btn-secondary ${className}`}
      onClick={onClick}
      disabled={disabled}
    >
      {children}
    </button>
  );
}

function PageHeader({
  eyebrow,
  title,
  detail,
  action,
}: {
  eyebrow: string;
  title: string;
  detail: string;
  action?: ReactNode;
}) {
  return (
    <header className="page-header">
      <div className="page-heading">
        <p className="eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
        <p>{detail}</p>
      </div>
      {action ? <div className="page-actions">{action}</div> : null}
    </header>
  );
}

function Welcome({
  runs,
  theme,
  onThemeToggle,
  onEnter,
  onSystem,
}: {
  runs: RunRecord[];
  theme: Theme;
  onThemeToggle: () => void;
  onEnter: () => void;
  onSystem: () => void;
}) {
  const last = runs[0];
  const recentRows = last?.predictions?.slice(0, 3) ?? [];
  return (
    <div className="marketing">
      <header className="marketing-nav">
        <Logo />
        <nav aria-label="Marketing">
          <a href="#product">Product</a>
          <a href="#privacy">Privacy</a>
          <a href="#workflow">Workflow</a>
        </nav>
        <div className="marketing-actions">
          <ThemeToggle theme={theme} onToggle={onThemeToggle} />
          <a className="btn btn-secondary" href="/desktop-package" download>
            Desktop
          </a>
          <PrimaryButton onClick={onEnter}>
            Open workspace <Icon name="arrow" size={15} />
          </PrimaryButton>
        </div>
      </header>

      <main>
        <section className="hero-section" id="product">
          <div className="hero-copy">
            <span className="eyebrow eyebrow-strong">
              <StatusDot /> Offline GST voucher intelligence
            </span>
            <h1>
              Make every transaction
              <span> auditable.</span>
            </h1>
            <p>
              Upload accounting data, classify transactions into 27 GST voucher
              categories, inspect the evidence, and route uncertain rows to a
              human reviewer.
            </p>
            <div className="hero-actions">
              <PrimaryButton onClick={onEnter}>
                Start a classification <Icon name="arrow" size={16} />
              </PrimaryButton>
              <SecondaryButton onClick={onSystem}>
                <Icon name="shield" size={16} /> Inspect runtime
              </SecondaryButton>
            </div>
            <div className="trust-list">
              <span><Icon name="lock" size={14} /> Local processing</span>
              <span><Icon name="check" size={14} /> 27 voucher types</span>
              <span><Icon name="review" size={14} /> Human approval gate</span>
            </div>
          </div>

          <div className="hero-product">
            <div className="hero-product-top">
              <div className="window-lights"><i /><i /><i /></div>
              <span>{last ? `Latest run · ${last.file}` : "Ready for your workbook"}</span>
              <span className="runtime-badge"><StatusDot /> Local</span>
            </div>
            <div className="hero-product-body">
              <div className="hero-product-title">
                <div>
                  <span className="section-kicker">CLASSIFICATION RUN</span>
                  <h2>{last ? `${last.rows.toLocaleString()} transactions` : "Your results will appear here"}</h2>
                </div>
                <div className="hero-score">
                  <strong>{last ? last.status : "READY"}</strong>
                  <span>STATUS</span>
                </div>
              </div>
              <div className="mini-table">
                {recentRows.length
                  ? recentRows.map((row) => (
                      <div className="mini-row" key={row.row_id}>
                        <div>
                          <strong>{row.invoice_number}</strong>
                          <span>{row.evidence[0] ?? "Evidence captured"}</span>
                        </div>
                        <span className="tag">{row.voucher_type}</span>
                        <strong className={row.needs_review ? "text-warn" : "text-good"}>
                          {Math.round(row.confidence * 100)}%
                        </strong>
                      </div>
                    ))
                  : ["PI/26-0081", "SI/26-0412", "PAY/26-0037"].map((invoice, index) => (
                      <div className="mini-row" key={invoice}>
                        <div>
                          <strong>{invoice}</strong>
                          <span>{["Input GST", "Output GST", "Bank / UTR"][index]}</span>
                        </div>
                        <span className="tag">{["Purchase", "Sales", "Payment"][index]}</span>
                        <strong className={index === 2 ? "text-warn" : "text-good"}>
                          {[93, 97, 61][index]}%
                        </strong>
                      </div>
                    ))}
              </div>
            </div>
          </div>
        </section>

        <section className="stat-ribbon">
          <div><strong>27</strong><span>GST voucher categories</span></div>
          <div><strong>3</strong><span>Input paths · XLSX / CSV / documents</span></div>
          <div><strong>0</strong><span>Required cloud accounts</span></div>
          <div><strong>1</strong><span>Human gate before filing</span></div>
        </section>

        <section className="feature-grid" id="workflow">
          {[
            ["classify", "Classify once", "Normalize messy headers and score rows with rules or a local open-weight model."],
            ["review", "Review the edge cases", "See top alternatives, confidence and evidence before approving a row."],
            ["shield", "Keep it private", "Inference and workspace state stay local; document intake runs on-device."],
          ].map(([icon, title, body]) => (
            <article className="feature-card" key={title}>
              <span className="feature-icon"><Icon name={icon as IconName} /></span>
              <h3>{title}</h3>
              <p>{body}</p>
            </article>
          ))}
        </section>

        <section className="privacy-section" id="privacy">
          <div>
            <span className="section-kicker">PRIVACY FIRST</span>
            <h2>Built for financial data that should not leave the room.</h2>
          </div>
          <p>
            VouchPilot is designed around local inference. The browser talks to
            the local API, while model weights and transaction records stay on
            the device.
          </p>
        </section>
      </main>
    </div>
  );
}

function MetricCard({
  label,
  value,
  detail,
  tone = "neutral",
}: {
  label: string;
  value: string;
  detail: string;
  tone?: "neutral" | "good" | "warn";
}) {
  return (
    <article className={`metric-card tone-${tone}`}>
      <div className="metric-label">{label}</div>
      <strong>{value}</strong>
      <span>{detail}</span>
    </article>
  );
}

function Dashboard({
  navigate,
  runs,
  predictions,
  scorer,
}: {
  navigate: (area: Area) => void;
  runs: RunRecord[];
  predictions: Prediction[];
  scorer: string;
}) {
  const reviewCount = predictions.filter((p) => p.needs_review).length;
  const total = predictions.length || runs.reduce((sum, run) => sum + run.rows, 0);
  const confidence =
    predictions.length > 0
      ? (predictions.reduce((sum, row) => sum + row.confidence, 0) / predictions.length) * 100
      : 0;
  const counts = useMemo(() => {
    const map = new Map<string, number>();
    predictions.forEach((prediction) =>
      map.set(prediction.voucher_type, (map.get(prediction.voucher_type) ?? 0) + 1),
    );
    return [...map.entries()].sort((a, b) => b[1] - a[1]).slice(0, 8);
  }, [predictions]);
  const maxCount = Math.max(1, ...counts.map(([, count]) => count));
  const animatedTotal = Math.round(useCountUp(total));
  const animatedReview = Math.round(useCountUp(reviewCount));
  const animatedConfidence = useCountUp(confidence);

  return (
    <div className="view">
      <PageHeader
        eyebrow="LOCAL WORKSPACE"
        title="Your accounting control room."
        detail={
          total
            ? `${animatedTotal.toLocaleString()} transactions in the current workspace.`
            : "Classify a workbook to turn this page into a live control room."
        }
        action={
          <PrimaryButton onClick={() => navigate("Classify")}>
            <Icon name="upload" size={16} /> New classification
          </PrimaryButton>
        }
      />

      <section className="metric-grid">
        <MetricCard label="Transactions" value={animatedTotal.toLocaleString()} detail={runs.length ? `${runs.length} saved runs` : "No runs yet"} tone={runs.length ? "good" : "neutral"} />
        <MetricCard label="Mean confidence" value={predictions.length ? `${animatedConfidence.toFixed(1)}%` : "—"} detail="Current batch" />
        <MetricCard label="Needs review" value={String(animatedReview)} detail="Human gate" tone={reviewCount ? "warn" : "good"} />
        <MetricCard label="Runtime" value="Local" detail={scorerName(scorer)} tone="good" />
      </section>

      <section className="dashboard-grid">
        <article className="panel panel-large">
          <div className="panel-head">
            <div><span className="section-kicker">DISTRIBUTION</span><h2>Predicted voucher mix</h2></div>
            <span className="subtle-pill">{predictions.length} rows</span>
          </div>
          {counts.length ? (
            <div className="distribution-chart" role="img" aria-label="Predicted voucher type distribution">
              {counts.map(([label, count]) => (
                <div className="distribution-row" key={label}>
                  <div><strong>{label}</strong><span>{count}</span></div>
                  <div className="bar-track"><i style={{ width: `${(count / maxCount) * 100}%` }} /></div>
                </div>
              ))}
            </div>
          ) : (
            <div className="empty-panel">
              <Icon name="classify" size={30} />
              <h3>No predictions yet</h3>
              <p>Start a run and this chart will summarize your batch.</p>
              <SecondaryButton onClick={() => navigate("Classify")}>Go to Classify</SecondaryButton>
            </div>
          )}
        </article>

        <article className="panel attention-panel">
          <div className="panel-head">
            <div><span className="section-kicker">ATTENTION</span><h2>Review queue</h2></div>
            <StatusDot tone={reviewCount ? "warn" : "good"} />
          </div>
          <div className="big-number">{reviewCount}</div>
          <p>{reviewCount ? "Rows are waiting for a human decision." : "Everything in the current batch is above the review cutoff."}</p>
          <div className="progress-large"><i style={{ width: `${total ? Math.round((reviewCount / total) * 100) : 0}%` }} /></div>
          <PrimaryButton onClick={() => navigate("Review")} disabled={!reviewCount}>Open review queue <Icon name="arrow" size={15} /></PrimaryButton>
        </article>
      </section>

      <section className="panel">
        <div className="panel-head">
          <div><span className="section-kicker">RECENT ACTIVITY</span><h2>Saved runs</h2></div>
          <SecondaryButton onClick={() => navigate("Classify")}>New run</SecondaryButton>
        </div>
        <div className="data-table">
          <div className="table-row table-header">
            <span>FILE</span><span>ROWS</span><span>STATUS</span><span>CREATED</span><span />
          </div>
          {runs.length ? runs.slice(0, 8).map((run) => (
            <div className="table-row" key={run.id}>
              <span className="file-cell"><span className="file-icon"><Icon name="file" size={15} /></span><strong>{run.file}</strong></span>
              <span>{run.rows.toLocaleString()}</span>
              <span><b className={run.status === "Completed" ? "status-pill good" : "status-pill warn"}>{run.status}</b></span>
              <span className="muted">{run.completed}</span>
              <button
                className="icon-btn"
                aria-label={`Download predictions for ${run.file}`}
                onClick={() => {
                  if (run.predictions.length) downloadJsonl(`${run.file}.jsonl`, run.predictions);
                }}
                disabled={!run.predictions.length}
              >
                <Icon name="arrow" size={16} />
              </button>
            </div>
          )) : (
            <div className="empty-table">No saved runs yet. Your first classification will appear here.</div>
          )}
        </div>
      </section>
    </div>
  );
}

function classifyReviewFlags(predictions: Prediction[], threshold: number): Prediction[] {
  const cutoff = Math.max(0, Math.min(100, threshold)) / 100;
  return predictions.map((prediction) => ({
    ...prediction,
    needs_review: prediction.needs_review || prediction.confidence < cutoff,
  }));
}

function Classify({
  settings,
  initial,
  onDone,
}: {
  settings: Settings;
  initial: Prediction[];
  onDone: (run: RunRecord, predictions: Prediction[]) => void;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");
  const [dragOver, setDragOver] = useState(false);
  const [rows, setRows] = useState<Prediction[]>(initial);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<"all" | "review">("all");
  const input = useRef<HTMLInputElement>(null);

  const threshold = Number(settings.auto_approve_threshold ?? 85);
  const includeEvidence = Boolean(settings.include_evidence ?? true);
  const allowedSize = 50 * 1024 * 1024;

  useEffect(() => setRows(initial), [initial]);

  function choose(next: File | null) {
    if (!next) return;
    if (next.size > allowedSize) {
      setError("That file is larger than 50 MB. Split it into smaller batches and try again.");
      return;
    }
    setError("");
    setFile(next);
  }

  async function run() {
    if (!file) {
      setError("Choose a file first.");
      return;
    }
    setRunning(true);
    setError("");
    try {
      const result = await api.predictFile(file, {
        scorer: String(settings.scorer ?? "keyword"),
        workers: String(settings.workers ?? 1),
        challenge: Boolean(settings.challenger ?? true) ? "true" : "false",
        fraud: Boolean(settings.fraud ?? true) ? "true" : "false",
      });
      const normalized = classifyReviewFlags(result.predictions, threshold);
      setRows(normalized);
      const needsReview = normalized.filter((prediction) => prediction.needs_review).length;
      onDone(
        {
          id: `${Date.now()}-${file.name}`,
          file: file.name,
          rows: result.n_rows,
          accuracy: null,
          status: needsReview ? "Review needed" : "Completed",
          completed: new Date().toLocaleString(),
          predictions: normalized,
        },
        normalized,
      );
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Classification failed.");
    } finally {
      setRunning(false);
    }
  }

  const shown = rows.filter((row) => {
    const matchesQuery = `${row.invoice_number} ${row.voucher_type} ${row.evidence.join(" ")}`
      .toLowerCase()
      .includes(query.toLowerCase());
    return matchesQuery && (filter === "all" || row.needs_review);
  });

  const statusText = running
    ? "Scoring your rows…"
    : rows.length
      ? `${rows.length.toLocaleString()} rows ready`
      : "No run yet";

  return (
    <div className="view">
      <PageHeader
        eyebrow="CLASSIFY / NEW RUN"
        title="Turn transactions into vouchers."
        detail="Drop a workbook, CSV, PDF or bill image. The local API handles document intake, normalization and classification."
        action={
          <div className="page-actions">
            <input
              ref={input}
              className="visually-hidden"
              type="file"
              accept={FILE_TYPES}
              onChange={(event) => choose(event.target.files?.[0] ?? null)}
            />
            <SecondaryButton onClick={() => input.current?.click()}>
              <Icon name="upload" size={16} /> {file ? "Replace file" : "Choose file"}
            </SecondaryButton>
            <PrimaryButton onClick={run} disabled={!file || running}>
              <Icon name="spark" size={16} /> {running ? "Classifying…" : "Run classifier"}
            </PrimaryButton>
          </div>
        }
      />

      {error ? (
        <div className="alert alert-error" role="alert">
          <Icon name="alert" size={17} />
          <div><strong>Could not complete the run</strong><span>{error}</span></div>
        </div>
      ) : null}

      <section className="upload-zone-wrap">
        <div
          className={`upload-zone ${dragOver ? "dragging" : ""} ${file ? "has-file" : ""}`}
          onDragEnter={(event) => { event.preventDefault(); setDragOver(true); }}
          onDragOver={(event) => event.preventDefault()}
          onDragLeave={(event) => { event.preventDefault(); setDragOver(false); }}
          onDrop={(event) => {
            event.preventDefault();
            setDragOver(false);
            choose(event.dataTransfer.files?.[0] ?? null);
          }}
          onClick={() => input.current?.click()}
          role="button"
          tabIndex={0}
          onKeyDown={(event) => {
            if (event.key === "Enter" || event.key === " ") input.current?.click();
          }}
          aria-label="Choose accounting file"
        >
          <span className="upload-icon"><Icon name="upload" size={25} /></span>
          <div>
            <strong>{file ? file.name : "Drop your accounting file here"}</strong>
            <p>{file ? `${(file.size / 1024 / 1024).toFixed(2)} MB · ready to classify` : "XLSX, XLSM, CSV, PDF, PNG, JPG and TIFF · up to 50 MB"}</p>
          </div>
          <span className="upload-cta">{file ? "Change file" : "Browse files"}</span>
        </div>
      </section>

      <section className="run-context">
        <div><span className="section-kicker">SCORER</span><strong>{scorerName(settings.scorer)}</strong><span>{String(settings.scorer ?? "keyword") === "server" ? "llama.cpp required" : "No model download required"}</span></div>
        <div><span className="section-kicker">REVIEW CUTOFF</span><strong>{threshold}%</strong><span>Below this is routed to Review</span></div>
        <div><span className="section-kicker">PRIVACY</span><strong><StatusDot /> Local only</strong><span>Browser → local API → local engine</span></div>
        <div><span className="section-kicker">RUN STATUS</span><strong>{statusText}</strong><span>{rows.length ? `${rows.filter((r) => r.needs_review).length} need review` : "Waiting for input"}</span></div>
      </section>

      <section className="panel">
        <div className="panel-head panel-head-stack">
          <div><span className="section-kicker">RESULTS</span><h2>Predictions</h2></div>
          <div className="toolbar">
            <label className="search-control"><Icon name="search" size={16} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search invoice or evidence" /></label>
            <button className={`filter-chip ${filter === "review" ? "active" : ""}`} onClick={() => setFilter(filter === "all" ? "review" : "all")}>
              <Icon name="filter" size={15} /> {filter === "review" ? "Needs review" : "All rows"}
            </button>
            <SecondaryButton onClick={() => downloadJsonl("predictions.jsonl", exportablePredictions(rows, includeEvidence))} disabled={!rows.length}>JSONL</SecondaryButton>
            <SecondaryButton onClick={() => downloadBlob("predictions.csv", predictionsToCsv(exportablePredictions(rows, includeEvidence), includeEvidence), "text/csv")} disabled={!rows.length}>CSV</SecondaryButton>
          </div>
        </div>

        <div className="data-table prediction-table">
          <div className="table-row table-header prediction-grid">
            <span>TRANSACTION</span><span>VOUCHER</span><span>CONFIDENCE</span><span>EVIDENCE</span><span>STATE</span>
          </div>
          {running && !rows.length
            ? [1, 2, 3, 4].map((key) => (
                <div className="skeleton-row prediction-grid" key={key}>
                  <i /><i /><i /><i /><i />
                </div>
              ))
            : shown.slice(0, 150).map((row) => (
                <div className="table-row prediction-grid" key={row.row_id}>
                  <div className="transaction">
                    <strong>{row.invoice_number}</strong>
                    <span>row {row.row_id}</span>
                  </div>
                  <div><span className="tag tag-strong">{row.voucher_type}</span></div>
                  <div className="confidence">
                    <strong className={row.needs_review ? "text-warn" : "text-good"}>{Math.round(row.confidence * 100)}%</strong>
                    <span><i style={{ width: `${Math.max(2, row.confidence * 100)}%` }} /></span>
                  </div>
                  <div className="evidence-tags">
                    {row.evidence.slice(0, 3).map((tag) => <span key={tag}>{tag}</span>)}
                  </div>
                  <div><span className={row.needs_review ? "status-pill warn" : "status-pill good"}>{row.needs_review ? "Review" : "Auto"}</span></div>
                </div>
              ))}
          {!running && rows.length > 0 && !shown.length ? <div className="empty-table">No rows match your search.</div> : null}
          {!running && !rows.length ? <div className="empty-table">Choose a file and run the classifier to see predictions.</div> : null}
        </div>
        <div className="table-foot">Showing {Math.min(150, shown.length)} of {shown.length.toLocaleString()} matching rows</div>
      </section>
    </div>
  );
}

export interface Decision {
  row_id: number;
  verdict: "approve" | "override" | "escalate";
  label: string | null;
  note: string;
}

function Review({
  predictions,
  labels,
  threshold,
  exportFormat,
  includeEvidence,
  onExport,
}: {
  predictions: Prediction[];
  labels: LabelInfo[];
  threshold: number;
  exportFormat: string;
  includeEvidence: boolean;
  onExport: (decisions: Decision[], final: Prediction[]) => void;
}) {
  const queue = useMemo(
    () =>
      predictions.filter(
        (prediction) =>
          prediction.needs_review || prediction.confidence * 100 < threshold,
      ),
    [predictions, threshold],
  );
  const [decisions, setDecisions] = useState<Record<number, Decision>>({});
  const [view, setView] = useState<"all" | "open" | "done">("all");
  const [overrideRow, setOverrideRow] = useState<number | null>(null);

  useEffect(() => {
    setDecisions({});
    setOverrideRow(null);
  }, [predictions]);

  const shown = queue.filter((row) =>
    view === "all"
      ? true
      : view === "done"
        ? Boolean(decisions[row.row_id])
        : !decisions[row.row_id],
  );
  const done = Object.keys(decisions).length;
  const approved = Object.values(decisions).filter((d) => d.verdict === "approve").length;
  const overridden = Object.values(decisions).filter((d) => d.verdict === "override").length;
  const escalated = Object.values(decisions).filter((d) => d.verdict === "escalate").length;

  function decide(rowId: number, verdict: Decision["verdict"], label: string | null = null) {
    setDecisions((current) => ({
      ...current,
      [rowId]: { row_id: rowId, verdict, label, note: "" },
    }));
  }

  function finalRows(): Prediction[] {
    return predictions.map((prediction) => {
      const decision = decisions[prediction.row_id];
      if (!decision) return prediction;
      if (decision.verdict === "override" && decision.label) {
        return {
          ...prediction,
          voucher_type: decision.label,
          needs_review: false,
          evidence: [...prediction.evidence, `HUMAN:override->${decision.label}`],
        };
      }
      if (decision.verdict === "approve") {
        return {
          ...prediction,
          needs_review: false,
          evidence: [...prediction.evidence, "HUMAN:approved"],
        };
      }
      return {
        ...prediction,
        needs_review: true,
        evidence: [...prediction.evidence, "HUMAN:escalated"],
      };
    });
  }

  function finish() {
    if (done < queue.length) return;
    const final = finalRows();
    onExport(Object.values(decisions), final);
  }

  function downloadDecisions() {
    downloadJson("decisions.json", { decisions: Object.values(decisions) });
  }

  function downloadFinal() {
    if (done < queue.length || !queue.length) return;
    const rows = exportablePredictions(finalRows(), includeEvidence);
    if (exportFormat === "jsonl") {
      downloadJsonl("final.jsonl", rows);
      return;
    }
    downloadBlob("final.csv", predictionsToCsv(rows, includeEvidence), "text/csv");
  }

  return (
    <div className="view">
      <PageHeader
        eyebrow="HUMAN APPROVAL GATE"
        title="Review only what needs a person."
        detail={
          queue.length
            ? `${Math.max(0, queue.length - done)} of ${queue.length} rows still need a decision.`
            : "This batch has no rows below the configured review cutoff."
        }
        action={
          <button className="filter-chip active" onClick={() => setView(view === "all" ? "open" : view === "open" ? "done" : "all")}>
            <Icon name="filter" size={15} /> {view === "all" ? "All" : view === "open" ? "Open" : "Decided"}
          </button>
        }
      />

      <section className="review-layout">
        <div className="review-stack">
          {shown.length ? shown.map((row) => {
            const decision = decisions[row.row_id];
            const override = overrideRow === row.row_id;
            const isResolved = Boolean(decision);
            return (
              <article className={`review-card ${isResolved ? "resolved" : ""}`} key={row.row_id}>
                <div className="review-card-head">
                  <div className="transaction">
                    <span className="file-icon"><Icon name="file" size={15} /></span>
                    <div><strong>{row.invoice_number}</strong><span>Row {row.row_id}</span></div>
                  </div>
                  <span className={row.confidence < 0.5 ? "status-pill bad" : "status-pill warn"}>
                    {Math.round(row.confidence * 100)}% confidence
                  </span>
                </div>

                <div className="decision-matrix">
                  <div><span>MODEL PREDICTION</span><strong>{row.voucher_type}</strong></div>
                  <div><span>TOP ALTERNATIVE</span><strong>{row.top_k[1]?.[0] ?? "—"}</strong></div>
                  <div><span>EVIDENCE</span><strong>{row.evidence.slice(0, 2).join(" · ") || "No tags"}</strong></div>
                </div>

                {!isResolved ? (
                  <>
                    <div className="review-actions">
                      <PrimaryButton onClick={() => decide(row.row_id, "approve")}><Icon name="check" size={15} /> Approve</PrimaryButton>
                      <SecondaryButton onClick={() => setOverrideRow(override ? null : row.row_id)}>Override</SecondaryButton>
                      <button className="btn btn-ghost" onClick={() => decide(row.row_id, "escalate")}>Escalate</button>
                    </div>
                    {override ? (
                      <div className="override-panel">
                        <select
                          value={decisions[row.row_id]?.label ?? ""}
                          onChange={(event) => {
                            const label = event.target.value || null;
                            if (!label) return;
                            decide(row.row_id, "override", label);
                            setOverrideRow(null);
                          }}
                          aria-label={`Correct voucher for ${row.invoice_number}`}
                        >
                          <option value="">Choose the correct voucher…</option>
                          {(labels.length
                            ? labels
                            : [...new Set(predictions.map((prediction) => prediction.voucher_type))]
                              .map((name) => ({ code: name, group: "", name } as LabelInfo))
                          ).map((label) => (
                            <option key={label.code} value={label.name}>{label.name}</option>
                          ))}
                        </select>
                        <span>Selecting a label immediately records the override.</span>
                      </div>
                    ) : null}
                  </>
                ) : (
                  <div className="resolved-strip">
                    <Icon name="check" size={16} />
                    <strong>{decision.verdict === "approve" ? "Approved" : decision.verdict === "override" ? `Overridden to ${decision.label}` : "Escalated"}</strong>
                  </div>
                )}
              </article>
            );
          }) : (
            <div className="empty-panel">
              <span className="success-icon"><Icon name="check" size={24} /></span>
              <h3>{queue.length ? "No rows in this view" : "Review queue is clear"}</h3>
              <p>{queue.length ? "Switch the filter to see the remaining decisions." : "Every prediction is above the configured review cutoff."}</p>
            </div>
          )}
        </div>

        <aside className="review-summary panel">
          <span className="section-kicker">BATCH CHECKPOINT</span>
          <div className="review-ring" style={{ "--progress": `${queue.length ? (done / queue.length) * 360 : 360}deg` } as CSSProperties}>
            <div><strong>{done}</strong><span>of {queue.length}</span></div>
          </div>
          <h3>Decision status</h3>
          <p>Export unlocks only after every queued row has a human decision.</p>
          <div className="decision-stats">
            <span><StatusDot tone="good" /> Approved <b>{approved}</b></span>
            <span><StatusDot tone="warn" /> Overridden <b>{overridden}</b></span>
            <span><StatusDot tone="bad" /> Escalated <b>{escalated}</b></span>
          </div>
          <PrimaryButton onClick={finish} disabled={done < queue.length || !queue.length}>
            Complete review <Icon name="arrow" size={15} />
          </PrimaryButton>
          <SecondaryButton onClick={downloadFinal} disabled={done < queue.length || !queue.length}>
            Download final.{exportFormat === "jsonl" ? "jsonl" : "csv"}
          </SecondaryButton>
          <button className="btn btn-ghost btn-full" onClick={downloadDecisions} disabled={!done}>Download decisions.json</button>
        </aside>
      </section>
    </div>
  );
}

function System() {
  const [data, setData] = useState<Awaited<ReturnType<typeof api.system>> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function refresh() {
    setLoading(true);
    setError("");
    try {
      setData(await api.system());
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Diagnostics unavailable.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void refresh(); }, []);

  const entries = data ? Object.entries(data.modules) : [];
  const okCount = entries.filter(([, value]) => value === "OK").length;
  const overallGood = data ? okCount === entries.length : false;

  return (
    <div className="view">
      <PageHeader
        eyebrow="PRIVATE RUNTIME"
        title="System health"
        detail="Check the local API, model server, Python modules and weights from one place."
        action={<SecondaryButton onClick={refresh} disabled={loading}>{loading ? "Checking…" : "Run diagnostics"}</SecondaryButton>}
      />

      {error ? <div className="alert alert-error" role="alert"><Icon name="alert" size={17} /><span>{error}</span></div> : null}

      <section className={`health-banner ${overallGood ? "good" : "warn"}`}>
        <span className="health-symbol"><Icon name={overallGood ? "check" : "alert"} size={22} /></span>
        <div>
          <span className="section-kicker">OVERALL STATUS</span>
          <h2>{loading ? "Checking local services…" : overallGood ? "Core modules are healthy" : "Some modules need attention"}</h2>
          <p>{data ? `${okCount}/${entries.length} Python modules import correctly · model server ${data.server.up ? "reachable" : "offline"}` : "Waiting for a response from the local API."}</p>
        </div>
      </section>

      <section className="system-grid">
        <article className="panel">
          <div className="panel-head"><div><span className="section-kicker">MODULES</span><h2>Pipeline health</h2></div></div>
          <div className="system-list">
            {entries.map(([name, status]) => (
              <div className="system-row" key={name}>
                <span className="system-icon"><Icon name={name === "ingest" || name === "normalise" ? "database" : "cpu"} size={17} /></span>
                <div><strong>{name}</strong><span>Python module</span></div>
                <b className={status === "OK" ? "text-good" : "text-bad"}><StatusDot tone={status === "OK" ? "good" : "bad"} />{status}</b>
              </div>
            ))}
          </div>
        </article>

        <article className="panel">
          <div className="panel-head"><div><span className="section-kicker">MODEL RUNTIME</span><h2>Local inference</h2></div><StatusDot tone={data?.server.up ? "good" : "warn"} /></div>
          <div className="runtime-card">
            <div><span className="section-kicker">ENDPOINT</span><strong>{data?.server.url ?? "127.0.0.1:8080"}</strong></div>
            <div><span className="section-kicker">WEIGHTS</span><strong>{data?.weights.length ? data.weights.join(", ") : "No GGUF weights found"}</strong></div>
            <div><span className="section-kicker">VERSION</span><strong>{data?.version ?? "—"}</strong></div>
          </div>
          <p className="muted-copy">Keyword mode needs no model weights. The local server scorer does.</p>
        </article>
      </section>
    </div>
  );
}

function Toggle({
  enabled,
  onChange,
  label,
}: {
  enabled: boolean;
  onChange: () => void;
  label: string;
}) {
  return (
    <button className={`toggle ${enabled ? "on" : ""}`} role="switch" aria-checked={enabled} aria-label={label} onClick={onChange}>
      <span />
    </button>
  );
}

function SettingsPage({
  theme,
  onThemeToggle,
  settings,
  onSaved,
}: {
  theme: Theme;
  onThemeToggle: () => void;
  settings: Settings;
  onSaved: (settings: Settings) => void;
}) {
  const [scorer, setScorer] = useState(String(settings.scorer ?? "keyword"));
  const [threshold, setThreshold] = useState(Number(settings.auto_approve_threshold ?? 85));
  const [challenger, setChallenger] = useState(Boolean(settings.challenger ?? true));
  const [fraud, setFraud] = useState(Boolean(settings.fraud ?? true));
  const [workers, setWorkers] = useState(Number(settings.workers ?? 1));
  const [format, setFormat] = useState(String(settings.export_format ?? "jsonl"));
  const [evidence, setEvidence] = useState(Boolean(settings.include_evidence ?? true));
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    setScorer(String(settings.scorer ?? "keyword"));
    setThreshold(Number(settings.auto_approve_threshold ?? 85));
    setChallenger(Boolean(settings.challenger ?? true));
    setFraud(Boolean(settings.fraud ?? true));
    setWorkers(Number(settings.workers ?? 1));
    setFormat(String(settings.export_format ?? "jsonl"));
    setEvidence(Boolean(settings.include_evidence ?? true));
  }, [settings]);

  async function save() {
    setSaving(true);
    setSaved(false);
    setError("");
    try {
      const next = await api.saveSettings({
        scorer,
        auto_approve_threshold: threshold,
        challenger,
        fraud,
        workers,
        export_format: format,
        include_evidence: evidence,
      });
      onSaved(next);
      setSaved(true);
      window.setTimeout(() => setSaved(false), 1800);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not save settings.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="view">
      <PageHeader
        eyebrow="WORKSPACE CONTROL"
        title="Settings"
        detail="Choose the classifier, review threshold, privacy checks and export behavior used by new runs."
        action={<PrimaryButton onClick={save} disabled={saving}>{saving ? "Saving…" : saved ? <><Icon name="check" size={15} /> Saved</> : "Save changes"}</PrimaryButton>}
      />

      {error ? <div className="alert alert-error" role="alert"><Icon name="alert" size={17} /><span>{error}</span></div> : null}

      <div className="settings-grid">
        <section className="panel settings-panel">
          <div className="panel-head"><div><span className="section-kicker">CLASSIFICATION</span><h2>How VouchPilot scores</h2></div></div>
          <div className="setting">
            <div><strong>Default scorer</strong><span>Used for new classification runs.</span></div>
            <div className="choice-grid">{["keyword", "vouchpilot", "stub", "server"].map((value) => (
              <button key={value} className={scorer === value ? "choice selected" : "choice"} onClick={() => setScorer(value)}>
                <strong>{scorerName(value)}</strong>
                <span>{value === "server" ? "Local model" : value === "vouchpilot" ? "Rules + fraud screen" : value === "keyword" ? "Fastest path" : "Demo only"}</span>
              </button>
            ))}</div>
          </div>
          <div className="setting">
            <div className="setting-line"><div><strong>Review cutoff</strong><span>Rows below this confidence are routed to Review.</span></div><b>{threshold}%</b></div>
            <input className="range" type="range" min="60" max="99" value={threshold} onChange={(event) => setThreshold(Number(event.target.value))} />
            <div className="range-hints"><span>More human review</span><span>More automation</span></div>
          </div>
          <div className="setting-row"><div><strong>Pairwise challenger</strong><span>Re-check close calls against the strongest alternative.</span></div><Toggle enabled={challenger} onChange={() => setChallenger((value) => !value)} label="Pairwise challenger" /></div>
          <div className="setting-row"><div><strong>Parallel workers</strong><span>Increase throughput for local scoring.</span></div><div className="segmented">{[1, 2, 4, 8].map((value) => <button key={value} className={workers === value ? "selected" : ""} onClick={() => setWorkers(value)}>{value}</button>)}</div></div>
        </section>

        <section className="panel settings-panel">
          <div className="panel-head"><div><span className="section-kicker">PRIVACY & OUTPUT</span><h2>Local controls</h2></div><Icon name="shield" /></div>
          <div className="local-note"><Icon name="lock" size={17} /><div><strong>Local by design</strong><span>Browser, API and model runtime all stay on the machine.</span></div></div>
          <div className="setting-row"><div><strong>Fraud / injection scanner</strong><span>Applied by the VouchPilot+ scorer to narration and bill signals.</span></div><Toggle enabled={fraud} onChange={() => setFraud((value) => !value)} label="Fraud and injection scanner" /></div>
          <div className="setting-row"><div><strong>Primary export format</strong><span>Controls the one-click final export in Review.</span></div><div className="segmented">{["jsonl", "csv"].map((value) => <button key={value} className={format === value ? "selected" : ""} onClick={() => setFormat(value)}>{value.toUpperCase()}</button>)}</div></div>
          <div className="setting-row"><div><strong>Include evidence</strong><span>Keep evidence tags and decision markers in exports.</span></div><Toggle enabled={evidence} onChange={() => setEvidence((value) => !value)} label="Include evidence" /></div>
        </section>

        <section className="panel settings-panel">
          <div className="panel-head"><div><span className="section-kicker">APPEARANCE</span><h2>Workspace theme</h2></div></div>
          <div className="setting-row"><div><strong>Color mode</strong><span>Use a bright workspace or a low-glare dark canvas.</span></div><ThemeToggle theme={theme} onToggle={onThemeToggle} /></div>
        </section>
      </div>
    </div>
  );
}

function Footer({ navigate }: { navigate: (area: Area) => void }) {
  return (
    <footer className="footer">
      <div>
        <Logo compact />
        <p>Offline voucher intelligence for Indian accounting workflows.</p>
      </div>
      <nav aria-label="Footer">
        <button onClick={() => navigate("Dashboard")}>Product</button>
        <button onClick={() => navigate("Classify")}>Classify</button>
        <button onClick={() => navigate("Review")}>Review</button>
        <button onClick={() => navigate("Privacy")}>Privacy</button>
        <button onClick={() => navigate("Terms")}>Terms</button>
        <button onClick={() => navigate("Cookies")}>Cookies</button>
        <button onClick={() => navigate("Refunds")}>Refunds</button>
      </nav>
      <span>© {new Date().getFullYear()} CodeCarto · VouchPilot</span>
    </footer>
  );
}

function Legal({
  eyebrow,
  title,
  children,
}: {
  eyebrow: string;
  title: string;
  children: ReactNode;
}) {
  return (
    <div className="view">
      <PageHeader eyebrow={eyebrow} title={title} detail="VouchPilot local workspace policies and notices." />
      <article className="legal">
        {children}
      </article>
    </div>
  );
}

function App() {
  const [area, setArea] = useState<Area>("Dashboard");
  const [entered, setEntered] = useState(false);
  const [predictions, setPredictions] = useState<Prediction[]>([]);
  const [runs, setRuns] = useState<RunRecord[]>(() => loadRuns());
  const [labels, setLabels] = useState<LabelInfo[]>([]);
  const [settings, setSettings] = useState<Settings>({});
  const [navOpen, setNavOpen] = useState(false);
  const [theme, setTheme] = useState<Theme>(() => {
    try {
      return window.localStorage.getItem(THEME_KEY) === "dark" ? "dark" : "light";
    } catch {
      return "light";
    }
  });

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try {
      window.localStorage.setItem(THEME_KEY, theme);
    } catch {
      // Continue without persistence in private mode.
    }
  }, [theme]);

  useEffect(() => {
    void api.labels().then((response) => setLabels(response.labels)).catch(() => undefined);
    void api.settings().then((response) => setSettings(response)).catch(() => undefined);
  }, []);

  function navigate(next: Area) {
    setArea(next);
    setNavOpen(false);
    window.scrollTo({ top: 0, behavior: "auto" });
  }

  function commitRun(run: RunRecord, nextPredictions: Prediction[]) {
    setPredictions(nextPredictions);
    setRuns((current) => {
      const next = [run, ...current.filter((item) => item.id !== run.id)].slice(0, 20);
      saveRuns(next);
      return next;
    });
    setArea("Dashboard");
  }

  function commitReview(_decisions: Decision[], nextPredictions: Prediction[]) {
    setPredictions(nextPredictions);
    setRuns((current) => {
      const sourceRunId = current[0]?.id;
      if (!sourceRunId) return current;
      const next = applyReviewToRuns(current, sourceRunId, nextPredictions);
      saveRuns(next);
      return next;
    });
  }

  if (!entered) {
    return (
      <Welcome
        runs={runs}
        theme={theme}
        onThemeToggle={() => setTheme((value) => value === "light" ? "dark" : "light")}
        onEnter={() => setEntered(true)}
        onSystem={() => { setEntered(true); setArea("System"); }}
      />
    );
  }

  const reviewCount = predictions.filter((prediction) => prediction.needs_review).length;
  const isLegal = ["Privacy", "Terms", "Cookies", "Refunds"].includes(area);

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main">Skip to content</a>
      <aside className={`sidebar ${navOpen ? "open" : ""}`}>
        <div className="sidebar-top">
          <Logo />
          <div className="workspace-label"><span>LOCAL WORKSPACE</span><strong>VouchPilot</strong></div>
          <nav aria-label="Primary">
            {NAV.map((item) => (
              <button key={item.label} className={area === item.label ? "active" : ""} onClick={() => navigate(item.label)}>
                <Icon name={item.icon} />
                <span>{item.label}</span>
                {item.label === "Review" && reviewCount ? <b>{reviewCount}</b> : null}
              </button>
            ))}
          </nav>
        </div>
        <div className="sidebar-bottom">
          <div className="local-status"><StatusDot /><div><strong>Local runtime</strong><span>{scorerName(settings.scorer)} ready</span></div></div>
          <div className="sidebar-theme"><span>Theme</span><ThemeToggle theme={theme} onToggle={() => setTheme((value) => value === "light" ? "dark" : "light")} /></div>
        </div>
      </aside>

      {navOpen ? <button className="nav-backdrop" aria-label="Close navigation" onClick={() => setNavOpen(false)} /> : null}

      <main id="main" className="main">
        <div className="mobile-bar">
          <Logo compact />
          <button className="icon-btn" aria-label="Open navigation" onClick={() => setNavOpen(true)}><Icon name="more" /></button>
        </div>

        {!isLegal ? (
          <div className="breadcrumbs">
            <span>VouchPilot</span><Icon name="chevron" size={13} /><strong>{area}</strong>
          </div>
        ) : null}

        {area === "Dashboard" ? <Dashboard navigate={navigate} runs={runs} predictions={predictions} scorer={String(settings.scorer ?? "keyword")} /> : null}
        {area === "Classify" ? <Classify settings={settings} initial={predictions} onDone={commitRun} /> : null}
        {area === "Review" ? <Review
          predictions={predictions}
          labels={labels}
          threshold={Number(settings.auto_approve_threshold ?? 85)}
          exportFormat={String(settings.export_format ?? "jsonl")}
          includeEvidence={Boolean(settings.include_evidence ?? true)}
          onExport={commitReview}
        /> : null}
        {area === "System" ? <System /> : null}
        {area === "Settings" ? <SettingsPage theme={theme} onThemeToggle={() => setTheme((value) => value === "light" ? "dark" : "light")} settings={settings} onSaved={setSettings} /> : null}

        {area === "Privacy" ? (
          <Legal eyebrow="PRIVACY" title="Privacy policy">
            <p>VouchPilot is local-first. The browser communicates with a local API endpoint and the classification pipeline runs on the same machine. Recent run metadata and appearance settings may be kept in browser local storage.</p>
            <h2>Data handling</h2>
            <p>Uploaded workbooks and document images are processed by the local application. They are not intentionally uploaded to a third-party service by the VouchPilot UI.</p>
            <h2>Contact</h2>
            <p>For privacy questions or vulnerability reports, contact the project maintainer through the repository.</p>
          </Legal>
        ) : null}

        {area === "Terms" ? (
          <Legal eyebrow="TERMS" title="Terms of use">
            <p>VouchPilot is decision-support software for classifying accounting transactions. It is not tax, audit or legal advice.</p>
            <p>You remain responsible for reviewing classifications and complying with applicable GST requirements before filing or posting entries.</p>
          </Legal>
        ) : null}

        {area === "Cookies" ? (
          <Legal eyebrow="COOKIES" title="Cookie policy">
            <p>The web UI does not require advertising or tracking cookies. Functional preferences such as theme and recent run metadata may be stored in local storage.</p>
          </Legal>
        ) : null}

        {area === "Refunds" ? (
          <Legal eyebrow="REFUNDS" title="Refund policy">
            <p>The current VouchPilot workspace contains no in-app purchase flow. This page is retained as a placeholder for any future paid distribution policy.</p>
          </Legal>
        ) : null}

        <Footer navigate={navigate} />
      </main>
    </div>
  );
}

export default App;

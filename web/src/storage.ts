import { isPrediction, type Prediction, type RunRecord } from "./api.ts";

export const RUNS_KEY = "vouchpilot-runs";
export const THEME_KEY = "vouchpilot-theme";
export const SETTINGS_KEY = "vouchpilot-settings";

export const DEFAULT_SETTINGS: Record<string, unknown> = {
  scorer: "keyword",
  endpoint: "http://127.0.0.1:8080",
  workers: 1,
  challenger: true,
  fraud: true,
  auto_approve_threshold: 85,
  export_format: "jsonl",
  include_evidence: true,
  theme: "light",
};

export function loadSettings(fallback: Record<string, unknown> = {}): Record<string, unknown> {
  const base = { ...DEFAULT_SETTINGS, ...fallback };
  try {
    const parsed: unknown = JSON.parse(window.localStorage.getItem(SETTINGS_KEY) ?? "{}");
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) return base;
    return { ...base, ...(parsed as Record<string, unknown>) };
  } catch {
    return base;
  }
}

export function saveSettings(settings: Record<string, unknown>): void {
  try {
    window.localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings));
  } catch {
    // Continue without persistence in private mode.
  }
}


type StoredRun = Partial<RunRecord> & Pick<RunRecord, "file" | "rows" | "status" | "completed">;

function normalizeRun(value: unknown, index: number): RunRecord | null {
  if (!value || typeof value !== "object") return null;
  const raw = value as Partial<StoredRun>;
  if (
    typeof raw.file !== "string" ||
    typeof raw.rows !== "number" ||
    typeof raw.status !== "string" ||
    typeof raw.completed !== "string"
  ) {
    return null;
  }
  return {
    id: typeof raw.id === "string" ? raw.id : `${raw.completed}-${raw.file}-${index}`,
    file: raw.file,
    rows: raw.rows,
    accuracy: typeof raw.accuracy === "number" ? raw.accuracy : null,
    status: raw.status,
    completed: raw.completed,
    predictions: Array.isArray(raw.predictions)
      ? raw.predictions.filter(isPrediction)
      : [],
  };
}

export function loadRuns(): RunRecord[] {
  try {
    const parsed: unknown = JSON.parse(window.localStorage.getItem(RUNS_KEY) ?? "[]");
    if (!Array.isArray(parsed)) return [];
    return parsed.map(normalizeRun).filter((run): run is RunRecord => run !== null).slice(0, 20);
  } catch {
    return [];
  }
}

export function saveRuns(runs: RunRecord[]): void {
  const candidates = Array.from(new Set([20, 12, 8, 4, 1].filter((limit) => runs.length >= limit)));
  for (const limit of candidates) {
    try {
      window.localStorage.setItem(RUNS_KEY, JSON.stringify(runs.slice(0, limit)));
      return;
    } catch {
      // Retry with a smaller complete set before dropping prediction data.
    }
  }

  if (runs.length) {
    try {
      const latest = runs[0];
      const { predictions: _predictions, ...metadata } = latest;
      window.localStorage.setItem(
        RUNS_KEY,
        JSON.stringify([{ ...metadata, predictions: [] }]),
      );
    } catch {
      // In-memory state remains authoritative for this session.
    }
  }
}

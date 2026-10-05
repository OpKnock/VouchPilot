import type { Prediction, RunRecord } from "./api";

export const RUNS_KEY = "vouchpilot-runs";
export const THEME_KEY = "vouchpilot-theme";

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
      ? (raw.predictions as Prediction[])
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
  try {
    window.localStorage.setItem(RUNS_KEY, JSON.stringify(runs.slice(0, 20)));
  } catch {
    // A full/private storage bucket must never break the workspace.
    try {
      window.localStorage.setItem(
        RUNS_KEY,
        JSON.stringify(
          runs.slice(0, 8).map(({ predictions: _predictions, ...run }) => ({
            ...run,
            predictions: [],
          })),
        ),
      );
    } catch {
      // In-memory state remains authoritative for this session.
    }
  }
}

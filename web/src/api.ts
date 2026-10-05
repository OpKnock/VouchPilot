export interface Prediction {
  row_id: number;
  invoice_number: string;
  voucher_type: string;
  confidence: number;
  needs_review: boolean;
  top_k: [string, number][];
  evidence: string[];
}

export interface LabelInfo {
  code: string;
  group: string;
  name: string;
}

export interface RunRecord {
  id: string;
  file: string;
  rows: number;
  accuracy: number | null;
  status: string;
  completed: string;
  predictions: Prediction[];
}

export interface SystemInfo {
  version: string;
  modules: Record<string, string>;
  server: { url: string; up: boolean };
  weights: string[];
}

type PredictionResponse = {
  predictions: Prediction[];
  n_rows: number;
  invalid: number;
};

export function isPrediction(value: unknown): value is Prediction {
  if (!value || typeof value !== "object") return false;
  const row = value as Record<string, unknown>;
  const topK = row.top_k;
  const evidence = row.evidence;
  return (
    typeof row.row_id === "number" &&
    Number.isInteger(row.row_id) &&
    row.row_id > 0 &&
    typeof row.invoice_number === "string" &&
    row.invoice_number.length > 0 &&
    typeof row.voucher_type === "string" &&
    typeof row.confidence === "number" &&
    Number.isFinite(row.confidence) &&
    row.confidence >= 0 &&
    row.confidence <= 1 &&
    typeof row.needs_review === "boolean" &&
    Array.isArray(topK) &&
    topK.every(
      (entry) =>
        Array.isArray(entry) &&
        entry.length === 2 &&
        typeof entry[0] === "string" &&
        typeof entry[1] === "number" &&
        Number.isFinite(entry[1]),
    ) &&
    Array.isArray(evidence) &&
    evidence.every((entry) => typeof entry === "string")
  );
}

function parsePredictionResponse(payload: unknown): PredictionResponse {
  if (!payload || typeof payload !== "object") {
    throw new ApiError("VouchPilot received an invalid response from the API.", 0, payload);
  }

  const body = payload as Record<string, unknown>;
  const predictions = body.predictions;
  const nRows = body.n_rows;
  const invalid = body.invalid;

  if (
    !Array.isArray(predictions) ||
    !predictions.every(isPrediction) ||
    typeof nRows !== "number" ||
    !Number.isInteger(nRows) ||
    nRows < 0 ||
    typeof invalid !== "number" ||
    !Number.isInteger(invalid) ||
    invalid < 0
  ) {
    throw new ApiError("VouchPilot received an invalid response from the API.", 0, payload);
  }

  return { predictions, n_rows: nRows, invalid };
}

export const BASE =
  ((import.meta as unknown as { env?: Record<string, string> }).env?.VITE_API_URL as
    | string
    | undefined) ?? "";

const RUNTIME_MODE =
  ((import.meta as unknown as { env?: Record<string, string> }).env?.VITE_RUNTIME_MODE as
    | string
    | undefined) ?? "";

const DESKTOP_DOWNLOAD_URL =
  ((import.meta as unknown as { env?: Record<string, string> }).env?.VITE_DESKTOP_DOWNLOAD_URL as
    | string
    | undefined) ?? "/desktop-package";

export function isHostedMode(): boolean {
  if (RUNTIME_MODE.toLowerCase() === "hosted") return true;
  if (RUNTIME_MODE.toLowerCase() === "local") return false;
  if (!BASE || typeof window === "undefined") return false;
  try {
    return new URL(BASE, window.location.origin).origin !== window.location.origin;
  } catch {
    return false;
  }
}

export class ApiError extends Error {
  status: number;
  details: unknown;

  constructor(message: string, status: number, details: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.details = details;
  }
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(BASE + path, {
      ...init,
      headers: {
        Accept: "application/json",
        ...(init?.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
        ...init?.headers,
      },
    });
  } catch {
    throw new ApiError(
      "VouchPilot could not reach the local API. Start the backend and try again.",
      0,
      null,
    );
  }

  const contentType = response.headers.get("content-type") ?? "";
  const payload = contentType.includes("application/json")
    ? await response.json().catch(() => null)
    : await response.text().catch(() => "");

  if (!response.ok) {
    const message =
      typeof payload === "object" && payload && "detail" in payload
        ? String((payload as { detail?: unknown }).detail)
        : typeof payload === "string" && payload.trim()
          ? payload
          : response.statusText || "Request failed";
    throw new ApiError(message, response.status, payload);
  }

  return payload as T;
}

export const api = {
  health: () => req<{ status: string; version: string; modules: Record<string, string> }>("/health"),
  system: () => req<SystemInfo>("/system"),
  labels: () => req<{ labels: LabelInfo[] }>("/labels"),
  settings: () => req<Record<string, unknown>>("/settings"),
  saveSettings: (patch: Record<string, unknown>) =>
    req<Record<string, unknown>>("/settings", {
      method: "POST",
      body: JSON.stringify(patch),
    }),
  evaluate: (gold: object[], pred: object[]) =>
    req<Record<string, unknown>>("/evaluate", {
      method: "POST",
      body: JSON.stringify({ gold, pred }),
    }),
  predictFile: async (
    file: File,
    params: Record<string, string>,
  ): Promise<PredictionResponse> => {
    const fd = new FormData();
    fd.append("file", file);
    const query = new URLSearchParams(params).toString();
    const payload = await req<unknown>("/predict?" + query, {
      method: "POST",
      body: fd,
    });
    return parsePredictionResponse(payload);
  },
  launcherUrl: () =>
    DESKTOP_DOWNLOAD_URL.startsWith("/")
      ? BASE + DESKTOP_DOWNLOAD_URL
      : DESKTOP_DOWNLOAD_URL,
  desktopDownloadUrl: () =>
    DESKTOP_DOWNLOAD_URL.startsWith("/")
      ? BASE + DESKTOP_DOWNLOAD_URL
      : DESKTOP_DOWNLOAD_URL,
};

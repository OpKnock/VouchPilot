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

const BASE =
  ((import.meta as unknown as { env?: Record<string, string> }).env?.VITE_API_URL as
    | string
    | undefined) ?? "";

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
  ): Promise<{ predictions: Prediction[]; n_rows: number; invalid: number }> => {
    const fd = new FormData();
    fd.append("file", file);
    const query = new URLSearchParams(params).toString();
    return req<{ predictions: Prediction[]; n_rows: number; invalid: number }>(
      "/predict?" + query,
      { method: "POST", body: fd },
    );
  },
  launcherUrl: () => BASE + "/desktop-package",
};

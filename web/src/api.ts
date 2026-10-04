export interface Prediction {
  row_id: number;
  invoice_number: string;
  voucher_type: string;
  confidence: number;
  needs_review: boolean;
  top_k: [string, number][];
  evidence: string[];
}

export interface LabelInfo { code: string; group: string; name: string }

export interface RunRecord {
  file: string;
  rows: number;
  accuracy: number | null;
  status: string;
  completed: string;
  predictions: Prediction[];
}

const BASE: string =
  ((import.meta as unknown as { env?: Record<string, string> }).env?.VITE_API_URL as string | undefined) ?? "";

async function req(path: string, init?: RequestInit): Promise<never> {
  const res = await fetch(BASE + path, init);
  if (!res.ok) throw new Error(await res.text());
  return (await res.json()) as never;
}

export const api = {
  health: (): Promise<never> => req("/health"),
  system: (): Promise<never> => req("/system"),
  labels: (): Promise<{ labels: LabelInfo[] }> => req("/labels"),
  settings: (): Promise<Record<string, unknown>> => req("/settings"),
  saveSettings: (patch: Record<string, unknown>): Promise<Record<string, unknown>> =>
    req("/settings", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(patch) }),
  evaluate: (gold: object[], pred: object[]): Promise<never> =>
    req("/evaluate", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ gold, pred }) }),
  predictFile: async (file: File, params: Record<string, string>): Promise<{ predictions: Prediction[]; n_rows: number; invalid: number }> => {
    const fd = new FormData();
    fd.append("file", file);
    const res = await fetch(BASE + "/predict?" + new URLSearchParams(params).toString(), { method: "POST", body: fd });
    if (!res.ok) throw new Error(await res.text());
    return (await res.json()) as { predictions: Prediction[]; n_rows: number; invalid: number };
  },
  launcherUrl: (): string => BASE + "/desktop-package",
};

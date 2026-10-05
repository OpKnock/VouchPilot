import { strict as assert } from "node:assert";
import test, { afterEach } from "node:test";

import type { Prediction, RunRecord } from "./api.ts";
import {
  RUNS_KEY,
  SETTINGS_KEY,
  loadRuns,
  loadSettings,
  saveRuns,
  saveSettings,
} from "./storage.ts";

const realWindow = globalThis.window;

afterEach(() => {
  globalThis.window = realWindow;
});

function prediction(): Prediction {
  return {
    row_id: 1,
    invoice_number: "PI-001",
    voucher_type: "Purchase",
    confidence: 0.91,
    needs_review: false,
    top_k: [["Purchase", 0.91]],
    evidence: ["PERSPECTIVE: seller"],
  };
}

test("storage pressure retries with fewer runs while preserving predictions", () => {
  const calls: string[] = [];
  const stored: Record<string, string> = {};
  let failures = 2;

  globalThis.window = {
    localStorage: {
      getItem: () => null,
      setItem: (key: string, value: string) => {
        calls.push(value);
        if (failures > 0) {
          failures -= 1;
          throw new Error("quota");
        }
        stored[key] = value;
      },
    },
  } as unknown as Window & typeof globalThis;

  const runs: RunRecord[] = Array.from({ length: 20 }, (_, index) => ({
    id: `run-${index}`,
    file: `ledger-${index}.xlsx`,
    rows: 1,
    accuracy: null,
    status: "Completed",
    completed: `2026-10-05T00:00:0${index % 10}Z`,
    predictions: [prediction()],
  }));

  saveRuns(runs);

  assert.equal(calls.length, 3);
  const recovered = JSON.parse(stored[RUNS_KEY]) as RunRecord[];
  assert.equal(recovered.length, 8);
  assert.ok(recovered[0].predictions.length > 0);
});

    
test("loadRuns drops malformed persisted predictions instead of crashing the workspace", () => {
  globalThis.window = {
    localStorage: {
      getItem: () =>
        JSON.stringify([
          {
            id: "run-1",
            file: "ledger.xlsx",
            rows: 1,
            accuracy: null,
            status: "Completed",
            completed: "2026-10-05T00:00:00Z",
            predictions: [{ row_id: "bad", confidence: "not-a-number" }],
          },
        ]),
      setItem: () => undefined,
    },
  } as unknown as Window & typeof globalThis;

  const runs = loadRuns();
  assert.equal(runs.length, 1);
  assert.deepEqual(runs[0].predictions, []);
});


test("hosted settings round-trip through browser storage", () => {
  const stored: Record<string, string> = {};
  globalThis.window = {
    localStorage: {
      getItem: (key: string) => stored[key] ?? null,
      setItem: (key: string, value: string) => {
        stored[key] = value;
      },
    },
  } as unknown as Window & typeof globalThis;

  saveSettings({ scorer: "vouchpilot", auto_approve_threshold: 92 });
  const loaded = loadSettings({ fraud: false });

  assert.equal(stored[SETTINGS_KEY] !== undefined, true);
  assert.equal(loaded.scorer, "vouchpilot");
  assert.equal(loaded.auto_approve_threshold, 92);
  assert.equal(loaded.fraud, false);
});

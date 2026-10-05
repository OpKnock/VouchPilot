import { strict as assert } from "node:assert";
import test from "node:test";

import { applyReviewToRuns } from "./review.ts";

const prediction = (needs_review: boolean) => ({
  row_id: 1,
  invoice_number: "PI-001",
  voucher_type: "Purchase",
  confidence: 0.8,
  needs_review,
  top_k: [["Purchase", 0.8], ["Sales", 0.2]] as [string, number][],
  evidence: [],
});

test("marks the source run completed after every review item is resolved", () => {
  const runs = [{
    id: "run-1",
    file: "ledger.xlsx",
    rows: 1,
    accuracy: null,
    status: "Review needed",
    completed: "today",
    predictions: [prediction(true)],
  }];

  const updated = applyReviewToRuns(runs, "run-1", [prediction(false)]);

  assert.equal(updated[0].status, "Completed");
  assert.deepEqual(updated[0].predictions, [prediction(false)]);
});

test("keeps a run in review-needed state when an escalation remains open", () => {
  const runs = [{
    id: "run-1",
    file: "ledger.xlsx",
    rows: 1,
    accuracy: null,
    status: "Review needed",
    completed: "today",
    predictions: [prediction(true)],
  }];

  const updated = applyReviewToRuns(runs, "run-1", [prediction(true)]);

  assert.equal(updated[0].status, "Review needed");
});

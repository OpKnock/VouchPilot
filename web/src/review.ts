import type { Prediction, RunRecord } from "./api.ts";

export function applyReviewToRuns(
  runs: RunRecord[],
  sourceRunId: string,
  predictions: Prediction[],
): RunRecord[] {
  return runs.map((run) => {
    if (run.id !== sourceRunId) return run;
    return {
      ...run,
      status: predictions.some((prediction) => prediction.needs_review)
        ? "Review needed"
        : "Completed",
      predictions,
    };
  });
}

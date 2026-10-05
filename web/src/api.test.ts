import { strict as assert } from "node:assert";
import test, { afterEach } from "node:test";

import { ApiError, api } from "./api.ts";

const realFetch = globalThis.fetch;

afterEach(() => {
  globalThis.fetch = realFetch;
});

test("rejects a successful prediction response without predictions", async () => {
  globalThis.fetch = (async () =>
    new Response(JSON.stringify({ n_rows: 1 }), {
      status: 200,
      headers: { "content-type": "application/json" },
    })) as typeof fetch;

  const file = new File(["Invoice No,Total\nPI-1,100\n"], "sample.csv", {
    type: "text/csv",
  });

  await assert.rejects(
    api.predictFile(file, {}),
    (error: unknown) =>
      error instanceof ApiError &&
      error.status === 0 &&
      error.message.includes("invalid response"),
  );
});

test("rejects successful prediction responses with malformed prediction rows", async () => {
  globalThis.fetch = (async () =>
    new Response(
      JSON.stringify({
        predictions: [{ row_id: "one" }],
        n_rows: 1,
        invalid: 0,
      }),
      {
        status: 200,
        headers: { "content-type": "application/json" },
      },
    )) as typeof fetch;

  const file = new File(["Invoice No,Total\nPI-1,100\n"], "sample.csv", {
    type: "text/csv",
  });

  await assert.rejects(
    api.predictFile(file, {}),
    (error: unknown) =>
      error instanceof ApiError &&
      error.status === 0 &&
      error.message.includes("invalid response"),
  );
});

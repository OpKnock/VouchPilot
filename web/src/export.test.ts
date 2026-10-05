import test from "node:test";
import assert from "node:assert/strict";

import { csvEscape } from "./export.ts";

test("csvEscape neutralizes spreadsheet formula prefixes", () => {
  assert.equal(csvEscape("=HYPERLINK(\"http://evil\")"), "\"'=HYPERLINK(\"\"http://evil\"\")\"");
  assert.equal(csvEscape("+SUM(A1:A2)"), "\"'+SUM(A1:A2)\"");
  assert.equal(csvEscape("-10"), "\"'-10\"");
  assert.equal(csvEscape("@cmd"), "\"'@cmd\"");
  assert.equal(csvEscape("normal text"), "\"normal text\"");
});

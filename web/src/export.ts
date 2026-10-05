const FORMULA_PREFIX = /^[=+\\-@]/;

export function csvEscape(value: unknown): string {
  let text = String(value ?? "");
  if (FORMULA_PREFIX.test(text)) {
    text = "'" + text;
  }
  return '"' + text.replace(/"/g, '""') + '"';
}

export function predictionsToCsv(
  rows: Array<{
    row_id: number;
    invoice_number: string;
    voucher_type: string;
    confidence: number;
    needs_review: boolean;
    evidence: string[];
  }>,
  includeEvidence = true,
): string {
  const header = [
    "row_id",
    "invoice_number",
    "voucher_type",
    "confidence",
    "needs_review",
    ...(includeEvidence ? ["evidence"] : []),
  ];
  return [
    header.join(","),
    ...rows.map((row) =>
      [
        row.row_id,
        csvEscape(row.invoice_number),
        csvEscape(row.voucher_type),
        row.confidence.toFixed(4),
        row.needs_review,
        ...(includeEvidence ? [csvEscape(row.evidence.join(" | "))] : []),
      ].join(","),
    ),
  ].join("\n");
}

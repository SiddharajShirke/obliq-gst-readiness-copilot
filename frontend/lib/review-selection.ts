type ExtractionReviewCandidate = {
  id: string;
  review_status: string;
  review_eligible?: boolean;
  document_type?: string | null;
  invoice_category?: string | null;
  source_type?: string | null;
};

const CLIENT_EXTRACTION_CATEGORIES = new Set([
  "sales_register",
  "purchase_register",
  "sales_invoices",
  "purchase_expense_invoices",
  "credit_debit_notes",
  "gst_special_transactions",
]);

export function extractionReviewEligibleIds(
  records: ExtractionReviewCandidate[],
): string[] {
  return records.filter(record => {
    if (typeof record.review_eligible === "boolean") return record.review_eligible;
    const category = CLIENT_EXTRACTION_CATEGORIES.has(record.source_type ?? "")
      ? record.source_type
      : record.document_type ?? record.invoice_category;
    return record.review_status === "pending"
      && CLIENT_EXTRACTION_CATEGORIES.has(category ?? "")
      && !["gstr2b", "developer_ground_truth"].includes(record.source_type ?? "");
  }).map(record => record.id);
}

export function selectAllVisible(
  current: Set<string>,
  visibleEligibleIds: string[],
  checked: boolean,
): Set<string> {
  const next = new Set(current);
  for (const id of visibleEligibleIds) {
    if (checked) next.add(id);
    else next.delete(id);
  }
  return next;
}

export function trimSelectionToVisible(
  current: Set<string>,
  visibleEligibleIds: string[],
): Set<string> {
  const visible = new Set(visibleEligibleIds);
  return new Set([...current].filter(id => visible.has(id)));
}

export function selectionState(
  current: Set<string>,
  visibleEligibleIds: string[],
): {checked: boolean; indeterminate: boolean; selectedVisibleCount: number} {
  const selectedVisibleCount = visibleEligibleIds.filter(id => current.has(id)).length;
  return {
    checked: visibleEligibleIds.length > 0 && selectedVisibleCount === visibleEligibleIds.length,
    indeterminate: selectedVisibleCount > 0 && selectedVisibleCount < visibleEligibleIds.length,
    selectedVisibleCount,
  };
}

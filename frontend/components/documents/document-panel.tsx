"use client";

import {CheckCircle2, FileSearch, FileText, XCircle} from "lucide-react";
import {useCallback, useEffect, useState} from "react";
import {toast} from "sonner";
import {apiFetch, resolveAssetUrl} from "../../lib/api";
import {formatDate, formatStatus} from "../../lib/format";
import {
  extractionReviewEligibleIds,
  selectAllVisible,
  trimSelectionToVisible,
} from "../../lib/review-selection";
import type {
  DocumentRecord,
  Extraction,
  ExtractionPortfolioResult,
  ExtractionPortfolioScope,
  GSTRecord,
  Requirement,
} from "../../lib/types";
import {Badge} from "../ui/badge";
import {Button} from "../ui/button";
import {Card} from "../ui/card";
import {ExtractionPortfolio, ExtractionReviewWorkspace} from "./extraction-portfolio";

type SummaryDocument = DocumentRecord & {extraction?: Extraction | null};
type ExtractionSummary = {documents: SummaryDocument[]; records: GSTRecord[]};
type Props = {applicationId: string; checklist: Requirement[]; onChanged: () => void};

const money = (value?: string | number | null) => value == null
  ? "—"
  : new Intl.NumberFormat("en-IN", {
      style: "currency", currency: "INR", maximumFractionDigits: 2,
    }).format(Number(value));

const editableFields = [
  ["document_number", "Invoice / document number"], ["document_date", "Date"],
  ["supplier_name", "Supplier"], ["supplier_gstin", "Supplier GSTIN"],
  ["taxable_value", "Taxable value"], ["igst", "IGST"], ["cgst", "CGST"],
  ["sgst_utgst", "SGST"], ["total_document_value", "Total value"],
] as const;

const EMPTY_PORTFOLIO: ExtractionPortfolioResult = {
  scope: "combined",
  summary: {
    record_count: 0, taxable_value: 0, total_tax: 0, document_value: 0,
    approved_count: 0, needs_review_count: 0, rcm_count: 0,
  },
  records: [],
};

export function DocumentPanel({applicationId, checklist, onChanged}: Props) {
  const [summary, setSummary] = useState<ExtractionSummary>({documents: [], records: []});
  const [portfolio, setPortfolio] = useState<ExtractionPortfolioResult>(EMPTY_PORTFOLIO);
  const [portfolioScope, setPortfolioScope] = useState<ExtractionPortfolioScope>("combined");
  const [portfolioMode, setPortfolioMode] = useState<"portfolio" | "table">("portfolio");
  const [selectedRecordIds, setSelectedRecordIds] = useState<Set<string>>(new Set());
  const [selected, setSelected] = useState<SummaryDocument | null>(null);
  const [selectedRecord, setSelectedRecord] = useState<GSTRecord | null>(null);
  const [signedUrl, setSignedUrl] = useState("");
  const [search, setSearch] = useState("");
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState(false);
  const [editedRows, setEditedRows] = useState<Record<string, unknown>[]>([]);

  const load = useCallback(async () => {
    const [nextSummary, nextPortfolio] = await Promise.all([
      apiFetch<ExtractionSummary>(`/applications/${applicationId}/documents/extraction-summary`),
      apiFetch<ExtractionPortfolioResult>(`/applications/${applicationId}/documents/portfolio?scope=${portfolioScope}`),
    ]);
    setSummary(nextSummary);
    setPortfolio(nextPortfolio);
    const eligibleIds = extractionReviewEligibleIds(nextPortfolio.records);
    setSelectedRecordIds(current => trimSelectionToVisible(current, eligibleIds));
  }, [applicationId, portfolioScope]);

  useEffect(() => {
    const initial = window.setTimeout(() => void load().catch(error =>
      toast.error(error instanceof Error ? error.message : "Unable to load extraction data")), 0);
    const timer = window.setInterval(() => void load().catch(() => undefined), 3000);
    return () => { window.clearTimeout(initial); window.clearInterval(timer); };
  }, [load]);

  const labels = new Map(checklist.map(item => [item.id, item.label]));
  const selectedRows = selected
    ? summary.records.filter(row => row.document_id === selected.id)
    : [];

  function toggleRecordSelection(id: string) {
    setSelectedRecordIds(current => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }

  async function openDocument(document: SummaryDocument, startEditing = false) {
    setSelected(document);
    setSignedUrl("");
    setEditing(startEditing);
    const structuredRows = document.extraction?.structured_data?.rows;
    setEditedRows(Array.isArray(structuredRows)
      ? structuredRows.map(row => ({...(row as Record<string, unknown>)})) : []);
    try {
      const detail = await apiFetch<DocumentRecord>(`/documents/${document.id}`);
      setSignedUrl(resolveAssetUrl(detail.signed_url ?? ""));
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Unable to open original document");
    }
  }

  async function action(path: string, body?: unknown) {
    setBusy(true);
    try {
      await apiFetch(path, {method: "POST", body: body ? JSON.stringify(body) : undefined});
      await load();
      onChanged();
      toast.success("Extraction status updated");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Action failed");
    } finally {
      setBusy(false);
    }
  }

  function updateEditedRow(index: number, field: string, value: string) {
    setEditedRows(current => current.map((row, rowIndex) =>
      rowIndex === index ? {...row, [field]: value || null} : row));
  }

  async function editAndApprove() {
    if (!selected?.extraction) return;
    setBusy(true);
    try {
      await apiFetch(`/documents/${selected.id}/extraction`, {
        method: "PATCH",
        body: JSON.stringify({
          structured_data: {...selected.extraction.structured_data, rows: editedRows},
          review_notes: "Corrected and approved in OBLIQ",
        }),
      });
      setEditing(false);
      setSelected(null);
      await load();
      onChanged();
      toast.success("Corrected extraction approved");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Unable to save corrections");
    } finally {
      setBusy(false);
    }
  }

  function editPortfolioRecord(record: GSTRecord) {
    const document = summary.documents.find(item => item.id === record.document_id);
    setSelectedRecord(null);
    if (document) void openDocument(document, true);
  }

  async function bulkReview(actionName: "approve" | "reject") {
    const eligible = new Set(extractionReviewEligibleIds(portfolio.records));
    const recordIds = [...selectedRecordIds].filter(id => eligible.has(id));
    if (!recordIds.length) {
      setSelectedRecordIds(new Set());
      toast.info("No pending client extraction records remain selected.");
      return;
    }
    if (recordIds.length !== selectedRecordIds.size) {
      setSelectedRecordIds(new Set(recordIds));
    }
    const verb = actionName === "approve" ? "approve" : "reject";
    if (!window.confirm(`${verb === "approve" ? "Approve" : "Reject"} ${recordIds.length} selected extraction records? This action will be audited.`)) return;
    setBusy(true);
    try {
      await apiFetch(`/applications/${applicationId}/extractions/bulk-review`, {
        method: "POST",
        body: JSON.stringify({record_ids: recordIds, action: actionName, notes: "Bulk CA review in OBLIQ"}),
      });
      setSelectedRecordIds(new Set());
      await load();
      onChanged();
      toast.success(`${recordIds.length} extraction records updated`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Bulk review failed");
    } finally {
      setBusy(false);
    }
  }

  return <div className="grid gap-6">
    <Card className="border-blue-200 bg-blue-50 p-5">
      <h2 className="font-bold text-blue-950">Structured GST extraction</h2>
      <p className="mt-2 text-sm leading-6 text-blue-900">Originals remain private in Supabase Storage. Deterministic parsing runs first; AI-assisted fields remain subject to CA review.</p>
    </Card>
    <Card className="overflow-hidden">
      <div className="border-b border-[#eeeae6] p-5">
        <h3 className="font-bold">Original document intake</h3>
        <p className="mt-1 text-xs text-[#77716e]">{summary.documents.length} private files in this application</p>
      </div>
      <div className="divide-y divide-[#eeeae6]">
        {summary.documents.map(document => <div key={document.id} className="flex flex-wrap items-center gap-3 p-5">
          <span className="grid h-10 w-10 place-items-center rounded-xl bg-[#e8f1fa]"><FileText size={18}/></span>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-semibold">{document.original_name}</p>
            <p className="mt-1 text-xs text-[#77716e]">{document.requirement_id
              ? labels.get(document.requirement_id) ?? formatStatus(document.document_type ?? "unknown")
              : formatStatus(document.document_type ?? "unknown")} · {formatDate(document.created_at)}</p>
          </div>
          <Badge value={document.processing_status}/>
          {document.processing_status === "awaiting_processing" && <Button variant="secondary" disabled={busy} onClick={() => void action(`/documents/${document.id}/process`)}>Process</Button>}
          <Button variant="ghost" onClick={() => void openDocument(document)}><FileSearch size={16}/>Review</Button>
        </div>)}
        {!summary.documents.length && <div className="p-10 text-center text-sm text-[#77716e]">No files uploaded yet.</div>}
      </div>
    </Card>
    <ExtractionPortfolio
      result={portfolio}
      mode={portfolioMode}
      search={search}
      selectedIds={selectedRecordIds}
      onScopeChange={scope => {
        setPortfolioScope(scope);
        setSearch("");
        setSelectedRecordIds(new Set());
      }}
      onModeChange={setPortfolioMode}
      onSearchChange={value => {
        setSearch(value);
        setSelectedRecordIds(new Set());
      }}
      onToggleSelection={toggleRecordSelection}
      onSelectVisible={(ids, checked) => setSelectedRecordIds(current =>
        selectAllVisible(current, ids, checked))}
      onInspect={setSelectedRecord}
      onBulkReview={actionName => void bulkReview(actionName)}
      reviewBusy={busy}
    />
    {selectedRecord && <ExtractionReviewWorkspace
      record={selectedRecord}
      onClose={() => setSelectedRecord(null)}
      onApprove={() => {
        void action(`/documents/${selectedRecord.document_id}/approve`, {notes: "Reviewed in OBLIQ"});
        setSelectedRecord(null);
      }}
      onEdit={() => editPortfolioRecord(selectedRecord)}
      onReject={() => {
        void action(`/documents/${selectedRecord.document_id}/reject`, {notes: "Needs clarification"});
        setSelectedRecord(null);
      }}
    />}
    {selected && <div className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-4" onClick={() => setSelected(null)}>
      <Card className="max-h-[95vh] w-full max-w-[95vw] overflow-auto p-5" onClick={event => event.stopPropagation()}>
        <div className="flex items-start justify-between"><div><p className="text-xs font-bold tracking-[.12em] text-[#477ca8]">ORIGINAL DOCUMENT | EXTRACTED INFORMATION</p><h3 className="mt-2 text-xl font-bold">{selected.original_name}</h3></div><button aria-label="Close review" onClick={() => setSelected(null)}><XCircle/></button></div>
        <div className="mt-5 grid gap-5 lg:grid-cols-2">
          <div className="min-h-96 overflow-hidden rounded-2xl border border-[#ddd8d3] bg-[#f8f7f5]">{signedUrl ? <iframe title="Original document" src={signedUrl} className="h-[650px] w-full"/> : <div className="grid h-96 place-items-center text-sm text-[#77716e]">Loading original document…</div>}</div>
          <div><h4 className="font-bold">Extracted information</h4><div className="mt-3 grid gap-3">{editing
            ? editedRows.map((row, index) => <div key={index} className="grid gap-3 rounded-2xl border border-[#e5e2de] p-4 sm:grid-cols-2">{editableFields.map(([field, label]) => <label key={field} className="grid gap-1 text-xs text-[#77716e]">{label}<input className="rounded-lg border border-[#ddd8d3] px-3 py-2 text-sm text-[#211f1e]" value={String(row[field] ?? "")} onChange={event => updateEditedRow(index, field, event.target.value)}/></label>)}</div>)
            : selectedRows.map(row => <div key={row.id} className="rounded-2xl border border-[#e5e2de] p-4"><div className="flex justify-between gap-3"><strong>{row.invoice_number ?? "Unnumbered record"}</strong><Badge value={row.review_status}/></div><dl className="mt-3 grid grid-cols-2 gap-2 text-xs"><div><dt className="text-[#77716e]">Party</dt><dd>{row.supplier_name ?? row.customer_name ?? "—"}</dd></div><div><dt className="text-[#77716e]">Taxable value</dt><dd>{money(row.taxable_value)}</dd></div><div><dt className="text-[#77716e]">Total tax</dt><dd>{money(row.total_tax)}</dd></div><div><dt className="text-[#77716e]">Source</dt><dd>Row {row.source_row ?? "—"}</dd></div></dl></div>)}</div>
            <div className="mt-5 flex flex-wrap gap-2">{editing ? <><Button disabled={busy} onClick={() => void editAndApprove()}><CheckCircle2 size={16}/>Save & Approve</Button><Button variant="ghost" disabled={busy} onClick={() => setEditing(false)}>Cancel edit</Button></> : <><Button disabled={busy || !selected.extraction} onClick={() => void action(`/documents/${selected.id}/approve`, {notes: "Reviewed in OBLIQ"})}><CheckCircle2 size={16}/>Approve</Button><Button variant="secondary" disabled={busy || !selected.extraction || !editedRows.length} onClick={() => setEditing(true)}>Edit & Approve</Button><Button variant="ghost" disabled={busy || !selected.extraction} onClick={() => void action(`/documents/${selected.id}/reject`, {notes: "Needs clarification"})}>Reject / Clarify</Button></>}</div>
          </div>
        </div>
      </Card>
    </div>}
  </div>;
}

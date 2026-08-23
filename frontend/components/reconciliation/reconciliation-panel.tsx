"use client";

import {AlertTriangle, CheckCircle2, Download, FileUp, GitCompareArrows, Play} from "lucide-react";
import {useCallback, useEffect, useMemo, useRef, useState} from "react";
import {toast} from "sonner";
import {apiFetch, preferredExportUrls} from "../../lib/api";
import {formatStatus} from "../../lib/format";
import {explainReconciliationItem} from "../../lib/record-explanations";
import {selectAllVisible, selectionState} from "../../lib/review-selection";
import type {ReconciliationItem, ReconciliationResult} from "../../lib/types";
import {Badge} from "../ui/badge";
import {Button} from "../ui/button";
import {Card} from "../ui/card";

type GSTRStatus = {status: string; document: {id: string; original_name: string; processing_status: string} | null};
type EvidenceSide = Record<string, string | number | boolean | null> | null;
const labels: Record<string, string> = {exact_match: "Exact Matches", needs_review: "Needs Review", books_only: "Books Only", gstr2b_only: "GSTR-2B Only", value_mismatch: "Value Mismatches", invoice_number_mismatch: "Invoice Number Mismatches", itc_not_available: "ITC Not Available", rcm: "RCM"};
const filters = ["all", "exact_match", "value_mismatch", "invoice_number_mismatch", "books_only", "gstr2b_only", "itc_not_available", "rcm"];
const comparisonFields = ["supplier_gstin", "invoice_number", "invoice_date", "taxable_value", "igst", "cgst", "sgst", "cess", "total_tax", "total_document_value"];
const moneyFields = new Set(["taxable_value", "igst", "cgst", "sgst", "cess", "total_tax", "total_document_value"]);
const money = (value: unknown) => value == null ? "—" : new Intl.NumberFormat("en-IN", {style: "currency", currency: "INR", maximumFractionDigits: 2}).format(Number(value));
const side = (item: ReconciliationItem, key: "books" | "gstr2b"): EvidenceSide => item.evidence?.[key] ?? null;

export function ReconciliationPanel({applicationId, onChanged}: {applicationId: string; onChanged: () => void}) {
  const [result, setResult] = useState<ReconciliationResult>({summary: {}, items: []});
  const [gstr, setGstr] = useState<GSTRStatus>({status: "not_uploaded", document: null});
  const [busy, setBusy] = useState(false);
  const [filter, setFilter] = useState("all");
  const [selected, setSelected] = useState<ReconciliationItem | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const load = useCallback(async () => {
    const [next, status] = await Promise.all([
      apiFetch<ReconciliationResult>(`/applications/${applicationId}/reconciliation`),
      apiFetch<GSTRStatus>(`/applications/${applicationId}/reconciliation/gstr2b`),
    ]);
    setResult(next); setGstr(status);
  }, [applicationId]);
  useEffect(() => {
    const initial = window.setTimeout(() => void load().catch(() => undefined), 0);
    return () => window.clearTimeout(initial);
  }, [load]);

  async function upload(file: File) {
    setBusy(true);
    try {
      const body = new FormData(); body.append("file", file);
      await apiFetch(`/applications/${applicationId}/reconciliation/gstr2b`, {method: "POST", body});
      toast.success("GSTR-2B parsed and ready to reconcile"); await load();
    } catch (error) { toast.error(error instanceof Error ? error.message : "GSTR-2B upload failed"); }
    finally { setBusy(false); }
  }
  async function run() {
    setBusy(true);
    try {
      setResult(await apiFetch<ReconciliationResult>(`/applications/${applicationId}/reconcile`, {method: "POST"}));
      toast.success("Deterministic reconciliation completed"); onChanged();
    } catch (error) { toast.error(error instanceof Error ? error.message : "Reconciliation failed"); }
    finally { setBusy(false); }
  }
  async function itemAction(item: ReconciliationItem, kind: "review" | "raise-alert") {
    setBusy(true);
    try {
      await apiFetch(`/reconciliation/items/${item.id}/${kind}`, {method: "POST"});
      toast.success(kind === "review" ? "Finding marked reviewed" : "Alert raised for CA follow-up"); await load(); onChanged();
    } catch (error) { toast.error(error instanceof Error ? error.message : "Action failed"); }
    finally { setBusy(false); }
  }
  const visible = useMemo(() => result.items.filter(item => {
    if (filter === "all") return true;
    if (filter === "itc_not_available" || filter === "rcm") return item.special_flags?.includes(filter);
    return item.match_status === filter;
  }), [filter, result.items]);
  const eligibleIds = visible.filter(item => item.match_status !== "exact_match" && !["reviewed", "resolved"].includes(item.review_status ?? "pending")).map(item => item.id);
  const selectAll = selectionState(selectedIds, eligibleIds);
  const selectAllRef = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (selectAllRef.current) selectAllRef.current.indeterminate = selectAll.indeterminate;
  }, [selectAll.indeterminate]);

  async function bulkReview() {
    const itemIds = [...selectedIds];
    if (!itemIds.length) return;
    if (!window.confirm(`Mark ${itemIds.length} selected reconciliation findings reviewed?`)) return;
    setBusy(true);
    try {
      await apiFetch(`/applications/${applicationId}/reconciliation/items/bulk-review`, {method: "POST", body: JSON.stringify({item_ids: itemIds, action: "mark_reviewed"})});
      setSelectedIds(new Set()); await load(); onChanged();
      toast.success(`${itemIds.length} reconciliation findings reviewed`);
    } catch (error) { toast.error(error instanceof Error ? error.message : "Bulk reconciliation review failed"); }
    finally { setBusy(false); }
  }

  async function exportReconciliation() {
    setBusy(true);
    try {
      const files = await apiFetch<Record<string, string>>(`/applications/${applicationId}/reconciliation/export`, {method: "POST"});
      preferredExportUrls(files, "reconciliation_export_zip").forEach(url =>
        window.open(url, "_blank", "noopener,noreferrer"),
      );
      toast.success("Reconciliation working generated");
    } catch (error) { toast.error(error instanceof Error ? error.message : "Unable to export reconciliation"); }
    finally { setBusy(false); }
  }

  return <div className="grid gap-5">
    <Card className="p-5"><div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center"><div><div className="flex items-center gap-2"><GitCompareArrows size={20}/><h3 className="font-bold">Purchase-side Books ↔ GSTR-2B</h3></div><p className="mt-2 text-sm text-[#6b6562]">Exact normalized field comparison with no monetary tolerance. The CA remains responsible for GST and ITC decisions.</p><div className="mt-3 flex gap-2"><Badge value={gstr.status}/>{gstr.document && <span className="text-xs text-[#77716e]">{gstr.document.original_name}</span>}</div></div><div className="flex flex-wrap gap-2"><label className="inline-flex cursor-pointer items-center gap-2 rounded-full border border-[#dcd7d2] bg-white px-5 py-3 text-sm font-semibold"><FileUp size={16}/>Upload GSTR-2B<input type="file" className="hidden" accept=".csv,.xlsx,.json,.pdf" disabled={busy} onChange={event => {const file = event.target.files?.[0]; if (file) void upload(file); event.target.value = "";}}/></label><Button onClick={run} disabled={busy || gstr.status !== "ready_to_reconcile"}><Play size={16}/>{busy ? "Working…" : "Start Reconciliation"}</Button><Button variant="secondary" onClick={() => void exportReconciliation()} disabled={busy || !result.review_progress?.export_enabled} title={result.review_progress?.export_enabled ? "Download the reconciliation working" : "Complete Reconciliation Review before exporting"}><Download size={16}/>Export Reconciliation</Button></div></div><div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">{Object.entries(labels).map(([key, label]) => <div key={key} className="rounded-2xl bg-[#f8f7f5] p-4"><p className="text-2xl font-bold">{result.summary[key] ?? 0}</p><p className="mt-1 text-[11px] text-[#77716e]">{label}</p></div>)}</div></Card>
    <Card className="overflow-hidden"><div className="border-b border-[var(--obliq-border)] p-5"><div className="flex flex-wrap items-start justify-between gap-3"><div><h3 className="font-bold">Reconciliation findings</h3><p className="mt-1 text-xs text-[var(--obliq-muted)]">Select any finding to compare evidence and understand the outcome.</p></div><label className="flex items-center gap-2 rounded-full border border-[var(--obliq-border)] px-3 py-2 text-xs font-semibold"><input ref={selectAllRef} aria-label="Select all visible reconciliation findings" type="checkbox" checked={selectAll.checked} disabled={!eligibleIds.length} onChange={event => setSelectedIds(current => selectAllVisible(current, eligibleIds, event.target.checked))}/>Select All</label></div><div className="mt-3 flex flex-wrap gap-2">{filters.map(value => <button key={value} onClick={() => {setFilter(value); setSelectedIds(new Set());}} className={`obliq-focus rounded-full px-3 py-1.5 text-xs font-semibold ${filter === value ? "obliq-selected" : "obliq-interactive bg-[var(--obliq-surface-raised)]"}`}>{value === "all" ? "All" : labels[value] ?? formatStatus(value)}</button>)}</div></div>{selectedIds.size > 0 && <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--obliq-info-border)] bg-[var(--obliq-info-soft)] px-5 py-3"><strong className="text-sm text-[var(--obliq-info-ink)]">{selectedIds.size} selected</strong><Button variant="secondary" disabled={busy} onClick={() => void bulkReview()}>Mark Selected Reviewed</Button></div>}<div className="overflow-x-auto"><table className="w-full min-w-[1100px] text-left text-sm"><thead className="bg-[var(--obliq-surface-raised)] text-xs text-[var(--obliq-muted)]"><tr>{["Select", "Status", "Supplier GSTIN", "Books Invoice", "GSTR-2B Invoice", "Date", "Books Taxable", "2B Taxable", "Review"].map(label => <th key={label} className="px-4 py-3">{label}</th>)}</tr></thead><tbody className="divide-y divide-[var(--obliq-border)]">{visible.map(item => {const books = side(item, "books"); const twoB = side(item, "gstr2b"); const eligible = eligibleIds.includes(item.id); return <tr key={item.id} role="button" tabIndex={0} aria-label={`Inspect reconciliation finding ${String(books?.invoice_number ?? twoB?.invoice_number ?? item.id)}`} className="obliq-focus cursor-pointer hover:bg-[var(--obliq-interactive-hover)]" onClick={() => setSelected(item)} onKeyDown={event => {if (event.key === "Enter" || event.key === " ") setSelected(item);}}><td className="px-4 py-4" onClick={event => event.stopPropagation()}><input aria-label={`Select reconciliation ${String(books?.invoice_number ?? twoB?.invoice_number ?? item.id)}`} type="checkbox" disabled={!eligible} checked={selectedIds.has(item.id)} onChange={() => setSelectedIds(current => {const next = new Set(current); if (next.has(item.id)) next.delete(item.id); else next.add(item.id); return next;})}/></td><td className="px-4 py-4"><Badge value={item.match_status}/></td><td className="px-4 py-4 font-mono text-xs">{String(books?.supplier_gstin ?? twoB?.supplier_gstin ?? "—")}</td><td className="px-4 py-4 font-semibold">{String(books?.invoice_number ?? "—")}</td><td className="px-4 py-4 font-semibold">{String(twoB?.invoice_number ?? "—")}</td><td className="px-4 py-4">{String(books?.invoice_date ?? twoB?.invoice_date ?? "—")}</td><td className="px-4 py-4">{money(books?.taxable_value)}</td><td className="px-4 py-4">{money(twoB?.taxable_value)}</td><td className="px-4 py-4"><Badge value={item.review_status ?? "pending"}/></td></tr>;})}</tbody></table></div>{!visible.length && <div className="p-10 text-center text-sm text-[var(--obliq-muted)]">No reconciliation findings for this filter.</div>}</Card>
    <div className="sr-only">Raise Alert</div>
    {selected && <div className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-4" onClick={() => setSelected(null)}><Card role="dialog" aria-modal="true" className="max-h-[90vh] w-full max-w-4xl overflow-auto p-6" onClick={event => event.stopPropagation()}><div className="flex justify-between gap-3"><div><Badge value={selected.match_status}/><h3 className="mt-3 text-2xl font-bold">{String(side(selected, "books")?.invoice_number ?? side(selected, "gstr2b")?.invoice_number ?? "Reconciliation finding")}</h3></div><button onClick={() => setSelected(null)}>Close</button></div><div className="mt-4 rounded-2xl bg-blue-50 p-4 text-sm leading-6 text-blue-950"><strong>{explainReconciliationItem(selected).title}</strong><p className="mt-1">{explainReconciliationItem(selected).summary}</p><p className="mt-2 border-t border-blue-100 pt-2 text-xs"><strong>What the CA should review:</strong> {explainReconciliationItem(selected).review}</p></div><div className="mt-5 overflow-x-auto rounded-2xl border border-[#e5e2de]"><table className="w-full text-left text-sm"><thead className="bg-[#f8f7f5]"><tr><th className="p-3">Field</th><th className="p-3">Books</th><th className="p-3">GSTR-2B</th></tr></thead><tbody>{comparisonFields.map(field => {const different = selected.evidence?.difference_fields?.includes(field); return <tr key={field} className={different ? "bg-amber-50" : "border-t border-[#eeeae6]"}><td className="p-3 font-semibold">{formatStatus(field)}</td><td className="p-3">{moneyFields.has(field) ? money(side(selected, "books")?.[field]) : String(side(selected, "books")?.[field] ?? "—")}</td><td className="p-3">{moneyFields.has(field) ? money(side(selected, "gstr2b")?.[field]) : String(side(selected, "gstr2b")?.[field] ?? "—")}</td></tr>;})}</tbody></table></div>{selected.evidence?.difference_fields?.length ? <div className="mt-4 rounded-2xl bg-amber-50 p-4 text-sm"><AlertTriangle className="inline" size={16}/> Exact differences: {selected.evidence.difference_fields.map(formatStatus).join(", ")}. This item requires CA review.</div> : <div className="mt-4 rounded-2xl bg-emerald-50 p-4 text-sm"><CheckCircle2 className="inline" size={16}/> All compared fields match exactly.</div>}<div className="mt-5 flex justify-end gap-2"><Button variant="secondary" disabled={busy} onClick={() => void itemAction(selected, "review")}>Mark Reviewed</Button><Button disabled={busy || selected.match_status === "exact_match"} onClick={() => void itemAction(selected, "raise-alert")}>Raise Alert</Button></div></Card></div>}
  </div>;
}

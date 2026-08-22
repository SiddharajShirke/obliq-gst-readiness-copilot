"use client";

import {CheckCircle2, Edit3, Grid2X2, Search, Table2, X, XCircle} from "lucide-react";
import type {
  ExtractionPortfolioResult,
  ExtractionPortfolioScope,
  GSTRecord,
} from "../../lib/types";
import {formatDate, formatStatus} from "../../lib/format";
import {Badge} from "../ui/badge";
import {Button} from "../ui/button";
import {Card} from "../ui/card";

const SCOPES: {value: ExtractionPortfolioScope; label: string}[] = [
  {value: "sales_register", label: "Sales Register"},
  {value: "purchase_register", label: "Purchase Register"},
  {value: "sales_invoices", label: "Sales Invoices"},
  {value: "purchase_expense_invoices", label: "Purchase & Expense Invoices"},
  {value: "credit_debit_notes", label: "Credit & Debit Notes"},
  {value: "gst_special_transactions", label: "GST Special Transactions"},
  {value: "combined", label: "Combined GST Portfolio"},
];

const money = (value?: string | number | null) => value == null
  ? "—"
  : new Intl.NumberFormat("en-IN", {
      style: "currency", currency: "INR", maximumFractionDigits: 2,
    }).format(Number(value));

const party = (row: GSTRecord) => row.supplier_name ?? row.customer_name ?? "Party unavailable";

type PortfolioProps = {
  result: ExtractionPortfolioResult;
  mode: "portfolio" | "table";
  search: string;
  selectedIds: Set<string>;
  onScopeChange: (scope: ExtractionPortfolioScope) => void;
  onModeChange: (mode: "portfolio" | "table") => void;
  onSearchChange: (value: string) => void;
  onToggleSelection: (id: string) => void;
  onInspect: (record: GSTRecord) => void;
  onBulkReview: (action: "approve" | "reject") => void;
};

export function ExtractionPortfolio(props: PortfolioProps) {
  const {result, mode, search, selectedIds} = props;
  const records = result.records.filter(row =>
    `${row.invoice_number ?? ""} ${party(row)} ${row.supplier_gstin ?? row.customer_gstin ?? ""}`
      .toLowerCase().includes(search.toLowerCase()),
  );
  const summaryCards = [
    ["Extracted records", result.summary.record_count],
    ["Taxable value", money(result.summary.taxable_value)],
    ["GST total", money(result.summary.total_tax)],
    ["Document value", money(result.summary.document_value)],
    ["Needs review", result.summary.needs_review_count],
  ];
  return <div className="grid gap-5">
    <nav aria-label="Extraction portfolio scopes" className="flex gap-2 overflow-x-auto pb-1">
      {SCOPES.map(scope => <button
        key={scope.value}
        type="button"
        onClick={() => props.onScopeChange(scope.value)}
        className={`obliq-focus whitespace-nowrap rounded-full border px-4 py-2 text-xs font-semibold transition ${result.scope === scope.value ? "obliq-selected border-[#191515] dark:border-[var(--obliq-focus)]" : "border-[#ddd8d3] bg-white text-[#625d5a] hover:border-[#8d8782] dark:border-[var(--obliq-border)] dark:bg-[var(--obliq-surface)] dark:text-[var(--obliq-muted)]"}`}
      >{scope.label}</button>)}
    </nav>
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
      {summaryCards.map(([label, value]) => <Card key={label} className="p-4">
        <p className="text-2xl font-bold tracking-tight">{value}</p>
        <p className="mt-1 text-xs text-[#77716e]">{label}</p>
      </Card>)}
    </div>
    <Card className="overflow-hidden">
      <div className="flex flex-col gap-3 border-b border-[#eeeae6] p-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h3 className="font-bold">{SCOPES.find(scope => scope.value === result.scope)?.label}</h3>
          <p className="mt-1 text-xs text-[#77716e]">{records.length} visible · {selectedIds.size} selected</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <label className="flex items-center gap-2 rounded-full border border-[#ddd8d3] px-3 py-2">
            <Search size={15}/><input aria-label="Search portfolio" className="w-44 bg-transparent text-sm outline-none" value={search} onChange={event => props.onSearchChange(event.target.value)} placeholder="Invoice, party, GSTIN"/>
          </label>
          <div className="flex rounded-full border border-[#ddd8d3] bg-[#f8f7f5] p-1">
            <button type="button" onClick={() => props.onModeChange("portfolio")} className={`obliq-focus flex items-center gap-1 rounded-full px-3 py-1.5 text-xs font-semibold ${mode === "portfolio" ? "obliq-segment-selected shadow-sm" : "text-[#77716e]"}`}><Grid2X2 size={14}/>Portfolio</button>
            <button type="button" onClick={() => props.onModeChange("table")} className={`obliq-focus flex items-center gap-1 rounded-full px-3 py-1.5 text-xs font-semibold ${mode === "table" ? "obliq-segment-selected shadow-sm" : "text-[#77716e]"}`}><Table2 size={14}/>Table</button>
          </div>
        </div>
      </div>
      {selectedIds.size > 0 && <div className="flex flex-col justify-between gap-3 border-b border-[#c8dff2] bg-[#edf6ff] px-4 py-3 sm:flex-row sm:items-center">
        <div><p className="text-sm font-bold text-[#153a59]">{selectedIds.size} selected for review</p><p className="mt-1 text-xs text-[#47708f]">A confirmation preview appears before changes are saved.</p></div>
        <div className="flex flex-wrap gap-2"><Button onClick={() => props.onBulkReview("approve")}><CheckCircle2 size={15}/>Approve selected</Button><Button variant="secondary" onClick={() => props.onBulkReview("reject")}><XCircle size={15}/>Reject selected</Button></div>
      </div>}
      {mode === "portfolio" ? <div className="grid gap-4 p-4 md:grid-cols-2 xl:grid-cols-3">
        {records.map(row => <article key={row.id} className="rounded-2xl border border-[var(--obliq-border)] bg-[var(--obliq-surface)] p-4 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md dark:hover:bg-[var(--obliq-interactive-hover)]">
          <div className="flex items-start justify-between gap-3"><label className="flex items-center gap-2"><input type="checkbox" checked={selectedIds.has(row.id)} onChange={() => props.onToggleSelection(row.id)}/><Badge value={row.document_type ?? row.invoice_category}/></label><Badge value={row.review_status}/></div>
          <button type="button" onClick={() => props.onInspect(row)} className="mt-4 w-full text-left">
            <h4 className="text-lg font-bold">{row.invoice_number ?? "Unnumbered record"}</h4>
            <p className="mt-1 text-sm text-[#625d5a]">{party(row)}</p>
            <dl className="mt-4 grid grid-cols-2 gap-3 text-xs"><div><dt className="text-[#8a837e]">Taxable</dt><dd className="mt-1 font-semibold">{money(row.taxable_value)}</dd></div><div><dt className="text-[#8a837e]">Total GST</dt><dd className="mt-1 font-semibold">{money(row.total_tax)}</dd></div><div><dt className="text-[#8a837e]">Date</dt><dd className="mt-1">{formatDate(row.invoice_date)}</dd></div><div><dt className="text-[#8a837e]">Source row</dt><dd className="mt-1">{row.source_row ?? "—"}</dd></div></dl>
          </button>
        </article>)}
      </div> : <div className="overflow-x-auto"><table className="w-full min-w-[960px] text-left text-sm"><thead className="bg-[#f8f7f5] text-xs text-[#77716e]"><tr>{["Select", "Type", "Invoice", "Party", "GSTIN", "Date", "Taxable", "GST", "Total", "Review"].map(label => <th key={label} className="px-4 py-3">{label}</th>)}</tr></thead><tbody className="divide-y divide-[#eeeae6]">{records.map(row => <tr key={row.id} className="cursor-pointer hover:bg-[#faf9f7]" onClick={() => props.onInspect(row)}><td className="px-4 py-3" onClick={event => event.stopPropagation()}><input aria-label={`Select ${row.invoice_number ?? row.id}`} type="checkbox" checked={selectedIds.has(row.id)} onChange={() => props.onToggleSelection(row.id)}/></td><td className="px-4 py-3"><Badge value={row.document_type ?? row.invoice_category}/></td><td className="px-4 py-3 font-semibold">{row.invoice_number ?? "—"}</td><td className="px-4 py-3">{party(row)}</td><td className="px-4 py-3 font-mono text-xs">{row.supplier_gstin ?? row.customer_gstin ?? "—"}</td><td className="px-4 py-3">{formatDate(row.invoice_date)}</td><td className="px-4 py-3">{money(row.taxable_value)}</td><td className="px-4 py-3">{money(row.total_tax)}</td><td className="px-4 py-3">{money(row.invoice_total)}</td><td className="px-4 py-3"><Badge value={row.review_status}/></td></tr>)}</tbody></table></div>}
      {!records.length && <div className="p-10 text-center text-sm text-[#77716e]">No normalized records match this portfolio.</div>}
    </Card>
  </div>;
}

type WorkspaceProps = {
  record: GSTRecord;
  onClose: () => void;
  onApprove: () => void;
  onEdit: () => void;
  onReject: () => void;
};

export function ExtractionReviewWorkspace({record, onClose, onApprove, onEdit, onReject}: WorkspaceProps) {
  const fields = [
    ["Invoice / document", record.invoice_number ?? "—"], ["Date", formatDate(record.invoice_date)],
    ["Party", party(record)], ["GSTIN", record.supplier_gstin ?? record.customer_gstin ?? "—"],
    ["Taxable value", money(record.taxable_value)], ["IGST", money(record.igst)],
    ["CGST", money(record.cgst)], ["SGST / UTGST", money(record.sgst)],
    ["Cess", money(record.cess)], ["Total tax", money(record.total_tax)],
    ["Document total", money(record.invoice_total)], ["ITC status", record.itc_status ? formatStatus(record.itc_status) : "—"],
  ];
  return <div className="fixed inset-0 z-50 grid place-items-center bg-black/60 p-3" onClick={onClose}>
    <section aria-modal="true" role="dialog" className="max-h-[95vh] w-full max-w-[95vw] overflow-auto rounded-3xl bg-[var(--obliq-surface)] text-[var(--obliq-ink)] shadow-2xl" onClick={event => event.stopPropagation()}>
      <header className="sticky top-0 z-10 flex items-start justify-between border-b border-[var(--obliq-border)] bg-white/95 p-5 backdrop-blur dark:bg-[var(--obliq-surface)]">
        <div><p className="text-xs font-bold tracking-[.14em] text-[#477ca8]">GST EXTRACTION REVIEW WORKSPACE</p><h2 className="mt-2 text-2xl font-bold">{record.invoice_number ?? "Unnumbered record"}</h2><p className="mt-1 text-sm text-[#625d5a]">{party(record)}</p></div>
        <button type="button" aria-label="Close review workspace" onClick={onClose}><X size={22}/></button>
      </header>
      <div className="grid gap-6 p-5 lg:grid-cols-[minmax(0,.8fr)_minmax(0,1.2fr)]">
        <Card className="min-h-[420px] bg-[#f8f7f5] p-5"><h3 className="font-bold">Source provenance</h3><p className="mt-2 text-sm leading-6 text-[#625d5a]">Private source document <strong>{record.document_id}</strong>. Extracted from page {record.source_page ?? "—"}, row {record.source_row ?? "—"}. Opening this workspace never reruns extraction.</p><div className="mt-5 rounded-2xl border border-dashed border-[#bbb4ae] p-8 text-center text-sm text-[#77716e]">Use the parent document review to open the signed original file.</div></Card>
        <div><div className="flex items-center justify-between"><h3 className="font-bold">Normalized extracted information</h3><Badge value={record.review_status}/></div><dl className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">{fields.map(([label, value]) => <div key={label} className="rounded-2xl border border-[#e5e2de] p-4"><dt className="text-xs text-[#77716e]">{label}</dt><dd className="mt-2 font-semibold">{value}</dd></div>)}</dl><div className="mt-6 flex flex-wrap gap-2"><Button onClick={onApprove}><CheckCircle2 size={16}/>Approve Extraction</Button><Button variant="secondary" onClick={onEdit}><Edit3 size={16}/>Edit & Approve</Button><Button variant="ghost" onClick={onReject}><XCircle size={16}/>Reject / Clarify</Button></div></div>
      </div>
    </section>
  </div>;
}

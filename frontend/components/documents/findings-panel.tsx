"use client";
/* eslint-disable react-hooks/set-state-in-effect */

import {AlertTriangle, CheckCircle2, FileCheck2, Grid2X2, Play, Sparkles, Table2, X} from "lucide-react";
import {useCallback, useEffect, useMemo, useRef, useState} from "react";
import {toast} from "sonner";
import {apiFetch} from "../../lib/api";
import {formatStatus} from "../../lib/format";
import {displayDetailValue, explainFinding} from "../../lib/record-explanations";
import {selectAllVisible, selectionState} from "../../lib/review-selection";
import type {Finding, ValidationCorrectionProposal, ValidationPortfolio} from "../../lib/types";
import {Badge} from "../ui/badge";
import {Button} from "../ui/button";
import {Card} from "../ui/card";
import {CorrectionPreviewDialog} from "./correction-preview-dialog";

export function FindingsPanel({applicationId, onChanged}: {applicationId: string; onChanged: () => void}) {
  const [portfolio, setPortfolio] = useState<ValidationPortfolio | null>(null);
  const [category, setCategory] = useState("all");
  const [selected, setSelected] = useState<Finding | null>(null);
  const [proposal, setProposal] = useState<ValidationCorrectionProposal | null>(null);
  const [mode, setMode] = useState<"portfolio" | "table">("portfolio");
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setPortfolio(await apiFetch<ValidationPortfolio>(`/applications/${applicationId}/validation-portfolio`));
  }, [applicationId]);

  useEffect(() => {
    void load().catch(() => undefined);
    const timer = window.setInterval(() => void load().catch(() => undefined), 2500);
    return () => window.clearInterval(timer);
  }, [load]);

  const activeCategory = portfolio?.categories.find(item => item.type === category);
  const findings = useMemo(() => {
    if (!portfolio) return [];
    return activeCategory
      ? activeCategory.findings
      : portfolio.categories.flatMap(item => item.findings);
  }, [portfolio, activeCategory]);
  const eligibleIds = findings.filter(item => item.status === "open").map(item => item.id);
  const selectAll = selectionState(selectedIds, eligibleIds);
  const selectAllRef = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (selectAllRef.current) selectAllRef.current.indeterminate = selectAll.indeterminate;
  }, [selectAll.indeterminate]);

  async function run() {
    setBusy(true);
    try {
      const result = await apiFetch<{finding_count: number; eligible_record_count: number; pending_review_count: number}>(`/applications/${applicationId}/validate`, {method: "POST"});
      await load();
      toast.success(`${result.finding_count} findings generated from ${result.eligible_record_count} approved records`);
      if (result.pending_review_count) toast.info(`${result.pending_review_count} pending records were excluded`);
      onChanged();
    } catch (error) { toast.error(error instanceof Error ? error.message : "Validation failed"); }
    finally { setBusy(false); }
  }

  async function resolve(id: string, status: "resolved" | "accepted") {
    setBusy(true);
    try {
      await apiFetch(`/findings/${id}/resolve`, {method: "POST", body: JSON.stringify({status})});
      setSelected(null); await load(); onChanged();
      toast.success(status === "resolved" ? "Finding resolved" : "Finding accepted for review");
    } catch (error) { toast.error(error instanceof Error ? error.message : "Unable to update finding"); }
    finally { setBusy(false); }
  }

  async function bulkResolve(status: "resolved" | "accepted") {
    const findingIds = [...selectedIds];
    if (!findingIds.length) return;
    if (!window.confirm(`${status === "resolved" ? "Resolve" : "Accept"} ${findingIds.length} selected validation findings?`)) return;
    setBusy(true);
    try {
      await apiFetch(`/applications/${applicationId}/findings/bulk-review`, {
        method: "POST",
        body: JSON.stringify({finding_ids: findingIds, status}),
      });
      setSelectedIds(new Set());
      await load(); onChanged();
      toast.success(`${findingIds.length} validation findings updated`);
    } catch (error) { toast.error(error instanceof Error ? error.message : "Bulk validation review failed"); }
    finally { setBusy(false); }
  }

  async function raiseAlert(finding: Finding) {
    setBusy(true);
    try {
      await apiFetch(`/findings/${finding.id}/raise-alert`, {method: "POST"});
      await load(); onChanged();
      toast.success("Categorized validation alert raised");
    } catch (error) { toast.error(error instanceof Error ? error.message : "Unable to raise alert"); }
    finally { setBusy(false); }
  }

  async function propose(finding: Finding, proposalMode: "manual" | "ai") {
    if (!finding.invoice_record_id) return toast.error("This finding is not linked to an extracted record");
    let changes: Record<string, unknown> = {};
    if (proposalMode === "manual") {
      const field = window.prompt("Field to correct (for example: taxable_value)");
      if (!field) return;
      const nextValue = window.prompt(`New value for ${field}`);
      if (nextValue == null) return;
      changes = {[field]: nextValue};
    }
    setBusy(true);
    try {
      setProposal(await apiFetch<ValidationCorrectionProposal>(
        `/applications/${applicationId}/validation-corrections/proposals`,
        {method: "POST", body: JSON.stringify({
          mode: proposalMode,
          record_ids: [finding.invoice_record_id],
          finding_ids: [finding.id],
          changes,
          rationale: proposalMode === "manual" ? "Manual CA correction" : undefined,
        })},
      ));
    } catch (error) { toast.error(error instanceof Error ? error.message : "Unable to create correction proposal"); }
    finally { setBusy(false); }
  }

  async function decideProposal(action: "apply" | "reject") {
    if (!proposal) return;
    setBusy(true);
    try {
      await apiFetch(`/validation-corrections/${proposal.id}/${action}`, {method: "POST"});
      toast.success(action === "apply" ? "Correction applied and validation refreshed" : "Correction proposal rejected");
      setProposal(null); setSelected(null); await load(); onChanged();
    } catch (error) { toast.error(error instanceof Error ? error.message : "Unable to update proposal"); }
    finally { setBusy(false); }
  }

  const summary = portfolio?.summary;
  const detailEntries = selected ? Object.entries(selected.details || {}) : [];
  return <div className="grid gap-5">
    <Card className="p-5">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div><h3 className="font-bold">Validation Portfolio</h3><p className="mt-2 text-sm text-[var(--obliq-muted)]">Live category cards are generated from approved extraction records, deterministic findings, and explicitly raised alerts. Manual corrections and AI recommendations always require CA confirmation.</p></div>
        <Button onClick={run} disabled={busy}><Play size={16}/>{busy ? "Checking…" : "Run approved-data checks"}</Button>
      </div>
      <div className="mt-6 grid gap-3 sm:grid-cols-4">
        <Metric value={summary?.approved_record_count ?? 0} label="Approved records"/>
        <Metric value={summary?.finding_count ?? 0} label="Validation findings" tone="warning"/>
        <Metric value={summary?.open_finding_count ?? 0} label="Open review" tone="danger"/>
        <Metric value={summary?.alert_count ?? 0} label="Alerts raised by CA" tone="info"/>
      </div>
    </Card>

    <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
      {(portfolio?.categories ?? []).map(item => <button key={item.type} onClick={() => {setCategory(item.type); setSelectedIds(new Set());}} className={`obliq-focus rounded-[22px] border p-4 text-left transition ${category === item.type ? "border-[var(--obliq-focus)] bg-[var(--obliq-interactive-active)]" : "border-[var(--obliq-border)] bg-[var(--obliq-surface)] hover:bg-[var(--obliq-interactive-hover)]"}`}>
        <div className="flex items-start justify-between gap-3"><span className="grid h-10 w-10 place-items-center rounded-xl bg-[var(--obliq-success-soft)] text-[var(--obliq-success-ink)]"><FileCheck2 size={18}/></span><Badge value={item.requirement_status}/></div>
        <strong className="mt-4 block">{item.label}</strong>
        <p className="mt-1 text-xs text-[var(--obliq-muted)]">{item.approved_record_count}/{item.record_count} approved · {item.open_finding_count} open · {item.alert_count} alerts</p>
        <div className="mt-3 flex flex-wrap gap-1.5">{item.finding_groups.length ? item.finding_groups.map(group => <span key={group.type} className="rounded-full border border-[var(--obliq-warning-border)] bg-[var(--obliq-warning-soft)] px-2 py-1 text-[11px] font-semibold text-[var(--obliq-warning-ink)]">{group.label} · {group.count}</span>) : <span className="text-xs text-[var(--obliq-muted)]">No deterministic findings</span>}</div>
      </button>)}
    </div>

    <Card className="overflow-hidden">
      <div className="flex flex-col justify-between gap-3 border-b border-[var(--obliq-border)] p-5 sm:flex-row sm:items-center">
        <div><h3 className="font-bold">{activeCategory?.label ?? "All categories"} review queue</h3><p className="mt-1 text-xs text-[var(--obliq-muted)]">Every value below comes from the current application database state.</p></div>
        <div className="flex flex-wrap items-center gap-2"><label className="flex items-center gap-2 rounded-full border border-[var(--obliq-border)] px-3 py-2 text-xs font-semibold"><input ref={selectAllRef} aria-label="Select all visible validation findings" type="checkbox" checked={selectAll.checked} disabled={!eligibleIds.length} onChange={event => setSelectedIds(current => selectAllVisible(current, eligibleIds, event.target.checked))}/>Select All</label><Button variant="ghost" onClick={() => {setCategory("all"); setSelectedIds(new Set());}}>All categories</Button><div className="flex rounded-full border border-[var(--obliq-border)] bg-[var(--obliq-surface-raised)] p-1"><button onClick={() => setMode("portfolio")} className={`obliq-focus flex items-center gap-1 rounded-full px-3 py-1.5 text-xs font-semibold ${mode === "portfolio" ? "obliq-segment-selected" : "obliq-interactive"}`}><Grid2X2 size={14}/>Portfolio</button><button onClick={() => setMode("table")} className={`obliq-focus flex items-center gap-1 rounded-full px-3 py-1.5 text-xs font-semibold ${mode === "table" ? "obliq-segment-selected" : "obliq-interactive"}`}><Table2 size={14}/>Table</button></div></div>
      </div>
      {selectedIds.size > 0 && <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--obliq-info-border)] bg-[var(--obliq-info-soft)] px-5 py-3"><strong className="text-sm text-[var(--obliq-info-ink)]">{selectedIds.size} selected</strong><div className="flex gap-2"><Button variant="secondary" disabled={busy} onClick={() => void bulkResolve("resolved")}>Mark Selected Resolved</Button><Button variant="ghost" disabled={busy} onClick={() => void bulkResolve("accepted")}>Accept Selected for Review</Button></div></div>}
      {findings.length ? mode === "portfolio" ? <div className="grid gap-4 p-4 md:grid-cols-2 xl:grid-cols-3">{findings.map(item => <FindingCard key={item.id} finding={item} selected={selectedIds.has(item.id)} onToggle={() => setSelectedIds(current => {const next = new Set(current); if (next.has(item.id)) next.delete(item.id); else next.add(item.id); return next;})} onClick={() => setSelected(item)}/>)}</div> : <div className="overflow-x-auto"><table className="w-full min-w-[780px] text-left text-sm"><thead className="bg-[var(--obliq-surface-raised)] text-xs text-[var(--obliq-muted)]"><tr><th className="p-3">Select</th><th className="p-3">Finding</th><th className="p-3">Type</th><th className="p-3">Severity</th><th className="p-3">Record</th><th className="p-3">Status</th></tr></thead><tbody>{findings.map(item => <tr key={item.id} className="cursor-pointer border-t border-[var(--obliq-border)] hover:bg-[var(--obliq-interactive-hover)]" onClick={() => setSelected(item)}><td className="p-3" onClick={event => event.stopPropagation()}><input aria-label={`Select ${item.message}`} type="checkbox" disabled={item.status !== "open"} checked={selectedIds.has(item.id)} onChange={() => setSelectedIds(current => {const next = new Set(current); if (next.has(item.id)) next.delete(item.id); else next.add(item.id); return next;})}/></td><td className="p-3 font-semibold">{item.message}</td><td className="p-3">{formatStatus(item.finding_type)}</td><td className="p-3"><Badge value={item.severity}/></td><td className="p-3 font-mono text-xs">{item.invoice_record_id ?? "—"}</td><td className="p-3"><Badge value={item.status}/></td></tr>)}</tbody></table></div> : <div className="p-10 text-center text-sm text-[var(--obliq-muted)]">No validation findings for this category.</div>}
    </Card>

    {selected && <div className="fixed inset-0 z-50 grid place-items-center bg-black/60 p-4" onClick={() => setSelected(null)}><Card role="dialog" aria-modal="true" className="max-h-[94vh] w-full max-w-[92vw] overflow-auto p-6" onClick={event => event.stopPropagation()}><div className="flex items-start justify-between"><div><p className="text-xs font-bold tracking-[.14em] text-[var(--obliq-warning-ink)]">VALIDATION REVIEW WORKSPACE</p><h3 className="mt-2 text-2xl font-bold">{formatStatus(selected.finding_type)}</h3><p className="mt-2 text-sm text-[var(--obliq-muted)]">{explainFinding(selected).summary}</p></div><button onClick={() => setSelected(null)} aria-label="Close validation review"><X/></button></div><div className="mt-5 grid gap-4 lg:grid-cols-2"><section className="rounded-2xl border border-[var(--obliq-border)] p-5"><h4 className="font-bold">Deterministic evidence</h4><dl className="mt-4 grid gap-3 sm:grid-cols-2"><div><dt className="text-xs text-[var(--obliq-muted)]">Severity</dt><dd className="mt-1"><Badge value={selected.severity}/></dd></div><div><dt className="text-xs text-[var(--obliq-muted)]">Status</dt><dd className="mt-1"><Badge value={selected.status}/></dd></div><div><dt className="text-xs text-[var(--obliq-muted)]">Document</dt><dd className="mt-1 font-mono text-xs">{selected.document_id ?? "—"}</dd></div><div><dt className="text-xs text-[var(--obliq-muted)]">Extracted record</dt><dd className="mt-1 font-mono text-xs">{selected.invoice_record_id ?? "—"}</dd></div>{detailEntries.map(([key, value]) => <div key={key}><dt className="text-xs text-[var(--obliq-muted)]">{formatStatus(key)}</dt><dd className="mt-1 font-semibold text-[var(--obliq-warning-ink)]">{displayDetailValue(value)}</dd></div>)}</dl></section><section className="rounded-2xl border border-[var(--obliq-info-border)] bg-[var(--obliq-info-soft)] p-5"><div className="flex items-center gap-2 font-bold text-[var(--obliq-info-ink)]"><Sparkles size={17}/>Review and correction controls</div><p className="mt-3 text-sm leading-6 text-[var(--obliq-ink)]">Change a field manually or ask AI for a read-only recommendation. OBLIQ shows an exact before/after preview before any change can be saved.</p><div className="mt-5 flex flex-wrap gap-2"><Button variant="secondary" disabled={busy || !selected.invoice_record_id} onClick={() => void propose(selected, "manual")}>Manual correction</Button><Button variant="secondary" disabled={busy || !selected.invoice_record_id} onClick={() => void propose(selected, "ai")}><Sparkles size={15}/>AI recommendation</Button><Button disabled={busy} onClick={() => void raiseAlert(selected)}>Raise categorized alert</Button></div></section></div>{selected.status === "open" && <div className="mt-5 flex justify-end gap-2"><Button variant="secondary" disabled={busy} onClick={() => void resolve(selected.id, "resolved")}>Mark resolved</Button><Button variant="ghost" disabled={busy} onClick={() => void resolve(selected.id, "accepted")}>Accept for review</Button></div>}</Card></div>}
    {proposal && <CorrectionPreviewDialog proposal={proposal} busy={busy} onApply={() => void decideProposal("apply")} onReject={() => void decideProposal("reject")} onClose={() => setProposal(null)}/>}
  </div>;
}

function Metric({value, label, tone = "neutral"}: {value: number; label: string; tone?: "neutral" | "warning" | "danger" | "info"}) {
  const classes = {neutral: "bg-[var(--obliq-neutral-soft)] text-[var(--obliq-neutral-ink)]", warning: "bg-[var(--obliq-warning-soft)] text-[var(--obliq-warning-ink)]", danger: "bg-[var(--obliq-danger-soft)] text-[var(--obliq-danger-ink)]", info: "bg-[var(--obliq-info-soft)] text-[var(--obliq-info-ink)]"};
  return <div className={`rounded-2xl p-4 ${classes[tone]}`}><p className="text-2xl font-bold">{value}</p><p className="text-xs">{label}</p></div>;
}

function FindingCard({finding, selected, onToggle, onClick}: {finding: Finding; selected: boolean; onToggle: () => void; onClick: () => void}) {
  return <article className="rounded-2xl border border-[var(--obliq-border)] bg-[var(--obliq-surface)] p-4 text-left shadow-sm transition hover:-translate-y-0.5 hover:bg-[var(--obliq-interactive-hover)] hover:shadow-md"><div className="flex items-start justify-between gap-3"><label className="flex items-center gap-2"><input aria-label={`Select ${finding.message}`} type="checkbox" disabled={finding.status !== "open"} checked={selected} onChange={onToggle}/><span className={`grid h-9 w-9 place-items-center rounded-xl ${finding.status === "open" ? "bg-[var(--obliq-warning-soft)] text-[var(--obliq-warning-ink)]" : "bg-[var(--obliq-success-soft)] text-[var(--obliq-success-ink)]"}`}>{finding.status === "open" ? <AlertTriangle size={17}/> : <CheckCircle2 size={17}/>}</span></label><div className="flex gap-2"><Badge value={finding.severity}/><Badge value={finding.status}/></div></div><button type="button" className="mt-4 w-full text-left" onClick={onClick}><strong className="block text-sm">{finding.message}</strong><span className="mt-2 block text-xs text-[var(--obliq-muted)]">{formatStatus(finding.finding_type)}</span></button></article>;
}

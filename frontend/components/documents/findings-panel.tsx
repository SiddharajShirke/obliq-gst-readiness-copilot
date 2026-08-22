"use client";
/* eslint-disable react-hooks/set-state-in-effect, react-hooks/exhaustive-deps */

import {AlertTriangle, CheckCircle2, Grid2X2, Play, Sparkles, Table2, X} from "lucide-react";
import {useEffect, useState} from "react";
import {toast} from "sonner";
import {apiFetch} from "../../lib/api";
import {formatStatus} from "../../lib/format";
import {displayDetailValue, explainFinding} from "../../lib/record-explanations";
import type {Finding, ValidationCorrectionProposal} from "../../lib/types";
import {Badge} from "../ui/badge";
import {Button} from "../ui/button";
import {Card} from "../ui/card";
import {CorrectionPreviewDialog} from "./correction-preview-dialog";

export function FindingsPanel({applicationId, onChanged}: {applicationId: string; onChanged: () => void}) {
  const [findings, setFindings] = useState<Finding[]>([]);
  const [selected, setSelected] = useState<Finding | null>(null);
  const [proposal, setProposal] = useState<ValidationCorrectionProposal | null>(null);
  const [mode, setMode] = useState<"portfolio" | "table">("portfolio");
  const [busy, setBusy] = useState(false);

  async function load() {
    setFindings(await apiFetch<Finding[]>(`/applications/${applicationId}/findings`));
  }
  useEffect(() => { load().catch(() => undefined); }, [applicationId]);

  async function run() {
    setBusy(true);
    try {
      const result = await apiFetch<{finding_count: number; findings: Finding[]; eligible_record_count: number; pending_review_count: number}>(`/applications/${applicationId}/validate`, {method: "POST"});
      setFindings(result.findings);
      toast.success(`${result.finding_count} findings generated from ${result.eligible_record_count} approved records`);
      if (result.pending_review_count) toast.info(`${result.pending_review_count} unapproved records were excluded`);
      onChanged();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Validation failed");
    } finally { setBusy(false); }
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

  async function raiseAlert(finding: Finding) {
    setBusy(true);
    try {
      await apiFetch(`/findings/${finding.id}/raise-alert`, {method: "POST"});
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
      const created = await apiFetch<ValidationCorrectionProposal>(
        `/applications/${applicationId}/validation-corrections/proposals`,
        {method: "POST", body: JSON.stringify({
          mode: proposalMode, record_ids: [finding.invoice_record_id],
          finding_ids: [finding.id], changes,
          rationale: proposalMode === "manual" ? "Manual CA correction" : undefined,
        })},
      );
      setProposal(created);
    } catch (error) { toast.error(error instanceof Error ? error.message : "Unable to create correction proposal"); }
    finally { setBusy(false); }
  }

  async function decideProposal(action: "apply" | "reject") {
    if (!proposal) return;
    setBusy(true);
    try {
      await apiFetch(`/validation-corrections/${proposal.id}/${action}`, {method: "POST"});
      toast.success(action === "apply" ? "Correction applied; rerun validation to refresh findings" : "Correction proposal rejected");
      setProposal(null); setSelected(null); await load(); onChanged();
    } catch (error) { toast.error(error instanceof Error ? error.message : "Unable to update proposal"); }
    finally { setBusy(false); }
  }

  const open = findings.filter(item => item.status === "open");
  const detailEntries = selected ? Object.entries(selected.details || {}) : [];
  return <div className="grid gap-5">
    <Card className="p-5">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center"><div><h3 className="font-bold">Validation Portfolio</h3><p className="mt-2 text-sm text-[#6b6562]">Deterministic checks run only on CA-approved extraction records. Manual corrections and AI recommendations always require CA confirmation.</p></div><Button onClick={run} disabled={busy}><Play size={16}/>{busy ? "Checking…" : "Run approved-data checks"}</Button></div>
      <div className="mt-6 grid gap-3 sm:grid-cols-3"><div className="rounded-2xl bg-[#f8f7f5] p-4"><p className="text-2xl font-bold">{findings.length}</p><p className="text-xs text-[#77716e]">Total findings</p></div><div className="rounded-2xl bg-red-50 p-4"><p className="text-2xl font-bold text-red-700">{open.length}</p><p className="text-xs text-red-700">Open findings</p></div><div className="rounded-2xl bg-emerald-50 p-4"><p className="text-2xl font-bold text-emerald-700">{findings.length - open.length}</p><p className="text-xs text-emerald-700">Reviewed</p></div></div>
    </Card>
    <Card className="overflow-hidden">
      <div className="flex flex-col justify-between gap-3 border-b border-[var(--obliq-border)] p-5 sm:flex-row sm:items-center"><div><h3 className="font-bold">Validation review queue</h3><p className="mt-1 text-xs text-[var(--obliq-muted)]">Choose a card or table row to inspect deterministic evidence.</p></div><div className="flex rounded-full border border-[var(--obliq-border)] bg-[var(--obliq-surface-raised)] p-1"><button onClick={() => setMode("portfolio")} className={`obliq-focus flex items-center gap-1 rounded-full px-3 py-1.5 text-xs font-semibold ${mode === "portfolio" ? "obliq-segment-selected shadow-sm" : "text-[#77716e]"}`}><Grid2X2 size={14}/>Portfolio</button><button onClick={() => setMode("table")} className={`obliq-focus flex items-center gap-1 rounded-full px-3 py-1.5 text-xs font-semibold ${mode === "table" ? "obliq-segment-selected shadow-sm" : "text-[#77716e]"}`}><Table2 size={14}/>Table</button></div></div>
      {findings.length ? mode === "portfolio" ? <div className="grid gap-4 p-4 md:grid-cols-2 xl:grid-cols-3">{findings.map(item => <button key={item.id} className="rounded-2xl border border-[#e5e2de] p-4 text-left shadow-sm transition hover:-translate-y-0.5 hover:shadow-md" onClick={() => setSelected(item)}><div className="flex items-start justify-between gap-3"><span className={`grid h-9 w-9 place-items-center rounded-xl ${item.status === "open" ? "bg-amber-50 text-amber-700" : "bg-emerald-50 text-emerald-700"}`}>{item.status === "open" ? <AlertTriangle size={17}/> : <CheckCircle2 size={17}/>}</span><div className="flex gap-2"><Badge value={item.severity}/><Badge value={item.status}/></div></div><strong className="mt-4 block text-sm">{item.message}</strong><span className="mt-2 block text-xs text-[#77716e]">{formatStatus(item.finding_type)}</span></button>)}</div> : <div className="overflow-x-auto"><table className="w-full min-w-[780px] text-left text-sm"><thead className="bg-[#f8f7f5] text-xs text-[#77716e]"><tr><th className="p-3">Finding</th><th className="p-3">Type</th><th className="p-3">Severity</th><th className="p-3">Record</th><th className="p-3">Status</th></tr></thead><tbody>{findings.map(item => <tr key={item.id} className="cursor-pointer border-t border-[#eeeae6] hover:bg-[#faf9f7]" onClick={() => setSelected(item)}><td className="p-3 font-semibold">{item.message}</td><td className="p-3">{formatStatus(item.finding_type)}</td><td className="p-3"><Badge value={item.severity}/></td><td className="p-3 font-mono text-xs">{item.invoice_record_id ?? "—"}</td><td className="p-3"><Badge value={item.status}/></td></tr>)}</tbody></table></div> : <div className="p-10 text-center text-sm text-[#77716e]">No validation findings yet.</div>}
    </Card>
    {selected && <div className="fixed inset-0 z-50 grid place-items-center bg-black/60 p-4" onClick={() => setSelected(null)}><Card role="dialog" aria-modal="true" className="max-h-[94vh] w-full max-w-[92vw] overflow-auto p-6" onClick={event => event.stopPropagation()}><div className="flex items-start justify-between"><div><p className="text-xs font-bold tracking-[.14em] text-[#b66b16]">VALIDATION REVIEW WORKSPACE</p><h3 className="mt-2 text-2xl font-bold">{formatStatus(selected.finding_type)}</h3><p className="mt-2 text-sm text-[#625d5a]">{explainFinding(selected).summary}</p></div><button onClick={() => setSelected(null)} aria-label="Close validation review"><X/></button></div><div className="mt-5 grid gap-4 lg:grid-cols-2"><section className="rounded-2xl border border-[#e5e2de] p-5"><h4 className="font-bold">Deterministic evidence</h4><dl className="mt-4 grid gap-3 sm:grid-cols-2"><div><dt className="text-xs text-[#77716e]">Severity</dt><dd className="mt-1"><Badge value={selected.severity}/></dd></div><div><dt className="text-xs text-[#77716e]">Status</dt><dd className="mt-1"><Badge value={selected.status}/></dd></div><div><dt className="text-xs text-[#77716e]">Document</dt><dd className="mt-1 font-mono text-xs">{selected.document_id ?? "—"}</dd></div><div><dt className="text-xs text-[#77716e]">Extracted record</dt><dd className="mt-1 font-mono text-xs">{selected.invoice_record_id ?? "—"}</dd></div>{detailEntries.map(([key, value]) => <div key={key}><dt className="text-xs text-[#77716e]">{formatStatus(key)}</dt><dd className="mt-1 font-semibold text-amber-800">{displayDetailValue(value)}</dd></div>)}</dl></section><section className="rounded-2xl border border-violet-200 bg-violet-50 p-5"><div className="flex items-center gap-2 font-bold text-violet-950"><Sparkles size={17}/>Review and correction controls</div><p className="mt-3 text-sm leading-6 text-violet-900">Change a field manually or ask AI for a read-only recommendation. OBLIQ shows an exact before/after preview before any change can be saved.</p><div className="mt-5 flex flex-wrap gap-2"><Button variant="secondary" disabled={busy || !selected.invoice_record_id} onClick={() => void propose(selected, "manual")}>Manual correction</Button><Button variant="secondary" disabled={busy || !selected.invoice_record_id} onClick={() => void propose(selected, "ai")}><Sparkles size={15}/>AI recommendation</Button><Button disabled={busy} onClick={() => void raiseAlert(selected)}>Raise categorized alert</Button></div></section></div>{selected.status === "open" && <div className="mt-5 flex justify-end gap-2"><Button variant="secondary" disabled={busy} onClick={() => void resolve(selected.id, "resolved")}>Mark resolved</Button><Button variant="ghost" disabled={busy} onClick={() => void resolve(selected.id, "accepted")}>Accept for review</Button></div>}</Card></div>}
    {proposal && <CorrectionPreviewDialog proposal={proposal} busy={busy} onApply={() => void decideProposal("apply")} onReject={() => void decideProposal("reject")} onClose={() => setProposal(null)}/>}
  </div>;
}

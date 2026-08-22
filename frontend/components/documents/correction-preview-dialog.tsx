"use client";

import {ArrowRight, Sparkles, X} from "lucide-react";
import type {ValidationCorrectionProposal} from "../../lib/types";
import {formatStatus} from "../../lib/format";
import {Badge} from "../ui/badge";
import {Button} from "../ui/button";
import {Card} from "../ui/card";

const value = (field: string, raw: unknown) => {
  if (raw == null || raw === "") return "—";
  if (["taxable_value", "igst", "cgst", "sgst", "cess", "total_tax", "invoice_total"].includes(field)) {
    return new Intl.NumberFormat("en-IN", {style: "currency", currency: "INR", maximumFractionDigits: 2}).format(Number(raw));
  }
  return String(raw);
};

export function CorrectionPreviewDialog({proposal, busy, onApply, onReject, onClose}: {
  proposal: ValidationCorrectionProposal;
  busy: boolean;
  onApply: () => void;
  onReject: () => void;
  onClose: () => void;
}) {
  return <div className="fixed inset-0 z-[60] grid place-items-center bg-black/60 p-4" onClick={onClose}>
    <Card role="dialog" aria-modal="true" className="max-h-[92vh] w-full max-w-5xl overflow-auto p-6" onClick={event => event.stopPropagation()}>
      <div className="flex items-start justify-between gap-4"><div><p className="text-xs font-bold tracking-[.14em] text-[#6d55a8]">CORRECTION CONFIRMATION</p><h3 className="mt-2 text-2xl font-bold">Review proposed changes</h3><div className="mt-3 flex gap-2"><Badge value={proposal.proposal_type}/>{proposal.provider && <Badge value={proposal.provider}/>}</div></div><button aria-label="Close correction preview" onClick={onClose}><X/></button></div>
      {proposal.proposal_type === "ai" && <div className="mt-5 rounded-2xl border border-violet-200 bg-violet-50 p-4 text-sm text-violet-950"><Sparkles className="mr-2 inline" size={17}/>AI suggested these changes for CA review. It cannot save any value without your approval. {proposal.provider && <span className="font-semibold">{formatStatus(proposal.provider)}</span>}{proposal.model ? ` · ${proposal.model}` : ""}</div>}
      <p className="mt-5 text-sm text-[#625d5a]">{proposal.rationale || "Compare every proposed value with the original evidence before applying."}</p>
      <div className="mt-4 grid gap-3">{proposal.changes.map((change, index) => <section key={`${change.record_id}-${change.field}-${index}`} className="rounded-2xl border border-[#e5e2de] p-4"><div className="flex flex-wrap items-center justify-between gap-2"><strong>{formatStatus(change.field)}</strong><span className="font-mono text-xs text-[#77716e]">{change.record_id}</span></div><div className="mt-4 grid items-center gap-3 sm:grid-cols-[1fr_auto_1fr]"><div className="rounded-xl bg-red-50 p-3"><p className="text-xs text-red-700">Before</p><p className="mt-1 font-semibold">{value(change.field, change.before)}</p></div><ArrowRight className="mx-auto text-[#77716e]"/><div className="rounded-xl bg-emerald-50 p-3"><p className="text-xs text-emerald-700">Proposed</p><p className="mt-1 font-semibold">{value(change.field, change.after)}</p></div></div><p className="mt-3 text-xs text-[#625d5a]">{change.rationale}</p></section>)}{!proposal.changes.length && <div className="rounded-2xl bg-[#f8f7f5] p-8 text-center text-sm text-[#625d5a]">No safe correction was proposed. The current value remains unchanged.</div>}</div>
      <div className="mt-6 flex flex-wrap justify-end gap-2"><Button variant="ghost" disabled={busy} onClick={onReject}>Reject proposal</Button><Button disabled={busy || !proposal.changes.length} onClick={onApply}>Apply confirmed correction</Button></div>
    </Card>
  </div>;
}

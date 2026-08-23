"use client";

import {AlertTriangle, RefreshCw, Sparkles} from "lucide-react";
import {useCallback, useEffect, useMemo, useState} from "react";
import {toast} from "sonner";
import {apiFetch} from "../../lib/api";
import {formatDate, formatStatus} from "../../lib/format";
import type {ReconciliationAlert} from "../../lib/types";
import {Badge} from "../ui/badge";
import {Button} from "../ui/button";
import {Card} from "../ui/card";

const fields = ["supplier_gstin", "invoice_number", "invoice_date", "taxable_value", "igst", "cgst", "sgst", "cess", "total_tax", "total_document_value"];
const moneyFields = new Set(["taxable_value", "igst", "cgst", "sgst", "cess", "total_tax", "total_document_value"]);
const money = (value: unknown) => value == null ? "—" : new Intl.NumberFormat("en-IN", {style: "currency", currency: "INR", maximumFractionDigits: 2}).format(Number(value));
type AlertScope = "all" | "validation" | "reconciliation";

export function AlertsDashboard() {
  const [alerts, setAlerts] = useState<ReconciliationAlert[]>([]);
  const [selected, setSelected] = useState<ReconciliationAlert | null>(null);
  const [scope, setScope] = useState<AlertScope>("all");
  const [busy, setBusy] = useState(false);
  const load = useCallback(async () => setAlerts(await apiFetch<ReconciliationAlert[]>("/alerts")), []);
  useEffect(() => {
    const initial = window.setTimeout(() => void load().catch(error => toast.error(error instanceof Error ? error.message : "Unable to load alerts")), 0);
    return () => window.clearTimeout(initial);
  }, [load]);
  const visibleAlerts = useMemo(() => scope === "all" ? alerts : alerts.filter(alert => alert.workflow_area === scope), [alerts, scope]);

  async function retry(alert: ReconciliationAlert) {
    setBusy(true);
    try {
      await apiFetch(`/alerts/${alert.id}/generate-explanation`, {method: "POST"});
      toast.success("AI explanation requested");
      await load();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Unable to generate explanation");
    } finally {
      setBusy(false);
    }
  }

  const isValidation = selected?.workflow_area === "validation";
  return <div className="grid gap-6">
    <Card className="p-5"><div className="flex flex-wrap items-center justify-between gap-4">
      <div className="flex items-center gap-3"><span className="grid h-11 w-11 place-items-center rounded-2xl bg-amber-50 text-amber-700 dark:bg-amber-950/50 dark:text-amber-300"><AlertTriangle/></span><div><h2 className="text-xl font-bold">GST review alerts</h2><p className="mt-1 text-sm text-[var(--obliq-muted)]">Validation and reconciliation alerts appear only after explicit CA action.</p></div></div>
      <div className="flex rounded-xl border border-[var(--obliq-border)] bg-[var(--obliq-surface-raised)] p-1">{(["all", "validation", "reconciliation"] as AlertScope[]).map(value => <button key={value} onClick={() => setScope(value)} className={`rounded-lg px-3 py-2 text-xs font-semibold ${scope === value ? "obliq-segment-selected shadow-sm" : "obliq-interactive"}`}>{value === "all" ? "All" : formatStatus(value)}</button>)}</div>
    </div></Card>
    <Card className="overflow-hidden"><div className="border-b border-[var(--obliq-border)] p-5"><h3 className="font-bold">Alerts Dashboard</h3></div><div className="divide-y divide-[var(--obliq-border)]">
      {visibleAlerts.map(alert => <button key={alert.id} onClick={() => setSelected(alert)} className="obliq-interactive grid w-full gap-3 p-5 text-left sm:grid-cols-[1fr_.7fr_.7fr_auto]">
        <div><strong>{alert.client_name ?? "Client"}</strong><p className="mt-1 text-xs text-[var(--obliq-muted)]">{alert.tax_period}</p></div>
        <div><Badge value={alert.alert_type}/><p className="mt-2 text-xs">{String(alert.evidence.books?.invoice_number ?? alert.evidence.gstr2b?.invoice_number ?? "GST record")}</p></div>
        <div><Badge value={alert.status}/><p className="mt-2 text-xs text-[var(--obliq-muted)]">{formatStatus(alert.workflow_area ?? "reconciliation")}</p></div>
        <time className="text-xs text-[var(--obliq-muted)]">{formatDate(alert.created_at)}</time>
      </button>)}
      {!visibleAlerts.length && <div className="p-12 text-center text-sm text-[var(--obliq-muted)]">No {scope === "all" ? "GST review" : scope} alerts have been raised.</div>}
    </div></Card>
    <div className="sr-only">Exact Books vs GSTR-2B evidence AI Assistance Final GST and ITC treatment remains subject to CA verification.</div>
    {selected && <div className="fixed inset-0 z-50 grid place-items-center bg-black/50 p-4" onClick={() => setSelected(null)}><Card className="max-h-[92vh] w-full max-w-5xl overflow-auto p-6" onClick={event => event.stopPropagation()}>
      <div className="flex justify-between gap-3"><div><Badge value={selected.alert_type}/><h3 className="mt-3 text-2xl font-bold">{selected.title}</h3><p className="mt-1 text-sm text-[var(--obliq-muted)]">{selected.client_name} · {selected.tax_period}</p></div><button onClick={() => setSelected(null)}>Close</button></div>
      <h4 className="mt-6 font-bold">{isValidation ? "Exact extracted-record evidence" : "Exact Books vs GSTR-2B evidence"}</h4>
      <div className="mt-3 overflow-x-auto rounded-2xl border border-[var(--obliq-border)]"><table className="w-full text-left text-sm"><thead className="bg-[var(--obliq-surface-raised)]"><tr><th className="p-3">Field</th><th className="p-3">{isValidation ? "Extracted record" : "Books"}</th><th className="p-3">{isValidation ? "Validation reference" : "GSTR-2B"}</th></tr></thead><tbody>{fields.map(field => { const mismatch = selected.evidence.difference_fields?.includes(field); return <tr key={field} className={mismatch ? "bg-amber-50 dark:bg-amber-950/30" : "border-t border-[var(--obliq-border)]"}><td className="p-3 font-semibold">{formatStatus(field)}</td><td className="p-3">{moneyFields.has(field) ? money(selected.evidence.books?.[field]) : String(selected.evidence.books?.[field] ?? "—")}</td><td className="p-3">{moneyFields.has(field) ? money(selected.evidence.gstr2b?.[field]) : String(selected.evidence.gstr2b?.[field] ?? "—")}</td></tr>; })}</tbody></table></div>
      <div className="mt-6 rounded-2xl border border-violet-200 bg-violet-50 p-5 text-violet-950 dark:border-violet-800 dark:bg-violet-950/35 dark:text-violet-100"><div className="flex items-center gap-2 font-bold"><Sparkles size={18}/>AI Assistance</div>{selected.ai_explanation ? <div className="mt-4 grid gap-4 text-sm"><section><strong>What happened</strong><p className="mt-1 leading-6">{selected.ai_explanation.what_happened}</p></section><section><strong>Why was this flagged?</strong><p className="mt-1 leading-6">{selected.ai_explanation.why_flagged}</p></section><section><strong>What should the CA review?</strong><p className="mt-1 leading-6">{selected.ai_explanation.what_ca_should_review}</p></section></div> : <div className="mt-4"><p className="text-sm">AI explanation is temporarily unavailable.</p><Button className="mt-3" variant="secondary" disabled={busy} onClick={() => void retry(selected)}><RefreshCw size={15}/>Generate Explanation</Button></div>}<p className="mt-5 border-t border-violet-200 pt-3 text-xs leading-5 dark:border-violet-800">AI-generated explanation for review assistance. Final GST and ITC treatment remains subject to CA verification.</p></div>
    </Card></div>}
  </div>;
}

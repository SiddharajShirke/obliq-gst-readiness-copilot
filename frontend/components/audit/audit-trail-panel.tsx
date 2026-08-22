"use client";

import {FileText} from "lucide-react";
import {useState} from "react";
import {formatDate, formatStatus} from "../../lib/format";
import {displayDetailValue, explainAuditEvent} from "../../lib/record-explanations";
import type {AuditEvent} from "../../lib/types";
import {Card} from "../ui/card";
import {RowInsightModal, type InsightField} from "../ui/row-insight-modal";

function auditFields(event: AuditEvent): InsightField[] {
  const fields: InsightField[] = [
    {label: "Action", value: formatStatus(event.action.replaceAll(".", "_"))},
    {label: "Entity type", value: formatStatus(event.entity_type)},
    {label: "Entity ID", value: event.entity_id || "—"},
    {label: "Recorded at", value: formatDate(event.created_at)},
  ];
  for (const [group, values] of [
    ["Metadata", event.metadata],
    ["Before", event.before_data],
    ["After", event.after_data],
  ] as const) {
    for (const [key, value] of Object.entries(values || {})) {
      fields.push({label: `${group} · ${formatStatus(key)}`, value: displayDetailValue(value)});
    }
  }
  return fields;
}

export function AuditTrailPanel({events}: {events: AuditEvent[]}) {
  const [selected, setSelected] = useState<AuditEvent | null>(null);
  return <>
    <Card className="overflow-hidden">
      <div className="border-b border-[var(--obliq-border)] p-5">
        <h2 className="font-bold">Audit trail</h2>
        <p className="mt-1 text-xs text-[var(--obliq-muted)]">Select any event to inspect its recorded context.</p>
      </div>
      <div className="divide-y divide-[var(--obliq-border)]">
        {events.map(event => <button key={event.id} className="obliq-focus grid w-full gap-3 p-5 text-left transition hover:bg-[#faf9f7] sm:grid-cols-[auto_1fr_auto]" onClick={() => setSelected(event)}>
          <span className="grid h-9 w-9 place-items-center rounded-xl bg-[var(--obliq-blue-soft)] text-[var(--obliq-blue-strong)]"><FileText size={16}/></span>
          <span><span className="block text-sm font-semibold">{formatStatus(event.action.replaceAll(".", "_"))}</span><span className="mt-1 block text-xs text-[#77716e]">{event.entity_type} · {event.entity_id}</span></span>
          <time className="text-xs text-[#77716e]">{formatDate(event.created_at)}</time>
        </button>)}
        {!events.length && <div className="p-10 text-center text-sm text-[var(--obliq-muted)]">No audit events yet.</div>}
      </div>
    </Card>
    {selected && <RowInsightModal eyebrow="AUDIT EVENT DETAILS" explanation={explainAuditEvent(selected)} fields={auditFields(selected)} onClose={() => setSelected(null)}/>} 
  </>;
}

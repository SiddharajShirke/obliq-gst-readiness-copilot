"use client";

import {CheckCircle2, Copy, MessageCircleMore, ShieldCheck} from "lucide-react";
import {Button} from "../ui/button";
import {Card} from "../ui/card";
import {formatDate} from "../../lib/format";

export type WhatsAppRuntimeStatusValue = {
  provider: string;
  configuration: string;
  sandbox_sender: string;
  inbound_webhook_url: string;
  status_callback_url: string;
  public_base_url: string;
  last_webhook_time: string | null;
  last_successful_message: string | null;
};

export function WhatsAppRuntimeStatus({status, onCopy}: {status: WhatsAppRuntimeStatusValue; onCopy: (value: string) => void}) {
  const rows = [
    ["Provider", status.provider],
    ["Configuration", status.configuration],
    ["Sandbox sender", status.sandbox_sender],
    ["Public base URL", status.public_base_url],
    ["Last webhook", status.last_webhook_time ? formatDate(status.last_webhook_time) : "Not received yet"],
    ["Last successful message", status.last_successful_message ? formatDate(status.last_successful_message) : "Not sent yet"],
  ];
  return <div className="grid gap-6 xl:grid-cols-[.72fr_1.28fr]">
    <div className="grid content-start gap-5">
      <Card className="bg-[#a4c5e5] p-6"><MessageCircleMore size={25}/><h2 className="mt-8 text-2xl font-bold tracking-[-.04em]">One live transport.</h2><p className="mt-3 text-sm leading-6 text-[#403b38]">OBLIQ uses the Vonage Messages API Sandbox for one-judge inbound text, outbound checklists, and delivery-status tracking.</p></Card>
      <Card className="p-5"><div className="flex items-start gap-3"><ShieldCheck className="mt-0.5 shrink-0 text-emerald-700" size={20}/><div><h3 className="font-bold">Server-managed configuration</h3><p className="mt-2 text-xs leading-5 text-[#6b6562]">Credentials, encryption keys, and token peppers are supplied only through backend environment variables and are never shown or edited here.</p></div></div></Card>
    </div>
    <Card className="p-6">
      <div className="flex items-center gap-3"><span className="grid h-10 w-10 place-items-center rounded-2xl bg-[#e8f1fa]"><CheckCircle2 size={19}/></span><div><h2 className="font-bold">Vonage runtime status</h2><p className="text-xs text-[#77716e]">Non-secret operational information from FastAPI.</p></div></div>
      <dl className="mt-6 grid gap-3 sm:grid-cols-2">{rows.map(([label, value]) => <div key={label} className="rounded-2xl bg-[#f8f7f5] p-4"><dt className="text-xs text-[#77716e]">{label}</dt><dd className="mt-2 break-all text-sm font-semibold">{value}</dd></div>)}</dl>
      {[['Inbound webhook URL', status.inbound_webhook_url], ['Status callback URL', status.status_callback_url]].map(([label, value]) => <div key={label} className="mt-5"><p className="text-xs font-semibold text-[#6b6562]">{label}</p><div className="mt-2 flex gap-2"><code className="min-w-0 flex-1 overflow-x-auto rounded-xl bg-[#f8f7f5] p-3 text-xs">{value}</code><Button variant="secondary" className="px-4" onClick={() => onCopy(value)} aria-label={`Copy ${label}`}><Copy size={16}/></Button></div></div>)}
    </Card>
  </div>;
}

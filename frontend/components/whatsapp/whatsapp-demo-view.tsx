"use client";

import QRCode from "react-qr-code";
import {Copy, MessageCircleMore, RefreshCw, ShieldCheck, XCircle} from "lucide-react";
import {Badge} from "../ui/badge";
import {Button} from "../ui/button";
import {Card} from "../ui/card";
import {formatDate, formatStatus} from "../../lib/format";
import type {WhatsAppDemoCreated, WhatsAppDemoStatus} from "../../lib/whatsapp-demo";

type Props = {
  created: WhatsAppDemoCreated;
  status: WhatsAppDemoStatus | null;
  countdown: string;
  busy: boolean;
  onCopy: (value: string) => void;
  onRegenerate: () => void;
  onCancel: () => void;
  onReconnect?: () => void;
};

function QrAction({value, label}: {value: string; label: string}) {
  return <div className="rounded-3xl border border-[#e5e2de] bg-white p-5">
    <div className="mx-auto grid w-fit place-items-center rounded-2xl bg-white p-4">
      <QRCode value={value} size={190} aria-label={label}/>
    </div>
  </div>;
}

function CopyValue({value, onCopy}: {value: string; onCopy: (value: string) => void}) {
  return <div className="mt-4 flex items-center gap-2">
    <code className="min-w-0 flex-1 overflow-x-auto rounded-xl bg-[#f8f7f5] p-3 text-xs">{value}</code>
    <Button variant="secondary" className="px-4" onClick={() => onCopy(value)} aria-label="Copy message">
      <Copy size={16}/>
    </Button>
  </div>;
}

export function WhatsAppDemoView({created, status, countdown, busy, onCopy, onRegenerate, onCancel, onReconnect}: Props) {
  const currentStatus = status?.status ?? created.status;
  return <>
    <Card className="mb-6 border-amber-200 bg-amber-50 p-5 text-sm leading-6 text-amber-900">
      <strong>This demonstration uses the Vonage WhatsApp Sandbox and your real WhatsApp account.</strong>
      <p className="mt-2">Your number is temporarily encrypted and used only for this session.</p>
      <p>This sandbox demonstration is limited to one judge at a time.</p>
      <p>Do not send confidential or real client information.</p>
    </Card>

    <div className="grid gap-6 xl:grid-cols-2">
      <Card className="p-6">
        <p className="text-xs font-bold tracking-[.13em] text-[#477ca8]">STEP 1</p>
        <h2 className="mt-2 text-xl font-bold">Step 1: Join the Sandbox</h2>
        <p className="mt-2 text-sm leading-6 text-[#6b6562]">The judge must send Vonage&apos;s allow-list message. OBLIQ cannot automatically confirm this step. Joining is normally required only once while this Sandbox membership remains active.</p>
        <div className="mt-5"><QrAction value={created.sandbox_join_whatsapp_url} label="Vonage Sandbox join QR"/></div>
        <CopyValue value={created.sandbox_join_message} onCopy={onCopy}/>
        <p className="mt-3 text-xs text-[#77716e]">Sandbox sender: {created.sandbox_sender}</p>
      </Card>

      <Card className="p-6">
        <p className="text-xs font-bold tracking-[.13em] text-[#477ca8]">STEP 2</p>
        <h2 className="mt-2 text-xl font-bold">Step 2: Start the OBLIQ session</h2>
        <p className="mt-2 text-sm leading-6 text-[#6b6562]">This QR is unique to {created.base_client_name} · {created.gst_period}. It expires in <strong>{countdown}</strong>.</p>
        <div className="mt-5"><QrAction value={created.start_whatsapp_url} label="Unique OBLIQ START QR"/></div>
        <CopyValue value={created.start_message} onCopy={onCopy}/>
        <div className="mt-4 flex flex-wrap gap-2">
          <Button variant="secondary" onClick={onRegenerate} disabled={busy || currentStatus !== "waiting_for_start"}><RefreshCw size={16}/>Regenerate</Button>
          <Button variant="ghost" onClick={onCancel} disabled={busy || ["cancelled", "expired"].includes(currentStatus)}><XCircle size={16}/>Cancel session</Button>
        </div>
      </Card>
    </div>

    <Card className="mt-6 p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div><p className="text-xs font-bold tracking-[.13em] text-[#477ca8]">LIVE STATUS</p><h2 className="mt-2 text-xl font-bold">Session status</h2></div>
        <Badge value={currentStatus}/>
      </div>
      <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {[
          ["Connection", status?.connection_status ?? "waiting"],
          ["Connected WhatsApp", status?.masked_phone ?? "Not connected"],
          ["Current step", status?.current_step ? formatStatus(status.current_step) : "Waiting for START"],
          ["Last delivery", status?.last_outbound_delivery_status ? formatStatus(status.last_outbound_delivery_status) : "No outbound message"],
          ["Last activity", status?.last_activity_at ? formatDate(status.last_activity_at) : "—"],
          ["Session expiry", formatDate(status?.session_expires_at ?? created.session_expires_at)],
        ].map(([label, value]) => <div key={label} className="rounded-2xl bg-[#f8f7f5] p-4"><p className="text-xs text-[#77716e]">{label}</p><p className="mt-2 text-sm font-semibold capitalize">{value}</p></div>)}
      </div>
      <div className="mt-6 border-t border-[#eeeae6] pt-5">
        <div className="flex items-center gap-2"><MessageCircleMore size={18}/><h3 className="font-bold">Cloned GST checklist</h3></div>
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          {(status?.checklist ?? []).map(item => <div key={item.id} className="flex items-center justify-between gap-3 rounded-2xl border border-[#e5e2de] p-4">
            <span className="text-sm font-semibold">{item.label}</span>
            <div className="flex flex-wrap justify-end gap-2">
              <Badge value={item.status}/>
              {item.upload_status === "uploaded" && <Badge value="uploaded"/>}
              {item.processing_status && <Badge value={item.processing_status}/>}
            </div>
          </div>)}
          {!status?.checklist.length && <p className="text-sm text-[#77716e]">Checklist appears after the session is created.</p>}
        </div>
      </div>
      <div className="mt-6 flex items-start gap-3 rounded-2xl bg-[#e8f1fa] p-4 text-sm leading-6 text-[#315d82]"><ShieldCheck className="mt-0.5 shrink-0" size={19}/>Only masked phone digits and live Vonage delivery status are shown. The browser never receives Vonage credentials, signature secrets, or encryption keys.</div>
      {onReconnect && ["cancelled", "expired"].includes(currentStatus) && <div className="mt-5 rounded-2xl border border-amber-200 bg-amber-50 p-4">
        <p className="text-sm text-amber-900">Reconnect explicitly to keep the same retained checklist and uploads. A new single-use START token will be generated.</p>
        <Button className="mt-3" onClick={onReconnect} disabled={busy}><RefreshCw size={16}/>Reconnect WhatsApp</Button>
      </div>}
    </Card>
  </>;
}

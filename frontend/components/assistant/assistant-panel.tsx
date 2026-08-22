"use client";

import {BookOpenCheck, Send, ShieldCheck, Sparkles, X} from "lucide-react";
import {FormEvent, useEffect, useMemo, useState} from "react";
import {toast} from "sonner";
import {apiFetch} from "../../lib/api";
import type {AssistantAnswer, Citation} from "../../lib/types";
import {Button} from "../ui/button";
import {Textarea} from "../ui/field";

type Message = {
  role: "user" | "assistant";
  text: string;
  citations?: Citation[];
  meta?: string;
};

type Props = {
  applicationId: string;
  clientName: string;
  period: string;
  missingCount: number;
  hasExtraction: boolean;
  hasReconciliation: boolean;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
};

function createConversationId() {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return crypto.randomUUID();
  return `conversation-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export function RagAssistantDrawer({
  applicationId,
  clientName,
  period,
  missingCount,
  hasExtraction,
  hasReconciliation,
  open,
  onOpenChange,
}: Props) {
  const [internalOpen, setInternalOpen] = useState(false);
  const [question, setQuestion] = useState("");
  const [conversationId, setConversationId] = useState("");
  const [busy, setBusy] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const isOpen = open ?? internalOpen;

  const suggestions = useMemo(() => {
    const rows: string[] = [];
    if (missingCount > 0) {
      rows.push("Which client documents are still missing?");
      rows.push("Draft a reminder for the missing documents.");
    }
    if (hasExtraction) {
      rows.push("Summarize the Purchase Register.");
      rows.push("Which extracted records need CA review?");
    }
    if (hasReconciliation) {
      rows.push("Explain the GSTR-2B mismatches.");
      rows.push("Which findings have raised alerts?");
    }
    return rows.length ? rows : ["What evidence is available for this GST period?"];
  }, [hasExtraction, hasReconciliation, missingCount]);

  useEffect(() => {
    const nextConversation = createConversationId();
    const timer = window.setTimeout(() => {
      setConversationId(nextConversation);
      setMessages([{
        role: "assistant",
        text: `I am scoped to ${clientName} for ${period}. Ask about this application's checklist, approved extractions, reconciliation findings, alerts, or GST guidance.`,
      }]);
    }, 0);
    return () => window.clearTimeout(timer);
  }, [applicationId, clientName, period]);

  useEffect(() => {
    if (!isOpen) return;
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  });

  function setOpen(next: boolean) {
    if (open === undefined) setInternalOpen(next);
    onOpenChange?.(next);
  }

  async function ask(event?: FormEvent) {
    event?.preventDefault();
    const value = question.trim();
    if (!value || busy) return;
    const activeConversation = conversationId || createConversationId();
    if (!conversationId) setConversationId(activeConversation);
    setQuestion("");
    setMessages(rows => [...rows, {role: "user", text: value}]);
    setBusy(true);
    try {
      const answer = await apiFetch<AssistantAnswer>("/assistant/query", {
        method: "POST",
        body: JSON.stringify({
          application_id: applicationId,
          conversation_id: activeConversation,
          question: value,
        }),
      });
      setMessages(rows => [...rows, {
        role: "assistant",
        text: answer.answer,
        citations: answer.citations,
        meta: `${answer.source_types.length ? answer.source_types.join(" + ") : "scoped evidence"} · ${Math.round(answer.confidence * 100)}% confidence`,
      }]);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Assistant failed");
      setMessages(rows => [...rows, {
        role: "assistant",
        text: "I could not retrieve a grounded answer just now. No application data was changed.",
      }]);
    } finally {
      setBusy(false);
    }
  }

  return <div data-application-id={applicationId}>
    <button
      type="button"
      onClick={() => setOpen(true)}
      className="obliq-focus fixed bottom-6 right-6 z-40 inline-flex items-center gap-2 rounded-full bg-[var(--obliq-action)] px-5 py-3 text-sm font-bold text-[var(--obliq-action-ink)] shadow-xl transition hover:-translate-y-0.5 hover:bg-[var(--obliq-action-hover)]"
      aria-label="Open OBLIQ RAG Assistant"
    >
      <Sparkles size={18}/> Ask OBLIQ
    </button>

    {isOpen && <button
      type="button"
      aria-label="Close assistant"
      className="fixed inset-0 z-40 cursor-default bg-black/35"
      onClick={() => setOpen(false)}
    />}

    {isOpen && <aside
      aria-label="OBLIQ RAG Assistant"
      className="fixed inset-y-0 right-0 z-50 flex w-full max-w-[460px] flex-col border-l border-[var(--obliq-border)] bg-[var(--obliq-surface)] text-[var(--obliq-ink)] shadow-2xl"
    >
      <header className="border-b border-[var(--obliq-border)] p-5">
        <div className="flex items-start justify-between gap-4">
          <div className="flex gap-3">
            <span className="grid h-11 w-11 shrink-0 place-items-center rounded-2xl bg-[var(--obliq-action)] text-[var(--obliq-action-ink)]"><Sparkles size={20}/></span>
            <div>
              <p className="text-xs font-bold tracking-[.12em] text-[var(--obliq-blue-strong)]">APPLICATION-SCOPED</p>
              <h2 className="mt-1 text-lg font-bold">OBLIQ RAG Assistant</h2>
            </div>
          </div>
          <button type="button" onClick={() => setOpen(false)} className="obliq-focus obliq-interactive rounded-xl p-2" aria-label="Close OBLIQ Assistant"><X size={19}/></button>
        </div>
        <div className="mt-4 rounded-2xl border border-[var(--obliq-border)] bg-[var(--obliq-surface-raised)] p-3">
          <p className="font-semibold">{clientName}</p>
          <p className="mt-1 text-xs text-[var(--obliq-muted)]">{period} · Private to this GST application</p>
        </div>
      </header>

      <div className="flex-1 space-y-4 overflow-y-auto bg-[var(--obliq-canvas)] p-4">
        {messages.length === 0 && <div className="rounded-2xl border border-[var(--obliq-border)] bg-[var(--obliq-surface)] p-4 text-sm leading-6">
          Ask about this application&apos;s documents, extracted records, reconciliation findings, or alerts.
        </div>}
        {messages.map((message, index) => <div
          key={`${message.role}-${index}`}
          className={message.role === "user"
            ? "ml-auto max-w-[86%] rounded-2xl rounded-br-sm bg-[var(--obliq-action)] p-4 text-sm leading-6 text-[var(--obliq-action-ink)]"
            : "max-w-[94%] rounded-2xl rounded-bl-sm border border-[var(--obliq-border)] bg-[var(--obliq-surface)] p-4 text-sm leading-6 shadow-sm"}
        >
          <p className="whitespace-pre-wrap">{message.text}</p>
          {message.meta && <p className="mt-3 text-[11px] text-[var(--obliq-muted)]">{message.meta}</p>}
          {message.citations?.map((citation, citationIndex) => <CitationCard key={`${citation.title}-${citationIndex}`} citation={citation}/>)}
        </div>)}
        {busy && <div className="max-w-[80%] animate-pulse rounded-2xl border border-[var(--obliq-border)] bg-[var(--obliq-surface)] p-4 text-sm text-[var(--obliq-muted)]">Loading exact facts and scoped evidence…</div>}
      </div>

      <div className="border-t border-[var(--obliq-border)] bg-[var(--obliq-surface)] p-4">
        <div className="mb-3 flex gap-2 overflow-x-auto pb-1">
          {suggestions.map(item => <button key={item} type="button" onClick={() => setQuestion(item)} className="obliq-focus obliq-interactive shrink-0 rounded-full border border-[var(--obliq-border)] px-3 py-2 text-xs font-semibold">{item}</button>)}
        </div>
        <form onSubmit={ask} className="flex items-end gap-2">
          <Textarea className="min-h-12 flex-1 resize-none" placeholder="Ask about this GST application…" value={question} onChange={event => setQuestion(event.target.value)}/>
          <Button type="submit" disabled={busy || !question.trim()} className="h-11 w-11 shrink-0 px-0" aria-label="Send question"><Send size={17}/></Button>
        </form>
        <p className="mt-3 flex items-center gap-2 text-[11px] text-[var(--obliq-muted)]"><ShieldCheck size={13}/> CA-controlled assistance. Professional GST decisions remain with the assigned CA.</p>
        <p className="sr-only">Sources appear here with document, page, sheet, or row provenance.</p>
      </div>
    </aside>}
  </div>;
}

function CitationCard({citation}: {citation: Citation}) {
  const location = [
    citation.reference,
    citation.section,
    citation.page !== undefined && citation.page !== null ? `Page ${citation.page}` : null,
    citation.sheet_name ? `Sheet ${citation.sheet_name}` : null,
    citation.row_start ? `Rows ${citation.row_start}${citation.row_end && citation.row_end !== citation.row_start ? `–${citation.row_end}` : ""}` : null,
  ].filter(Boolean).join(" · ");
  return <div className="mt-3 rounded-xl border border-[var(--obliq-border)] bg-[var(--obliq-surface-raised)] px-3 py-2 text-xs text-[var(--obliq-muted)]">
    <BookOpenCheck size={14} className="mr-2 inline text-[var(--obliq-blue-strong)]"/>
    <strong className="text-[var(--obliq-ink)]">{citation.title}</strong>
    {location && <p className="mt-1 pl-6">{location}</p>}
  </div>;
}

export function AssistantPanel({applicationId}: {applicationId: string}) {
  return <RagAssistantDrawer applicationId={applicationId} clientName="Current client" period="Current GST period" missingCount={0} hasExtraction hasReconciliation/>;
}

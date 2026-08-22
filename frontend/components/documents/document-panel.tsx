"use client";

import {FileJson2} from "lucide-react";
import {useCallback, useEffect, useState} from "react";
import {toast} from "sonner";
import {apiFetch} from "../../lib/api";
import {formatDate, formatStatus} from "../../lib/format";
import type {DocumentRecord, Requirement} from "../../lib/types";
import {Badge} from "../ui/badge";
import {Card} from "../ui/card";

type Props = {
  applicationId: string;
  checklist: Requirement[];
  onChanged: () => void;
};

export function DocumentPanel({applicationId, checklist}: Props) {
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const fetchDocuments = useCallback(
    () => apiFetch<DocumentRecord[]>(`/applications/${applicationId}/documents`),
    [applicationId],
  );

  useEffect(() => {
    let active = true;
    const refresh = () => fetchDocuments()
      .then(rows => {
        if (active) setDocuments(rows);
      })
      .catch(error => {
        if (active) toast.error(error instanceof Error ? error.message : "Unable to load documents");
      });
    void refresh();
    const timer = window.setInterval(() => void refresh(), 3000);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [fetchDocuments]);

  const labels = new Map(checklist.map(item => [item.id, item.label]));

  return <div className="grid gap-6">
    <Card className="border-blue-200 bg-blue-50 p-5">
      <h2 className="font-bold text-blue-950">Uploaded documents</h2>
      <p className="mt-2 text-sm leading-6 text-blue-900">
        Phase 2 stores original files securely and marks the matching checklist category as received.
        Uploaded files remain <strong>Awaiting processing</strong> until a later implementation phase.
      </p>
    </Card>
    <Card className="overflow-hidden">
      <div className="border-b border-[#eeeae6] p-5">
        <h3 className="font-bold">Private Storage intake</h3>
        <p className="mt-1 text-xs text-[#77716e]">{documents.length} files stored for this GST application</p>
      </div>
      <div className="divide-y divide-[#eeeae6]">
        {documents.map(document => <div key={document.id} className="flex flex-wrap items-start gap-3 p-5">
          <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-[#e8f1fa]">
            <FileJson2 size={18}/>
          </span>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-semibold">{document.original_name}</p>
            <p className="mt-1 text-xs text-[#77716e]">
              {document.requirement_id ? labels.get(document.requirement_id) ?? "Checklist document" : "Checklist document"}
              {" · "}{formatDate(document.created_at)}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Badge value="stored"/>
            <Badge value={document.processing_status || "awaiting_processing"}/>
          </div>
        </div>)}
        {!documents.length && <div className="p-10 text-center text-sm text-[#77716e]">
          No files uploaded through the secure client link yet.
        </div>}
      </div>
      <div className="border-t border-[#eeeae6] bg-[#faf9f7] px-5 py-3 text-xs text-[#77716e]">
        Extraction, validation, reconciliation, and document-content review are not enabled in Phase 2.
        Current status: {formatStatus("awaiting_processing")}.
      </div>
    </Card>
  </div>;
}

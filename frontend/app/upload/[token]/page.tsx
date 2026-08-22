"use client";

import {useParams} from "next/navigation";
import {useCallback, useEffect, useState} from "react";
import {toast} from "sonner";
import {
  SecureUploadView,
  type UploadTransientState,
} from "@/components/documents/secure-upload-view";
import {Loading} from "@/components/ui/loading";
import {ApiError, apiFetch} from "@/lib/api";
import type {PublicUploadContext, PublicUploadRequirement} from "@/lib/types";

export default function SecureUploadPage() {
  const {token} = useParams<{token: string}>();
  const [context, setContext] = useState<PublicUploadContext | null>(null);
  const [fatalError, setFatalError] = useState<string | null>(null);
  const [busyRequirementId, setBusyRequirementId] = useState<string | null>(null);
  const [transientStates, setTransientStates] = useState<Record<string, UploadTransientState>>({});

  const fetchContext = useCallback(async (statusOnly = false) => {
    const suffix = statusOnly ? "/status" : "";
    return apiFetch<PublicUploadContext>(`/public/upload/${token}${suffix}`, {}, false);
  }, [token]);

  useEffect(() => {
    let active = true;
    fetchContext()
      .then(nextContext => {
        if (active) {
          setContext(nextContext);
          setFatalError(null);
        }
      })
      .catch(error => {
        if (active) setFatalError(error instanceof Error ? error.message : "This upload link is unavailable");
      });
    const timer = window.setInterval(() => {
      fetchContext(true).then(nextContext => {
        if (active) setContext(nextContext);
      }).catch(() => undefined);
    }, 2500);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [fetchContext]);

  async function upload(requirement: PublicUploadRequirement, file: File) {
    setBusyRequirementId(requirement.id);
    setTransientStates(current => ({...current, [requirement.id]: "uploading"}));
    try {
      const data = new FormData();
      data.append("file", file);
      data.append("requirement_id", requirement.id);
      await apiFetch(`/public/upload/${token}`, {method: "POST", body: data}, false);
      setTransientStates(current => {
        const next = {...current};
        delete next[requirement.id];
        return next;
      });
      toast.success(`${requirement.label} uploaded securely`);
      setContext(await fetchContext(true));
      setFatalError(null);
    } catch (error) {
      const state: UploadTransientState = error instanceof ApiError && error.status === 409
        ? "duplicate"
        : "failed";
      setTransientStates(current => ({...current, [requirement.id]: state}));
      toast.error(error instanceof Error ? error.message : "Upload failed");
    } finally {
      setBusyRequirementId(null);
    }
  }

  if (fatalError) {
    return <main className="grid min-h-screen place-items-center bg-[#e8f1fa] p-6">
      <div className="max-w-lg rounded-3xl bg-white p-8 text-center shadow-xl">
        <h1 className="text-xl font-bold">Secure upload link unavailable</h1>
        <p className="mt-3 text-sm leading-6 text-[#625d5a]">{fatalError}</p>
        <p className="mt-3 text-xs text-[#77716e]">Ask the CA firm for a new upload link.</p>
      </div>
    </main>;
  }
  if (!context) return <main className="min-h-screen bg-[#e8f1fa]"><Loading label="Verifying secure upload link…"/></main>;
  return <SecureUploadView
    context={context}
    busyRequirementId={busyRequirementId}
    transientStates={transientStates}
    onUpload={upload}
  />;
}

import React from "react";
import { CloudOff, Send, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useOffline } from "@/context/OfflineContext";
import { useReference } from "@/context/ReferenceContext";
import * as sync from "@/services/offlineSync";
import { fromNow } from "@/utils/formatters";
import { OFFLINE } from "@/constants/testIds";

/**
 * Antrean kerja tersimpan di perangkat (Fase 35) — tampil di Papan Mandor.
 *
 * Mandor harus bisa MELIHAT apa yang belum terkirim, kenapa gagal, dan mencoba lagi.
 * Tanpa panel ini "tersimpan otomatis" cuma janji yang tidak bisa diperiksa.
 *
 * Label jenis & status diambil dari SSOT `/api/reference`
 * (`offline_queue_kind` / `offline_queue_status`) — bukan peta hardcode.
 */
export default function OfflineQueuePanel() {
  const { jobs, online, refresh } = useOffline();
  const { labelOf } = useReference();
  if (!jobs.length) return null;

  const retry = async (id) => { await sync.retry(id); await refresh(); };
  const drop = async (id) => { await sync.remove(id); await refresh(); };

  return (
    <div data-testid={OFFLINE.queuePanel}
      className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-amber-900">
      <p className="flex items-center gap-1.5 text-xs font-semibold">
        <CloudOff className="h-3.5 w-3.5" />
        Tersimpan di perangkat ({jobs.length}) — belum sampai ke server
      </p>
      <p className="mt-0.5 text-[11px]">
        {online
          ? "Sedang dikirim otomatis. Anda juga bisa menekan “Kirim” pada barisnya."
          : "Akan terkirim sendiri begitu sinyal kembali. Aman ditutup — data tidak hilang."}
      </p>
      <div className="mt-2 space-y-2">
        {jobs.map((j) => (
          <div key={j.id} data-testid={OFFLINE.queueRow} data-status={j.status}
            className="rounded-lg border bg-card p-2 text-[11px] text-foreground">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div>
                <p className="font-semibold">
                  {labelOf("offline_queue_kind", j.kind)} · {j.unit_code} ·{" "}
                  <span className="font-mono text-[10px]">{j.step_code}</span> {j.name}
                </p>
                <p className="text-muted-foreground">
                  {labelOf("offline_queue_status", j.status)} · dibuat {fromNow(j.created_at)}
                  {(j.photos || []).length ? ` · ${j.photos.length} foto bukti ikut tersimpan` : ""}
                  {j.attempts ? ` · ${j.attempts}× dicoba` : ""}
                </p>
                {j.last_error ? (
                  <p className={j.status === "rejected" ? "text-rose-700" : "text-amber-700"}>
                    {j.last_error}
                  </p>
                ) : null}
              </div>
              <div className="flex items-center gap-1">
                <Button size="sm" variant="outline" data-testid={OFFLINE.queueRetry}
                  disabled={!online || j.status === "sending"} onClick={() => retry(j.id)}>
                  <Send className="mr-1 h-3 w-3" /> Kirim
                </Button>
                <Button size="sm" variant="ghost" data-testid={OFFLINE.queueRemove}
                  aria-label="Hapus dari antrean" onClick={() => drop(j.id)}>
                  <Trash2 className="h-3.5 w-3.5 text-rose-600" />
                </Button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

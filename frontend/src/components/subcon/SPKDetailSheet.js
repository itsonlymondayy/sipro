import React, { useEffect, useState } from "react";
import { toast } from "sonner";
import { Save } from "lucide-react";
import {
  Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription,
} from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import StatusPill from "@/components/patterns/StatusPill";
import ChangeOrdersSection from "@/components/subcon/ChangeOrdersSection";
import SpkScopeSection from "@/components/subcon/SpkScopeSection";
import { formatIDR, formatDateWIB } from "@/utils/formatters";
import api from "@/services/apiClient";
import { PROCUREMENT } from "@/constants/testIds";
import { useReference } from "@/context/ReferenceContext";


function Row({ label, value }) {
  return (
    <div className="flex justify-between gap-4 py-1 text-sm">
      <span className="text-muted-foreground">{label}</span>
      <span className="text-right font-medium">{value || "-"}</span>
    </div>
  );
}

export default function SPKDetailSheet({ spk, open, canManage, onOpenChange, onChanged }) {
  const { labelOf, options } = useReference();
  const [status, setStatus] = useState("");
  const [progress, setProgress] = useState(0);
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (spk) { setStatus(spk.status); setProgress(spk.progress_pct || 0); } }, [spk]);
  if (!spk) return null;
  const itemBased = spk.scope_mode === "items";

  const saveStatus = async () => {
    setBusy(true);
    try {
      await api.post(`/subcon/spk/${spk.id}/status`, { status });
      toast.success(`Status SPK → ${labelOf("spk_status", status)}.`);
      onOpenChange(false); onChanged && onChanged();
    } catch (e) { toast.error(e?.response?.data?.detail || "Gagal mengubah status."); }
    finally { setBusy(false); }
  };
  const saveProgress = async () => {
    setBusy(true);
    try {
      await api.put(`/subcon/spk/${spk.id}`, { progress_pct: Number(progress) || 0 });
      toast.success("Progres SPK diperbarui.");
      onChanged && onChanged();
    } catch (e) { toast.error(e?.response?.data?.detail || "Gagal memperbarui progres."); }
    finally { setBusy(false); }
  };

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent data-testid={PROCUREMENT.spkDetail} className="w-full overflow-y-auto sm:max-w-3xl">
        <SheetHeader>
          <SheetTitle>{spk.spk_number}</SheetTitle>
          <SheetDescription>{spk.title}</SheetDescription>
        </SheetHeader>
        <div className="mt-5 space-y-5">
          <div className="rounded-xl border bg-card p-4">
            <div className="mb-2"><StatusPill status={spk.status} group="spk_status" /></div>
            <Row label="Subkontraktor" value={spk.subcontractor_name} />
            <Row label="Proyek" value={spk.project_name} />
            <Row label="Nilai Kontrak" value={formatIDR(spk.contract_value)} />
            <Row label="Retensi" value={`${spk.retention_pct}%`} />
            <Row label="Mulai" value={spk.start_date ? formatDateWIB(spk.start_date) : "-"} />
            <Row label="Selesai" value={spk.end_date ? formatDateWIB(spk.end_date) : "-"} />
            <Row label="Progres" value={`${spk.progress_pct}%${itemBased ? " (dari bukti kerja)" : ""}`} />
            {itemBased ? (
              <Row label="Sudah ditagih" value={`${spk.billed_pct || 0}% · ${formatIDR(spk.scope_billed_value)}`} />
            ) : null}
            {spk.scope ? <p className="mt-2 rounded-lg bg-secondary p-3 text-sm">{spk.scope}</p> : null}
          </div>

          <SpkScopeSection spk={spk} canManage={canManage} onChanged={onChanged} />

          {canManage ? (
            <div className="space-y-3 rounded-xl border bg-card p-4">
              <p className="text-sm font-semibold">Kelola SPK</p>
              {itemBased ? (
                <p className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-[12px] text-emerald-900">
                  Progres SPK ini <b>dihitung otomatis</b> dari pekerjaan yang sudah diverifikasi
                  ({spk.progress_pct}%), jadi tidak bisa diketik manual. Untuk menaikkannya:
                  verifikasi pekerjaan di Progres &amp; Mutu Konstruksi.
                </p>
              ) : (
                <div className="space-y-1.5"><Label>Progres (%)</Label>
                  <div className="flex gap-2">
                    <Input type="number" value={progress} aria-label="Progres SPK"
                      onChange={(e) => setProgress(e.target.value)} />
                    <Button variant="outline" disabled={busy} onClick={saveProgress}>Simpan</Button>
                  </div>
                </div>
              )}
              <div className="space-y-1.5"><Label>Status</Label>
                <Select value={status} onValueChange={setStatus}>
                  <SelectTrigger data-testid={PROCUREMENT.spkStatusSelect}><SelectValue /></SelectTrigger>
                  <SelectContent>{options("spk_status").map((o) => <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>)}</SelectContent>
                </Select>
              </div>
              <Button data-testid={PROCUREMENT.spkStatusSubmit} className="w-full" disabled={busy || status === spk.status} onClick={saveStatus}>
                <Save className="mr-1.5 h-4 w-4" /> Simpan Status
              </Button>
            </div>
          ) : null}

          <ChangeOrdersSection spk={spk} onChanged={onChanged} />
        </div>
      </SheetContent>
    </Sheet>
  );
}

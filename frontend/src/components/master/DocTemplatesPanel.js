import React, { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { FileText, Plus, Pencil, Archive } from "lucide-react";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import EmptyState from "@/components/patterns/EmptyState";
import { LoadingCards, ErrorState } from "@/components/patterns/StateViews";
import ConfirmDialog from "@/components/patterns/ConfirmDialog";
import api from "@/services/apiClient";
import { MASTER } from "@/constants/testIds";

const EMPTY = { code: "", name: "", content: "" };

function TemplateDialog({ open, onOpenChange, initial, onDone }) {
  const editing = Boolean(initial?.id);
  const [form, setForm] = useState(EMPTY);
  const [busy, setBusy] = useState(false);
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));
  useEffect(() => {
    if (open) setForm(initial ? { code: initial.code, name: initial.name, content: initial.content || "" } : EMPTY);
  }, [open, initial]);

  const submit = async () => {
    if (!form.name.trim() || !form.content.trim() || (!editing && !form.code.trim())) {
      toast.error("Kode, nama, dan isi template wajib diisi."); return;
    }
    setBusy(true);
    try {
      if (editing) {
        await api.put(`/master/doc-templates/${initial.id}`, { name: form.name, content: form.content });
        toast.success("Template dokumen diperbarui.");
      } else {
        await api.post("/master/doc-templates", form);
        toast.success("Template dokumen dibuat.");
      }
      onOpenChange(false); onDone && onDone();
    } catch (e) { toast.error(e?.response?.data?.detail || "Gagal menyimpan template."); }
    finally { setBusy(false); }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>{editing ? "Ubah Template Dokumen" : "Tambah Template Dokumen"}</DialogTitle>
          <DialogDescription>
            Gunakan placeholder seperti <code>{"{{buyer_name}}"}</code>, <code>{"{{unit_code}}"}</code>,{" "}
            <code>{"{{price}}"}</code>, <code>{"{{doc_number}}"}</code>, <code>{"{{date}}"}</code>.
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label htmlFor="doctemplatespanel-kode-template">Kode Template</Label>
            <Input id="doctemplatespanel-kode-template" data-testid={MASTER.docFormCode} value={form.code} disabled={editing}
              onChange={(e) => set("code", e.target.value.toUpperCase())} placeholder="mis. BAST" />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="doctemplatespanel-nama-template">Nama Template</Label>
            <Input id="doctemplatespanel-nama-template" data-testid={MASTER.docFormName} value={form.name}
              onChange={(e) => set("name", e.target.value)} placeholder="mis. Berita Acara Serah Terima" />
          </div>
          <div className="space-y-1.5 sm:col-span-2">
            <Label htmlFor="doctemplatespanel-isi-template">Isi Template</Label>
            <Textarea id="doctemplatespanel-isi-template" data-testid={MASTER.docFormContent} rows={10} value={form.content}
              onChange={(e) => set("content", e.target.value)}
              placeholder={"BERITA ACARA SERAH TERIMA\n\nNo : {{doc_number}}\nUnit : {{unit_code}}"} />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={busy}>Batal</Button>
          <Button data-testid={MASTER.docSubmit} onClick={submit} disabled={busy}>
            {busy ? "Menyimpan…" : "Simpan"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default function DocTemplatesPanel() {
  const [rows, setRows] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [dlg, setDlg] = useState({ open: false, initial: null });
  const [archiveTarget, setArchiveTarget] = useState(null);
  const [archiveBusy, setArchiveBusy] = useState(false);

  const load = useCallback(async () => {
    setLoading(true); setError("");
    try {
      const r = await api.get("/master/doc-templates", { params: { include_inactive: true } });
      setRows(r.data.data || []);
    } catch (e) { setError(e?.response?.data?.detail || "Gagal memuat template dokumen."); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const archive = async () => {
    const t = archiveTarget;
    if (!t) return;
    setArchiveBusy(true);
    try {
      await api.delete(`/master/doc-templates/${t.id}`);
      toast.success(`Template ${t.code} diarsipkan.`);
      setArchiveTarget(null);
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Gagal mengarsipkan."); }
    finally { setArchiveBusy(false); }
  };

  if (loading) return <LoadingCards count={3} />;
  if (error) return <ErrorState message={error} onRetry={load} />;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm text-muted-foreground">
          Template untuk PPJB, Surat Pesanan, AJB, BAST, dll. Dipakai saat menerbitkan dokumen deal.
        </p>
        <Button data-testid={MASTER.docAddBtn} size="sm" onClick={() => setDlg({ open: true, initial: null })}>
          <Plus className="mr-1.5 h-4 w-4" /> Tambah Template
        </Button>
      </div>
      {!rows?.length ? (
        <EmptyState icon={FileText} title="Belum ada template dokumen"
          description="Buat template pertama agar dokumen legal bisa diterbitkan."
          actionLabel="Tambah Template" onAction={() => setDlg({ open: true, initial: null })} />
      ) : (
        <div className="space-y-3">
          {rows.map((t) => (
            <div key={t.id} data-testid={MASTER.docRow} data-template-code={t.code}
              data-template-archived={t.is_active === false ? "true" : "false"}
              className="rounded-xl border bg-card p-4">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <p className="font-heading text-sm font-semibold">
                    {t.name} <span className="ml-1 rounded bg-secondary px-1.5 py-0.5 text-xs font-medium">{t.code}</span>
                    {t.is_active === false ? (
                      <span className="ml-2 rounded bg-muted px-1.5 py-0.5 text-[11px] text-muted-foreground">diarsipkan</span>
                    ) : null}
                  </p>
                  <p className="mt-1 line-clamp-2 whitespace-pre-line text-xs text-muted-foreground">{t.content}</p>
                </div>
                <div className="flex gap-2">
                  <Button data-testid={MASTER.docEditBtn} data-template-code={t.code}
                    aria-label={`Ubah template dokumen ${t.code}`} title={`Ubah template ${t.code}`}
                    size="sm" variant="outline"
                    onClick={() => setDlg({ open: true, initial: t })}>
                    <Pencil className="mr-1 h-3.5 w-3.5" /> Ubah
                  </Button>
                  {t.is_active !== false ? (
                    <Button data-testid={MASTER.docArchiveBtn} data-template-code={t.code}
                      aria-label={`Arsipkan template dokumen ${t.code}`} title={`Arsipkan template ${t.code}`}
                      size="sm" variant="ghost" onClick={() => setArchiveTarget(t)}>
                      <Archive className="mr-1 h-3.5 w-3.5" /> Arsip
                    </Button>
                  ) : null}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
      <TemplateDialog open={dlg.open} initial={dlg.initial}
        onOpenChange={(o) => setDlg((d) => ({ ...d, open: o }))} onDone={load} />
      <ConfirmDialog open={!!archiveTarget} onOpenChange={(v) => !v && setArchiveTarget(null)}
        title={`Arsipkan template “${archiveTarget?.name || ""}”?`}
        description="Template yang diarsipkan tidak lagi bisa dipilih saat menerbitkan dokumen baru, tetapi dokumen yang sudah terbit tetap utuh."
        confirmLabel="Ya, arsipkan" busy={archiveBusy} onConfirm={archive}
        testId="doc-archive-confirm" />
    </div>
  );
}

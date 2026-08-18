import React, { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { Plus, Pencil, Trash2, FileText } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "@/components/ui/dialog";
import StatusPill from "@/components/patterns/StatusPill";
import EmptyState from "@/components/patterns/EmptyState";
import { LoadingCards, ErrorState } from "@/components/patterns/StateViews";
import { useReference } from "@/context/ReferenceContext";
import api from "@/services/apiClient";
import { OMNI } from "@/constants/testIds";


function emptyForm() {
  return { name: "", category: "utility", language: "id", body: "", variables: "" };
}

export default function TemplatesPanel() {
  const { options, labelOf } = useReference();
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [open, setOpen] = useState(false);
  const [editId, setEditId] = useState(null);
  const [form, setForm] = useState(emptyForm());
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setLoading(true); setError("");
    try {
      const res = await api.get("/wa-templates");
      setRows(res.data.data || []);
    } catch (e) {
      setError(e?.response?.data?.detail || "Gagal memuat template.");
    } finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const openCreate = () => { setEditId(null); setForm(emptyForm()); setOpen(true); };
  const openEdit = (t) => {
    setEditId(t.id);
    setForm({ name: t.name, category: t.category, language: t.language || "id", body: t.body,
      variables: (t.variables || []).join(", ") });
    setOpen(true);
  };

  const save = async () => {
    if (!form.name.trim() || !form.body.trim()) { toast.error("Nama & isi template wajib diisi."); return; }
    setBusy(true);
    const payload = {
      name: form.name.trim(), category: form.category, language: form.language,
      body: form.body, variables: form.variables.split(",").map((v) => v.trim()).filter(Boolean),
    };
    try {
      if (editId) await api.put(`/wa-templates/${editId}`, payload);
      else await api.post("/wa-templates", payload);
      toast.success(editId ? "Template diperbarui." : "Template dibuat.");
      setOpen(false); load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Gagal menyimpan template."); }
    finally { setBusy(false); }
  };

  const remove = async (t) => {
    try { await api.delete(`/wa-templates/${t.id}`); toast.success("Template dihapus."); load(); }
    catch { toast.error("Gagal menghapus template."); }
  };

  if (loading) return <LoadingCards count={3} />;
  if (error) return <ErrorState message={error} onRetry={load} />;

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">Template WA pra-approved (dipakai untuk membuka sesi 24 jam).</p>
        <Button data-testid={OMNI.tmplAddBtn} size="sm" onClick={openCreate}>
          <Plus className="mr-1.5 h-4 w-4" /> Tambah Template
        </Button>
      </div>

      {!rows.length ? (
        <EmptyState icon={FileText} title="Belum ada template" description="Buat template WA pertama."
          actionLabel="Tambah Template" onAction={openCreate} />
      ) : (
        <div className="grid gap-2 md:grid-cols-2">
          {rows.map((t) => (
            <div key={t.id} data-testid={OMNI.tmplRow} className="rounded-xl border bg-card p-3">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <p className="font-medium">{t.name}</p>
                    <StatusPill status={t.status === "approved" ? "approved" : "pending"} group="wa_template_status" />
                  </div>
                  <p className="text-[11px] text-muted-foreground">kode: {t.code} &middot; {labelOf("wa_template_category", t.category)} &middot; {t.language}</p>
                </div>
                <div className="flex shrink-0 gap-1">
                  <Button variant="ghost" size="icon" onClick={() => openEdit(t)}><Pencil className="h-4 w-4" /></Button>
                  <Button data-testid={OMNI.tmplDeleteBtn} variant="ghost" size="icon" onClick={() => remove(t)}>
                    <Trash2 className="h-4 w-4 text-destructive" />
                  </Button>
                </div>
              </div>
              <p className="mt-2 whitespace-pre-line rounded-lg bg-secondary p-2 text-xs text-secondary-foreground">{t.body}</p>
            </div>
          ))}
        </div>
      )}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{editId ? "Ubah Template" : "Tambah Template"}</DialogTitle>
            <DialogDescription>Variabel ditulis {"{{nama}}"} — daftarkan di kolom Variabel.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="templatespanel-nama-template">Nama Template</Label>
              <Input id="templatespanel-nama-template" data-testid={OMNI.tmplName} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label>Kategori</Label>
                <Select value={form.category} onValueChange={(v) => setForm({ ...form, category: v })}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>{options("wa_template_category").map((c) => <SelectItem key={c.value} value={c.value}>{c.label}</SelectItem>)}</SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="templatespanel-bahasa">Bahasa</Label>
                <Input id="templatespanel-bahasa" value={form.language} onChange={(e) => setForm({ ...form, language: e.target.value })} />
              </div>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="templatespanel-isi-pesan">Isi Pesan</Label>
              <Textarea id="templatespanel-isi-pesan" data-testid={OMNI.tmplBody} rows={4} value={form.body}
                onChange={(e) => setForm({ ...form, body: e.target.value })} placeholder="Halo {{name}}, ..." />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="templatespanel-variabel-pisahkan-koma">Variabel (pisahkan koma)</Label>
              <Input id="templatespanel-variabel-pisahkan-koma" value={form.variables} onChange={(e) => setForm({ ...form, variables: e.target.value })} placeholder="name, date" />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)} disabled={busy}>Batal</Button>
            <Button data-testid={OMNI.tmplSave} onClick={save} disabled={busy}>{busy ? "Menyimpan..." : "Simpan"}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

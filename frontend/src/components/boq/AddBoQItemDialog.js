import React, { useEffect, useState } from "react";
import { toast } from "sonner";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { formatIDR } from "@/utils/formatters";
import ReferenceSelect from "@/components/patterns/ReferenceSelect";
import api from "@/services/apiClient";
import { PROCUREMENT } from "@/constants/testIds";

// Daftar kategori & satuan TIDAK lagi hardcode di sini — sumbernya /api/reference (SSOT).
const EMPTY = { cost_code: "", category: "struktur", description: "", uom: "unit", quantity: "1", unit_price: "0" };

export default function AddBoQItemDialog({ projectId, open, onOpenChange, onDone }) {
  const [form, setForm] = useState(EMPTY);
  const [busy, setBusy] = useState(false);
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));
  useEffect(() => { if (open) setForm(EMPTY); }, [open]);

  const amount = (Number(form.quantity) || 0) * (Number(form.unit_price) || 0);

  const submit = async () => {
    if (!form.description.trim()) { toast.error("Isi uraian pekerjaan."); return; }
    setBusy(true);
    try {
      await api.post("/boq/items", {
        project_id: projectId, cost_code: form.cost_code || null, category: form.category,
        description: form.description, uom: form.uom, quantity: Number(form.quantity) || 0,
        unit_price: Math.round(Number(form.unit_price) || 0),
      });
      toast.success("Item RAB ditambahkan.");
      onOpenChange(false); onDone && onDone();
    } catch (e) { toast.error(e?.response?.data?.detail || "Gagal menambah item."); }
    finally { setBusy(false); }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Tambah Item RAB</DialogTitle>
          <DialogDescription>Kode biaya, volume, dan harga satuan (Rp).</DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-1.5"><Label htmlFor="addboqitemdialog-kode-biaya">Kode Biaya</Label><Input id="addboqitemdialog-kode-biaya" value={form.cost_code} onChange={(e) => set("cost_code", e.target.value)} placeholder="mis. STR-01" /></div>
          <div className="space-y-1.5"><Label>Kategori</Label>
            <ReferenceSelect group="work_category" value={form.category}
              onChange={(v) => set("category", v)} testId="boq-form-category" /></div>
          <div className="space-y-1.5 sm:col-span-2"><Label htmlFor="addboqitemdialog-uraian-pekerjaan">Uraian Pekerjaan</Label><Input id="addboqitemdialog-uraian-pekerjaan" value={form.description} onChange={(e) => set("description", e.target.value)} placeholder="mis. Beton K-300 kolom & balok" /></div>
          <div className="space-y-1.5"><Label>Satuan (UOM)</Label>
            <ReferenceSelect group="uom" value={form.uom} onChange={(v) => set("uom", v)}
              testId="boq-form-uom" /></div>
          <div className="space-y-1.5"><Label htmlFor="boq-qty">Volume</Label><Input id="boq-qty" data-testid="boq-form-qty" type="number" value={form.quantity} onChange={(e) => set("quantity", e.target.value)} /></div>
          <div className="space-y-1.5 sm:col-span-2"><Label htmlFor="boq-price">Harga Satuan (Rp)</Label><Input id="boq-price" data-testid="boq-form-price" type="number" value={form.unit_price} onChange={(e) => set("unit_price", e.target.value)} /></div>
        </div>
        <div className="rounded-lg bg-secondary p-3 text-sm">Jumlah: <span className="font-semibold tabular-nums">{formatIDR(amount)}</span></div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={busy}>Batal</Button>
          <Button data-testid={PROCUREMENT.boqAddSubmit} onClick={submit} disabled={busy}>{busy ? "Menyimpan…" : "Simpan"}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

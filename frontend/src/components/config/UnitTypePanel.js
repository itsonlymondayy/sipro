import React, { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { AlertTriangle, Pencil, Plus } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import DataTable from "@/components/patterns/DataTable";
import api from "@/services/apiClient";
import { formatIDR } from "@/utils/formatters";
import { CONFIG } from "@/constants/testIds";

const EMPTY = {
  code: "", name: "", building_area: 30, land_area_std: 60, base_price: 0, bedrooms: 2,
  bathrooms: 1, floors: 1, active: true,
};

/** Master TIPE UNIT — dasar harga & spesifikasi unit (dipakai generator unit & SPR). */
export default function UnitTypePanel() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [query, setQuery] = useState({ q: "", sort: "code", direction: "asc", skip: 0, limit: 50 });
  const [form, setForm] = useState(null);

  const load = useCallback(async () => {
    setLoading(true); setError("");
    try {
      const res = await api.get("/catalog/unit-types");
      setRows(res.data.data || []);
    } catch (e) {
      setError(e?.response?.data?.detail || "Gagal memuat tipe unit.");
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const submit = async () => {
    try {
      const body = {
        ...form,
        building_area: Number(form.building_area) || 0,
        land_area_std: Number(form.land_area_std) || 0,
        base_price: Number(form.base_price) || 0,
      };
      if (form.id) {
        const { id, code, org_id, created_at, updated_at, units_count, ...patch } = body;
        await api.put(`/catalog/unit-types/${form.id}`, { ...patch, needs_review: false });
      } else {
        await api.post("/catalog/unit-types", body);
      }
      toast.success("Tipe unit disimpan.");
      setForm(null); load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menyimpan tipe unit.");
    }
  };

  const filtered = rows.filter((r) => {
    const q = (query.q || "").toLowerCase();
    return !q || `${r.code} ${r.name}`.toLowerCase().includes(q);
  });

  const columns = [
    { key: "code", header: "Kode", sortable: true,
      render: (r) => <span className="font-mono text-xs">{r.code}</span> },
    { key: "name", header: "Tipe", sortable: true,
      render: (r) => (
        <div className="flex items-center gap-2">
          <span className="font-medium">{r.name}</span>
          {r.needs_review ? (
            <span className="inline-flex items-center gap-1 rounded border bg-amber-50 px-1.5 py-0.5 text-[10px] text-amber-800">
              <AlertTriangle className="h-3 w-3" /> perlu ditinjau
            </span>
          ) : null}
        </div>
      ) },
    { key: "building_area", header: "Luas bangunan (m²)", align: "right", sortable: true,
      render: (r) => r.building_area ?? "belum diisi" },
    { key: "land_area_std", header: "Luas tanah standar (m²)", align: "right", sortable: true,
      render: (r) => r.land_area_std ?? "belum diisi" },
    { key: "base_price", header: "Harga dasar", align: "right", sortable: true,
      render: (r) => (r.base_price ? formatIDR(r.base_price)
        : <span className="text-muted-foreground">belum diisi</span>),
      exportValue: (r) => r.base_price },
    { key: "units_count", header: "Jumlah unit", align: "right", sortable: true },
    { key: "actions", header: "Aksi", align: "right",
      render: (r) => (
        <Button data-testid={CONFIG.typeEdit} size="sm" variant="ghost"
          onClick={() => setForm({ ...EMPTY, ...r })}>
          <Pencil className="h-3.5 w-3.5" />
        </Button>
      ), exportValue: () => "" },
  ];

  return (
    <div data-testid={CONFIG.typePanel} className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm text-muted-foreground">
          Tipe hasil migrasi data lama ditandai <strong>perlu ditinjau</strong> bila luas/harga
          tidak bisa dipastikan — sistem tidak mengarang angka.
        </p>
        <Button data-testid={CONFIG.typeAdd} size="sm" onClick={() => setForm({ ...EMPTY })}>
          <Plus className="mr-1.5 h-4 w-4" /> Tipe unit baru
        </Button>
      </div>
      <DataTable
        testId="config-type-table"
        testIds={{ search: "config-type-search", row: CONFIG.typeRow,
          export: "config-type-export", columns: "config-type-columns" }}
        columns={columns} rows={filtered} total={filtered.length} query={query}
        onQueryChange={(p) => setQuery((q) => ({ ...q, ...p }))}
        loading={loading} error={error} onRefresh={load}
        searchPlaceholder="Cari tipe unit…" exportName="tipe-unit"
        emptyTitle="Belum ada tipe unit" />

      <Dialog open={!!form} onOpenChange={(o) => { if (!o) setForm(null); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{form?.id ? "Ubah tipe unit" : "Tipe unit baru"}</DialogTitle>
            <DialogDescription>
              Harga dasar dipakai saat membuat unit (dikalikan pengali harga cluster).
            </DialogDescription>
          </DialogHeader>
          {form ? (
            <div className="space-y-3">
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="space-y-1.5">
                  <Label htmlFor="ut-code">Kode</Label>
                  <Input id="ut-code" data-testid={CONFIG.typeFormCode} value={form.code}
                    disabled={!!form.id} placeholder="T30-60"
                    onChange={(e) => setForm({ ...form, code: e.target.value.toUpperCase() })} />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="ut-name">Nama tipe</Label>
                  <Input id="ut-name" data-testid={CONFIG.typeFormName} value={form.name}
                    placeholder="Tipe 30/60"
                    onChange={(e) => setForm({ ...form, name: e.target.value })} />
                </div>
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="space-y-1.5">
                  <Label htmlFor="ut-lb">Luas bangunan (m²)</Label>
                  <Input id="ut-lb" data-testid={CONFIG.typeFormBuilding} type="number"
                    value={form.building_area ?? ""}
                    onChange={(e) => setForm({ ...form, building_area: e.target.value })} />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="ut-lt">Luas tanah standar (m²)</Label>
                  <Input id="ut-lt" data-testid={CONFIG.typeFormLand} type="number"
                    value={form.land_area_std ?? ""}
                    onChange={(e) => setForm({ ...form, land_area_std: e.target.value })} />
                </div>
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="ut-price">Harga dasar (Rp)</Label>
                <Input id="ut-price" data-testid={CONFIG.typeFormPrice} type="number"
                  value={form.base_price ?? ""}
                  onChange={(e) => setForm({ ...form, base_price: e.target.value })} />
              </div>
              <div className="grid gap-3 sm:grid-cols-3">
                <div className="space-y-1.5">
                  <Label htmlFor="ut-kt">Kamar tidur</Label>
                  <Input id="ut-kt" type="number" value={form.bedrooms ?? ""}
                    onChange={(e) => setForm({ ...form, bedrooms: Number(e.target.value) })} />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="ut-km">Kamar mandi</Label>
                  <Input id="ut-km" type="number" value={form.bathrooms ?? ""}
                    onChange={(e) => setForm({ ...form, bathrooms: Number(e.target.value) })} />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="ut-fl">Jumlah lantai</Label>
                  <Input id="ut-fl" type="number" value={form.floors ?? 1}
                    onChange={(e) => setForm({ ...form, floors: Number(e.target.value) })} />
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Switch checked={!!form.active} aria-label="Aktif"
                  onCheckedChange={(v) => setForm({ ...form, active: v })} />
                <span className="text-sm">Aktif (bisa dipakai membuat unit)</span>
              </div>
            </div>
          ) : null}
          <DialogFooter>
            <Button variant="ghost" onClick={() => setForm(null)}>Batal</Button>
            <Button data-testid={CONFIG.typeSubmit} onClick={submit}
              disabled={!form?.code || !form?.name}>Simpan</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

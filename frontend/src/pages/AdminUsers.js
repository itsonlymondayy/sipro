import React, { useCallback, useEffect, useState } from "react";
import { Users2, UserPlus, ShieldCheck } from "lucide-react";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogTrigger,
} from "@/components/ui/dialog";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { LoadingCards, ErrorState } from "@/components/patterns/StateViews";
import EmptyState from "@/components/patterns/EmptyState";
import { roleLabel } from "@/utils/formatters";
import api from "@/services/apiClient";
import { ADMIN } from "@/constants/testIds";

const ROLES = [
  "super_admin", "owner", "sales_manager", "marketing_admin",
  "sales", "finance", "project_manager", "site_engineer",
];

export default function AdminUsers() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ name: "", email: "", password: "", role: "sales" });
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const res = await api.get("/admin/users", { params: { limit: 100 } });
      setRows(res.data.data || []);
    } catch (e) {
      setError(e?.response?.data?.detail || "Gagal memuat pengguna.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const create = async () => {
    setSaving(true);
    setFormError("");
    try {
      await api.post("/admin/users", form);
      setOpen(false);
      setForm({ name: "", email: "", password: "", role: "sales" });
      load();
    } catch (e) {
      setFormError(e?.response?.data?.detail || "Gagal membuat pengguna.");
    } finally {
      setSaving(false);
    }
  };

  const toggleActive = async (u) => {
    await api.put(`/admin/users/${u.id}`, { is_active: !u.is_active });
    load();
  };

  return (
    <div data-testid={ADMIN.usersPage} className="space-y-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Users2 className="h-5 w-5 text-primary" />
          <h1 className="font-heading text-xl font-semibold">Pengguna</h1>
          <span className="rounded-full bg-secondary px-2 py-0.5 text-xs text-muted-foreground tabular-nums">{rows.length}</span>
        </div>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button size="sm"><UserPlus className="h-4 w-4 mr-1.5" /> Tambah Pengguna</Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader><DialogTitle>Tambah Pengguna</DialogTitle></DialogHeader>
            {formError ? <p className="text-sm text-rose-600">{formError}</p> : null}
            <div className="space-y-3">
              <div className="space-y-1.5"><Label htmlFor="user-name">Nama</Label>
                <Input id="user-name" data-testid="user-form-name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="mis. Budi Santoso" /></div>
              <div className="space-y-1.5"><Label htmlFor="user-email">Email</Label>
                <Input id="user-email" data-testid="user-form-email" type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} placeholder="nama@sipro.co.id" /></div>
              <div className="space-y-1.5"><Label htmlFor="user-password">Kata Sandi</Label>
                <Input id="user-password" data-testid="user-form-password" type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} placeholder="minimal 8 karakter" /></div>
              <div className="space-y-1.5"><Label htmlFor="user-role">Peran</Label>
                <Select value={form.role} onValueChange={(v) => setForm({ ...form, role: v })}>
                  <SelectTrigger id="user-role" aria-label="Peran" data-testid="user-form-role"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {ROLES.map((r) => <SelectItem key={r} value={r}>{roleLabel(r)}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setOpen(false)}>Batal</Button>
              <Button onClick={create} disabled={saving}>{saving ? "Menyimpan..." : "Simpan"}</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      {loading ? <LoadingCards count={5} /> : error ? <ErrorState message={error} onRetry={load} /> :
        rows.length === 0 ? (
          <EmptyState icon={Users2} title="Belum ada pengguna" description="Tambahkan pengguna pertama untuk organisasi ini." actionLabel="Tambah Pengguna" onAction={() => setOpen(true)} />
        ) : (
        <div data-testid={ADMIN.usersTable} className="overflow-hidden rounded-xl border bg-card">
          <table className="w-full text-sm">
            <thead className="bg-secondary/60 text-left text-xs uppercase text-muted-foreground">
              <tr>
                <th className="px-4 py-2.5 font-medium">Nama</th>
                <th className="px-4 py-2.5 font-medium">Email</th>
                <th className="px-4 py-2.5 font-medium">Peran</th>
                <th className="px-4 py-2.5 font-medium">Status</th>
                <th className="px-4 py-2.5 font-medium text-right">Aksi</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {rows.map((u) => (
                <tr key={u.id} className="hover:bg-secondary/30">
                  <td className="px-4 py-2.5 font-medium">{u.name}</td>
                  <td className="px-4 py-2.5 font-mono text-xs text-muted-foreground">{u.email}</td>
                  <td className="px-4 py-2.5">
                    <span className="inline-flex items-center gap-1 rounded-full border bg-accent/50 px-2 py-0.5 text-xs">
                      <ShieldCheck className="h-3 w-3" /> {roleLabel(u.role)}
                    </span>
                  </td>
                  <td className="px-4 py-2.5">
                    <span className={`status-pill ${u.is_active ? "status-available" : "status-sold"}`}>
                      {u.is_active ? "Aktif" : "Nonaktif"}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-right">
                    <Button size="sm" variant="outline" onClick={() => toggleActive(u)}>
                      {u.is_active ? "Nonaktifkan" : "Aktifkan"}
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

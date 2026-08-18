import React, { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { Plus } from "lucide-react";

import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import api from "@/services/apiClient";
import { WORK } from "@/constants/testIds";
import { useReference } from "@/context/ReferenceContext";

/**
 * CreateTaskDialog — tugas ad-hoc dari supervisor.
 *
 * Endpoint `POST /api/work/tasks` sudah ada sejak fase awal tetapi TIDAK PERNAH dipakai UI,
 * sehingga supervisor tidak punya cara menugaskan pekerjaan di luar jobdesk otomatis.
 */
export default function CreateTaskDialog({ division, onDone }) {
  const { options } = useReference();
  const [open, setOpen] = useState(false);
  const [members, setMembers] = useState([]);
  const [form, setForm] = useState({
    title: "", description: "", type: "todo", priority: "medium", assigned_to: "", due: "",
  });
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    if (!division) return;
    try {
      const res = await api.get(`/work/divisions/${division}/members`);
      setMembers(res.data.data || []);
    } catch { /* biarkan kosong; penerima bisa dibiarkan default (diri sendiri) */ }
  }, [division]);

  useEffect(() => { if (open) load(); }, [open, load]);

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const submit = async () => {
    if (form.title.trim().length < 3) { toast.error("Judul tugas minimal 3 karakter."); return; }
    setBusy(true);
    try {
      await api.post("/work/tasks", {
        title: form.title.trim(), description: form.description || null,
        type: form.type, priority: form.priority,
        assigned_to: form.assigned_to || null,
        due_date: form.due ? new Date(form.due).toISOString() : null,
      });
      toast.success("Tugas dibuat.");
      setOpen(false);
      setForm({ title: "", description: "", type: "todo", priority: "medium", assigned_to: "", due: "" });
      onDone && onDone();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal membuat tugas.");
    } finally { setBusy(false); }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm" data-testid={WORK.createTaskBtn}>
          <Plus className="mr-1.5 h-4 w-4" /> Tugas Baru
        </Button>
      </DialogTrigger>
      <DialogContent className="bg-background">
        <DialogHeader>
          <DialogTitle>Tugas Baru</DialogTitle>
          <DialogDescription>
            Untuk pekerjaan di luar jobdesk otomatis. Penerima akan mendapat notifikasi.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="nt-title">Judul</Label>
            <Input id="nt-title" value={form.title} onChange={(e) => set("title", e.target.value)}
              placeholder="mis. Siapkan materi open house Sabtu" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label>Jenis</Label>
              <Select value={form.type} onValueChange={(v) => set("type", v)}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {options("task_type").map((o) => (
                    <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label>Prioritas</Label>
              <Select value={form.priority} onValueChange={(v) => set("priority", v)}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {options("priority").map((o) => (
                    <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="space-y-1.5">
            <Label>Penerima</Label>
            <Select value={form.assigned_to} onValueChange={(v) => set("assigned_to", v)}>
              <SelectTrigger><SelectValue placeholder="Saya sendiri" /></SelectTrigger>
              <SelectContent>
                {members.map((m) => (
                  <SelectItem key={m.email} value={m.email}>
                    {m.name} — {m.level === "supervisor" ? "Supervisor" : "Staf"}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="nt-due">Tenggat</Label>
            <Input id="nt-due" type="datetime-local" value={form.due}
              onChange={(e) => set("due", e.target.value)} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="nt-desc">Keterangan</Label>
            <Textarea id="nt-desc" rows={2} value={form.description}
              onChange={(e) => set("description", e.target.value)} />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)} disabled={busy}>Batal</Button>
          <Button data-testid={WORK.createTaskSubmit} onClick={submit} disabled={busy}>
            {busy ? "Menyimpan…" : "Buat Tugas"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

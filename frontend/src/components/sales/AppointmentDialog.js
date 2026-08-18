import React, { useState } from "react";
import { toast } from "sonner";

import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import api from "@/services/apiClient";
import { LEADS } from "@/constants/testIds";

/**
 * AppointmentDialog — penjadwalan survei/janji temu.
 *
 * Fase 40: diangkat keluar dari `LeadDetail` (drawer) agar bisa dipakai halaman kanonik
 * `/leads/:id` maupun tab Survey tanpa menyalin kode (dulu dialog ini terkubur di dalam
 * berkas drawer, jadi halaman lain tidak bisa memakainya).
 */
export default function AppointmentDialog({ leadId, open, onOpenChange, onDone }) {
  const [title, setTitle] = useState("Survey lokasi & unit");
  const [when, setWhen] = useState("");
  const [location, setLocation] = useState("Kantor pemasaran Cluster Asri");
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    if (!when) { toast.error("Tentukan waktu appointment."); return; }
    setBusy(true);
    try {
      await api.post("/appointments", {
        lead_id: leadId, title, scheduled_at: new Date(when).toISOString(),
        type: "survey", location,
      });
      toast.success("Appointment dijadwalkan.");
      onOpenChange(false);
      onDone && onDone();
    } catch (e) { toast.error(e?.response?.data?.detail || "Gagal menjadwalkan."); }
    finally { setBusy(false); }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="bg-background">
        <DialogHeader><DialogTitle>Jadwalkan Survey / Janji Temu</DialogTitle></DialogHeader>
        <div className="space-y-4">
          <div className="space-y-1.5"><Label htmlFor="appt-title">Judul</Label>
            <Input id="appt-title" data-testid={LEADS.apptTitle} value={title}
              onChange={(e) => setTitle(e.target.value)} /></div>
          <div className="space-y-1.5"><Label htmlFor="appt-when">Waktu</Label>
            <Input id="appt-when" data-testid={LEADS.apptWhen} type="datetime-local" value={when}
              onChange={(e) => setWhen(e.target.value)} /></div>
          <div className="space-y-1.5"><Label htmlFor="appt-loc">Lokasi</Label>
            <Input id="appt-loc" data-testid={LEADS.apptLocation} value={location}
              onChange={(e) => setLocation(e.target.value)} /></div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={busy}>Batal</Button>
          <Button data-testid={LEADS.apptSubmit} onClick={submit} disabled={busy}>
            {busy ? "Menyimpan..." : "Jadwalkan"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

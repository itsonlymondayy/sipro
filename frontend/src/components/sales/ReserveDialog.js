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
import api from "@/services/apiClient";
import { DEALS } from "@/constants/testIds";

// Flexible reserve dialog: byLead (pick a unit) or byUnit (pick a lead).
export default function ReserveDialog({
  mode = "byLead", leadId, leadName, unitId, unitLabel, open, onOpenChange, onReserved,
}) {
  const [options, setOptions] = useState([]);
  const [choice, setChoice] = useState("");
  const [fee, setFee] = useState("5000000");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!open) return;
    setChoice("");
    setFee("5000000");
    (async () => {
      try {
        if (mode === "byLead") {
          const res = await api.get("/units", { params: { status: "available", limit: 200 } });
          setOptions(res.data.data || []);
        } else {
          const res = await api.get("/leads", { params: { limit: 200 } });
          setOptions(res.data.data || []);
        }
      } catch { setOptions([]); }
    })();
  }, [open, mode]);

  const submit = async () => {
    const unit = mode === "byLead" ? choice : unitId;
    const lead = mode === "byLead" ? leadId : choice;
    if (!unit || !lead) { toast.error("Lengkapi pilihan terlebih dahulu."); return; }
    setBusy(true);
    try {
      const res = await api.post("/deals/reserve", {
        unit_id: unit, lead_id: lead, booking_fee: Number(fee) || 0,
      });
      toast.success("Unit berhasil di-reserve (hold aktif).");
      onOpenChange(false);
      onReserved && onReserved(res.data.data);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal membuat reservasi.");
    } finally { setBusy(false); }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Buat Reservasi (SPR)</DialogTitle>
          <DialogDescription>
            {mode === "byLead"
              ? `Pesan unit tersedia untuk lead: ${leadName || ""}`
              : `Pilih lead untuk unit: ${unitLabel || ""}`}
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <div className="space-y-1.5">
            <Label>{mode === "byLead" ? "Unit Tersedia" : "Lead"}</Label>
            <Select value={choice} onValueChange={setChoice}>
              <SelectTrigger data-testid="reserve-choice-select">
                <SelectValue placeholder={mode === "byLead" ? "Pilih unit" : "Pilih lead"} />
              </SelectTrigger>
              <SelectContent>
                {options.map((o) => (
                  <SelectItem key={o.id} value={o.id}>
                    {mode === "byLead"
                      ? `${o.code} · ${o.type} · ${formatIDR(o.price)}`
                      : `${o.name} · ${o.phone}`}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {mode === "byLead" && !options.length ? (
              <p className="text-xs text-muted-foreground">Tidak ada unit tersedia.</p>
            ) : null}
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="fee">Booking Fee (Rp)</Label>
            <Input id="fee" type="number" value={fee} onChange={(e) => setFee(e.target.value)} />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={busy}>Batal</Button>
          <Button data-testid={DEALS.reserveSubmit} onClick={submit} disabled={busy}>
            {busy ? "Memproses..." : "Reservasi"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

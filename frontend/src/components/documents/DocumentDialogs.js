import React, { useEffect, useState } from "react";
import { toast } from "sonner";

import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import api from "@/services/apiClient";
import { DOCS } from "@/constants/testIds";

/** Dialog “Buat SPR” — dipindahkan dari DocumentsPage agar halaman dokumen bisa jadi hub. */
export function CreateSprDialog({ open, onOpenChange, onDone }) {
  const [deals, setDeals] = useState([]);
  const [dealId, setDealId] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!open) return;
    setDealId("");
    (async () => {
      try {
        const res = await api.get("/deals", { params: { status: "reserved,booked", limit: 100 } });
        setDeals(res.data.data || []);
      } catch { setDeals([]); }
    })();
  }, [open]);

  const submit = async () => {
    if (!dealId) { toast.error("Pilih deal terlebih dahulu."); return; }
    setBusy(true);
    try {
      const res = await api.post("/documents", { template_code: "SPR", deal_id: dealId });
      toast.success(`SPR ${res.data.data.doc_number} dibuat (draft).`);
      onOpenChange(false);
      onDone && onDone();
    } catch (e) { toast.error(e?.response?.data?.detail || "Gagal membuat SPR."); }
    finally { setBusy(false); }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="bg-background">
        <DialogHeader>
          <DialogTitle>Buat SPR</DialogTitle>
          <DialogDescription>
            Pilih deal (reserved/booked) untuk membuat Surat Pemesanan Rumah.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-1.5">
          <Label htmlFor="spr-deal">Deal</Label>
          <Select value={dealId} onValueChange={setDealId}>
            <SelectTrigger id="spr-deal" data-testid="spr-deal-select" aria-label="Pilih deal">
              <SelectValue placeholder="Pilih deal" />
            </SelectTrigger>
            <SelectContent>
              {deals.map((d) => (
                <SelectItem key={d.id} value={d.id}>
                  {d.unit_code} · {d.lead_name} ({d.status})
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          {!deals.length ? (
            <p className="text-xs text-muted-foreground">Belum ada deal reserved/booked.</p>
          ) : null}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={busy}>Batal</Button>
          <Button onClick={submit} disabled={busy}>{busy ? "Memproses..." : "Buat SPR"}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/** Dialog tanda tangan dokumen. */
export function SignDialog({ doc, onOpenChange, onDone }) {
  const [role, setRole] = useState("buyer");
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const open = !!doc;

  useEffect(() => { if (open) { setRole("buyer"); setName(""); } }, [open]);

  const submit = async () => {
    if (!name.trim()) { toast.error("Nama penandatangan wajib diisi."); return; }
    setBusy(true);
    try {
      await api.post(`/documents/${doc.id}/sign`, { role, name });
      toast.success("Dokumen ditandatangani.");
      onOpenChange(false);
      onDone && onDone();
    } catch (e) { toast.error(e?.response?.data?.detail || "Gagal menandatangani."); }
    finally { setBusy(false); }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="bg-background">
        <DialogHeader>
          <DialogTitle>Tandatangani Dokumen</DialogTitle>
          <DialogDescription>{doc?.doc_number}</DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="sign-role">Peran</Label>
            <Select value={role} onValueChange={setRole}>
              <SelectTrigger id="sign-role" aria-label="Peran penandatangan">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="buyer">Pembeli</SelectItem>
                <SelectItem value="seller">Penjual</SelectItem>
                <SelectItem value="sales">Sales</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="signer">Nama Penandatangan</Label>
            <Input id="signer" value={name} onChange={(e) => setName(e.target.value)} />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={busy}>Batal</Button>
          <Button data-testid={DOCS.signSubmit} onClick={submit} disabled={busy}>
            {busy ? "Memproses..." : "Tandatangani"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

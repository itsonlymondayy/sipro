import React, { useEffect, useState } from "react";
import { toast } from "sonner";
import { AlertTriangle } from "lucide-react";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import ReferenceSelect from "@/components/patterns/ReferenceSelect";
import { formatIDR } from "@/utils/formatters";
import api from "@/services/apiClient";
import { FINANCE } from "@/constants/testIds";

/**
 * Terima pembayaran pembeli.
 *
 * Fase 26 (kebenaran uang): metode pembayaran diambil dari SSOT `/api/reference`
 * (dulu daftar lokal memuat nilai "other" yang tidak dikenal backend), dan bila jumlah
 * melebihi sisa tagihan, kasir HARUS menyetujui secara sadar bahwa kelebihannya dicatat
 * sebagai **titipan pelanggan** (akun 2-1450). Sebelumnya kelebihan bayar hilang tanpa jejak.
 *
 * deal: { deal_id, unit_code, outstanding }
 */
export default function ReceiptDialog({ open, onOpenChange, deal, onDone }) {
  const [amount, setAmount] = useState("");
  const [method, setMethod] = useState("transfer");
  const [note, setNote] = useState("");
  const [allowOverpay, setAllowOverpay] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (open) {
      setAmount(deal?.outstanding ? String(deal.outstanding) : "");
      setMethod("transfer");
      setNote("");
      setAllowOverpay(false);
    }
  }, [open, deal]);

  const outstanding = Number(deal?.outstanding || 0);
  const amt = Number(amount) || 0;
  const excess = Math.max(0, amt - outstanding);
  const blocked = excess > 0 && !allowOverpay;

  const submit = async () => {
    if (!deal?.deal_id) return;
    if (!amt || amt <= 0) { toast.error("Masukkan jumlah pembayaran yang valid."); return; }
    setBusy(true);
    try {
      const res = await api.post("/finance/ar/receipts", {
        deal_id: deal.deal_id, amount: amt, method, note: note || null,
        allow_overpay: allowOverpay,
      });
      const rec = res.data?.data?.receipt || {};
      const dep = Number(rec.deposit_amount || 0);
      toast.success(
        dep > 0
          ? `Pembayaran diterima — ${formatIDR(dep)} dicatat sebagai titipan pelanggan.`
          : res.data?.data?.paid_off
            ? "Pembayaran diterima — AR LUNAS. Menunggu BAST."
            : "Pembayaran diterima & dialokasikan ke termin.");
      onOpenChange(false);
      onDone && onDone();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal mencatat pembayaran.");
    } finally { setBusy(false); }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Terima Pembayaran</DialogTitle>
          <DialogDescription>
            {deal ? `Unit ${deal.unit_code || "-"} · Sisa ${formatIDR(outstanding)}` : ""}
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="amt">Jumlah (Rp)</Label>
            <Input id="amt" type="number" value={amount} data-testid="ar-receipt-amount"
              onChange={(e) => setAmount(e.target.value)} placeholder="0" />
          </div>
          <div className="space-y-1.5">
            <Label>Metode</Label>
            <ReferenceSelect group="payment_method" value={method} onChange={setMethod}
              testId="ar-receipt-method" />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="note">Catatan (opsional)</Label>
            <Textarea id="note" value={note} onChange={(e) => setNote(e.target.value)}
              placeholder="mis. DP 20%, cicilan termin I" rows={2} />
          </div>

          {excess > 0 ? (
            <div data-testid="ar-receipt-overpay-warning"
              className="space-y-2 rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
              <p className="flex items-start gap-2 font-medium">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                Jumlah melebihi sisa tagihan {formatIDR(outstanding)}.
              </p>
              <p className="text-[12px] leading-relaxed">
                Kelebihan <span className="font-semibold tabular-nums">{formatIDR(excess)}</span> akan
                dicatat sebagai <span className="font-semibold">Titipan Pelanggan</span> (akun 2-1450),
                bukan pendapatan — nanti bisa dipakai untuk termin berikutnya atau dikembalikan.
              </p>
              <label className="flex items-start gap-2 text-[12px] font-medium">
                <Checkbox data-testid="ar-receipt-allow-overpay" checked={allowOverpay}
                  onCheckedChange={(v) => setAllowOverpay(!!v)} className="mt-0.5" />
                <span>Ya, saya memang menerima kelebihan ini dan mencatatnya sebagai titipan.</span>
              </label>
            </div>
          ) : null}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={busy}>Batal</Button>
          <Button data-testid={FINANCE.receiptSubmit} onClick={submit} disabled={busy || blocked}>
            {busy ? "Memproses…" : blocked ? "Centang persetujuan dulu" : "Simpan Pembayaran"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

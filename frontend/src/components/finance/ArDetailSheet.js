import React, { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { HandCoins, FileCheck2 } from "lucide-react";
import {
  Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription,
} from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import StatusPill from "@/components/patterns/StatusPill";
import { LoadingCards, ErrorState } from "@/components/patterns/StateViews";
import ReceiptDialog from "@/components/finance/ReceiptDialog";
import { useReference } from "@/context/ReferenceContext";
import { formatIDR, formatDateWIB } from "@/utils/formatters";
import api from "@/services/apiClient";
import { FINANCE } from "@/constants/testIds";

function Stat({ label, value, tone = "" }) {
  return (
    <div className="rounded-xl border bg-card p-3">
      <p className="text-[11px] text-muted-foreground">{label}</p>
      <p className={`mt-0.5 text-sm font-semibold tabular-nums ${tone}`}>{value}</p>
    </div>
  );
}

export default function ArDetailSheet({ dealId, open, onOpenChange, onChanged }) {
  const { labelOf } = useReference();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [schemes, setSchemes] = useState([]);
  const [schemeId, setSchemeId] = useState("");
  const [busy, setBusy] = useState(false);
  const [receiptOpen, setReceiptOpen] = useState(false);

  const load = useCallback(async () => {
    if (!dealId) return;
    setLoading(true); setError("");
    try {
      const [res, sc] = await Promise.all([
        api.get(`/finance/ar/${dealId}`),
        api.get("/finance/config/payment-schemes"),
      ]);
      setData({
        invoice: res.data.data,
        receipts: res.data.receipts || [],
        liability: res.data.contract_liability,
        revrec: res.data.revenue_recognition,
        deposit: res.data.deposit || null,
      });
      setSchemes(sc.data.data || []);
    } catch (e) {
      setError(e?.response?.data?.detail || "Gagal memuat detail AR.");
    } finally { setLoading(false); }
  }, [dealId]);

  useEffect(() => { if (open) load(); }, [open, load]);

  const changeScheme = async () => {
    if (!schemeId) { toast.error("Pilih skema pembayaran terlebih dahulu."); return; }
    setBusy(true);
    try {
      await api.post(`/finance/ar/${dealId}/schedule`, { scheme_id: schemeId });
      toast.success("Skema pembayaran diperbarui & jadwal termin dibuat ulang.");
      setSchemeId(""); load(); onChanged && onChanged();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal mengganti skema.");
    } finally { setBusy(false); }
  };

  const bast = async () => {
    setBusy(true);
    try {
      await api.post(`/finance/ar/${dealId}/bast`, {});
      toast.success("BAST dicatat \u2014 pendapatan diakui (PSAK 72), kewajiban kontrak dinolkan.");
      load(); onChanged && onChanged();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal mencatat BAST.");
    } finally { setBusy(false); }
  };

  const inv = data?.invoice;
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent data-testid={FINANCE.arDetail} className="w-full overflow-y-auto sm:max-w-xl">
        <SheetHeader>
          <SheetTitle>Detail Piutang (AR)</SheetTitle>
          <SheetDescription>
            {inv ? `${inv.unit_code || "Unit"} \u00b7 ${inv.lead_name || "Pembeli"}` : "Memuat\u2026"}
          </SheetDescription>
        </SheetHeader>

        {loading ? (
          <div className="mt-4"><LoadingCards count={3} /></div>
        ) : error ? (
          <div className="mt-4"><ErrorState message={error} onRetry={load} /></div>
        ) : inv ? (
          <div className="mt-4 space-y-5">
            <div className="grid grid-cols-3 gap-3">
              <Stat label="Total" value={formatIDR(inv.total)} />
              <Stat label="Terbayar" value={formatIDR(inv.paid)} tone="text-emerald-700" />
              <Stat label="Sisa" value={formatIDR(inv.outstanding)} tone="text-amber-700" />
            </div>

            <div className="flex flex-wrap items-center gap-3 text-sm">
              <StatusPill status={inv.status} group="ar_status" />
              <span className="text-muted-foreground">
                Kewajiban kontrak: <span className="font-medium tabular-nums text-foreground">{formatIDR(data.liability?.balance || 0)}</span>
              </span>
            </div>

            {data.deposit && Number(data.deposit.balance || 0) > 0 ? (
              <div data-testid={FINANCE.arDepositSection}
                className="rounded-lg border border-indigo-200 bg-indigo-50 p-3 text-sm text-indigo-900">
                <p className="font-medium">
                  Titipan pelanggan: <span className="tabular-nums">{formatIDR(data.deposit.balance)}</span>
                </p>
                <p className="mt-0.5 text-[12px] leading-relaxed">
                  Kelebihan bayar / setoran di muka yang belum dialokasikan (akun 2-1450). Kelola di
                  tab <span className="font-semibold">Titipan</span>: bisa dipakai untuk termin berikutnya
                  atau dikembalikan ke pembeli.
                </p>
              </div>
            ) : null}

            {data.revrec ? (
              <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">
                <p className="font-medium">Pendapatan diakui (BAST)</p>
                <p className="tabular-nums">Pendapatan {formatIDR(data.revrec.revenue)} · Margin {formatIDR(data.revrec.margin)}</p>
              </div>
            ) : null}

            <div className="flex flex-wrap gap-2">
              {inv.outstanding > 0 ? (
                <Button data-testid={FINANCE.receiptBtn} onClick={() => setReceiptOpen(true)}>
                  <HandCoins className="mr-1.5 h-4 w-4" /> Terima Pembayaran
                </Button>
              ) : null}
              {inv.status === "paid" && !data.revrec ? (
                <Button data-testid={FINANCE.bastBtn} onClick={bast} disabled={busy}>
                  <FileCheck2 className="mr-1.5 h-4 w-4" /> BAST / Akui Pendapatan
                </Button>
              ) : null}
            </div>

            <div>
              <h4 className="font-heading text-sm font-semibold">Jadwal Termin</h4>
              <div className="mt-2 space-y-2">
                {(inv.items || []).map((it) => (
                  <div key={it.id} className="flex items-center justify-between rounded-lg border bg-card p-2.5 text-sm">
                    <div>
                      <p className="font-medium">{it.label}</p>
                      <p className="text-[11px] text-muted-foreground">Jatuh tempo {formatDateWIB(it.due_date)}</p>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="tabular-nums">{formatIDR(it.amount)}</span>
                      <StatusPill status={it.status} group="ar_status" />
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="rounded-lg border bg-card p-3">
              <h4 className="font-heading text-sm font-semibold">Ganti Skema Pembayaran</h4>
              <div className="mt-2 flex gap-2">
                <Select value={schemeId} onValueChange={setSchemeId}>
                  <SelectTrigger data-testid={FINANCE.schemeSelect} className="flex-1">
                    <SelectValue placeholder="Pilih skema" />
                  </SelectTrigger>
                  <SelectContent>
                    {schemes.map((s) => (
                      <SelectItem key={s.id} value={s.id}>{s.name}{s.is_default ? " (default)" : ""}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Button variant="outline" data-testid={FINANCE.schemeChangeBtn} onClick={changeScheme} disabled={busy}>
                  Terapkan
                </Button>
              </div>
              <p className="mt-1 text-[11px] text-muted-foreground">
                Membuat ulang jadwal termin. Pembayaran yang sudah tercatat tetap tersimpan sebagai riwayat receipt.
              </p>
            </div>

            <div>
              <h4 className="font-heading text-sm font-semibold">Riwayat Pembayaran</h4>
              {!data.receipts.length ? (
                <p className="mt-2 text-sm text-muted-foreground">Belum ada pembayaran.</p>
              ) : (
                <div className="mt-2 space-y-2">
                  {data.receipts.map((rc) => (
                    <div key={rc.id} className="flex items-center justify-between rounded-lg border bg-card p-2.5 text-sm">
                      <div>
                        <p className="font-medium tabular-nums">{formatIDR(rc.applied)}
                          {Number(rc.deposit_amount || 0) > 0 ? (
                            <span className="ml-1.5 text-[11px] font-normal text-indigo-700">
                              + {formatIDR(rc.deposit_amount)} titipan
                            </span>
                          ) : null}
                        </p>
                        <p className="text-[11px] text-muted-foreground">
                          {rc.funding === "deposit" ? "Dari titipan" : labelOf("payment_method", rc.method)}
                          {" · "}{formatDateWIB(rc.created_at)}
                        </p>
                      </div>
                      <p className="max-w-[45%] truncate text-[11px] text-muted-foreground">{rc.note || ""}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        ) : null}

        <ReceiptDialog open={receiptOpen} onOpenChange={setReceiptOpen}
          deal={inv ? { deal_id: inv.deal_id, unit_code: inv.unit_code, outstanding: inv.outstanding } : null}
          onDone={() => { load(); onChanged && onChanged(); }} />
      </SheetContent>
    </Sheet>
  );
}

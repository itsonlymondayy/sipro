import React, { useEffect, useState } from "react";
import StatusPill from "@/components/patterns/StatusPill";
import { LoadingCards, ErrorState } from "@/components/patterns/StateViews";
import { formatIDR, formatDateWIB } from "@/utils/formatters";
import portalApi from "@/services/portalClient";
import { PORTAL } from "@/constants/testIds";

export default function PaymentsPanel() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = async () => {
    setLoading(true); setError("");
    try {
      const res = await portalApi.get("/portal/payments");
      setData(res.data.data || []);
    } catch (e) {
      setError(e?.response?.data?.detail || "Gagal memuat pembayaran.");
    } finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  if (loading) return <LoadingCards count={3} />;
  if (error) return <ErrorState message={error} onRetry={load} />;
  if (!data?.length) return <p className="rounded-xl border bg-white p-6 text-center text-sm text-slate-500">Belum ada tagihan.</p>;

  return (
    <div data-testid={PORTAL.paymentsPanel} className="space-y-6">
      {data.map((p) => (
        <div key={p.deal_id} className="space-y-3">
          <div className="grid grid-cols-3 gap-3">
            <div className="rounded-xl border bg-white p-4"><p className="text-xs text-slate-500">Total Harga</p><p className="mt-1 text-base font-semibold tabular-nums">{formatIDR(p.summary?.total)}</p></div>
            <div className="rounded-xl border bg-white p-4"><p className="text-xs text-slate-500">Sudah Dibayar</p><p className="mt-1 text-base font-semibold tabular-nums text-emerald-600">{formatIDR(p.summary?.paid)}</p></div>
            <div className="rounded-xl border bg-white p-4"><p className="text-xs text-slate-500">Sisa</p><p className="mt-1 text-base font-semibold tabular-nums text-rose-600">{formatIDR(p.summary?.outstanding)}</p></div>
          </div>

          <div className="rounded-xl border bg-white">
            <div className="border-b px-4 py-2.5 text-sm font-semibold">Jadwal Pembayaran (Termin)</div>
            <div className="divide-y">
              {(p.schedule || []).map((s) => (
                <div key={s.id} data-testid={PORTAL.paymentRow} className="flex items-center justify-between px-4 py-2.5 text-sm">
                  <div>
                    <p className="font-medium">{s.label}</p>
                    <p className="text-xs text-slate-400">Jatuh tempo {formatDateWIB(s.due_date)}</p>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="tabular-nums">{formatIDR(s.amount)}</span>
                    <StatusPill status={s.status} label={s.status === "paid" ? "Lunas" : s.status === "partial" ? "Sebagian" : "Belum"} />
                  </div>
                </div>
              ))}
            </div>
          </div>

          {(p.receipts || []).length > 0 && (
            <div className="rounded-xl border bg-white">
              <div className="border-b px-4 py-2.5 text-sm font-semibold">Riwayat Penerimaan</div>
              <div className="divide-y">
                {p.receipts.map((r) => (
                  <div key={r.id} className="flex items-center justify-between px-4 py-2.5 text-sm">
                    <span className="text-slate-500">{formatDateWIB(r.created_at)} · {r.method || "transfer"}</span>
                    <span className="tabular-nums text-emerald-600">{formatIDR(r.amount)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

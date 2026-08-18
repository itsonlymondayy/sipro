import React, { useCallback, useEffect, useState } from "react";
import MetricCard from "@/components/patterns/MetricCard";
import { LoadingKpis, ErrorState } from "@/components/patterns/StateViews";
import AgingBuckets from "@/components/finance/AgingBuckets";
import { formatIDR } from "@/utils/formatters";
import api from "@/services/apiClient";
import { FINANCE } from "@/constants/testIds";

export default function FinanceDashboard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true); setError("");
    try {
      const res = await api.get("/finance/summary");
      setData(res.data.data);
    } catch (e) {
      setError(e?.response?.data?.detail || "Gagal memuat ringkasan keuangan.");
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  if (loading) return <LoadingKpis count={5} />;
  if (error) return <ErrorState message={error} onRetry={load} />;
  if (!data) return null;

  const c = data.counts || {};
  return (
    <div data-testid={FINANCE.dashboard} className="space-y-6">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-6">
        <MetricCard label="Piutang (AR) Outstanding" value={data.ar_outstanding} tone="primary"
          format="idr" hint={`DSO ~${data.ar_dso} hari \u00b7 ${c.ar_invoices || 0} invoice`} />
        <MetricCard label="AR Jatuh Tempo" value={data.ar_overdue} tone="rose"
          format="idr" hint="Melewati tanggal termin" />
        <MetricCard label="Utang (AP) Outstanding" value={data.ap_outstanding} tone="amber"
          format="idr" hint={`${c.ap_pending || 0} menunggu approval`} />
        <MetricCard label="Kewajiban Kontrak" value={data.contract_liability} tone="indigo"
          format="idr" hint="Diterima sebelum BAST (PSAK 72)" />
        <MetricCard label="Titipan Pelanggan" value={data.customer_deposits || 0} tone="indigo"
          format="idr" hint="Kelebihan bayar / setoran di muka (2-1450)" />
        <MetricCard label="Pendapatan Diakui" value={data.revenue_recognized} tone="emerald"
          format="idr" hint="Point-in-time saat BAST" />
      </div>

      <div className="space-y-3">
        <h3 className="font-heading text-sm font-semibold">Aging Piutang (AR)</h3>
        <AgingBuckets buckets={data.ar_buckets} />
      </div>

      <div className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="font-heading text-sm font-semibold">Aging Utang (AP)</h3>
          <p className="text-xs text-muted-foreground">
            Retensi ditahan: <span className="font-medium tabular-nums text-foreground">{formatIDR(data.ap_retention_held)}</span>
          </p>
        </div>
        <AgingBuckets buckets={data.ap_buckets} />
      </div>

      <p className="text-[11px] italic text-muted-foreground">{data.worksheet_note}</p>
    </div>
  );
}

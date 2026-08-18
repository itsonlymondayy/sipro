import React, { useMemo, useState } from "react";
import { BarChart3, Boxes, LineChart, Megaphone, Users2, BookOpen } from "lucide-react";

import TabPage from "@/components/patterns/TabPage";
import EmptyState from "@/components/patterns/EmptyState";
import ReferenceSelect from "@/components/patterns/ReferenceSelect";
import MetricDictionaryTab from "@/components/bi/MetricDictionaryTab";
import {
  ExecutiveDashboard, MarketingDashboard, ProjectCostDashboard, SalesLeadDashboard, TeamDashboard,
} from "@/components/bi/dashboards";
import { useAuth } from "@/context/AuthContext";
import { useReference } from "@/context/ReferenceContext";
import { BI } from "@/constants/testIds";

/**
 * BiPage (`/bi`) — hub **Analitik & BI** (Fase 44, acuan `docs/v2/31_ANALYTICS_BI_SPEC.md`).
 *
 * Menu ini terakhir yang berstatus “Segera Hadir”. Sebelumnya setiap pertanyaan manajemen
 * dijawab dengan mengekspor tabel lalu menghitung di spreadsheet pribadi — dan setiap orang
 * membawa angka yang sedikit berbeda ke rapat. Sekarang: lima dashboard persona, satu kamus
 * metrik, dan satu aturan yang tidak bisa dilanggar layar — angka yang datanya belum ada
 * ditulis “belum ada data”, bukan 0.
 *
 * Rentang waktu tinggal di URL (`?period=`) supaya “lihat 90 hari terakhir” bisa dibagikan.
 */
export default function BiPage() {
  const { can } = useAuth();
  const { labelOf } = useReference();
  const canView = can("analytics", "view");
  const [period, setPeriod] = useState("30d");
  const params = useMemo(() => ({ period }), [period]);

  const header = (
    <div className="flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="font-heading text-2xl font-semibold tracking-tight">Analitik & BI</h1>
        <p className="max-w-3xl text-sm text-muted-foreground">
          Lima dashboard untuk lima pertanyaan yang berbeda, semuanya dihitung dari data
          operasional yang sama — bukan hitungan kedua. Setiap angka membawa
          <strong> status kelengkapan</strong>, <strong>rumusnya</strong>, dan
          <strong> tautan ke daftar barisnya</strong>.
        </p>
      </div>
      <div className="w-48">
        <ReferenceSelect group="analytics_period" value={period} onChange={setPeriod}
          testId={BI.period} placeholder="Rentang…" />
      </div>
    </div>
  );

  if (!canView) {
    return (
      <div data-testid={BI.page} className="space-y-4">
        {header}
        <EmptyState icon={BarChart3} title="Anda tidak punya akses ke Analitik & BI"
          description="Peran Anda tidak diberi izin melihat metrik. Hubungi admin bila memang
            perlu — halaman ini sengaja tidak menampilkan tabel kosong yang seolah-olah
            datanya tidak ada." />
      </div>
    );
  }

  return (
    <div data-testid={BI.page} className="space-y-4">
      {/* Nama tab = label SSOT `metric_persona`, BUKAN teks yang diketik ulang di sini:
          nama dashboard juga dipakai kamus metrik & jawaban API, jadi menuliskannya dua kali
          membuat "Kinerja Tim" di tab bisa berbeda dengan "Kinerja Tim" di kamus. */}
      <TabPage paramKey="hub" testId={BI.hubTab} header={header} tabs={[
        { key: "eksekutif", label: labelOf("metric_persona", "eksekutif"), icon: LineChart,
          content: <ExecutiveDashboard params={params} /> },
        { key: "penjualan", label: labelOf("metric_persona", "penjualan"), icon: Users2,
          content: <SalesLeadDashboard params={params} /> },
        { key: "marketing", label: labelOf("metric_persona", "marketing"), icon: Megaphone,
          content: <MarketingDashboard params={params} /> },
        { key: "proyek", label: labelOf("metric_persona", "proyek"), icon: Boxes,
          content: <ProjectCostDashboard params={params} /> },
        { key: "tim", label: labelOf("metric_persona", "tim"), icon: BarChart3,
          content: <TeamDashboard params={params} /> },
        { key: "kamus", label: "Kamus Metrik", icon: BookOpen,
          content: <MetricDictionaryTab /> },
      ]} />
    </div>
  );
}

import React, { useMemo } from "react";
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, Pie, PieChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";

import ChartFrame from "@/components/patterns/ChartFrame";
import { legendLabel } from "@/utils/chartUi";
import { formatMetric } from "@/components/bi/MetricValue";
import { formatNumber } from "@/utils/formatters";
import { BI } from "@/constants/testIds";

/**
 * MetricChart — grafik dipilih dari PERTANYAANNYA, bukan dari selera (Dok 31 §8):
 *   deret waktu kumulatif  → area (mis. unit terjual)
 *   deret waktu biasa      → garis
 *   perbandingan kategori  → bar horizontal (label terbaca, tanpa memiringkan teks)
 *   komposisi (≤6 irisan)  → donut, sisanya digabung “lainnya”
 * Tanpa 3D, tanpa animasi berlebihan, maksimal satu sumbu nilai — dan setiap grafik bisa
 * diunduh datanya (ChartFrame) supaya orang tidak perlu “membaca piksel”.
 */
const COLORS = ["#2563eb", "#0d9488", "#f59e0b", "#e11d48", "#7c3aed", "#64748b"];
const MAX_SLICES = 6;

function sliceForPie(rows) {
  // `rows` sudah disaring dari nilai kosong sebelum masuk sini, jadi TIDAK ADA fallback
  // `|| 0` — fallback semacam itu akan mengubah "belum ada data" menjadi irisan bernilai nol
  // yang terlihat seperti fakta.
  const sorted = [...rows].sort((a, b) => b.value - a.value);
  if (sorted.length <= MAX_SLICES) return sorted;
  const head = sorted.slice(0, MAX_SLICES - 1);
  const rest = sorted.slice(MAX_SLICES - 1);
  return [...head, {
    key: "lainnya", label: "Lainnya",
    value: rest.reduce((sum, r) => sum + Number(r.value), 0),
  }];
}

export default function MetricChart({ metric, kind = "auto", title, description, height }) {
  const rows = useMemo(() => {
    if (!metric) return [];
    if (kind === "series" || (kind === "auto" && (metric.series || []).length)) {
      return (metric.series || []).map((s) => ({ ...s, label: s.bucket }));
    }
    return (metric.breakdown || []).filter((r) => r && r.value !== null && r.value !== undefined);
  }, [metric, kind]);
  const isSeries = kind === "series" || (kind === "auto" && (metric?.series || []).length > 0);
  const cumulative = isSeries && rows.some((r) => r.cumulative !== undefined);
  const csvColumns = isSeries
    ? [{ key: "bucket", header: "Periode" }, { key: "value", header: metric?.label || "Nilai" },
       ...(cumulative ? [{ key: "cumulative", header: "Kumulatif" }] : [])]
    : [{ key: "label", header: "Kategori" }, { key: "value", header: metric?.label || "Nilai" }];
  const tip = (value) => formatMetric(value, metric?.unit) ?? formatNumber(value);

  return (
    <ChartFrame testId={BI.chart} title={title || metric?.label || "Grafik"}
      description={description || metric?.formula} rows={rows} csvColumns={csvColumns}
      csvName={`bi-${(metric?.code || "metrik").toLowerCase()}`} height={height}
      emptyText={metric?.state === "kosong"
        ? (metric?.note || "Data untuk metrik ini belum ada — grafik sengaja tidak digambar.")
        : "Belum ada rincian untuk digambarkan."}>
      <ResponsiveContainer width="100%" height="100%">
        {kind === "pie" ? (
          <PieChart>
            <Pie data={sliceForPie(rows)} dataKey="value" nameKey="label" innerRadius="45%"
              outerRadius="75%" paddingAngle={2}>
              {sliceForPie(rows).map((row, i) => (
                <Cell key={row.key || i} fill={COLORS[i % COLORS.length]} />
              ))}
            </Pie>
            <Tooltip formatter={(v, n) => [tip(v), n]} />
            <Legend wrapperStyle={{ fontSize: 12 }} formatter={legendLabel} />
          </PieChart>
        ) : cumulative ? (
          <AreaChart data={rows}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="bucket" tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} width={70}
              tickFormatter={(v) => formatNumber(v)} />
            <Tooltip formatter={(v, n) => [tip(v), n === "cumulative" ? "Kumulatif" : "Periode"]} />
            <Area type="monotone" dataKey="cumulative" stroke={COLORS[0]} fill={COLORS[0]}
              fillOpacity={0.18} strokeWidth={2} />
          </AreaChart>
        ) : isSeries ? (
          <LineChart data={rows}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="bucket" tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} width={70} tickFormatter={(v) => formatNumber(v)} />
            <Tooltip formatter={(v) => tip(v)} />
            <Line type="monotone" dataKey="value" stroke={COLORS[1]} strokeWidth={2} dot />
          </LineChart>
        ) : (
          <BarChart data={rows} layout="vertical" margin={{ left: 8, right: 16 }}>
            <CartesianGrid strokeDasharray="3 3" horizontal={false} />
            <XAxis type="number" tick={{ fontSize: 11 }} tickFormatter={(v) => formatNumber(v)} />
            <YAxis type="category" dataKey="label" tick={{ fontSize: 11 }} width={150} />
            <Tooltip formatter={(v) => tip(v)} />
            <Bar dataKey="value" fill={COLORS[0]} radius={[0, 4, 4, 0]} />
          </BarChart>
        )}
      </ResponsiveContainer>
    </ChartFrame>
  );
}

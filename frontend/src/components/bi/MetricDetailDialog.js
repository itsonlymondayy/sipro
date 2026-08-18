import React from "react";
import { Download } from "lucide-react";

import {
  Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { MetricNote, MetricStateBadge, formatMetric } from "@/components/bi/MetricValue";
import { formatNumber } from "@/utils/formatters";
import { BI } from "@/constants/testIds";

const BACKEND = process.env.REACT_APP_BACKEND_URL;

/**
 * MetricDetailDialog — rincian satu metrik: bahan mentahnya (`inputs`) + pecahannya
 * (`breakdown`) + tombol ekspor CSV yang mengambil dari server (bukan menyalin tampilan).
 *
 * Ini bagian dari janji “angka bisa dihitung ulang tangan”: pembaca bisa melihat pembilang &
 * penyebutnya, bukan hanya hasil akhirnya.
 */
export default function MetricDetailDialog({ metric, open, onOpenChange, range }) {
  if (!metric) return null;
  const rows = metric.breakdown || [];
  const keys = Array.from(rows.reduce((set, row) => {
    Object.keys(row || {}).forEach((k) => set.add(k));
    return set;
  }, new Set()));
  const exportUrl = `${BACKEND}/api/analytics/export/${encodeURIComponent(metric.code)}`
    + (range?.from ? `?date_from=${range.from}&date_to=${range.to}` : "");

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent data-testid={BI.detailDialog}
        className="max-h-[85vh] max-w-3xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex flex-wrap items-center gap-2">
            {metric.label}
            <span className="text-xs font-normal text-muted-foreground">{metric.code}</span>
            <MetricStateBadge state={metric.state} coverage={metric.coverage} />
          </DialogTitle>
          <DialogDescription>
            {metric.formula ? `Rumus: ${metric.formula}` : "Rincian angka"}
            {range?.from ? ` · rentang ${range.from} → ${range.to}` : ""}
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border bg-secondary/40 p-2.5">
            <p className="text-sm">
              Nilai: <strong>{formatMetric(metric.value, metric.unit) ?? "belum ada data"}</strong>
            </p>
            <Button size="sm" variant="outline" asChild data-testid={BI.detailExport}>
              <a href={exportUrl} target="_blank" rel="noreferrer">
                <Download className="mr-1.5 h-3.5 w-3.5" /> Ekspor CSV
              </a>
            </Button>
          </div>
          <MetricNote metric={metric} />
          {Object.keys(metric.inputs || {}).length ? (
            <div className="rounded-lg border p-2.5">
              <p className="mb-1.5 text-xs font-semibold uppercase text-muted-foreground">
                Bahan perhitungan
              </p>
              <dl className="grid gap-1 text-xs sm:grid-cols-2">
                {Object.entries(metric.inputs).map(([k, v]) => (
                  <div key={k} className="flex justify-between gap-2 border-b border-dashed py-0.5">
                    <dt className="text-muted-foreground">{k}</dt>
                    <dd className="text-right tabular-nums">
                      {typeof v === "object" ? JSON.stringify(v) : String(v)}
                    </dd>
                  </div>
                ))}
              </dl>
            </div>
          ) : null}
          {rows.length ? (
            <div data-testid={BI.detailTable}
              className="overflow-x-auto rounded-lg border bg-card">
              <table className="w-full text-sm">
                <thead className="bg-muted/50 text-xs uppercase text-muted-foreground">
                  <tr>{keys.map((k) => (
                    <th key={k} className="px-2.5 py-2 text-left">{k}</th>
                  ))}</tr>
                </thead>
                <tbody>
                  {rows.map((row, i) => (
                    <tr key={row.key || i} data-testid={BI.detailRow} className="border-t">
                      {keys.map((k) => (
                        <td key={k} className="px-2.5 py-1.5">
                          {row[k] === null || row[k] === undefined ? (
                            <span className="text-xs italic text-muted-foreground">
                              belum ada data
                            </span>
                          ) : typeof row[k] === "object" ? JSON.stringify(row[k])
                            : typeof row[k] === "number" ? formatNumber(row[k])
                              : String(row[k])}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">
              Metrik ini belum punya rincian untuk ditampilkan.
            </p>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}

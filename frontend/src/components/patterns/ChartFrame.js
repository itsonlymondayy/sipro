import React from "react";
import { Download } from "lucide-react";

import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/patterns/StateViews";
import { downloadCsv } from "@/utils/tableCsv";
import { cn } from "@/lib/utils";
import { CHART } from "@/constants/testIds";

/**
 * ChartFrame — bingkai standar grafik: judul, keterangan, state kosong/galat yang jujur,
 * dan unduh data mentahnya.
 *
 * Kenapa unduh data: grafik tanpa akses ke angkanya memaksa pemakai “membaca” piksel.
 * Kolom unduhan dideskripsikan pemanggil (`csvColumns`) agar isinya sama dengan yang dilihat.
 */
export default function ChartFrame({
  title, description, children, rows = [], csvColumns = null, csvName = "grafik",
  loading = false, error = "", onRetry, emptyText = "Belum ada data untuk digambarkan.",
  className, testId, actions = null, height = "h-64",
}) {
  const isEmpty = !loading && !error && (!rows || rows.length === 0);
  return (
    <section data-testid={testId || CHART.frame}
      className={cn("rounded-lg border bg-card p-4", className)}>
      <div className="mb-3 flex flex-wrap items-start justify-between gap-2">
        <div>
          <h3 data-testid={CHART.title} className="font-heading text-base font-semibold">
            {title}
          </h3>
          {description ? (
            <p className="text-xs text-muted-foreground">{description}</p>
          ) : null}
        </div>
        <div className="flex items-center gap-2">
          {actions}
          {csvColumns && rows?.length ? (
            <Button size="sm" variant="outline" data-testid={CHART.download}
              onClick={() => downloadCsv(csvColumns, rows, csvName)}>
              <Download className="mr-1.5 h-3.5 w-3.5" /> Data
            </Button>
          ) : null}
        </div>
      </div>
      {error ? <ErrorState message={error} onRetry={onRetry} /> : null}
      {loading ? (
        <div className={cn("animate-pulse rounded-md bg-secondary", height)} />
      ) : null}
      {isEmpty ? (
        <p data-testid={CHART.empty}
          className="rounded-md border border-dashed bg-secondary/40 p-6 text-center text-sm text-muted-foreground">
          {emptyText}
        </p>
      ) : null}
      {!loading && !error && !isEmpty ? children : null}
    </section>
  );
}

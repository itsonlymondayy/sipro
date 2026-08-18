import React from "react";
import { Link } from "react-router-dom";
import { ArrowUpRight, Sigma } from "lucide-react";

import { cn } from "@/lib/utils";
import { MetricNote, MetricStateBadge, MetricValue } from "@/components/bi/MetricValue";
import { BI } from "@/constants/testIds";

/**
 * MetricCard — satu angka BI yang MENJELASKAN DIRINYA SENDIRI.
 *
 * Isinya bukan cuma angka: ada status kelengkapan, rumusnya (bisa dibaca tanpa membuka
 * dokumen), tautan drill-down ke daftar barisnya (blueprint: KPI tanpa drill = belum selesai),
 * dan tombol “rincian” untuk melihat pecahannya. Tujuannya satu: angka di layar bisa
 * diperdebatkan dengan data, bukan dipercaya buta.
 */
export default function MetricCard({ metric, onDetail, className }) {
  if (!metric) return null;
  const hasBreakdown = (metric.breakdown || []).length > 0;
  return (
    <div data-testid={BI.card} data-code={metric.code} data-state={metric.state}
      className={cn("flex flex-col gap-2 rounded-lg border bg-card p-3", className)}>
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="truncate text-xs font-medium uppercase tracking-wide text-muted-foreground">
            {metric.label}
          </p>
          <p className="text-[10px] text-muted-foreground/70">{metric.code}</p>
        </div>
        <MetricStateBadge state={metric.state} coverage={metric.coverage} />
      </div>
      <MetricValue metric={metric} />
      <MetricNote metric={metric} />
      {metric.formula ? (
        <p data-testid={BI.cardFormula}
          className="flex items-start gap-1 text-[11px] text-muted-foreground">
          <Sigma className="mt-0.5 h-3 w-3 shrink-0" />
          <span className="break-words">{metric.formula}</span>
        </p>
      ) : null}
      <div className="mt-auto flex items-center justify-between gap-2 pt-1">
        {metric.drill ? (
          <Link to={metric.drill} data-testid={BI.cardDrill} data-drill={metric.code}
            className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline">
            Lihat daftar <ArrowUpRight className="h-3 w-3" />
          </Link>
        ) : <span />}
        {hasBreakdown && onDetail ? (
          <button type="button" onClick={() => onDetail(metric)}
            className="text-xs font-medium text-muted-foreground hover:text-foreground hover:underline">
            Rincian ({metric.breakdown.length})
          </button>
        ) : null}
      </div>
    </div>
  );
}

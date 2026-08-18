import React from "react";
import { Link } from "react-router-dom";
import { ArrowUpRight, TrendingDown, TrendingUp } from "lucide-react";

import { cn } from "@/lib/utils";
import { KPI } from "@/constants/testIds";

/**
 * KpiCard — angka ringkas yang WAJIB bisa ditelusuri (blueprint IA V2 §7.3:
 * “Angka pada KPI wajib bisa di-drill-down ke daftar barisnya. Tanpa drill-down =
 * dianggap tidak selesai”).
 *
 * Karena itu `to` (tautan ke daftar terfilter) adalah bagian dari kontrak: bila diberikan,
 * seluruh kartu menjadi tautan sungguhan (bisa dibuka di tab baru, bisa di-hover untuk
 * melihat tujuannya) — bukan div dengan onClick.
 */
const TONE = {
  primary: "text-primary", amber: "text-amber-600", rose: "text-rose-600",
  emerald: "text-emerald-600", sky: "text-sky-700", muted: "text-muted-foreground",
};

export default function KpiCard({
  label, value, hint, delta = null, tone = "primary", icon: Icon = null, to = null,
  drillLabel = "Lihat daftar", testId, className,
}) {
  const body = (
    <>
      <div className="flex items-start justify-between gap-2">
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          {label}
        </p>
        {Icon ? <Icon className={cn("h-4 w-4", TONE[tone] || TONE.primary)} /> : null}
      </div>
      <p data-testid={`${testId || KPI.card}-value`}
        className="mt-1.5 font-heading text-2xl font-semibold tabular-nums leading-none">
        {value}
      </p>
      <div className="mt-1.5 flex items-center gap-1.5">
        {delta !== null && delta !== undefined ? (
          <span className={cn("inline-flex items-center gap-0.5 text-xs tabular-nums",
            Number(delta) < 0 ? "text-rose-600" : "text-emerald-600")}>
            {Number(delta) < 0 ? <TrendingDown className="h-3 w-3" />
              : <TrendingUp className="h-3 w-3" />}
            {Math.abs(Number(delta))}%
          </span>
        ) : null}
        {hint ? <span className="truncate text-xs text-muted-foreground">{hint}</span> : null}
      </div>
      {to ? (
        <span className="mt-2 inline-flex items-center gap-1 text-xs font-medium text-primary">
          {drillLabel} <ArrowUpRight className="h-3 w-3" />
        </span>
      ) : null}
    </>
  );

  const base = cn("block rounded-lg border bg-card p-3.5 text-left shadow-sm transition-colors",
    to && "hover:border-primary/40 hover:bg-secondary/50", className);

  if (!to) {
    return <div data-testid={testId || KPI.card} className={base}>{body}</div>;
  }
  return (
    <Link to={to} data-testid={testId || KPI.card} data-drill={to} className={base}>
      {body}
    </Link>
  );
}

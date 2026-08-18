import React from "react";
import { ArrowLeft } from "lucide-react";
import { useNavigate } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/**
 * EntityHeader — kepala halaman kanonik (Profil Lead / Customer / Unit / Proyek).
 *
 * Tujuan: hierarki informasi yang jelas (judul besar, meta chip kecil, aksi di kanan)
 * supaya halaman tidak lagi "rata" seperti temuan audit UI owner.
 */
export default function EntityHeader({
  kicker, title, subtitle, chips = [], actions = null, onBack, backLabel = "Kembali",
  testId,
}) {
  const navigate = useNavigate();
  return (
    <div data-testid={testId}
      className="space-y-3 rounded-lg border bg-card p-4 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 space-y-1">
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm" className="-ml-2 h-7 px-2"
              onClick={() => (onBack ? onBack() : navigate(-1))}>
              <ArrowLeft className="mr-1 h-4 w-4" /> {backLabel}
            </Button>
            {kicker ? (
              <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                {kicker}
              </span>
            ) : null}
          </div>
          <h1 className="truncate font-heading text-2xl font-semibold leading-tight">{title}</h1>
          {subtitle ? <p className="text-sm text-muted-foreground">{subtitle}</p> : null}
        </div>
        {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
      </div>
      {chips.length ? (
        <div className="flex flex-wrap items-center gap-2">
          {chips.filter(Boolean).map((c, i) => (
            <span key={`${c.label}-${i}`}
              className={cn("inline-flex items-center gap-1.5 rounded-md border bg-secondary",
                "px-2 py-1 text-xs")}>
              <span className="text-muted-foreground">{c.label}</span>
              <span className="font-medium text-foreground">{c.value}</span>
            </span>
          ))}
        </div>
      ) : null}
    </div>
  );
}

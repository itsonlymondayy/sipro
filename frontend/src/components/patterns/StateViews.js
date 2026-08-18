import React from "react";
import { ArrowLeft, ShieldOff } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { WORK } from "@/constants/testIds";

export function LoadingCards({ count = 4 }) {
  return (
    <div data-testid={WORK.loadingState} className="grid gap-3">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="rounded-xl border bg-card p-4">
          <Skeleton className="h-4 w-2/3" />
          <Skeleton className="mt-2 h-3 w-1/3" />
        </div>
      ))}
    </div>
  );
}

export function LoadingKpis({ count = 5 }) {
  return (
    <div data-testid={WORK.loadingState} className="grid grid-cols-2 gap-3 md:grid-cols-5">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="rounded-xl border bg-card p-4">
          <Skeleton className="h-3 w-1/2" />
          <Skeleton className="mt-3 h-6 w-1/3" />
        </div>
      ))}
    </div>
  );
}

export function ErrorState({ message, onRetry }) {
  return (
    <div className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">
      <p>{message || "Terjadi kesalahan saat memuat data."}</p>
      {onRetry ? (
        <button data-testid={WORK.retryButton} onClick={onRetry} className="mt-2 rounded-lg border border-rose-300 bg-white px-3 py-1 text-rose-700 hover:bg-rose-100">
          Coba lagi
        </button>
      ) : null}
    </div>
  );
}

/**
 * AccessDenied — satu penjelasan sopan untuk pengguna yang memang tidak berhak.
 *
 * Sebelumnya halaman tetap dirender lalu setiap panel memunculkan pesan teknis
 * backend ("tidak memiliki izin 'view' pada 'construction'") berkali-kali. Itu
 * membocorkan nama izin internal dan membuat pengguna bingung. Sekarang: satu
 * kartu, bahasa manusia, plus jalan keluar yang jelas.
 */
export function AccessDenied({
  title = "Halaman ini bukan untuk peran Anda",
  description = "Anda tidak punya akses ke data ini.",
  askWho = null, backTo = "/", backLabel = "Kembali ke Beranda",
  testId = "access-denied",
}) {
  return (
    <div data-testid={testId}
      className="mx-auto max-w-xl rounded-xl border bg-card p-8 text-center shadow-sm">
      <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-secondary">
        <ShieldOff className="h-6 w-6 text-muted-foreground" />
      </div>
      <p className="mt-3 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
        Akses ditolak
      </p>
      <h2 className="mt-1 font-heading text-lg font-semibold">{title}</h2>
      <p className="mt-1.5 text-sm text-muted-foreground">{description}</p>
      {askWho ? (
        <p className="mt-2 text-xs text-muted-foreground">{askWho}</p>
      ) : null}
      <a href={backTo} data-testid={`${testId}-back`}
        className="mt-5 inline-flex items-center gap-1.5 rounded-lg bg-primary px-3.5 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90">
        <ArrowLeft className="h-4 w-4" /> {backLabel}
      </a>
    </div>
  );
}

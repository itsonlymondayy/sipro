import React, { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, Compass, Lock, Search } from "lucide-react";

import {
  Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { NAV_MIGRATION, NAV_SOON } from "@/config/navMigrationMap";
import { HUB } from "@/constants/testIds";

/**
 * NavMigrationDialog — "Menu saya ke mana?" (US-40c-1).
 *
 * Perubahan navigasi yang benar pun terasa seperti kehilangan fitur bila pemakai lama tidak
 * diberi peta. Dialog ini mencari nama menu LAMA dan menautkannya ke lokasi BARU (termasuk
 * tab yang tepat), plus daftar jujur fitur yang belum dibangun beserta fasenya.
 */
export default function NavMigrationDialog() {
  const [q, setQ] = useState("");
  const rows = useMemo(() => {
    const needle = q.trim().toLowerCase();
    if (!needle) return NAV_MIGRATION;
    return NAV_MIGRATION.filter((r) => `${r.old} ${r.now} ${r.why}`.toLowerCase()
      .includes(needle));
  }, [q]);

  return (
    <Dialog>
      <DialogTrigger asChild>
        <button type="button" data-testid={HUB.navMapBtn}
          className="flex w-full items-center gap-1.5 rounded-md px-1 py-1 text-[10px] font-medium text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground">
          <Compass className="h-3 w-3" /> Peta menu baru (menu saya ke mana?)
        </button>
      </DialogTrigger>
      <DialogContent data-testid={HUB.navMapDialog}
        className="max-h-[85vh] max-w-2xl overflow-y-auto bg-background">
        <DialogHeader>
          <DialogTitle>Peta menu: lama → baru</DialogTitle>
          <DialogDescription>
            Tujuh pintu menu dilebur menjadi hub bertab. Tidak ada fitur yang dihapus — klik
            tujuan untuk langsung dibawa ke tab yang benar.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-1.5">
          <Label htmlFor="nav-map-q" className="text-xs">Cari nama menu lama</Label>
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input id="nav-map-q" data-testid={HUB.navMapSearch} value={q}
              aria-label="Cari nama menu lama" className="bg-background pl-8"
              placeholder="mis. Deal, Kalender, Perizinan…"
              onChange={(e) => setQ(e.target.value)} />
          </div>
        </div>

        <div className="space-y-2">
          {rows.map((r) => (
            <div key={r.old} data-testid={HUB.navMapRow} data-old={r.old}
              className="rounded-lg border bg-card p-3">
              <div className="flex flex-wrap items-center gap-2 text-sm">
                <span className="font-medium text-muted-foreground line-through">{r.old}</span>
                <ArrowRight className="h-3.5 w-3.5 text-muted-foreground" />
                <Link to={r.to} className="font-medium text-primary hover:underline">{r.now}</Link>
              </div>
              <p className="mt-1 text-xs text-muted-foreground">{r.why}</p>
            </div>
          ))}
          {!rows.length ? (
            <p className="rounded-lg border border-dashed bg-card p-4 text-sm text-muted-foreground">
              Tidak ada menu lama yang cocok dengan “{q}”.
            </p>
          ) : null}
        </div>

        <div className="rounded-lg border bg-secondary p-3">
          <p className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            <Lock className="h-3 w-3" /> Belum dibangun (tampil terkunci di sidebar)
          </p>
          <ul className="mt-1.5 space-y-1 text-sm">
            {NAV_SOON.map((s) => (
              <li key={s.label} className="flex flex-wrap items-baseline gap-1.5">
                <span className="font-medium">{s.label}</span>
                <span className="text-xs text-muted-foreground">di grup {s.where}</span>
                <span className="rounded bg-amber-100 px-1 text-[10px] font-medium text-amber-800">
                  {s.when}
                </span>
              </li>
            ))}
          </ul>
        </div>
      </DialogContent>
    </Dialog>
  );
}

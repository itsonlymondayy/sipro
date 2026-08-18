import React, { useCallback, useEffect, useState } from "react";
import { Bell, CheckCheck, AtSign, AlarmClock, Info } from "lucide-react";
import { Button } from "@/components/ui/button";
import EmptyState from "@/components/patterns/EmptyState";
import { LoadingCards, ErrorState } from "@/components/patterns/StateViews";
import { fromNow } from "@/utils/formatters";
import { cn } from "@/lib/utils";
import api from "@/services/apiClient";
import { NOTIF } from "@/constants/testIds";

const ICONS = { mention: AtSign, sla: AlarmClock, info: Info };

export default function NotificationsPage() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const res = await api.get("/notifications", { params: { limit: 100 } });
      setRows(res.data.data || []);
    } catch (e) {
      setError(e?.response?.data?.detail || "Gagal memuat notifikasi.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const markRead = async (n) => {
    if (n.read) return;
    await api.post(`/notifications/${n.id}/read`);
    setRows((prev) => prev.map((r) => (r.id === n.id ? { ...r, read: true } : r)));
  };
  const markAll = async () => {
    await api.post("/notifications/read-all");
    load();
  };

  return (
    <div data-testid={NOTIF.page} className="space-y-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Bell className="h-5 w-5 text-primary" />
          <h1 className="font-heading text-xl font-semibold">Notifikasi</h1>
        </div>
        <Button data-testid={NOTIF.markAll} variant="outline" size="sm" onClick={markAll}>
          <CheckCheck className="h-4 w-4 mr-1.5" /> Tandai semua dibaca
        </Button>
      </div>

      {loading ? <LoadingCards count={4} /> : error ? <ErrorState message={error} onRetry={load} /> :
        rows.length === 0 ? (
          <EmptyState icon={Bell} title="Belum ada notifikasi" description="Notifikasi @mention, SLA, dan info sistem akan muncul di sini." />
        ) : (
          <div className="divide-y rounded-xl border bg-card">
            {rows.map((n) => {
              const Icon = ICONS[n.type] || Info;
              return (
                <button key={n.id} data-testid={NOTIF.item} onClick={() => markRead(n)}
                  className={cn("flex w-full items-start gap-3 px-4 py-3 text-left transition-colors hover:bg-secondary/50",
                    !n.read && "bg-accent/40")}>
                  <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-secondary text-muted-foreground">
                    <Icon className="h-4 w-4" />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="flex items-center gap-2">
                      <span className="text-sm font-medium">{n.title}</span>
                      {!n.read ? <span className="h-1.5 w-1.5 rounded-full bg-primary" /> : null}
                    </span>
                    {n.body ? <span className="block text-sm text-muted-foreground">{n.body}</span> : null}
                    <span className="block text-[11px] text-muted-foreground mt-0.5">{fromNow(n.created_at)}</span>
                  </span>
                </button>
              );
            })}
          </div>
        )}
    </div>
  );
}

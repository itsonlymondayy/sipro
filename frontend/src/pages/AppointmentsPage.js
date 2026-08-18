import React, { useCallback, useEffect, useMemo, useState } from "react";
import { CalendarDays, CalendarClock, MapPin } from "lucide-react";
import { Calendar } from "@/components/ui/calendar";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import StatusPill from "@/components/patterns/StatusPill";
import EmptyState from "@/components/patterns/EmptyState";
import { LoadingCards, ErrorState } from "@/components/patterns/StateViews";
import AppointmentDetailSheet from "@/components/appointments/AppointmentDetailSheet";
import { formatDateWIB } from "@/utils/formatters";
import { cn } from "@/lib/utils";
import api from "@/services/apiClient";
import { APPTS } from "@/constants/testIds";
import RefLabel from "@/components/patterns/RefLabel";
import ReferenceSelect from "@/components/patterns/ReferenceSelect";


const wibDayKey = (iso) =>
  new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Jakarta", year: "numeric", month: "2-digit", day: "2-digit" })
    .format(new Date(iso));
const localDayKey = (d) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const parseDayKey = (k) => { const [y, m, d] = k.split("-").map(Number); return new Date(y, m - 1, d); };
const timeWIB = (iso) =>
  new Intl.DateTimeFormat("id-ID", { hour: "2-digit", minute: "2-digit", timeZone: "Asia/Jakarta" })
    .format(new Date(iso));

export default function AppointmentsPage() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [selected, setSelected] = useState(new Date());
  const [selectedAppt, setSelectedAppt] = useState(null);

  const load = useCallback(async () => {
    setLoading(true); setError("");
    try {
      const res = await api.get("/appointments", {
        params: { status: statusFilter === "all" ? undefined : statusFilter, limit: 200 },
      });
      setRows(res.data.data || []);
    } catch (e) {
      setError(e?.response?.data?.detail || "Gagal memuat janji temu.");
    } finally { setLoading(false); }
  }, [statusFilter]);

  useEffect(() => { load(); }, [load]);

  const byDay = useMemo(() => {
    const map = {};
    rows.forEach((a) => {
      const k = wibDayKey(a.scheduled_at);
      (map[k] = map[k] || []).push(a);
    });
    return map;
  }, [rows]);

  const daysWithAppts = useMemo(() => Object.keys(byDay).map(parseDayKey), [byDay]);
  const agenda = useMemo(() => {
    const items = byDay[localDayKey(selected)] || [];
    return [...items].sort((a, b) => a.scheduled_at.localeCompare(b.scheduled_at));
  }, [byDay, selected]);

  const refresh = () => { load(); setSelectedAppt(null); };

  return (
    <div data-testid={APPTS.page} className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <CalendarDays className="h-5 w-5 text-primary" />
          <h1 className="font-heading text-xl font-semibold">Agenda & Survey</h1>
          <span className="rounded-full bg-secondary px-2 py-0.5 text-xs text-muted-foreground tabular-nums">
            {rows.length}
          </span>
        </div>
        <ReferenceSelect group="appointment_status" allowEmpty emptyLabel="Semua status"
          className="h-9 w-44" testId={APPTS.statusFilter}
          value={statusFilter === "all" ? "" : statusFilter}
          onChange={(v) => setStatusFilter(v || "all")} />
      </div>

      {loading ? <LoadingCards count={4} /> : error ? <ErrorState message={error} onRetry={load} /> : (
        <div className="grid gap-6 lg:grid-cols-[auto,1fr]">
          {/* Calendar */}
          <div data-testid={APPTS.calendar} className="rounded-xl border bg-card p-2 shadow-sm">
            <Calendar
              mode="single"
              selected={selected}
              onSelect={(d) => d && setSelected(d)}
              modifiers={{ hasAppt: daysWithAppts }}
              modifiersClassNames={{
                hasAppt: "relative font-semibold text-primary after:absolute after:bottom-1 after:left-1/2 after:h-1 after:w-1 after:-translate-x-1/2 after:rounded-full after:bg-primary",
              }}
            />
            <div className="flex items-center gap-2 border-t px-3 py-2 text-xs text-muted-foreground">
              <span className="inline-block h-1.5 w-1.5 rounded-full bg-primary" /> Ada janji temu
            </div>
          </div>

          {/* Agenda for selected day */}
          <div data-testid={APPTS.agenda} className="space-y-3">
            <h2 className="flex items-center gap-2 font-heading text-lg font-semibold">
              <CalendarClock className="h-4 w-4 text-primary" />
              Agenda · {formatDateWIB(selected.toISOString())}
            </h2>
            {agenda.length === 0 ? (
              <EmptyState icon={CalendarDays} title="Tidak ada janji temu"
                description="Pilih tanggal lain pada kalender, atau jadwalkan survey dari detail lead." />
            ) : (
              <div className="space-y-2">
                {agenda.map((a) => (
                  <button key={a.id} data-testid={APPTS.agendaItem} onClick={() => setSelectedAppt(a)}
                    className={cn("flex w-full items-center justify-between gap-3 rounded-xl border bg-card p-3 text-left",
                      "transition-colors hover:border-primary hover:bg-secondary")}>
                    <div className="flex items-center gap-3">
                      <div className="flex flex-col items-center rounded-lg bg-primary/10 px-2.5 py-1.5">
                        <span className="text-sm font-semibold tabular-nums text-primary">{timeWIB(a.scheduled_at)}</span>
                        <span className="text-[10px] uppercase text-muted-foreground"><RefLabel group="appointment_type" value={a.type} /></span>
                      </div>
                      <div>
                        <p className="font-medium">{a.title}</p>
                        <p className="flex items-center gap-1 text-xs text-muted-foreground">
                          <MapPin className="h-3 w-3" /> {a.location || "-"} · {a.lead_name || ""}
                        </p>
                      </div>
                    </div>
                    <StatusPill status={a.status} group="appointment_status" />
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      <AppointmentDetailSheet appointment={selectedAppt} open={!!selectedAppt}
        onOpenChange={(v) => !v && setSelectedAppt(null)} onChanged={refresh} />
    </div>
  );
}

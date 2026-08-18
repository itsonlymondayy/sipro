import React, { useState } from "react";
import { CalendarPlus } from "lucide-react";

import { Button } from "@/components/ui/button";
import StatusPill from "@/components/patterns/StatusPill";
import EmptyState from "@/components/patterns/EmptyState";
import AppointmentDialog from "@/components/sales/AppointmentDialog";
import { formatDateTimeWIB } from "@/utils/formatters";
import { LEADS } from "@/constants/testIds";

/** LeadSurveyTab — daftar appointment/survei lead + penjadwalan baru. */
export default function LeadSurveyTab({ leadId, appointments = [], onChanged }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-2">
        <p className="text-sm text-muted-foreground">
          Jadwal survei & janji temu lead ini.
        </p>
        <Button data-testid={LEADS.appointmentBtn} size="sm" onClick={() => setOpen(true)}>
          <CalendarPlus className="mr-1.5 h-4 w-4" /> Jadwalkan Survey
        </Button>
      </div>
      {appointments.length ? (
        <div className="space-y-2">
          {appointments.map((ap) => (
            <div key={ap.id} data-testid="lead-appointment-row" data-appointment={ap.id}
              aria-label={`Survei ${ap.title}`}
              className="flex flex-wrap items-center justify-between gap-2 rounded-lg border bg-card p-3">
              <div>
                <p className="text-sm font-medium">{ap.title}</p>
                <p className="text-xs text-muted-foreground">
                  {formatDateTimeWIB(ap.scheduled_at)} · {ap.location || "-"}
                </p>
              </div>
              <StatusPill status={ap.status} group="appointment_status"
                tone={ap.status === "scheduled" ? "active" : ap.status} />
            </div>
          ))}
        </div>
      ) : (
        <EmptyState icon={CalendarPlus} title="Belum ada survei terjadwal"
          description="Jadwalkan survei lokasi agar lead bisa naik ke tahap berikutnya."
          actionLabel="Jadwalkan Survey" onAction={() => setOpen(true)} />
      )}
      <AppointmentDialog leadId={leadId} open={open} onOpenChange={setOpen} onDone={onChanged} />
    </div>
  );
}

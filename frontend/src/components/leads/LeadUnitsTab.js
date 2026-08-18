import React, { useState } from "react";
import { Link } from "react-router-dom";
import { Handshake } from "lucide-react";

import { Button } from "@/components/ui/button";
import StatusPill from "@/components/patterns/StatusPill";
import EmptyState from "@/components/patterns/EmptyState";
import MoneyText from "@/components/patterns/MoneyText";
import ReserveDialog from "@/components/sales/ReserveDialog";
import { formatDateTimeWIB } from "@/utils/formatters";
import { LEADS } from "@/constants/testIds";

/**
 * LeadUnitsTab — unit yang dipegang lead ini (reservasi/booking) + tautan ke Unit 360.
 * SPR/booking fee menyusul di Fase 42; yang ditampilkan di sini hanya data yang benar-benar
 * ada sekarang (deal + unit + nominal booking fee bila sudah tercatat).
 */
export default function LeadUnitsTab({ leadId, leadName, deals = [], onChanged }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-2">
        <p className="text-sm text-muted-foreground">Unit yang dipegang lead ini.</p>
        <Button data-testid={LEADS.reserveBtn} size="sm" onClick={() => setOpen(true)}>
          <Handshake className="mr-1.5 h-4 w-4" /> Buat Reservasi
        </Button>
      </div>
      {deals.length ? (
        <div className="space-y-2">
          {deals.map((d) => (
            <div key={d.id} data-testid="lead-deal-row" data-deal={d.id}
              aria-label={`Deal unit ${d.unit_code || "-"}`}
              className="flex flex-wrap items-center justify-between gap-3 rounded-lg border bg-card p-3">
              <div>
                <p className="text-sm font-medium">
                  {d.unit_id ? (
                    <Link className="text-primary hover:underline" to={`/units/${d.unit_id}`}>
                      {d.unit_code || "Unit"}
                    </Link>
                  ) : (d.unit_code || "Unit")}
                  {d.unit_type ? <span className="text-muted-foreground"> · {d.unit_type}</span> : null}
                </p>
                <p className="text-xs text-muted-foreground">
                  Reservasi {d.reserved_at ? formatDateTimeWIB(d.reserved_at) : "-"}
                  {d.reserved_until ? ` · berlaku s/d ${formatDateTimeWIB(d.reserved_until)}` : ""}
                </p>
              </div>
              <div className="flex items-center gap-3">
                <div className="text-right">
                  <p className="text-xs text-muted-foreground">Harga</p>
                  <MoneyText value={d.price} className="text-sm font-medium" />
                </div>
                <div className="text-right">
                  <p className="text-xs text-muted-foreground">Booking fee</p>
                  <MoneyText value={d.booking_fee} className="text-sm" />
                </div>
                <StatusPill status={d.status} group="deal_status" />
              </div>
            </div>
          ))}
        </div>
      ) : (
        <EmptyState icon={Handshake} title="Belum ada unit dipegang"
          description="Buat reservasi untuk mengunci unit bagi lead ini (batas reservasi per lead ditegakkan Fase 42)."
          actionLabel="Buat Reservasi" onAction={() => setOpen(true)} />
      )}
      <ReserveDialog mode="byLead" leadId={leadId} leadName={leadName} open={open}
        onOpenChange={setOpen} onReserved={onChanged} />
    </div>
  );
}

import React from "react";

import TimelineFeed from "@/components/patterns/TimelineFeed";

/**
 * LeadTimelineTab — satu urutan waktu dari SEMUA jejak lead: perpindahan tahap, aktivitas/
 * catatan, appointment, dan penyerahan dokumen. Setiap baris menyebut aktornya (CR-10).
 */
function build({ lead, activities, appointments, submissions }) {
  const items = [];
  (lead?.stage_history || []).forEach((h) => items.push({
    at: h.at, actor: h.actor, kind: "stage",
    title: `Tahap ${h.from || "-"} → ${h.to}${h.override ? " (override supervisor)" : ""}`,
    body: h.reason || null,
  }));
  (activities || []).forEach((a) => items.push({
    at: a.created_at, actor: a.actor || a.created_by, kind: a.type === "comment"
      ? "activity" : "activity",
    title: a.type === "comment" ? "Catatan" : (a.title || "Aktivitas"),
    body: a.body,
  }));
  (appointments || []).forEach((ap) => items.push({
    at: ap.created_at || ap.scheduled_at, actor: ap.created_by || ap.assigned_to,
    kind: "task", title: `Appointment: ${ap.title}`,
    body: `${ap.location || "-"} · status ${ap.status}`,
  }));
  (submissions || []).forEach((s) => items.push({
    at: s.submitted_at || s.created_at, actor: s.submitted_by, kind: "upload",
    title: `Dokumen “${s.requirement_label || s.requirement_code}” diserahkan`,
    body: s.status === "verified"
      ? `Diverifikasi oleh ${s.verified_by || "-"}`
      : s.status === "rejected" ? `Ditolak: ${s.reject_reason || "-"}` : "Menunggu verifikasi",
  }));
  return items;
}

export default function LeadTimelineTab(props) {
  return (
    <div className="space-y-3">
      <p className="text-sm text-muted-foreground">
        Seluruh jejak lead ini dalam satu urutan waktu — termasuk siapa yang mengerjakan.
      </p>
      <TimelineFeed items={build(props)}
        emptyText="Belum ada jejak untuk lead ini (belum ada perpindahan tahap, catatan, atau dokumen)." />
    </div>
  );
}

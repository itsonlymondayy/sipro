import React, { useCallback, useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import {
  CalendarCheck2, ClipboardList, FileText, Handshake, History, MessageSquare,
  Phone, ShieldCheck, UserCircle2,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import EntityHeader from "@/components/patterns/EntityHeader";
import TabPage from "@/components/patterns/TabPage";
import AgingCell from "@/components/patterns/AgingCell";
import StatusPill from "@/components/patterns/StatusPill";
import DocChecklist from "@/components/patterns/DocChecklist";
import LeadWaPanel from "@/components/sales/LeadWaPanel";
import LeadSummaryTab from "@/components/leads/LeadSummaryTab";
import LeadTimelineTab from "@/components/leads/LeadTimelineTab";
import LeadSurveyTab from "@/components/leads/LeadSurveyTab";
import LeadUnitsTab from "@/components/leads/LeadUnitsTab";
import { LoadingCards, ErrorState } from "@/components/patterns/StateViews";
import { useReference } from "@/context/ReferenceContext";
import api from "@/services/apiClient";
import { LEADPROFILE, TABPAGE } from "@/constants/testIds";

/**
 * LeadProfilePage (`/leads/:id`) — HALAMAN kanonik lead (US-40-2, CR-10).
 *
 * Kenapa halaman, bukan drawer: isi lead jauh lebih dari satu layar (gerbang tahap,
 * dokumen syarat, survei, percakapan WA, unit, riwayat). Di drawer semuanya bertumpuk
 * vertikal sehingga checklist dokumen Fase 39b praktis tersembunyi di dasar gulungan —
 * itulah alasan owner memutuskan `DocChecklist` PINDAH ke halaman ini (tab "Dokumen").
 *
 * Semua panel yang sudah lulus uji pada fase sebelumnya dipakai ulang apa adanya
 * (LeadLifecyclePanel, LeadWaPanel, DocChecklist), jadi pemindahan ini tidak menghapus
 * satu pun kemampuan.
 */
export default function LeadProfilePage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { labelOf } = useReference();
  const [state, setState] = useState({ loading: true, error: "" });
  const [lead, setLead] = useState(null);
  const [life, setLife] = useState(null);
  const [acts, setActs] = useState([]);
  const [appts, setAppts] = useState([]);
  const [deals, setDeals] = useState([]);
  const [subs, setSubs] = useState([]);
  const [waKey, setWaKey] = useState(0);

  const load = useCallback(async () => {
    setState({ loading: true, error: "" });
    try {
      const [l, lf, a, ap, dl, sb] = await Promise.all([
        api.get(`/leads/${id}`),
        api.get(`/leads/${id}/lifecycle`),
        api.get("/activities", { params: { entity_type: "lead", entity_id: id } }),
        api.get("/appointments", { params: { lead_id: id } }),
        api.get("/deals", { params: { lead_id: id } }),
        api.get("/doc/submissions", { params: { entity_type: "lead", entity_id: id } })
          .catch(() => ({ data: { data: [] } })),
      ]);
      setLead(l.data.data);
      setLife(lf.data.data);
      setActs(a.data.data || []);
      setAppts(ap.data.data || []);
      setDeals(dl.data.data || []);
      setSubs(sb.data.data || []);
      setState({ loading: false, error: "" });
    } catch (e) {
      const status = e?.response?.status;
      setState({
        loading: false,
        error: status === 404 ? "Lead tidak ditemukan."
          : status === 403 ? "Lead ini bukan milik Anda (akses ditolak)."
            : (e?.response?.data?.detail || "Gagal memuat profil lead."),
      });
    }
  }, [id]);

  useEffect(() => { load(); }, [load]);

  const refresh = () => { load(); setWaKey((k) => k + 1); };

  // Aksi dari checklist syarat / kartu langkah berikutnya: pindah ke TAB yang tepat
  // (dulu men-scroll di dalam drawer; di halaman, tab adalah alamat yang bisa dibagikan).
  const goTab = (tab) => {
    const url = new URL(window.location.href);
    url.searchParams.set("tab", tab);
    navigate(`${url.pathname}${url.search}`, { replace: false });
  };
  const handleAction = (key) => {
    if (key === "appointment") return goTab("survey");
    if (key === "reserve" || key === "deal") return goTab("unit");
    if (key === "wa") return goTab("percakapan");
    if (key === "slik" || key === "disposition" || key === "close") return goTab("ringkasan");
    if (key === "document" || key === "doc") return goTab("dokumen");
    return undefined;
  };

  if (state.loading) {
    return <div className="space-y-4"><LoadingCards count={4} /></div>;
  }
  if (state.error || !lead) {
    return (
      <div data-testid={LEADPROFILE.notFound} className="space-y-3">
        <ErrorState message={state.error} onRetry={load} />
        <Button variant="outline" size="sm" onClick={() => navigate("/leads")}>
          Kembali ke daftar lead
        </Button>
      </div>
    );
  }

  const header = (
    <EntityHeader testId={LEADPROFILE.header} kicker="CRM · Profil Lead" title={lead.name}
      subtitle={[lead.phone, lead.email].filter(Boolean).join(" · ")}
      onBack={() => navigate("/leads")} backLabel="Daftar lead"
      chips={[
        { label: "Tahap", value: <StatusPill status={lead.stage} group="lead_stage" /> },
        { label: "Skor", value: `${lead.score} · ${labelOf("score_band", lead.score_band)}` },
        { label: "Sumber", value: labelOf("lead_source", lead.source) },
        { label: "PIC", value: lead.assigned_to || "-" },
        {
          label: "Umur",
          value: <AgingCell ageHours={lead.age_hours} stageAgeHours={lead.stage_age_hours}
            slaHours={lead.stage_sla_hours} state={lead.sla_state} />,
        },
      ]}
      actions={(
        <>
          <Button data-testid={LEADPROFILE.callBtn} size="sm" variant="outline" asChild>
            <a href={`tel:${lead.phone}`}><Phone className="mr-1.5 h-4 w-4" /> Telepon</a>
          </Button>
          <Button data-testid={LEADPROFILE.waBtn} size="sm" onClick={() => goTab("percakapan")}>
            <MessageSquare className="mr-1.5 h-4 w-4" /> WhatsApp
          </Button>
        </>
      )} />
  );

  const docCount = subs.filter((s) => s.status === "verified").length;

  return (
    <div data-testid={LEADPROFILE.page} className="space-y-4">
      <TabPage testId={TABPAGE.root} header={header} tabs={[
        {
          key: "ringkasan", label: "Ringkasan", icon: UserCircle2,
          content: <LeadSummaryTab lead={lead} lifecycle={life} onAction={handleAction}
            onChanged={refresh} />,
        },
        {
          key: "timeline", label: "Timeline", icon: History,
          content: <LeadTimelineTab lead={lead} activities={acts} appointments={appts}
            submissions={subs} />,
        },
        {
          key: "dokumen", label: "Dokumen", icon: FileText, badge: docCount || undefined,
          content: <DocChecklist entityType="lead" entityId={id} onChanged={refresh} />,
        },
        {
          key: "survey", label: "Survey", icon: CalendarCheck2,
          badge: appts.length || undefined,
          content: <LeadSurveyTab leadId={id} appointments={appts} onChanged={refresh} />,
        },
        {
          key: "unit", label: "Unit & SPR", icon: Handshake, badge: deals.length || undefined,
          content: <LeadUnitsTab leadId={id} leadName={lead.name} deals={deals}
            onChanged={refresh} />,
        },
        {
          key: "percakapan", label: "Percakapan", icon: MessageSquare,
          content: <LeadWaPanel key={waKey} leadId={id} onChanged={refresh} />,
        },
        {
          key: "bi", label: "BI / SLIK", icon: ShieldCheck,
          content: (
            <div className="rounded-lg border bg-card p-4 text-sm">
              <p className="font-medium">Pra-skrining BI/SLIK ada di tab Ringkasan.</p>
              <p className="mt-1 text-muted-foreground">
                Panel SLIK menempel pada gerbang tahap (bukti iDeb wajib sebelum Booking).
                Menu BI Checking mandiri dijadwalkan Fase 44.
              </p>
              <Button className="mt-3" size="sm" variant="outline"
                onClick={() => goTab("ringkasan")}>Buka gerbang tahap</Button>
            </div>
          ),
        },
        {
          key: "mitra", label: "Fee Mitra", icon: ClipboardList, soon: "Fase 45",
          soonNote: "Aturan fee mitra (7 basis perhitungan, split, pajak) baru dibuat pada "
            + "Fase 45 — sebelum itu tidak ada angka fee yang bisa ditampilkan tanpa mengarang.",
          content: null,
        },
      ]} />
    </div>
  );
}

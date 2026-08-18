import React, { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  Building2, CreditCard, FileText, Headset, History, Receipt, ScrollText, UserCircle2,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import EntityHeader from "@/components/patterns/EntityHeader";
import TabPage from "@/components/patterns/TabPage";
import StatusPill from "@/components/patterns/StatusPill";
import MoneyText from "@/components/patterns/MoneyText";
import DocChecklist from "@/components/patterns/DocChecklist";
import TimelineFeed from "@/components/patterns/TimelineFeed";
import CustomerSummaryTab from "@/components/customers/CustomerSummaryTab";
import CustomerFinancingTab from "@/components/customers/CustomerFinancingTab";
import {
  CustomerUnitsTab, CustomerComplaintsTab,
} from "@/components/customers/CustomerRelatedTabs";
import { LoadingCards, ErrorState } from "@/components/patterns/StateViews";
import api from "@/services/apiClient";
import { CUSTPROFILE } from "@/constants/testIds";

/**
 * CustomerProfilePage (`/customers/:id`) — HALAMAN kanonik pelanggan (US-40-2).
 *
 * Tab yang datanya baru dibuat pada fase mendatang TETAP TERLIHAT dengan keterangan jujur
 * (“belum aktif — Fase 43/44”) sesuai keputusan owner: pemakai berhak tahu peta jalannya,
 * tetapi TIDAK boleh disuguhi tabel kosong yang seolah-olah sudah berfungsi.
 */
export default function CustomerProfilePage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [state, setState] = useState({ loading: true, error: "" });
  const [cust, setCust] = useState(null);
  const [fins, setFins] = useState([]);
  const [units, setUnits] = useState([]);
  const [complaints, setComplaints] = useState([]);
  const [acts, setActs] = useState([]);
  const [subs, setSubs] = useState([]);

  const load = useCallback(async () => {
    setState({ loading: true, error: "" });
    try {
      const [c, f, u, cp, a, sb] = await Promise.all([
        api.get(`/customers/${id}`),
        api.get("/financing", { params: { customer_id: id } }).catch(() => ({ data: { data: [] } })),
        api.get("/units", { params: { customer_id: id } }).catch(() => ({ data: { data: [] } })),
        api.get("/complaints", { params: { customer_id: id, limit: 50 } })
          .catch(() => ({ data: { data: [] } })),
        api.get("/activities", { params: { entity_type: "customer", entity_id: id } })
          .catch(() => ({ data: { data: [] } })),
        api.get("/doc/submissions", { params: { entity_type: "customer", entity_id: id } })
          .catch(() => ({ data: { data: [] } })),
      ]);
      setCust(c.data.data);
      setFins(f.data.data || []);
      setUnits(u.data.data || []);
      setComplaints(cp.data.data || []);
      setActs(a.data.data || []);
      setSubs(sb.data.data || []);
      setState({ loading: false, error: "" });
    } catch (e) {
      const status = e?.response?.status;
      setState({
        loading: false,
        error: status === 404 ? "Pelanggan tidak ditemukan."
          : (e?.response?.data?.detail || "Gagal memuat profil pelanggan."),
      });
    }
  }, [id]);

  useEffect(() => { load(); }, [load]);

  if (state.loading) return <LoadingCards count={4} />;
  if (state.error || !cust) {
    return (
      <div data-testid={CUSTPROFILE.notFound} className="space-y-3">
        <ErrorState message={state.error} onRetry={load} />
        <Button variant="outline" size="sm" onClick={() => navigate("/customers")}>
          Kembali ke daftar pelanggan
        </Button>
      </div>
    );
  }

  const timeline = [
    ...acts.map((a) => ({
      at: a.created_at, actor: a.actor || a.created_by, kind: "activity",
      title: a.type === "comment" ? "Catatan" : (a.title || "Aktivitas"), body: a.body,
    })),
    ...subs.map((s) => ({
      at: s.submitted_at || s.created_at, actor: s.submitted_by, kind: "upload",
      title: `Dokumen “${s.requirement_label || s.requirement_code}” diserahkan`,
      body: s.status === "verified" ? `Diverifikasi oleh ${s.verified_by || "-"}`
        : s.status === "rejected" ? `Ditolak: ${s.reject_reason || "-"}` : "Menunggu verifikasi",
    })),
    ...complaints.map((c) => ({
      at: c.created_at, actor: c.assigned_to || "portal pembeli", kind: "message",
      title: `Komplain: ${c.subject}`, body: `Status ${c.status}`,
    })),
  ];

  const header = (
    <EntityHeader testId={CUSTPROFILE.header} kicker="CRM · Profil Pelanggan" title={cust.name}
      subtitle={[cust.phone, cust.email].filter(Boolean).join(" · ")}
      onBack={() => navigate("/customers")} backLabel="Daftar pelanggan"
      chips={[
        {
          label: "KYC",
          value: <StatusPill status={cust.kyc_status}
            label={cust.kyc_status === "submitted" ? "Terkirim" : "Pending"} />,
        },
        { label: "NIK", value: cust.nik || "-" },
        { label: "Penghasilan", value: <MoneyText value={cust.monthly_income} short /> },
        { label: "Unit", value: String(units.length) },
        { label: "KPR", value: String(fins.length) },
      ]} />
  );

  return (
    <div data-testid={CUSTPROFILE.page} className="space-y-4">
      <TabPage header={header} tabs={[
        {
          key: "ringkasan", label: "Ringkasan", icon: UserCircle2,
          content: <CustomerSummaryTab customer={cust} onChanged={load} />,
        },
        {
          key: "kontrak", label: "Kontrak & Harga", icon: ScrollText, soon: "Fase 43",
          soonNote: "Kontrak + rincian harga per komponen (BPHTB, notaris, bank, hook, "
            + "kelebihan tanah, promo) baru menjadi data pada Fase 43 — sampai itu tidak ada "
            + "angka kontrak yang bisa ditampilkan tanpa mengarang.",
          content: null,
        },
        {
          key: "bayar", label: "Rencana Bayar", icon: Receipt, soon: "Fase 43",
          soonNote: "Rencana bayar per termin, jatuh tempo, tunggakan, dan toleransi dibangun "
            + "pada Fase 43 bersama kontrak. Pembayaran yang sudah tercatat hari ini bisa "
            + "dilihat di menu Keuangan.",
          content: null,
        },
        {
          key: "kpr", label: "KPR", icon: CreditCard, badge: fins.length || undefined,
          content: <CustomerFinancingTab customer={cust} financings={fins} onChanged={load} />,
        },
        {
          key: "dokumen", label: "Dokumen & Legal", icon: FileText,
          badge: subs.filter((s) => s.status === "verified").length || undefined,
          content: <DocChecklist entityType="customer" entityId={id} onChanged={load} />,
        },
        {
          key: "unit", label: "Unit & Konstruksi", icon: Building2,
          badge: units.length || undefined,
          content: <CustomerUnitsTab units={units} />,
        },
        {
          key: "komplain", label: "Komplain", icon: Headset,
          badge: complaints.length || undefined,
          content: <CustomerComplaintsTab complaints={complaints} />,
        },
        {
          key: "timeline", label: "Timeline", icon: History,
          content: <TimelineFeed items={timeline}
            emptyText="Belum ada jejak untuk pelanggan ini." />,
        },
      ]} />
    </div>
  );
}

import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { CheckCircle2, FileText, ScrollText, XCircle } from "lucide-react";

import { Button } from "@/components/ui/button";
import DataTable from "@/components/patterns/DataTable";
import FilterBar from "@/components/patterns/FilterBar";
import StatusPill from "@/components/patterns/StatusPill";
import MoneyText from "@/components/patterns/MoneyText";
import AgingCell from "@/components/patterns/AgingCell";
import DealLegalDialog from "@/components/sales/DealLegalDialog";
import useListQuery from "@/hooks/useListQuery";
import { useReference } from "@/context/ReferenceContext";
import { formatDateWIB } from "@/utils/formatters";
import { slaFilter } from "@/utils/agingFilter";
import api from "@/services/apiClient";
import { DEALS } from "@/constants/testIds";

/**
 * DealsListTab — daftar deal sebagai tabel pro dengan aksi per baris.
 * Aksi yang sudah ada dipertahankan penuh: Konfirmasi Booking, Buat SPR, Legal, Batal.
 */
export default function DealsListTab({ onChanged }) {
  const navigate = useNavigate();
  const { options } = useReference();
  const { query, setQuery, reset, apiParams, activeCount } = useListQuery({
    filters: { status: [], created_from: "", created_to: "", sla: "" },
    sort: "created_at", direction: "desc", limit: 25,
  });
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState(null);
  const [legalDeal, setLegalDeal] = useState(null);

  const load = useCallback(async () => {
    setLoading(true); setError("");
    try {
      const res = await api.get("/deals", { params: apiParams });
      setData(res.data);
    } catch (e) {
      setError(e?.response?.data?.detail || "Gagal memuat deal.");
    } finally { setLoading(false); }
  }, [apiParams]);

  useEffect(() => { load(); }, [load]);

  const refresh = () => { load(); onChanged?.(); };

  const act = async (deal, action) => {
    setBusyId(deal.id);
    try {
      await api.post(action === "book" ? `/deals/${deal.id}/book` : `/deals/${deal.id}/cancel`, {});
      toast.success(action === "book" ? "Deal dikonfirmasi (booked)." : "Deal dibatalkan.");
      refresh();
    } catch (e) { toast.error(e?.response?.data?.detail || "Gagal."); }
    finally { setBusyId(null); }
  };

  const createSpr = async (deal) => {
    setBusyId(deal.id);
    try {
      const res = await api.post("/documents", { template_code: "SPR", deal_id: deal.id });
      toast.success(`SPR ${res.data.data.doc_number} dibuat.`);
      navigate("/documents");
    } catch (e) { toast.error(e?.response?.data?.detail || "Gagal membuat SPR."); }
    finally { setBusyId(null); }
  };

  const columns = useMemo(() => [
    {
      key: "unit_code", header: "Unit", sortable: true,
      render: (d) => (
        <div>
          <p className="font-medium text-primary">{d.unit_code || "Unit"}</p>
          <p className="text-xs text-muted-foreground">{d.unit_type || "-"}</p>
        </div>
      ),
    },
    {
      key: "lead_name", header: "Lead / pembeli",
      render: (d) => d.lead_name || "-",
    },
    {
      key: "status", header: "Status", sortable: true,
      render: (d) => (
        <div className="flex flex-wrap items-center gap-1">
          <StatusPill status={d.status} group="deal_status" />
          {d.legal_stage === "ppjb" ? <StatusPill status="pending" label="PPJB" /> : null}
          {d.legal_stage === "ajb" ? <StatusPill status="sold" label="AJB · SOLD" /> : null}
        </div>
      ),
      exportValue: (d) => `${d.status}${d.legal_stage ? ` (${d.legal_stage})` : ""}`,
    },
    {
      key: "price", header: "Harga", sortable: true, align: "right",
      render: (d) => <MoneyText value={d.price} />, exportValue: (d) => d.price || 0,
    },
    {
      key: "booking_fee", header: "Booking fee", sortable: true, align: "right",
      render: (d) => <MoneyText value={d.booking_fee} />, exportValue: (d) => d.booking_fee || 0,
    },
    {
      key: "reserved_until", header: "Hold s/d",
      render: (d) => (d.reserved_until
        ? <span className="text-xs">{formatDateWIB(d.reserved_until)}</span>
        : <span className="text-xs text-muted-foreground">—</span>),
    },
    {
      key: "age_hours", header: "Umur (total · status)",
      render: (d) => <AgingCell ageHours={d.age_hours} stageAgeHours={d.stage_age_hours}
        slaHours={d.stage_sla_hours} state={d.sla_state} />,
      exportValue: (d) => `${Math.round(d.age_hours || 0)}j`,
    },
    {
      key: "aksi", header: "Aksi", align: "right",
      render: (d) => (
        <div className="flex flex-wrap justify-end gap-1.5" onClick={(e) => e.stopPropagation()}>
          {d.status === "reserved" ? (
            <Button data-testid={DEALS.bookBtn} size="sm" disabled={busyId === d.id}
              onClick={() => act(d, "book")}>
              <CheckCircle2 className="mr-1 h-3.5 w-3.5" /> Booking
            </Button>
          ) : null}
          {["reserved", "booked"].includes(d.status) ? (
            <Button data-testid={DEALS.createSprBtn} size="sm" variant="outline"
              disabled={busyId === d.id} onClick={() => createSpr(d)}>
              <FileText className="mr-1 h-3.5 w-3.5" /> SPR
            </Button>
          ) : null}
          {["booked", "completed"].includes(d.status) ? (
            <Button data-testid={DEALS.legalBtn} size="sm" variant="outline"
              onClick={() => setLegalDeal(d)}>
              <ScrollText className="mr-1 h-3.5 w-3.5" /> Legal
            </Button>
          ) : null}
          {["reserved", "booked"].includes(d.status) ? (
            <Button data-testid={DEALS.cancelBtn} size="sm" variant="ghost"
              className="text-rose-600" disabled={busyId === d.id} onClick={() => act(d, "cancel")}>
              <XCircle className="mr-1 h-3.5 w-3.5" /> Batal
            </Button>
          ) : null}
        </div>
      ),
      exportValue: () => "",
    },
  ], [busyId]); // eslint-disable-line react-hooks/exhaustive-deps

  const filters = (
    <FilterBar value={query} onChange={setQuery} onReset={reset} filters={[
      { key: "status", label: "Status deal", type: "multiselect",
        options: options("deal_status").map((o) => ({ ...o, hint: data?.counts?.[o.value] })) },
      slaFilter(options("sla_state")),
      { key: "created", label: "Dibuat", type: "daterange",
        fromKey: "created_from", toKey: "created_to" },
    ]} />
  );

  return (
    <>
      <DataTable testId={DEALS.dealTable} testIds={{ row: DEALS.dealRow }}
        columns={columns} rows={data?.data || []} total={data?.total || 0}
        query={query} onQueryChange={setQuery} loading={loading} error={error}
        filters={filters} label="deal" exportName="deal" onRefresh={load}
        searchPlaceholder="Cari kode unit / catatan…"
        onRowClick={(d) => (d.unit_id ? navigate(`/units/${d.unit_id}`) : null)}
        emptyTitle={activeCount || query.q ? "Tidak ada deal yang cocok" : "Belum ada deal"}
        emptyDescription={activeCount || query.q
          ? "Longgarkan filter atau kosongkan pencarian."
          : "Buat reservasi dari tab Unit untuk memulai deal."} />
      <DealLegalDialog deal={legalDeal} open={!!legalDeal}
        onOpenChange={(v) => !v && setLegalDeal(null)} onChanged={refresh} />
    </>
  );
}

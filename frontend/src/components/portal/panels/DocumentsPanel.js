import React, { useEffect, useState } from "react";
import { FileText, Download } from "lucide-react";
import StatusPill from "@/components/patterns/StatusPill";
import { LoadingCards, ErrorState } from "@/components/patterns/StateViews";
import { formatDateWIB } from "@/utils/formatters";
import { API } from "@/services/apiClient";
import portalApi, { PORTAL_TOKEN_KEY } from "@/services/portalClient";
import { PORTAL } from "@/constants/testIds";

export default function DocumentsPanel() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = async () => {
    setLoading(true); setError("");
    try {
      const res = await portalApi.get("/portal/documents");
      setData(res.data.data || []);
    } catch (e) {
      setError(e?.response?.data?.detail || "Gagal memuat dokumen.");
    } finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  const pdfUrl = (id) => `${API}/portal/documents/${id}/pdf?auth=${localStorage.getItem(PORTAL_TOKEN_KEY)}`;

  if (loading) return <LoadingCards count={3} />;
  if (error) return <ErrorState message={error} onRetry={load} />;
  if (!data?.length) return <p className="rounded-xl border bg-white p-6 text-center text-sm text-slate-500">Belum ada dokumen.</p>;

  return (
    <div data-testid={PORTAL.documentsPanel} className="rounded-xl border bg-white">
      <div className="divide-y">
        {data.map((d) => (
          <div key={d.id} data-testid={PORTAL.documentRow} className="flex items-center justify-between px-4 py-3">
            <div className="flex items-center gap-3">
              <div className="grid h-9 w-9 place-items-center rounded-lg bg-indigo-50 text-indigo-600"><FileText className="h-5 w-5" /></div>
              <div>
                <p className="text-sm font-medium">{d.title}</p>
                <p className="text-xs text-slate-400">{d.doc_number} · {formatDateWIB(d.created_at)}</p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <StatusPill status={d.status} label={d.status === "signed" ? "Ditandatangani" : d.status === "finalized" ? "Final" : "Draf"} />
              <a className="flex items-center gap-1 text-sm text-indigo-600 hover:underline" href={pdfUrl(d.id)} target="_blank" rel="noreferrer">
                <Download className="h-4 w-4" /> PDF
              </a>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

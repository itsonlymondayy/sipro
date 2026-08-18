import React, { useEffect, useState } from "react";
import { ShieldCheck, Info } from "lucide-react";
import { LoadingCards, ErrorState } from "@/components/patterns/StateViews";
import { roleLabel } from "@/utils/formatters";
import api from "@/services/apiClient";
import { ADMIN } from "@/constants/testIds";

const ACTION_LABEL = {
  all: "semua", manage: "kelola", view: "lihat", view_all: "lihat semua",
  view_own: "lihat sendiri", create: "buat", update: "ubah", delete: "hapus",
  approve: "setujui", assign: "assign", sign: "ttd",
};

export default function AdminPermissions() {
  const [matrix, setMatrix] = useState(null);
  const [roles, setRoles] = useState([]);
  const [resources, setResources] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const res = await api.get("/admin/permissions");
      setMatrix(res.data.data.matrix);
      setRoles(res.data.data.roles);
      setResources(res.data.data.resources);
    } catch (e) {
      setError(e?.response?.data?.detail || "Gagal memuat hak akses.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const cell = (resource, role) => {
    if (role === "super_admin" || role === "owner") {
      return <span className="status-pill status-available">semua</span>;
    }
    const perms = (matrix?.[resource] || {})[role] || [];
    if (!perms.length) return <span className="text-muted-foreground/40">—</span>;
    return (
      <div className="flex flex-wrap gap-1">
        {perms.map((p) => (
          <span key={p} className="rounded border bg-secondary px-1.5 py-0.5 text-[10px]">{ACTION_LABEL[p] || p}</span>
        ))}
      </div>
    );
  };

  return (
    <div data-testid={ADMIN.permsPage} className="space-y-5">
      <div className="flex items-center gap-2">
        <ShieldCheck className="h-5 w-5 text-primary" />
        <h1 className="font-heading text-xl font-semibold">Hak Akses (RBAC)</h1>
      </div>
      <div className="flex items-start gap-2 rounded-lg border border-sky-200 bg-sky-50 px-3 py-2 text-sm text-sky-800">
        <Info className="h-4 w-4 mt-0.5 shrink-0" />
        <p>Matriks izin per peran (SSOT <span className="font-mono text-xs">permission_settings</span>). Ditegakkan di backend via <span className="font-mono text-xs">require_permission</span>. Penyuntingan matriks tersedia di fase berikut.</p>
      </div>

      {loading ? <LoadingCards count={6} /> : error ? <ErrorState message={error} onRetry={load} /> : (
        <div data-testid={ADMIN.permsMatrix} className="overflow-x-auto rounded-xl border bg-card">
          <table className="w-full min-w-[900px] text-sm">
            <thead className="bg-secondary/60 text-left text-xs uppercase text-muted-foreground">
              <tr>
                <th className="sticky left-0 bg-secondary/60 px-4 py-2.5 font-medium">Resource</th>
                {roles.map((r) => <th key={r} className="px-3 py-2.5 font-medium whitespace-nowrap">{roleLabel(r)}</th>)}
              </tr>
            </thead>
            <tbody className="divide-y">
              {resources.map((res) => (
                <tr key={res} className="hover:bg-secondary/20">
                  <td className="sticky left-0 bg-card px-4 py-2.5 font-mono text-xs font-medium">{res}</td>
                  {roles.map((r) => <td key={r} className="px-3 py-2.5 align-top">{cell(res, r)}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

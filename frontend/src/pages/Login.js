import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Building2, LogIn, AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/context/AuthContext";
import { AUTH } from "@/constants/testIds";

/**
 * Daftar masuk-cepat demo. `slug` dipakai untuk data-testid agar stabil & tanpa spasi
 * (dulu testid dibentuk dari label sehingga "Super Admin" menghasilkan selector berspasi
 * dan peran admin/marketing/site sama sekali tidak punya tombol cepat).
 */
const QUICK = [
  { role: "Owner", slug: "owner", email: "owner@sipro.co.id" },
  { role: "Manajer", slug: "manajer", email: "manager@sipro.co.id" },
  { role: "Marketing", slug: "marketing", email: "marketing@sipro.co.id" },
  { role: "Sales", slug: "sales", email: "sales@sipro.co.id" },
  { role: "Finance", slug: "finance", email: "finance@sipro.co.id" },
  { role: "Proyek", slug: "proyek", email: "pm@sipro.co.id" },
  { role: "Site", slug: "site", email: "site@sipro.co.id" },
  { role: "Super Admin", slug: "superadmin", email: "superadmin@sipro.co.id" },
];

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e, presetEmail) => {
    if (e) e.preventDefault();
    setError("");
    setBusy(true);
    try {
      await login(presetEmail || email, presetEmail ? "Sipro#2026" : password);
      navigate("/");
    } catch (err) {
      setError(err?.response?.data?.detail || "Gagal masuk. Periksa email & kata sandi.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center app-noise bg-background px-4">
      <div className="w-full max-w-md">
        <div className="mb-6 flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-primary text-primary-foreground">
            <Building2 className="h-6 w-6" />
          </div>
          <div>
            <p className="font-heading text-xl font-bold tracking-tight">SIPRO</p>
            <p className="text-xs text-muted-foreground">Property Development OS — PT SIPRO Land</p>
          </div>
        </div>

        <div className="rounded-2xl border bg-card p-6 shadow-sm">
          <h1 className="font-heading text-lg font-semibold">Masuk ke akun Anda</h1>
          <p className="mt-1 text-sm text-muted-foreground">Gunakan email kerja Anda untuk melanjutkan.</p>

          <form data-testid={AUTH.loginForm} onSubmit={submit} className="mt-5 space-y-4">
            {error ? (
              <div data-testid={AUTH.errorAlert} className="flex items-center gap-2 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-800">
                <AlertCircle className="h-4 w-4 shrink-0" /> {error}
              </div>
            ) : null}
            <div className="space-y-1.5">
              <Label htmlFor="email">Email</Label>
              <Input data-testid={AUTH.emailInput} id="email" type="email" autoComplete="username"
                placeholder="nama@sipro.co.id" value={email} onChange={(e) => setEmail(e.target.value)} required />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="password">Kata Sandi</Label>
              <Input data-testid={AUTH.passwordInput} id="password" type="password" autoComplete="current-password"
                placeholder="••••••••" value={password} onChange={(e) => setPassword(e.target.value)} required />
            </div>
            <Button data-testid={AUTH.submitButton} type="submit" className="w-full" disabled={busy}>
              <LogIn className="h-4 w-4 mr-2" /> {busy ? "Memproses..." : "Masuk"}
            </Button>
          </form>

          <div className="mt-5 border-t pt-4">
            <p className="text-xs font-medium text-muted-foreground">Masuk cepat (akun demo · kata sandi Sipro#2026)</p>
            <div className="mt-2 flex flex-wrap gap-2">
              {QUICK.map((q) => (
                <button key={q.email} type="button" disabled={busy}
                  data-testid={`${AUTH.quickLoginPrefix}-${q.slug}`}
                  data-role-slug={q.slug}
                  aria-label={`Masuk cepat sebagai ${q.role}`}
                  title={`${q.role} — ${q.email}`}
                  onClick={() => submit(null, q.email)}
                  className="rounded-full border bg-secondary px-3 py-1 text-xs font-medium hover:bg-accent transition-colors disabled:opacity-50">
                  {q.role}
                </button>
              ))}
            </div>
          </div>
        </div>
        <p className="mt-4 text-center text-[11px] text-muted-foreground">
          Akun demo hanya untuk pengujian internal.
        </p>
      </div>
    </div>
  );
}

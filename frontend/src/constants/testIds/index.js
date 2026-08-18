// constants/testIds/ — central registry of data-testid values used by the
// end-to-end testing agent (qabot) to locate and interact with UI elements
// during automated tests. UI without testids cannot be automatically verified.
//
// Structure: each feature lives in its own file (auth.js, cart.js, ...) and
// is re-exported from here, so consumers can do a single import like
// `import { LOGIN, CART } from '@/constants/testIds'` (or relative).
//
// Adding a new feature:
//   1. Create constants/testIds/<feature>.js
//   2. Export named objects (e.g. `export const PROFILE = { ... }`)
//   3. Re-export here: `export * from './<feature>';`

export * from './offline';
export * from './auth';
export * from './home';
export * from './sales';
export * from './construction';
export * from './finance';
export * from './customers';
export * from './portal';
export * from './complaints';
export * from './permits';
export * from './field';
export * from './procurement';
export * from './gl';
export * from './appointments';
export * from './tax';
export * from './subconClaims';
export * from './inspection';
export * from './omni';
export * from './master';
export * from './sitePlan';
// Fase 27
export * from './pettyCash';
export * from './assets';
export * from './corpFinancing';
export * from './marketingFee';
// Fase 28b
export * from './showroom';
// Fase 31 — jadwal pembangunan berbukti per unit
export * from './build';
// Fase 33 — lingkup SPK, opname berbukti, kendali biaya RAB
export * from './opname';
// Fase 36 — Kalender Jadwal & master kalender kerja
export * from './buildCalendar';
// Fase 37 — Kalibrasi sekali klik durasi/waktu tunggu template jadwal
export * from './buildCalibration';
// Fase 39 — Pusat Konfigurasi + hierarki proyek/unit
export * from './configCenter';
// Fase 39b — checklist dokumen syarat (dipakai di layar lead & pelanggan)
export * from './docChecklist';
// Fase 40 — IA & Design System V2 (DataTable/FilterBar/TabPage/KPI drill-down + halaman kanonik)
export * from './ia';
// Fase 41 — umur tahap & kebijakan SLA (satu sumber ambang untuk semua daftar)
export * from './aging';
// Fase 42 — Mitra & Fee (master mitra, aturan fee, atribusi, analitik)
export * from './partners';
// Fase 43 — Kampanye & Biaya Iklan, Atribusi & CAPI, status integrasi, webhook lead mitra
export * from './ads';
// Fase 44 — Analitik & BI (5 dashboard persona + kamus metrik)
export * from './bi';

export * from './budget';
// Fase 46 — hub Pembangunan unit-centric: Papan Unit, kesiapan mulai bangun, Unit 360 →
// tab Pembangunan, dan izin bertingkat (proyek → cluster → blok → unit)
export * from './buildHub';

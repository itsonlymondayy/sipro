# SIPRO — CODEBASE MAP (hidup) — Fase 0 Fondasi

> SSOT peta file + endpoint. Perbarui saat menambah modul/endpoint (governance Dok 04 §7).

## Backend (`/app/backend`) — FastAPI, entry `server:app`
| File | Peran | Baris |
|---|---|---|
| `server.py` | App factory + lifespan (indexes, seed, scheduler) + router registry (/api) | ~69 |
| `db.py` | Motor client + config (ORG_ID, cookie, booking hold) dari `.env` | ~25 |
| `core_utils.py` | new_id, now_iso, iso, due_in, serialize_doc, parse_pagination | ~51 |
| `security.py` | JWT (HS256) + bcrypt; `get_current_user` (Bearer/cookie) | ~70 |
| `rbac.py` | DEFAULT_PERMISSIONS matrix, `require_permission`, `scope_query`, `audit_log` | ~163 |
| `engine.py` | Event Bus (outbox `emit`/`dispatch_pending`), handlers, Guided Work Engine (`auto_create_task`), Activity/Notif helpers, APScheduler jobs | ~206 |
| `models.py` | Pydantic request models | ~78 |
| `seed.py` | `ensure_indexes`, `seed_if_empty` (org + 9 users + permissions + demo project/units/leads/tasks) | ~141 |
| `routers/auth_router.py` | `/api/auth/login|register|me|logout` | ~72 |
| `routers/admin_router.py` | `/api/admin/users` (GET/POST/PUT), `/api/admin/permissions` (GET/PUT) | ~86 |
| `routers/work_router.py` | `/api/work/tasks` (+complete/snooze), `/api/work/home` (Role-Home KPI+NBA) | ~229 |
| `routers/activity_router.py` | `/api/activities` (+comment), `/api/notifications` (+read/read-all) | ~74 |

### Endpoint katalog (Fase 0)
- Auth: `POST /api/auth/login`, `POST /api/auth/register`, `GET /api/auth/me`, `POST /api/auth/logout`
- Work Hub: `GET/POST /api/work/tasks`, `PUT /api/work/tasks/{id}`, `POST /api/work/tasks/{id}/complete`, `POST /api/work/tasks/{id}/snooze`, `GET /api/work/home`
- Kolaborasi: `GET/POST /api/activities`, `POST /api/activities/{id}/comment`, `GET /api/notifications`, `POST /api/notifications/{id}/read`, `POST /api/notifications/read-all`
- Admin: `GET/POST /api/admin/users`, `PUT /api/admin/users/{id}`, `GET/PUT /api/admin/permissions`
- Sistem: `GET /api/`, `GET /api/health`

## Frontend (`/app/frontend/src`) — React 19, react-router, shadcn/ui
| File | Peran |
|---|---|
| `App.js` | Router + AuthProvider + protected/admin routes |
| `context/AuthContext.js` | State auth, login/logout, bootstrap `/auth/me` |
| `services/apiClient.js` | axios instance + Bearer token (localStorage) |
| `utils/formatters.js` | IDR, tanggal WIB, waktu relatif, due label, roleLabel |
| `config/navigationConfig.js` | PAGE_META, NAV_STRUCTURE, buildNavGroups(role), ROLE_HOME_REGISTRY |
| `components/layout/{AppShell,Sidebar,TopBar}.js` | Shell config-driven + role-aware |
| `components/patterns/*` | MetricCard, StatusPill, TaskCard, NBACard, ActivityItem, EmptyState, StateViews |
| `components/work/TaskInbox.js` | Buckets: Terlambat/Hari ini/Akan datang/Menunggu |
| `pages/{Login,Home,TasksPage,NotificationsPage,AdminUsers,AdminPermissions}.js` | Halaman fondasi |

## Engines (Dok 13)
- **Event Bus (outbox):** `events{status:pending→dispatched/failed}` + `dispatch_pending` (APScheduler tiap 8s).
- **Scheduler:** `reservation_expiry_sweeper` (300s), `sla_breach_check` (120s), `dispatcher_tick` (8s).
- **Guided Work Engine:** idempotent via `source_event`; handlers: `lead.created`, `lead.captured`, `message.received`.

## Koleksi (Fase 0)
`orgs, users, permission_settings, audit_logs, events, tasks, activities, notifications, leads(demo), projects(demo), units(demo)`.

## Gates (`/app/scripts`)
`seed_reset.sh` (drop DB + restart + jalankan semua gate) — semua HIJAU di DB bersih:
- `validate_compliance.py` — batas ukuran file (router ≤800, page/komponen ≤500, util ≤300, css ≤400)
- `health_check.py` — cek ISI endpoint kritis (bukan hanya 200)
- `verify_rbac.py` — RBAC denial + row-scope (sales vs sales2) + unauth 401
- `verify_api_contract.py` — (A) tidak ada duplicate FastAPI route; (B) setiap `api.<method>()` FE cocok route BE
- `check_nav_map.py` — nav config-driven vs route App.js + PAGE_META + Role-Home + deteksi dead page
- `audit_endpoint_sweep.py` — hit SEMUA GET /api sebagai owner, catat status/emptiness/error

## Kredensial uji
`/app/memory/test_credentials.md` (org PT SIPRO Land; sandi `Sipro#2026`).

## Phase 9 & 10 (fork continuation)
- **Backend:**
  - `routers/complaints_router.py` — Staff Complaint/CS: `GET /complaints`(+counts), `/complaints/stats`, `/complaints/{id}`, `POST /respond`, `PUT /status`, `POST /assign`. RBAC `complaints` (sales row-scoped ke `assigned_to`). Balasan → WhatsApp sim ke pembeli.
  - `routers/permits_router.py` — Permit tracker: `GET /permits`(+summary), `POST /permits`, `GET/PUT /permits/{id}`, `POST /permits/{id}/status`, `DELETE`. RBAC `permits` (PM full, site view+update).
  - `engine.permit_deadline_sweeper` (interval 900s) — task korektif + notifikasi PM saat izin due-soon/overdue.
  - `portal_router` — komplain baru kini simpan `assigned_to` (dari deal.assigned_to).
- **Frontend:**
  - `pages/ComplaintsPage.js` + `components/complaints/ComplaintDetailSheet.js` (nav grup "Layanan", SALES_SIDE).
  - `pages/PermitsPage.js` + `components/permits/{AddPermitDialog,PermitDetailSheet}.js` (nav "Perizinan & Dokumen" di grup Proyek, PROJECT_SIDE).
  - `ConstructionPage` — banner `curve-deviation-alert` saat Kurva-S `behind`.
  - testIds: `constants/testIds/{complaints,permits}.js`.
- **Koleksi baru:** `complaints` (seed 3: open/in_progress-breached/resolved), `permits` (seed 5: KRK/IMB approved, PBG submitted, SLF not_started, AMDAL overdue).
- **Status verifikasi:** gates 8/8 PASS; testing_agent_v3 iter.10 backend 153/153, frontend OK.

## Phase 11 — Field Ops (EPIC 2.8)
- **Backend:** `routers/field_router.py` — Site Diary (`/field/diaries`) + Punch List (`/field/punch`) dengan status open→in_progress→verified→closed. RBAC `field`.
- **Frontend:** `pages/FieldPage.js` + `components/field/*` (nav "Buku Harian & Punch" grup Proyek).
- **Status:** backend 166/166, frontend 95% (tanpa bug fungsional).

## Phase 12 — Pilar Pengadaan (EPIC 2.1 BoQ + 2.2 Subcon/SPK + 3.6 Anti-Fraud 3-way)
- **Backend:**
  - `routers/boq_router.py` — RAB/BoQ per proyek: `GET /boq/items`, `POST/PUT/DELETE /boq/items`, `GET /boq/summary` (budget vs committed(PO) vs actual(tagihan) + kategori). RBAC `boq` (PM full; finance/SM/site view).
  - `routers/subcon_router.py` — Subkontraktor + SPK: `GET/POST/PUT /subcon/subcontractors`, `GET/POST/PUT /subcon/spk`, `POST /subcon/spk/{id}/status`. RBAC `subcon`.
  - `routers/procurement_router.py` — PO→GRN→Tagihan + **3-way match**: `GET /procurement/pos`(+summary), `POST /pos`, `GET /pos/{id}` (grns+bills), `POST /pos/{id}/approve|cancel`, `GET/POST /grns`, `GET /threeway`, `POST /bills`. RBAC `procurement`.
  - **Kontrol anti-fraud:** (1) segregasi tugas — PM/site buat PO/GRN/tagihan, finance/owner *approve*; (2) *tiered approval* — PO > Rp 500 jt wajib Owner/super_admin; (3) *3-way match* — tagihan kumulatif > nilai barang diterima / nilai PO → `flagged` + task review urgent + notifikasi finance; (4) audit trail (`audit_logs` + activities). GRN material otomatis posting `material_txns` type `in`.
- **Frontend:**
  - `pages/{BoQPage,SubconPage,ProcurementPage}.js` — nav grup **"Pengadaan"** (PROCUREMENT_SIDE: owner/PM/site/finance).
  - `components/boq/AddBoQItemDialog.js`, `components/subcon/{SubcontractorsPanel,SPKPanel,AddSubcontractorDialog,AddSPKDialog,SubcontractorDetailSheet,SPKDetailSheet}.js`, `components/procurement/{POPanel,ThreeWayPanel,AddPODialog,PODetailSheet}.js`.
  - testIds: `constants/testIds/procurement.js`; status pill baru: matched/flagged/received/partially_received/completed.
- **Koleksi baru:** `subcontractors`(seed 2), `spk`(seed 2), `boq_items`(seed 6, budget Rp 472 jt), `purchase_orders`(seed 2), `grns`(seed 1); `ap_invoices` diperkaya `po_id/grn_id/match_status/match_detail` (seed: 1 matched + 1 flagged).
- **Guardrail:** `verify_data_integrity.py` CHECK 6 — referensial PO/GRN/SPK/BoQ + uang integer.

## Phase 13 — CoA / General Ledger (EPIC 3.4) — double-entry penuh
- **Backend:**
  - `gl_engine.py` — Chart of Accounts standar (19 akun), `post_journal()` (validasi seimbang + idempotent via `source_event`), `account_balances`, `trial_balance`, `income_statement`, `balance_sheet`, `ledger`. **Auto-posting** dari event outbox (tanpa mengubah finance_engine): `payment.received`→Dr Bank/Cr Uang Muka; `ap.approved`→Dr Persediaan/WIP/Beban, Cr Utang(+Retensi); `ap.paid`→Dr Utang/Cr Bank; `commission.approved`→Dr Beban Komisi/Cr Utang Komisi; `revenue.recognized`→Dr Uang Muka+AR/Cr Pendapatan & Dr HPP/Cr WIP. Handler didaftarkan ke `engine.HANDLERS` saat import.
  - `routers/gl_router.py` — `/gl/accounts`, `/gl/journals`(+POST manual balanced), `/gl/journals/{id}`, `/gl/ledger`, `/gl/trial-balance`, `/gl/income-statement`, `/gl/balance-sheet`, `/gl/summary`. RBAC `gl` (finance + owner/super_admin saja).
- **Frontend:** nav grup **"Akuntansi"** (FINANCE_SIDE): `pages/AccountingPage.js` (tabs Jurnal Umum, Buku Besar, Neraca Saldo, Bagan Akun) + `pages/AccountingReportsPage.js` (Laba Rugi + Neraca). `components/gl/*` (CoAPanel, JournalPanel, AddJournalDialog balanced-check, JournalDetailSheet, LedgerPanel, TrialBalancePanel, StatementsPanel). testIds `constants/testIds/gl.js`.
- **Koleksi baru:** `accounts`(19), `journal_entries`(seed: saldo awal + auto-post dari event). Seed: opening balance Rp 3 M + approve/pay AP demo + `dispatch_pending()` agar jurnal terposting saat seed.
- **Guardrail:** `verify_data_integrity.py` CHECK 7 — jurnal seimbang, akun valid, buku besar seimbang.

## Continuation — Wiring `CommissionBreakdown` ke Beranda
- **Frontend:** `pages/Home.js` — panel **"Komisi Saya"** (`components/sales/CommissionBreakdown.js`) kini dirender di kolom kanan Beranda, hanya untuk role dengan akses komisi: `sales, sales_manager, marketing_admin, owner, super_admin, finance` (via `canSeeCommission`). Data dari `GET /api/finance/commissions/summary` (testIds `COMM_HOME` di `constants/testIds/appointments.js`).
- **Status verifikasi:** 8/8 gates PASS (DB bersih via `seed_reset.sh`); testing_agent_v3 iter.14 frontend 100% (6/6 role-based access tests — panel tampil untuk role berwenang, tersembunyi untuk PM/site).

## Phase 14 — EPIC 1.2 Appointment & Survey + EPIC 1.6 Commission Breakdown (SELESAI & TERVERIFIKASI)
- **Backend (sudah ada, terverifikasi):** `routers/survey_router.py` (`/surveys` list/create/detail/update/`/result`/`/photos` via storage), `routers/leads_router.py` `GET /appointments` (+filter status/date_from/date_to), `routers/commissions_router.py` (`/finance/commissions` + `/summary` + `/{id}/approve` + `/{id}/pay`), `finance_engine.pay_commission()`, `gl_engine` handler `commission.paid` (Dr Utang Komisi / Cr Bank, idempotent). RBAC baru: `appointments`, `surveys`. `verify_data_integrity.py` CHECK 8.
- **Frontend (wiring diselesaikan pada continuation):** `pages/AppointmentsPage.js` (route baru `/appointments`) — Kalender bulanan (shadcn Calendar + dot hari ber-appointment) + Agenda harian + filter status; `components/appointments/{AppointmentDetailSheet,SurveyPanel}.js` (kelola status appointment + survey: checklist toggle, upload foto, hasil/rekomendasi). `components/sales/CommissionBreakdown.js` dirender di `Home.js` (role-gated). `components/finance/CommissionsPanel.js` (tombol "Bayar" komisi approved) di tab Komisi `FinancePage`. Nav item **"Agenda & Survey"** (`CalendarDays`) di grup **Penjualan**; `App.js` route + `navigationConfig.js` PAGE_META/NAV_STRUCTURE ditambahkan. testIds `constants/testIds/appointments.js` (APPTS/SURVEY/COMM_HOME).
- **Koleksi:** `appointments`(seed 3: survey-done/meeting-scheduled/survey-scheduled), `surveys`(seed 2: in_progress + completed-recommended w/ foto), `commissions` (pending/approved/paid).
- **Status verifikasi:** `seed_reset.sh` → **8/8 gates PASS**; testing_agent_v3 iter.15 → backend 100% (13/13), frontend ~95% (2 temuan = false-positive, diverifikasi ulang OK).

## Phase 15 — EPIC 3.3 Perpajakan / Tax Management (SELESAI & TERVERIFIKASI)
- **Backend:** `tax_engine.py` (baru — `tax_summary`, `ppn_input` estimasi PPN Masukan dari AP inklusif, `issue_faktur` idempoten, `faktur_pdf_bytes`), `routers/tax_router.py` (baru, prefix `/tax`: `/summary`,`/periods`,`/ppn-input`,`/records`, `PUT /records/{id}`, `/faktur`,`/faktur-candidates`, `POST /faktur`, `/faktur/{id}` + `/faktur/{id}/pdf`). Model `TaxRecordUpdate`/`FakturIssue`. RBAC resource `tax` (finance `manage`; owner/super_admin full). Koleksi baru `faktur_pajak` (index unik org_id+deal_id). `verify_data_integrity.py` **CHECK 9**.
- **Sumber pajak:** PPN Keluaran / PPh Final 4(2) / BPHTB dari `tax_records` (per-deal, dibuat finance_engine saat AR). PPN Masukan = estimasi worksheet dari `ap_invoices` (inklusif). Faktur Pajak Keluaran = koleksi `faktur_pajak` + PDF (reportlab). **Bukan e-Faktur resmi DJP.**
- **Frontend:** `pages/TaxPage.js` (route `/tax`, 3 tab: Ringkasan & SPT PPN / Faktur Pajak / Catatan Pajak) + `components/tax/{TaxSummaryPanel,FakturPanel,IssueFakturDialog,TaxRecordsPanel}.js`. Nav **"Perpajakan"** (`Landmark`, grup Akuntansi, `FINANCE_SIDE`) di `navigationConfig.js` + route `App.js`. testIds `constants/testIds/tax.js`; StatusPill + pill CSS `reported`/`issued`.
- **Status verifikasi:** `seed_reset.sh` → **8/8 gates PASS**; testing_agent_v3 iter.16 → **backend 100% (192/192, 26 tes pajak)**, **frontend 100%** (RBAC nav finance-only, terbitkan faktur idempoten + PDF, kelola status pajak, regresi). 0 bug.

## Phase 16 — EPIC 2.3 Progress Claim (Termin) & Change Order (SELESAI & TERVERIFIKASI)
- **Backend:** `routers/subcon_claims_router.py` (baru, prefix `/subcon`): Progress Claim (`/claims` list+summary, `POST` ajukan, `/{id}/verify` opname, `/{id}/approve` → **buat+approve tagihan AP** (retensi+GL) & majukan progres SPK, `/{id}/reject`) + Change Order (`/change-orders` list, `POST`, `/{id}/approve` → update nilai kontrak SPK, `/{id}/reject`). Model `ProgressClaim*`/`ChangeOrderCreate`/`StatusNote`. RBAC resource baru `progress_claims` & `change_orders` (SoD: field ajukan/opname, finance/owner setujui). Koleksi baru `progress_claims`, `change_orders`. `seed_phase16.py` (jaga seed.py<800). `verify_data_integrity.py` **CHECK 10**.
- **Integrasi:** termin disetujui → `finance_engine.create_ap_bill`+`approve_ap_bill` (retensi ditahan sesuai SPK, posting Buku Besar). Change order disetujui → `spk.contract_value` diperbarui (guardrail nilai baru >0 & ≥ tertagih).
- **Frontend:** tab **"Progress & Termin"** (`components/subcon/ClaimsPanel.js` + `SubmitClaimDialog.js`) di `SubconPage.js`; **`components/subcon/ChangeOrdersSection.js`** disematkan di `SPKDetailSheet.js`. testIds `constants/testIds/subconClaims.js`; StatusPill label `submitted`/`verified`/`rejected`.
- **Status verifikasi:** `seed_reset.sh` → **8/8 gates PASS**; testing_agent_v3 iter.17 → backend 18/19 (1 "gagal" = guardrail menolak nilai negatif dengan benar, bukan bug), frontend 100% (opname/approve/AP bill, CO update nilai kontrak, RBAC SoD, regresi). 0 bug.


## Phase 17 — EPIC 2.4 QC/Inspeksi (SELESAI & TERVERIFIKASI)
- **Backend:** `routers/inspection_router.py` (prefix `/inspections`, RBAC resource `construction`): `GET /templates`, `GET ` (list+summary open/passed/failed, scope proyek utk PM/site), `POST ` (dari template/kustom + phase/unit opsional, nomor `QC/YYYY/####`), `GET /{id}`, `PUT /{id}/items` (set hasil pass/fail/na + note, recompute counts), `POST /{id}/finalize`. **Finalize FAIL** → status `failed`, tiap item gagal jadi `punch_item` + task korektif **urgent** ke PM, phase→`qc_hold` (unit→`qc_hold`), emit `qc.failed`. **Finalize PASS** → `passed`; kategori `handover`+unit → unit `ready_handover` (kesiapan BAST), phase qc_hold→in_progress, emit `qc.passed`. `seed_phase17.py`: 3 template (QC-STR/QC-MEP/QC-HO) + 1 inspeksi demo `in_progress`. Registrasi di `server.py`; seed dari `seed.py`.
- **Frontend:** `components/construction/InspectionsPanel.js` disematkan di `pages/ConstructionPage.js` (halaman "Progres & QC"): chips ringkasan (Total/Berjalan/Lulus/Gagal), daftar inspeksi, dialog **Inspeksi Baru** (template + fase opsional), dialog **Detail** (set hasil item pass/fail/na + catatan, "Simpan Hasil", "Finalisasi" pass/fail), RBAC `canUpdate` (owner/super_admin/PM/site). testIds `constants/testIds/inspection.js`.
- **Koleksi:** `inspections`, `inspection_templates`; `punch_items` diperkaya `source='inspection'`+`inspection_id`.
- **Status verifikasi:** `seed_reset.sh` → **8/8 gates PASS** di DB bersih; `testing_agent_v3` iter.18 → **backend 100% (18/18)**, **frontend 100% (7/7)** (buat inspeksi, set hasil, finalisasi pass & fail + punch, RBAC finance view-only/sales 403, regresi). **0 bug, 0 action item.** Object storage = mongo fallback (`STORAGE_PROVIDER=mongo`).


## Phase 18 — EPIC 2.6 Material Ledger + Requisition + Anggaran RAB (SELESAI & TERVERIFIKASI)
- **Backend:** `routers/materials_router.py` diperdalam (prefix `/materials`, RBAC resource `materials`): (a) **Requisition** `GET/POST /requisitions`, `GET /requisitions/{id}`, `POST /{id}/approve|reject|issue`; SoD — site **mengajukan** (create) & **mengeluarkan** (update), PM **menyetujui** (approve). (b) **Issue-to-task**: transaksi `out` menyimpan `requisition_id/phase_id/task_id`; guard stok. (c) **Anggaran RAB**: `GET /project/{id}/budget` (budget_qty vs consumed) + `PUT /{material_id}/budget`; material ditaut ke item BoQ (`boq_item_id`). (d) **Alert > BoQ**: helper `_check_material_budget` set `over_budget` + tugas urgent + notifikasi ke PM (idempotent `material.overbudget:{id}`) + event. `seed_phase18.py` (dipanggil `seed.py` setelah boq_items terisi): taut 4 material ke RAB + 2 requisition demo (1 approved, 1 issued BTA 5000 → over RAB 4000). `models.py`: RequisitionCreate/RequisitionIssue/MaterialBudgetSet + MaterialCreate(+boq_item_id,budget_qty). `rbac.py`: materials + `approve` utk PM.
- **Frontend:** `pages/MaterialsPage.js` kini **3 tab** (Tabs terkontrol, tab persist saat reload): **Stok & Buku Besar** (tabel + ledger + transaksi/opname), **Permintaan Material** (`components/materials/RequisitionsPanel.js` — chips, buat/ setujui/ tolak/ keluarkan, detail read-only), **Anggaran (RAB)** (`components/materials/BudgetPanel.js` — kartu per-material + bar; badge merah "Melebihi RAB"). testIds di `constants/testIds/construction.js` (REQUISITION, MATBUDGET).
- **Koleksi:** `material_requisitions` (baru); `materials` diperkaya `boq_item_id/budget_qty/consumed_qty/over_budget`; `material_txns` diperkaya `requisition_id/phase_id/task_id`.
- **Gate:** `verify_data_integrity` +CHECK 12 (requisition referensial + qty_issued≤requested + boq link valid). **8/8 gates PASS**. `testing_agent_v3` iter.19 → **backend 100% (21/21)**, **frontend 95→100%** (fix: hapus duplikat testid di detail dialog + Tabs terkontrol agar tab tidak reset). 0 bug tersisa.


## Phase 19 — EPIC 3.3 Tax → GL Setoran Journal + NTPN (SELESAI & TERVERIFIKASI)
- **Backend:** `gl_engine.py` +akun CoA **6-1400 Beban Pajak** (expense) + helper `post_tax_accrual` (Dr 6-1400 / Cr **2-1300 Utang Pajak**, idempotent `tax.accrue:{id}`) & `post_tax_payment` (jamin akrual dulu → Dr 2-1300 / Cr **1-1200 Bank**, memo + **NTPN**, idempotent `tax.setor:{id}`). `routers/tax_router.py` `PUT /tax/records/{id}`: transisi status `reported` → posting akrual; `paid` → posting setoran (**NTPN wajib**, else 400) + simpan `gl_accrual_entry_no`/`gl_setor_entry_no` di catatan. `seed_phase19.py` (dipanggil `seed.py` setelah dispatch): tandai 1 catatan PPh `paid` + NTPN + posting 2 jurnal (demo Buku Besar). Idempotensi lewat `post_journal(source_event=...)`; Trial Balance tetap seimbang (Utang Pajak net 0 setelah setor).
- **Frontend:** `components/tax/TaxRecordsPanel.js` (halaman Perpajakan → tab Catatan Pajak): kolom **"Jurnal GL"** (badge hijau `gl_setor_entry_no`), dialog status — pilih "Disetor" menampilkan hint jurnal setoran + **NTPN wajib** (validasi klien+server), pilih "Dilaporkan" menampilkan hint akrual; toast sukses menyebut nomor jurnal GL. testId `recordGlLink`.
- **Koleksi:** `journal_entries` bertambah `source_type` `tax_accrual`/`tax_setor`; `tax_records` diperkaya `gl_accrual_entry_no`/`gl_setor_entry_no`/`gl_setor_entry_id`.
- **Status verifikasi:** **8/8 gates PASS** (TB balanced via CHECK GL). `testing_agent_v3` iter.20 → **backend 100% (18/18)** (reported→akrual, paid→setoran+NTPN, paid tanpa NTPN 400, idempotent, TB balanced, akun 2-1300/6-1400), **frontend** semua fitur utama jalan (badge Jurnal GL, dialog hint, validasi NTPN). **0 bug, 0 action item.**


## Phase 20 — EPIC 1.4 Legal Milestone Tracker: PPJB → AJB → SOLD (SELESAI & TERVERIFIKASI)
Menutup lingkar penjualan: setelah `booked`, deal melaju ke **PPJB** (Perjanjian Pengikatan Jual Beli) lalu **AJB** (Akta Jual Beli) yang menyelesaikan deal (`completed`) + menandai unit **`sold`**.
- **Backend:** `routers/deals_router.py` + endpoint: `GET /deals/{id}/legal` (ringkasan pembayaran dari `ar_invoices` {price/paid/outstanding/paid_pct} + status KPR dari `financing_apps` {bank/status/plafon/tenor} + timeline). `POST /deals/{id}/ppjb` (guard status `booked`; nomor `PPJB/YYYY/####`; simpan `legal_stage=ppjb`, `ppjb{number,signed_date,dp_pct,...}`; emit `deal.ppjb` + tugas jadwalkan AJB). `POST /deals/{id}/ajb` (guard `legal_stage=ppjb`; nomor `AJB/YYYY/####` + notaris; set `legal_stage=ajb`, `status=completed`, `sold_at`; unit → `status=sold`; emit `deal.ajb` + `deal.sold`). `models.py`: `PpjbSign`, `AjbSign`. RBAC resource `deals` (update).
- **Frontend:** `components/sales/DealLegalDialog.js` (dipakai di `pages/DealsPage.js`): stepper **Reservasi→Booking→PPJB→AJB/Lunas**, bar pembayaran + info **KPR**, kartu PPJB/AJB, tombol **Tandatangani PPJB/AJB** (form nomor+notaris), badge **"Unit terjual (SOLD)"**. Baris deal menampilkan badge legal_stage (PPJB / AJB·SOLD). testIds di `constants/testIds/sales.js` (legalBtn/ppjbSignBtn/ajbSignBtn/legalSubmit/…).
- **Koleksi:** `deals` diperkaya `legal_stage`/`ppjb`/`ajb`/`sold_at`; `units` → `sold` + `sold_at`.
- **Status verifikasi:** **8/8 gates PASS**. `testing_agent_v3` iter.21 → **frontend 100%**, **backend Phase 20 semua lolos** (GET legal + PPJB + AJB + guards 400 + unit sold); 1 "fail" hanya mismatch assertion tester pada `/api/work/home` (bukan bug, di luar cakupan Phase 20). **0 bug fungsional.**



## Lapisan Integritas Data (Fase 24 — audit forensik)
| File | Peran |
|---|---|
| `backend/reference.py` | **SSOT enum**: 32 grup nilai kanonik + label ID, sinonim, `CHANNEL_TO_SOURCE`, `SOURCE_SCORE`, tipe `Annotated` untuk models |
| `backend/sequences.py` | Nomor dokumen **atomik** (`counters`, `$inc`) per org+tahun — mengganti `count_documents+1` |
| `backend/denorm.py` | `DENORM_MAP`, `cascade_master_change()`, `resync_all()`, `audit_stale()` — jaga SSOT field kopi |
| `backend/migrations.py` | Migrasi idempoten saat startup: kanonikalisasi enum, normalisasi telepon E.164, backfill counter, resync denormalisasi |
| `backend/indexes.py` | 24 unique index natural key (partial untuk field opsional) |
| `backend/models_master.py` | Model request master data (ProjectUpdate, UnitUpdate, PhaseUpdate, SchemeUpdate, template, dll) |
| `backend/routers/reference_router.py` | `GET /api/reference[/{group}]` — daftar pilihan untuk seluruh form frontend |
| `backend/routers/master_router.py` | CRUD `/api/master/doc-templates`, `/api/master/qc-templates`, `GET /api/master/data-health` |
| `frontend/src/context/ReferenceContext.js` | Provider daftar pilihan (fetch sekali), `options()`, `labelOf()` |
| `frontend/src/components/patterns/ReferenceSelect.js` | Dropdown terkontrol (mendukung grup dinamis + “Nilai baru…”) |
| `frontend/src/pages/MasterDataPage.js` | Admin → Master Data & Integritas (Template Dokumen / Template QC / Kesehatan Data) |
| `frontend/src/pages/AuditLogsPage.js` | Admin → Jejak Audit (filter objek/aksi) |

### Endpoint tambahan Fase 24
- Reference: `GET /api/reference`, `GET /api/reference/{group}`
- Master data: `GET/POST/PUT/DELETE /api/master/doc-templates[/{id}]`, `GET/POST/PUT/DELETE /api/master/qc-templates[/{id}]`, `GET /api/master/data-health`
- Koreksi master: `PUT /api/projects/{id}`, `PUT|DELETE /api/projects/{pid}/units/{uid}`, `PUT|DELETE /api/construction/phases/{id}`, `PUT /api/materials/{id}`, `PUT /api/gl/accounts/{code}`, `PUT /api/finance/config/payment-schemes/{id}`, `PUT /api/finance/config/commission-schemes/{id}`
- Transparansi: `GET /api/admin/audit-logs`, `GET /api/finance/ap/payments`

### Gate tambahan
`scripts/forensic_audit.py` — SSOT/duplikasi/FK yatim/cacat form (gate ke-9, wajib hijau).


## Fase 25 — Site Plan Interaktif (EPIC P29) + Kelengkapan Akuntansi (P25)

### 25a — Site Plan / Showroom Digital (EPIC P29)
| File | Peran |
|---|---|
| `backend/routers/site_plan_router.py` | (sudah ada, **kini di-register di `server.py`**) `GET /api/site-plan/{project_id}` auto-layout blok/kavling + statistik absorpsi; `PUT /api/site-plan/{project_id}/layout` simpan posisi kustom (izin `projects:update`) |
| `backend/seed_phase25.py` | Kavling demo multi-blok (blok B & C, 12 kavling: tipe besar, ruko, kavling siap bangun) — idempoten, dipanggil di lifespan `server.py` |
| `frontend/src/pages/SitePlanPage.js` | Halaman `/site-plan`: pilih proyek, 5 KPI (total/tersedia/reserved+booked/absorpsi/nilai tersedia), filter status+tipe+cari, zoom, legenda, peta |
| `frontend/src/components/siteplan/PlotMap.js` | Peta kavling absolut-posisi: blok dipisah "jalan", warna per status, bar progres konstruksi, kavling redup bila tak cocok filter |
| `frontend/src/components/siteplan/PlotDetailSheet.js` | Detail kavling (harga, luas, orientasi/hook, progres, status bayar, pembeli) + tombol **Reservasi** (reuse `ReserveDialog` mode byUnit) |
| `frontend/src/components/siteplan/PlanLegend.js` | Legenda + hitungan per status (SSOT warna kavling) |
| `frontend/src/constants/testIds/sitePlan.js` | testIds `site-plan-*` (plot punya `data-unit-code`/`data-unit-status` sebagai pembeda baris) |
- Nav: item **Site Plan** untuk sisi penjualan & sisi proyek (`navigationConfig.js` + PAGE_META + route `App.js`).
- Klik-booking: kavling `available` → Reservasi (pilih lead + booking fee) → `POST /api/deals/reserve` (atomic anti double-booking) → peta & KPI ikut berubah.

### 25b — Kelengkapan Akuntansi (P25)
| File | Peran |
|---|---|
| `backend/gl_reports.py` | Mesin laporan **berperiode**: `worksheet()` (Neraca Lajur), `income_statement()` (+pembanding), `balance_sheet(as_of)`, `cash_flow()` (metode langsung, klasifikasi operasi/investasi/pendanaan), `project_report()` (segment per proyek), `ratios()` (likuiditas/solvabilitas/profitabilitas + interpretasi), `ledger()` (drill-down berperiode) |
| `backend/gl_periods.py` | Tutup periode: `accounting_periods`, `resolve_post_date()` — jurnal **manual** di periode tertutup ditolak; posting **otomatis** digeser ke periode terbuka + catatan memo (transaksi nyata tidak pernah hilang) |
| `backend/gl_engine.py` | `post_journal()` kini memanggil guard tutup-periode sebelum membukukan |
| `backend/routers/gl_reports_router.py` | `GET /api/gl/reports/{worksheet,income-statement,balance-sheet,cash-flow,projects,ratios,ledger}`, `GET /api/gl/periods`, `POST /api/gl/periods/close` (finance), `POST /api/gl/periods/reopen` (owner/super_admin — SoD) |
| `frontend/src/pages/AccountingReportsPage.js` | 7 tab laporan + `PeriodPicker` bersama + drill-down sheet |
| `frontend/src/components/gl/PeriodPicker.js` | Periode dari/sampai + preset (bulan ini/lalu, kuartal, tahun berjalan, tahun lalu) |
| `frontend/src/components/gl/IncomeStatementPanel.js` | Laba Rugi: KPI + pertumbuhan vs periode lalu, HPP→laba kotor, beban operasi, ekspor CSV, klik akun → drill-down |
| `frontend/src/components/gl/BalanceSheetPanel.js` | Neraca per tanggal: aset lancar/tidak lancar, liabilitas pendek/panjang, ekuitas + laba berjalan, badge seimbang |
| `frontend/src/components/gl/WorksheetPanel.js` | Neraca Lajur 14 kolom (awal|transaksi|penyesuaian|akhir|L/R|Neraca) + total + badge seimbang |
| `frontend/src/components/gl/CashFlowStatementPanel.js` | Arus Kas: 5 KPI, 3 seksi aktivitas, badge rekonsiliasi kas awal+perubahan=kas akhir |
| `frontend/src/components/gl/ProjectPLPanel.js` | Laba Rugi per proyek + belanja WIP/material + bucket "Tidak teralokasi" (jujur) |
| `frontend/src/components/gl/RatiosPanel.js` | 10 rasio + status Sehat/Perhatian/Berisiko/Belum cukup data + dasar perhitungan |
| `frontend/src/components/gl/PeriodClosePanel.js` | Daftar periode (jurnal/pendapatan/beban/laba), Tutup (finance) & Buka kembali (owner) dengan ConfirmDialog |
| `frontend/src/components/gl/LedgerDrillSheet.js` | Drill-down: laporan → buku besar akun (saldo awal/mutasi/akhir) → dialog jurnal asal |
| `frontend/src/utils/csv.js` | Ekspor CSV klien (delimiter `;`, BOM UTF-8 agar rapi di Excel Indonesia) |
- Koleksi baru: `accounting_periods` (org_id, period, status, closed_by/at, reopened_by/at, note).
- Semua angka dihitung dari `journal_entries` (tanpa estimasi/mock); nilai yang tak bisa dilacak ke proyek ditampilkan sebagai "Tidak teralokasi".

## Fase 26 — SSOT penuh + Kebenaran Uang ("perbaiki semua temuan")

### Lapisan SSOT (kamus data tunggal)
| File | Peran |
|---|---|
| `backend/reference.py` | **74 grup** nilai terkontrol (naik dari 43). Tambahan Fase 26: `po_status`, `spk_status`, `punch_status`, `threeway_status`, `stock_movement`, `qc_result`, `signer_role`, `scheme_basis`, `financing_status`, `slik_status`, `financing_bank`, `appointment_status`, `activity_type`, `msg_direction`, `automation_trigger`, `automation_action`, `survey_check_status`, `survey_result`, `survey_status`, `inspection_item_result`, `inspection_status`, `document_status`, `deal_status`, `legal_stage`, `unit_payment_status`, `ar_status`, `ap_status`, `commission_status`, `collection_bucket`, `deposit_txn`, `tax_status`, `faktur_status`, `requisition_status`, `claim_status`, `change_order_status`, `org_status`, `vendor`, `document_template`, `inspection_template`, `wa_template_status`, `notification_type` |
| `backend/models.py` | 23 field enum tambahan kini bertipe Annotated SSOT (total 67 field tervalidasi). Tidak ada lagi `status: str` bebas |
| `backend/server.py` | Handler `RequestValidationError` → **400 + pesan Indonesia terbaca** (dulu 422 dengan detail objek → toast `[object Object]`) |
| `backend/routers/reference_router.py` | Grup dinamis mendukung **beberapa sumber** (`sources`) — mis. `vendor` dikumpulkan dari master subkontraktor + vendor pada tagihan & PO |
| `backend/routers/portal_router.py` | `GET /api/portal/reference` — subset kamus untuk portal pembeli (portal tidak boleh memakai token staf) |
| `frontend/src/components/patterns/RefLabel.js` | Komponen label enum dari SSOT (`<RefLabel group="po_status" value={...} />`) |
| `frontend/src/components/patterns/StatusPill.js` | Semua pemakaian di halaman staf kini memberi `group="..."`; peta label lokal tinggal fallback **khusus portal** |
- Vocabulary duplikat DIHAPUS: `financing_router.VALID_STATUS`, `gl_engine.VALID_TYPES`,
  `omnichannel_router.VALID_EVENTS/VALID_ACTIONS`, `tax_engine.TAX_TYPES/RECORD_STATUSES`,
  literal `("pass","fail")`, `("in","out")`, `("scheduled","done",…)`, plus **30 peta/daftar label
  hardcode di 25 file frontend**.
- UI baru: **Master Data → tab "Kamus Data (SSOT)"** (`components/master/ReferencePanel.js`) —
  74 grup / 350+ nilai, pencarian, badge *Terkunci* vs *Bisa tambah nilai*.

### Lapisan Kebenaran Uang (titipan pelanggan)
| File | Peran |
|---|---|
| `backend/finance_engine.py` | `_allocate()` (alokasi termin jatuh tempo terlama dulu), `apply_receipt(..., allow_overpay)` — kelebihan **ditolak 400** kecuali disetujui lalu jadi titipan; `receive_deposit()`, `apply_deposit()`, `refund_deposit()`, `deposits_total()`; `pay_ap_bill()` kini menolak bayar > sisa tagihan |
| `backend/gl_engine.py` | CoA baru **`2-1450 Titipan Pelanggan (Kelebihan Bayar)`**; `ensure_coa()` idempoten **per kode akun** (dulu hanya saat koleksi kosong sehingga akun baru tak pernah muncul); handler `deposit.received` (Dr 1-1200/Cr 2-1450), `deposit.applied` (Dr 2-1450/Cr 2-1400), `deposit.refunded` (Dr 2-1450/Cr 1-1200) |
| `backend/routers/ar_router.py` | `GET /api/finance/ar/deposits`, `POST /api/finance/ar/{deal_id}/deposit`, `…/deposit/apply`, `…/deposit/refund`; detail AR menyertakan saldo titipan |
| `backend/routers/financing_router.py` | Pencairan KPR otomatis dibukukan sebagai penerimaan AR (`book_to_ar`, metode `kpr`) + `receipt_id` disimpan pada entri pencairan |
| `backend/models_finance.py` | `DepositReceive` / `DepositApply` / `DepositRefund` (dipisah agar `models.py` tetap < 800 baris) |
| `frontend/src/components/finance/DepositPanel.js` | Tab **Titipan**: 4 KPI, tabel saldo/masuk/dipakai/dikembalikan/sisa tagihan, Terima–Gunakan–Kembalikan + dialog riwayat mutasi |
| `frontend/src/components/finance/ReceiptDialog.js` | Metode dari SSOT + kotak peringatan kelebihan bayar (nominal tepat) + checkbox persetujuan; tombol simpan nonaktif sampai dicentang |
| `frontend/src/components/finance/ApPanel.js` | Dialog bayar dibatasi sisa tagihan (peringatan merah + tombol nonaktif) |
| `frontend/src/components/customers/FinancingDialogs.js` | Bank = dropdown SSOT; dialog pencairan punya opsi "Bukukan sebagai penerimaan AR" (default aktif) |
| Koleksi baru | `customer_deposits` (org_id, deal_id, unit_code, balance, received_total, applied_total, refunded_total, entries[]) |

### Gate (11 — semua blocking)
`validate_compliance`, `health_check`, `verify_rbac`, `verify_api_contract`, `check_nav_map`,
`audit_endpoint_sweep`, `verify_data_integrity`, `ux_audit`, `forensic_audit`,
**`audit_forms_deep`** (E1 dropdown wajib, E2 angka, E3 tanggal, E4 label/aria, **E5 vocabulary
hardcode**), **`verify_business_invariants`** (AR/AP/komisi/KPR/unit↔deal + **titipan** +
tie-out `2-1400/2-1100/2-1200/2-1600/2-1450` ke buku besar).
Alat verifikasi tambahan: `scripts/verify_f26_money.py` (33 asersi HTTP end-to-end untuk uang & enum).


## Phase 27 — Kas Bon + Aset Tetap + Pembiayaan Korporat + Marketing Fee (SELESAI & TERVERIFIKASI)
- **Backend (file baru):**
  | File | Peran |
  |---|---|
  | `reference_p27.py` | 18 grup SSOT baru + `TAX_GROUP_MONTHS` (kelompok fiskal Pasal 11 UU PPh) + `CASHBON_ACCOUNT` (kategori→akun) ; digabung ke `reference.GROUPS` |
  | `models_p27.py` | Request model 4 modul, semua field pilihan pakai Annotated validator SSOT |
  | `p27_utils.py` | `cash_account`, `period_of/validate_period/period_end_iso`, `month_add`, `days_overdue`, `rp` |
  | `petty_cash.py` | Siklus kas bon + jurnal + sweeper pengingat belum dipertanggungjawabkan |
  | `fixed_assets.py` | Register aset, `monthly_amount`, `schedule`, `run_depreciation` (idempoten/periode), `dispose_asset`, AP otomatis untuk perolehan utang |
  | `loans.py` | `build_schedule` (anuitas/pokok_tetap/flat, Σ pokok tepat), `activate_loan`, `pay_installment`, `loan_metrics`, `annotate_schedule` (`amount_due`), sweeper jatuh tempo |
  | `marketing_fee.py` | Master agen + pengajuan/approve/reject/pay fee + PPh + papan peringkat |
  | `seed_phase27.py` | Demo idempoten (marker `finance_configs.seed_phase27`) lewat engine, bukan insert mentah |
- **CoA baru (`gl_engine.STANDARD_COA`, idempoten per kode):** `1-1500`, `1-2100`, `1-2200`, `2-1500`,
  `2-2100`, `4-1300`, `6-1500`, `6-1600`, `6-1800`.
- **Endpoint baru:**
  - Kas Bon: `GET /api/petty-cash/advances`, `GET /api/petty-cash/summary`, `GET /api/petty-cash/advances/{id}`, `POST /api/petty-cash/advances`, `POST /api/petty-cash/advances/{id}/approve|reject|cancel|disburse|settle`
  - Aset Tetap: `GET /api/fixed-assets/assets`, `GET /api/fixed-assets/summary`, `GET /api/fixed-assets/depreciations`, `GET /api/fixed-assets/assets/{id}`, `POST /api/fixed-assets/assets`, `POST /api/fixed-assets/depreciation/run`, `POST /api/fixed-assets/assets/{id}/dispose`
  - Pembiayaan: `GET /api/corp-financing/loans`, `GET /api/corp-financing/summary`, `GET /api/corp-financing/payments`, `GET /api/corp-financing/loans/{id}`, `POST /api/corp-financing/loans`, `POST /api/corp-financing/loans/{id}/activate|pay`
  - Marketing Fee: `GET/POST /api/marketing/agents`, `PUT /api/marketing/agents/{id}`, `GET /api/marketing/fees`, `GET /api/marketing/summary`, `GET /api/marketing/fees/{id}`, `POST /api/marketing/fees`, `POST /api/marketing/fees/{id}/approve|reject|pay`
- **RBAC:** resource `petty_cash` (semua peran create; finance/owner approve), `fixed_assets` (finance/owner; PM view), `loans` (finance/owner), `marketing_fee` (sales/marketing ajukan; finance/owner approve+bayar).
  `migrations.sync_permission_matrix()` menambahkan resource baru ke matriks RBAC yang tersimpan di DB
  (tanpa migrasi ini semua peran non-owner mendapat 403 pada modul rilis baru).
- **Frontend:** `pages/{PettyCashPage,FixedAssetsPage,CorporateFinancingPage,MarketingFeePage}.js`;
  `components/pettyCash/{RequestAdvanceDialog,DisburseAdvanceDialog,SettleAdvanceDialog,AdvanceDetailSheet}.js`;
  `components/fixedAssets/{AssetsPanel,AddAssetDialog,AssetDetailSheet,DisposeAssetDialog,DepreciationPanel}.js`;
  `components/loans/{LoansPanel,AddLoanDialog,LoanDetailSheet,PayInstallmentDialog,LoanPaymentsPanel}.js`;
  `components/marketingFee/{FeesPanel,AgentsPanel,AgentDialog,SubmitFeeDialog,PayFeeDialog}.js`;
  testIds `constants/testIds/{pettyCash,assets,corpFinancing,marketingFee}.js`; nav grup **Kas & Pengeluaran**
  (Kas Bon, semua peran), **Keuangan** (+Marketing Fee), **Akuntansi** (+Aset Tetap, +Pembiayaan Korporat);
  status pill baru: `disbursed`, `settled`, `fully_depreciated`, `disposed`, `restructured`, `inactive`, `blacklist`.
- **Koleksi baru:** `cash_advances`, `fixed_assets`, `asset_depreciations`, `loans`, `loan_payments`,
  `agents`, `marketing_fees` (+ index unik nomor dokumen & `asset_depreciations(org_id,asset_id,period)`
  sebagai kunci idempotensi penyusutan di level DB).
- **Guardrail:** `verify_business_invariants.py` +4 blok (1-1500 / 1-2100+1-2200 / 2-2100 / 2-1500),
  `verify_data_integrity.py` **CHECK 13**, `forensic_audit.py` `ENGINE_MANAGED` untuk 7 koleksi baru,
  `audit_forms_deep.py` pencocokan batas kata (hilangkan false positive "pe-role-han").
- **Status verifikasi:** `seed_reset.sh` → **11/11 gates PASS**; POC `scripts/verify_p27_money.py`
  **90/90 PASS**; testing_agent_v3 iterasi 34 (0 bug kritis/UI) + verifikasi Playwright main agent.

## Fase 28a — Site Plan interaktif berbasis SVG
- **Backend:** `site_plan_svg.py` (generator geometri realistis + parser SVG aman + auto-match +
  statistik cakupan); `routers/site_plan_router.py` diperluas: `POST /{id}/generate`,
  `POST /{id}/svg`, `PUT /{id}/mapping`, `DELETE /{id}/plan`, `GET /{id}/unit/{unit_id}`.
- **Koleksi baru:** `site_plans` (per proyek: `view_box`, `source`, `shapes[]` dengan
  `unit_id` sebagai satu-satunya sumber pemetaan kavling→unit).
- **Frontend:** `components/siteplan/{SvgPlanMap,planStyles,PlanModeLegend,UnitQuickCard,
  UnitDetailDrawer,MappingStudio}.js` + `pages/SitePlanPage.js` (ditulis ulang).
  `PlotMap.js` & `PlanLegend.js` dipertahankan sebagai fallback bila proyek belum punya peta SVG.
- **Interaksi:** hover → tooltip; klik → kartu ringkas; "Detail Lengkap" → drawer 4 tab.
  Dua mode warna (siklus penjualan / progres pembangunan per unit), legenda klik-untuk-sorot,
  geser & zoom, mini-map, mode showroom, deep link `?unit=<kode>`, toggle privasi.

## Fase 28b — Foto lapangan nyata, heatmap, peta portal & showroom publik
- **Backend baru:**
  - `p28_utils.py` — SATU sumber logika lintas router: `photo_ref` (kontrak foto
    `{file_id | inline, label, date, scope}`), `collect_unit_photos` (punch unit +
    `fix_photos` + buku harian proyek), `days_on_market`, `parse_luas`, `block_of`,
    `public_unit`.
  - `models_p28.py` — turunan model lama + `photos` (maks 6): `DiaryCreateP28`,
    `PunchCreateP28`, `PunchStatusP28` (foto bukti perbaikan + catatan), `ShowroomConfig`,
    `ShowroomLeadCreate` (dengan honeypot `website`).
  - `reference_p28.py` — grup SSOT `unit_orientation` (8 arah) + sinonim; digabung ke
    `reference.GROUPS` (reference.py 790/800 baris → grup berikutnya WAJIB file terpisah).
  - `routers/public_router.py` — `GET /api/public/showroom/{token}`,
    `POST /api/public/showroom/{token}/lead` (tanpa auth; honeypot + rate limit
    6/10 menit per IP+token; memakai `engine.process_lead_capture`).
  - `seed_phase28.py` — `seed_demo_plans()` (peta SVG demo idempoten) +
    `seed_demo_photos()` (3 foto CONTOH lewat lapisan storage, marker
    `finance_configs.key="seed_28b_photos"`, sekaligus menautkan 1 punch demo ke kavling).
- **Backend diubah:** `field_router` (photos[] + fix_photos + aktivitas), `site_plan_router`
  (`days_on_market`, `dom_open`, `price_per_m2`, foto via p28_utils, `GET/POST
  /{id}/showroom`), `portal_router` (`GET /portal/site-plan`, foto di `/portal/progress`,
  `GET /portal/files/{id}` dengan verifikasi kepemilikan nyata), `models_master.UnitUpdate`
  (+luas/orientasi/hoek), `rbac.DEFAULT_PERMISSIONS` (+resource `showroom`),
  `migrations.ENUM_FIELDS` (+`units.orientation`), `seed_phase25` (orientasi kanonik).
- **Frontend baru:** `utils/photoSrc.js` (SATU penentu URL gambar staf/portal),
  `components/patterns/{PhotoUploader,PhotoGallery}.js`,
  `components/siteplan/ShareShowroomDialog.js`, `components/showroom/{ShowroomLeadDialog,
  ShowroomUnitCard,ShowroomUnitSheet}.js`, `pages/PublicShowroom.js`,
  `services/publicClient.js` (instance `publicApi` — sengaja bukan `api`),
  `components/portal/panels/PlanPanel.js`, testIds `constants/testIds/showroom.js`.
- **Frontend diubah:** `planStyles.js` (4 mode + `makeScales`/`unitKey`/pita kuantil bebas
  degenerasi), `PlanModeLegend.js` (4 tombol mode), `SvgPlanMap.js` (pinch 2 jari,
  `emphasizeIds`, sub-label per mode, prop `height`), `UnitQuickCard`/`UnitDetailDrawer`
  (galeri + orientasi SSOT + lama dipasarkan), `SitePlanPage.js` (skala + tombol Bagikan),
  `EditUnitDialog.js` (luas/orientasi/hoek), field dialogs & panels (multi-foto),
  `PortalDashboard.js` (tab Peta Kavling), `App.js` (rute publik `/showroom/:token`).
- **Field dokumen baru:** `projects.{showroom_enabled,showroom_token,showroom_headline,
  showroom_contact_wa,showroom_show_price}`; `site_diaries.photos[]`;
  `punch_items.{photos[],fix_photos[]}`; `units.{luas_tanah,luas_bangunan,orientation,corner}`.
- **Status verifikasi:** `seed_reset.sh` → **11/11 gates PASS**; POC
  `scripts/verify_28b.py` **61/61 PASS** (termasuk regresi matriks RBAC `showroom`);
  testing_agent_v3 iterasi 35 backend 54/54, 0 bug kritis/UI; verifikasi UI Playwright
  main agent untuk 15 user story (termasuk pinch-zoom lewat synthetic PointerEvent).

## Phase 31 — Construction Progress Engine v2 (SELESAI & TERVERIFIKASI)
> Jadwal pembangunan BERBUKTI per unit (bukan persen yang diketik), per TIPE unit,
> dengan gerbang mutu, reminder + eskalasi berbasis tanggal, dan anti-kecurangan.

- **Backend baru:**
  - `build_catalog.py` — template default SSOT: `RUMAH-9W` (20 item / 9 minggu / 60 hari
    kerja) & `RUKO-14W` (16 item / 90 hari kerja); per item: minggu, hari, bobot, bidang,
    pendahulu, waktu tunggu (curing), hold point, minimal foto, peran pelaksana/verifikator,
    checklist mutu (+ penanda KRITIS).
  - `build_engine.py` — generate jadwal per unit dari tanggal kalender (lewati hari libur
    mingguan, `work_week` konfigurabel), hitung `planned_progress`/`deviation_days`,
    evaluasi GERBANG (`predecessor` belum verified, waktu tunggu belum lewat, hold point,
    schedule hold), `recompute_unit_progress()` = Σ bobot item terverifikasi.
  - `build_actions.py` — start/submit/verify/reject/override + aturan bukti: minimal N foto
    (file_id object storage, watermark, EXIF dibuang), checklist wajib lengkap, item KRITIS
    wajib lulus, **foto daur ulang ditolak (hash SHA-256)**, **SoD** pengaju ≠ verifikator,
    rework wajib foto perbaikan baru, override wajib alasan SSOT + dicatat + notif direksi.
  - `build_monitor.py` — `summary()`, `timeline()`, papan pantau, laporan penyebab telat,
    tick: buka gerbang waktu tunggu, pengingat H-1/hari-H (idempoten), eskalasi L1/L2/L3
    (staf → supervisor → direksi) + tugas TK-13 lewat Work Hub v2, `buyer_milestones()`
    untuk portal pembeli (tanggal "disetujui" hanya bila SELURUH item minggu itu selesai).
  - `models_p31.py` / `reference_p31.py` — request models + grup SSOT
    (`build_item_status`, `build_schedule_status`, `build_override_reason`,
    `build_delay_cause`, `build_template_calendar_mode`, `build_work_week`).
  - `routers/build_router.py` (prefix `/api/build`) — `GET templates`, `POST/PUT/DELETE
    templates/{id}`, `POST templates/{id}/clone`, `POST schedules/generate`,
    `GET schedules` (+summary+can), `GET unit/{unit_id}`, `DELETE schedules/{id}`,
    `POST schedules/{id}/hold|resume`, `GET items` (filter `status=todo|open`, `mine=true`),
    `POST items/{id}/start|submit|verify|reject|override|delay-cause`, `GET delays`,
    `GET unscheduled`, `GET summary`, `POST tick`.
- **Backend diubah:** `engine.recompute_project_progress()` **tidak lagi menimpa progres
  semua unit** (cacat D-A); `engine` + APScheduler `_build_tick`; `jobdesk_catalog`
  (TK-11 verifikasi, TK-12 perbaikan, TK-13 kejar keterlambatan); `units.{lead_id,deal_id,
  customer_id}` eksplisit (cacat D-F) + invariant di `scripts/verify_data_integrity.py`;
  `portal_router./progress` memuat `build` (progres RUMAH) dan memisahkan fase KAWASAN.
- **Koleksi baru:** `build_templates`, `build_schedules`, `build_items`,
  `build_item_submissions` (jejak audit proof: siapa, kapan, hash foto).
- **Frontend baru:** `pages/ConstructionPage.js` 5 tab (Monitoring Unit / Antrean Kerja /
  Infrastruktur Kawasan / QC & Inspeksi / Template Jadwal) +
  `components/construction/{BuildMonitorPanel,BuildScheduleRow,BuildDelayReport,
  BuildHealthCard,BuildQueuePanel,UnitScheduleSheet,UnitTimelineChart,BuildItemCard,
  BuildItemDialogs,GenerateScheduleDialog,BuildTemplatePanel,BuildTemplateEditor,
  BuildStepEditor,UnitTypePicker}.js`, `utils/buildUi.js`,
  `constants/testIds/build.js`, `components/portal/panels/ProgressPanel.js` (tahapan
  mingguan pembeli).
- **Pola UI baru (dipakai ulang):** `BuildItemDialogs.Hint` — panel syarat INLINE yang
  menyebut apa yang belum lengkap + tombol simpan disabled (`build-submit-requirements`,
  `build-reject-hint`, `build-override-hint`, `build-delay-hint`, `build-hold-hint`);
  `patterns/StateViews.AccessDenied` — satu kartu sopan untuk peran tanpa izin (tidak lagi
  membocorkan nama izin internal backend).
- **Gate baru:** `scripts/verify_31.py` (endpoint `/build` yatim, testId Fase 31 mati,
  kontrak antrean kerja) → masuk `run_all_gates.sh` (kini **12 gates**).
- **Status verifikasi:** `run_all_gates.sh` **PASS (12 gates)**; `scripts/poc_31.py`
  **63/63 PASS**; `scripts/verify_31.py` **30/30 PASS**; testing_agent_v3 iterasi 40 & 41 →
  **0 bug kritis, 0 bug medium** (16 user story lulus).

## Phase 32 — Task-based Execution + Papan Mandor + Laporan Mingguan + Analitik Telat (SELESAI)
> Owner: "setiap progress harus menjadi task, masing-masing upload foto sebagai bukti … setiap
> step konstruksi jadi INSTRUKSI TASK dan harus ada validasinya."

- **Backend baru:**
  - `build_instruction.py` — SATU penyusun instruksi kerja dari data template (lingkup, checklist
    mutu + penanda KRITIS, hold point, waktu tunggu/curing, urutan pendahulu, verifikator) +
    `item_link()` deep link `/construction?tab=board&item=<id>` + `brief()` untuk kartu.
  - `build_board.py` — Papan Mandor `today()`: kelompok `overdue/today/in_progress/rework/
    awaiting_verification/to_verify/upcoming/scheduled_later` + counts + kebijakan bukti kerja.
    `upcoming` = instruksi menunggu (blocked) beserta alasan terkunci → urutan tidak bisa dilangkahi.
  - `build_policy.py` — koleksi `build_policies` (1 dok/org): `geo_required`, `camera_only`,
    `min_note_chars`, `min_accuracy_m` + `check_note()` / `check_geo()` (pesan manusiawi).
  - `build_reports.py` — laporan mingguan idempoten per (org, project, `week_key`): baris per rumah,
    totals, kurva rencana vs realisasi kumulatif, pekerjaan paling sering telat, `pdf_bytes()`
    (reportlab landscape), `_announce()` → notifikasi + tugas baca **TK-14** per penerima.
  - `build_analytics.py` — analitik telat: `by_step`, `by_person`, `by_unit_type`, +
    `recommendations` kalibrasi template (durasi kurang, material selalu telat, tukang kurang,
    waktu tunggu tidak realistis, beban kerja, tipe unit).
  - `routers/build_ops_router.py` (`/api/build`) — `GET board/today`, `GET/PUT policy`,
    `GET reports/weekly`, `POST reports/weekly/run`, `GET reports/weekly/{id}`,
    `GET reports/weekly/{id}/pdf`, `GET analytics/delays`.
  - `seed_indexes.py` — seluruh `ensure_indexes()` dipindah dari `seed.py` (yang sudah menyentuh
    batas gate 800 baris) + `seed_phase31.ensure_build_indexes()`.
- **Backend diubah:**
  - `build_engine._spawn_work_task` — deskripsi task = instruksi kerja lengkap + `link` deep link +
    dipanggil untuk SEMUA item `ready` (bukan hanya transisi blocked→ready);
    `reconcile_item_tasks()` menutup **task hantu** (dipanggil `build_monitor.tick`).
  - `build_actions.submit_item` — kebijakan bukti kerja ditegakkan (panjang uraian + lokasi),
    koordinat disimpan pada item/evidence, jejak audit `build_item_submissions` (siapa, kapan,
    di mana, hash berkas, snapshot kebijakan); `reject_item` menyimpan `task_id` TK-12.
  - `routers/workhub_router.py` + `routers/work_router.py` — **PENJAGA ANTI-BYPASS**: task dengan
    `meta.build_item_id` tidak bisa start/submit/verify/reject/complete lewat jalur task generik
    (dulu bocor: cukup `photos:["file-palsu"]` tanpa checklist), dialihkan ke Papan Mandor.
  - `workhub.create_task/spawn` — parameter `link` (deep link per task).
  - `routers/files_router.py` — `lat/lng/accuracy/captured_at` opsional → `files.geo` (EXIF tetap dibuang).
  - `jobdesk_catalog.py` — **TK-14** baca laporan mingguan; `engine.py` — job cron Senin 00:05 UTC.
- **Koleksi baru:** `build_policies`, `build_weekly_reports` (+ `build_item_submissions` kini benar-benar terisi).
- **Frontend baru:** `components/construction/{ForemanBoard,ForemanTaskCard,WeeklyReportPanel,
  DelayAnalyticsPanel,BuildHint}.js`, `components/master/BuildPolicyPanel.js`, `utils/useGeo.js`.
- **Frontend diubah:** `ConstructionPage` → **7 tab** (Papan Mandor default untuk `site_engineer`)
  + deep link `?tab=&item=&unit=&report=`; `PhotoUploader` (tombol **Ambil foto** kamera +
  koordinat + penanda foto bergeotag); `BuildItemDialogs.SubmitItemDialog` (kebijakan + panel
  lokasi `build-geo-notice`); `TaskCard`/`TaskDetailSheet` (CTA "Buka & ajukan hasil" untuk task
  konstruksi); `MasterDataPage` (+tab Kebijakan Bukti Kerja).
- **Gate baru:** `scripts/verify_32.py` (endpoint ops yatim, testId mati, penjaga anti-bypass masih
  terpasang, kontrak board/policy/report/analytics) → `run_all_gates.sh` kini **13 gates**.
- **Status verifikasi:** gates **PASS (13)**; `scripts/poc_32.py` **79/79**; `scripts/verify_32.py`
  **28/28**; `poc_31.py` **63/63** (tanpa regresi); testing_agent_v3 iterasi 42 → **0 bug kritis,
  0 bug medium**.

---

## Fase 33 — RAB/BoQ ↔ item jadwal → opname & termin subkon (SELESAI & TERVERIFIKASI)

> Prinsip: **uang subkon hanya mengalir mengikuti bukti**. Termin = Σ nilai item jadwal
> TERVERIFIKASI (foto + checklist + verifikator ≠ pengaju) yang BELUM pernah ditagih.

- **Backend baru:**
  - `opname.py` — mesin lingkup SPK & opname: `scope_summary()`, `candidates()`, `add_scope()`,
    `remove_scope()`, `compute_opname()` (earned value dari `build_items` terverifikasi),
    `build_claim_lines()`, `apply_opname()`, `mark_billed()`, `cost_control()` (agregasi RAB).
  - `models_p33.py` — `ScopeItemsCreate`, `ScopeRow`, `ClaimOpnameRequest`, `OpnameLineDecision`,
    `BoQStepMap`. `reference_p33.py` — SSOT grup baru: **basis termin** (`items`|`lumpsum`),
    **mode lingkup**, **alasan pengurangan opname**.
  - `routers/spk_scope_router.py` — `GET /api/subcon/spk/{id}/scope`,
    `GET /api/subcon/spk/{id}/scope/candidates`, `POST /api/subcon/spk/{id}/scope`,
    `DELETE /api/subcon/spk/{id}/scope/{sid}`, `GET /api/subcon/spk/{id}/opname`.
  - `seed_phase33.py` — 6 item RAB dipetakan ke langkah + SPK borongan berbasis item
    `SPK/2026/0003` (10 baris lingkup pada unit A-01/A-02 yang jadwalnya nyata).
- **Backend diubah:**
  - `routers/subcon_claims_router.py` — termin **berbasis baris**: `POST /claims` menghitung sendiri
    dari pekerjaan terverifikasi (menolak `progress_pct` untuk SPK mode item), `/{id}/verify`
    = opname per baris (hanya boleh MENGURANGI + alasan wajib, **SoD**: pengaju ≠ peng-opname),
    `/{id}/approve` = finance/owner → tagihan AP + retensi + tandai baris `billed`.
  - `routers/subcon_router.py` — tolak `progress_pct` manual pada SPK `scope_mode=items`
    (INV-33-5), nilai kontrak tak bisa turun di bawah Σ lingkup, ringkasan lingkup ikut di list/detail.
  - `routers/boq_router.py` — `step_codes` pada item RAB, `GET /api/boq/steps`,
    `GET /api/boq/control` (anggaran vs dikontrakkan vs terverifikasi vs ditagih + over-commit).
- **Koleksi baru:** `spk_scope_items` (**index unik `(org_id, build_item_id)`** → INV-33-3 dijaga
  database, bukan hanya kode). `progress_claims` bertambah `basis`, `lines[]`, `opname_*`.
- **Frontend baru:** `components/subcon/{SpkScopeSection,AddScopeItemsDialog,ClaimOpnameSheet}.js`,
  `components/boq/{CostControlPanel,BoQStepMapDialog}.js`, `constants/testIds/opname.js`.
- **Frontend diubah:** `SPKDetailSheet` (panel “Lingkup & Opname” + tanpa input persen untuk mode
  item), `SubmitClaimDialog` (tabel pekerjaan terverifikasi, tanpa kolom persen bebas),
  `ClaimsPanel` (badge basis termin + tombol Opname/Setujui sesuai peran), `BoQPage` (tab
  **Kendali Biaya**), `BuildItemCard` (`build-item-contract`: nilai borongan + subkon + status tagih).
- **Gate baru:** `scripts/verify_33.py` → `run_all_gates.sh` kini **14 gates**.
- **Status verifikasi:** gates **PASS (14)**; `poc_33.py` **66/66**; `poc_31` 63/63 & `poc_32` 79/79
  (tanpa regresi); testing_agent iterasi **44** (alur backend + panel lingkup) dan **45**
  (interaksi UI lintas peran, **100%**, **0 error konsol**).

---

## Fase 34 — Jadwal massal per blok/cluster + geser tanggal serentak

> Prinsip: **jadwal boleh bergerak, bukti tidak boleh hilang.** Sebelum fase ini,
> memperbaiki tanggal berarti menghapus & membuat ulang jadwal → bukti kerja (foto +
> checklist + verifikasi) ikut hangus, sehingga orang memilih membiarkan tanggal salah.

- **Backend baru:**
  - `build_bulk.py` — mesin operasi massal: `blocks()` (ringkasan per blok/cluster),
    `candidates()` (unit belum terjadwal + template yang akan dipakai / alasan tidak bisa),
    `plan_create()`/`run_create()` (jadwal massal, pola gelombang `same|per_block|per_unit`
    + jeda hari), `plan_shift()`/`run_shift()` (geser serentak, hanya item belum selesai),
    `shift_targets()`, `runs()`, `ensure_indexes()`.
    **Satu fungsi hitung dipakai pratinjau DAN eksekusi** → pratinjau tidak bisa berbohong.
  - `models_p34.py` (`BulkScheduleIn`, `BulkShiftIn` — batas & validasi di model, bukan UI),
    `reference_p34.py` (SSOT `build_bulk_wave`, `build_shift_scope`).
  - `routers/build_bulk_router.py` — `GET /api/build/bulk/blocks`,
    `GET /api/build/bulk/candidates`, `POST /api/build/bulk/schedules/preview`,
    `POST /api/build/bulk/schedules`, `GET /api/build/bulk/shift/targets`,
    `POST /api/build/bulk/shift/preview`, `POST /api/build/bulk/shift`,
    `GET /api/build/bulk/runs`.
- **Koleksi baru:** `build_bulk_runs` (jejak operasi massal: pelaku, parameter, ringkasan,
  hasil per unit) + **index unik `(org_id, kind, client_ref)`** → klik ganda tidak dobel.
  `build_schedules` bertambah `shift_history[]` (dari→ke, hari, penyebab, catatan, pelaku).
- **Frontend baru:** `components/construction/{BulkScheduleDialog,BulkShiftDialog,
  BulkRunsPanel,ShiftHistoryPanel}.js` + blok testId Fase 34 pada `constants/testIds/build.js`.
- **Frontend diubah:** `BuildMonitorPanel` (tombol **Jadwal massal** & **Geser jadwal**,
  CTA "Jadwalkan sekaligus" pada banner rumah belum terjadwal, panel riwayat operasi massal),
  `UnitScheduleSheet` (panel riwayat penggeseran per unit).
- **Gate baru:** `scripts/verify_34.py` (40 asersi) → `run_all_gates.sh` kini **15 gates**;
  `scripts/forensic_audit.py` mendeklarasikan jalur baca `build_bulk_runs`.
- **Status verifikasi:** `poc_34.py` **57 PASS / 0 FAIL**, `verify_34.py` **40 PASS / 0 FAIL**,
  `poc_31` 63/63 · `poc_32` 79/79 · `poc_33` 66/66 (tanpa regresi).

## Fase 35 — Papan Mandor tahan sinyal hilang (antrean offline) — SELESAI & TERVERIFIKASI
- **Masalah nyata:** mandor kehilangan sinyal di lokasi; pengajuan hasil kerja + foto hilang,
  dan muat ulang saat offline melempar mandor ke halaman login.
- **Backend:** `build_actions.submit_item` dipecah — pembungkus **mengunci `client_ref`
  SEBELUM** item disentuh (koleksi `build_submit_claims`, indeks unik + TTL 7 hari),
  memutar ulang hasil bila penanda sudah pernah diterima, dan **melepas kunci bila pengajuan
  ditolak** supaya mandor bisa memperbaiki lalu mengirim ulang dengan penanda yang sama.
  Kunci basi (>120s tanpa jejak) boleh diambil ulang → tidak ada "kehilangan senyap".
  SSOT baru `reference_p35.py` (`offline_queue_status`, `offline_queue_kind`);
  pemuatan `reference.py` menjadi dinamis lewat tuple `_PHASES`.
- **Frontend:** `utils/offlineDb.js` (IndexedDB antrean + cadangan sesi/kamus/proyek),
  spanduk jaringan lintas halaman, panel antrean (`offline-queue-panel`), tombol berubah
  menjadi "Simpan & kirim nanti" saat offline; penolakan server tampil apa adanya (bukti tidak dihapus).
- **Gate:** `scripts/verify_35.py` (52 asersi) → `run_all_gates.sh` menjadi **16 gates**.
- **Status:** `poc_35.py` **43/43**, `verify_35.py` **52/52**, terbukti di browser nyata
  (offline sungguhan lewat Playwright, tanpa pengajuan dobel).

## Fase 36 — Kalender Jadwal (kalender bulanan + deteksi bentrok + master kalender kerja) — SELESAI & TERVERIFIKASI
- **Masalah nyata:** tenggat hanya terlihat per rumah/daftar → bentrok baru terasa setelah telat;
  `build_templates.holidays` selalu kosong pada data nyata sehingga tenggat mendarat di
  17 Agustus / Idul Fitri dan tidak ada satu pun layar admin untuk mengaturnya.
- **Backend baru:**
  - `build_calendar.py` — **MASTER kalender kerja** (pola 7 hari `full/half/off`, hari libur
    bernama, ambang bentrok) + resolver `resolve()` yang dipakai **UI dan MESIN jadwal**
    (`build_engine.generate_schedule`, `build_bulk.plan_for_template_at`, `build_bulk.plan_shift`
    lewat `params_for`). Koleksi `build_work_calendars` dengan **indeks unik `(org_id, project_id)`**.
  - `build_calendar_view.py` — agregasi bulanan 6 lapisan acara nyata (tenggat item, mulai/target
    selesai rumah, inspeksi QC terjadwal, punch list jatuh tempo, tugas Work Hub tim proyek) +
    **deteksi 3 bentrok** (`overload`, `critical_stack`, `non_workday`) dengan alasan yang bisa
    dibaca orang + saran hari kerja terdekat, `outlook` 3 bulan ke depan, daftar inspeksi
    **belum dijadwalkan** (kalender tidak mengarang tanggal).
  - `models_p36.py` (`WorkCalendarIn`, `HolidayIn`, `InspectionScheduleIn`),
    `reference_p36.py` (SSOT `calendar_event_kind`, `calendar_day_kind`, `calendar_conflict_kind`,
    `calendar_work_pattern`, `holiday_kind`, `calendar_scope`, **`calendar_settings_scope`**,
    **`holiday_source`**), `seed_phase36.py` (kalender bawaan + libur nasional 2026 **bertanda
    "perkiraan, wajib disesuaikan SKB"** + inspeksi demo, idempoten).
  - `routers/build_calendar_router.py` — `GET /api/build/calendar`,
    `GET /api/build/calendar/settings`, `PUT /api/build/calendar/settings`,
    **`DELETE /api/build/calendar/settings`** (lepas kalender khusus proyek),
    `POST /api/build/calendar/holidays`, `DELETE /api/build/calendar/holidays/{day}`,
    **`POST /api/build/calendar/holidays/{day}/restore`** (batalkan pengecualian),
    `GET /api/build/calendar/workday`, `GET /api/build/calendar/months`.
    Tambahan: `PUT /api/inspections/{id}/schedule` (menolak hari libur + memberi saran tanggal).
- **Frontend baru:** halaman `pages/BuildCalendarPage.js` (`/build-calendar`, menu "Kalender Jadwal")
  + `components/construction/calendar/{CalendarToolbar,CalendarMonthGrid,CalendarDayPanel,
  CalendarConflictPanel,CalendarUnscheduledPanel,WorkCalendarDialog,WorkCalendarHolidays}.js`,
  `utils/calendarUi.js`, `constants/testIds/buildCalendar.js`. Tombol "Geser jadwal" membuka
  **`BulkShiftDialog` Fase 34** (kalender READ-ONLY terhadap tanggal pekerjaan).
- **Fase 36b — perbaikan pewarisan kalender (cacat HIGH):** dulu kalender khusus proyek
  menjadi **PENGGANTI UTUH** kalender organisasi dan dibuat dengan `holidays: []`, sehingga sekali
  menekan "Simpan pola & ambang" pada cakupan proyek **18 libur nasional hilang senyap** dan
  inspeksi QC bisa dijadwalkan pada Hari Kemerdekaan. Sekarang: `_merge()` mewarisi libur
  organisasi (organisasi ∪ proyek), override hanya menimpa pola & ambang, penghapusan libur
  warisan menjadi **pengecualian yang disengaja** (`holiday_exclusions`, audit
  `calendar_holiday_exclude`, bisa dibatalkan), override bisa dilepas, dan bentrok `non_workday`
  diperluas ke **inspeksi & punch list** (`NONWORK_KINDS`).
- **Gate:** `scripts/verify_36.py` (135 asersi, termasuk §G regresi pewarisan) →
  `run_all_gates.sh` menjadi **17 gates**.
- **Status verifikasi:** `poc_36.py` **132 PASS / 0 FAIL** (INV-36-1..14),
  `verify_36.py` **135 PASS / 0 FAIL**, `run_all_gates.sh` **OVERALL PASS (17 gates)**,
  12 user story terbukti di browser (testing agent iterasi 50/51/52, 0 error konsol).

---

## FASE 39b — Checklist Dokumen Syarat terpakai nyata + audit yang jujur (16 Agu 2026)

**Masalah yang ditutup:** Fase 39 membuat master `doc_requirements` (17 syarat) + mesin
verifikasinya, tetapi `doc/matrix` & `doc/submissions` **nol kemunculan di frontend** →
`doc_submissions` mustahil terisi dari UI dan 4 gate audit merah.

- **Backend baru/berubah:**
  - `doc_registry.py` — `LEAD_ORDER`, **`contexts_for(entity_type, entity_id)`** (konteks syarat
    diturunkan dari data entitas: tahap lead sekarang + berikutnya, `customer:legal`
    (+`payment_scheme:kpr` bila ada pengajuan KPR), `partner:onboarding`);
    `_same_evidence_status()` (tolak bukti kembar berbasis **`files.sha256`**);
    `create_submission()` menangkap **DuplicateKeyError → 400** (dulu HTTP 500).
  - `routers/docreq_router.py` — `GET /api/doc/matrix` boleh **tanpa** `contexts` (backend
    menurunkannya sendiri).
  - `routers/admin_router.py` — **`GET /api/admin/migrations`** (izin `audit_logs.view`):
    riwayat `migration_runs` + **`state`** (hitungan nyata unit ber-cluster/blok/tipe).
  - `routers/reference_router.py` — `_labeled_options()` (grup dinamis boleh berlabel dari
    master via `source.label_field` + `label_format`) + passthrough **`allow_new`**.
    `reference.py` **tidak disentuh** (tetap 798/800 baris); `maps` lama
    (`channel_to_source`, `source_score`) dijaga tetap ada.
  - `reference_p39.py` — grup baru **`gl_account`** (dinamis dari koleksi `accounts`,
    label `kode — nama`, `allow_new:false`), **`doc_context`** (12 konteks),
    **`setting_origin`**, **`setting_source`**.
- **Frontend baru/berubah:**
  - **`components/patterns/DocChecklist.js`** (baru) — matriks syarat × bukti: unggah
    (input berkas **per baris**, `data-requirement` pada elemennya), verifikasi, tolak
    beralasan, riwayat aktor+waktu, ringkasan hitungan, chip konteks berlabel SSOT.
  - **`components/master/MigrationRunsPanel.js`** (baru) — panel "Migrasi & Pembenahan Data
    (V2)" di `pages/AuditLogsPage.js` (`/admin/audit`).
  - **`constants/testIds/docChecklist.js`** (baru, `DOCCHK`) + `AUDIT.migration*` di `master.js`.
  - `components/sales/LeadDetail.js` & `components/customers/CustomerDetailSheet.js` —
    memasang `DocChecklist` (`entityType="lead"` / `"customer"`).
  - `components/config/{AddonPanel,PriceComponentPanel}.js` — "Akun GL" input bebas →
    `ReferenceSelect group="gl_account"`.
  - `components/config/SettingsPanel.js` — `ORIGIN_LABEL`/`SOURCE_LABEL` dihapus →
    `labelOf("setting_origin"/"setting_source")`.
  - `components/config/DocRequirementsPanel.js` — `CONTEXT_OPTIONS` hardcode dihapus →
    `options("doc_context")` + `labelOf("doc_context", …)`.
  - `pages/ProjectsPage.js` — `project-open-structure` diberi `data-project` + `aria-label`.
  - `components/patterns/ReferenceSelect.js` — hormati `allow_new:false`.
- **Alat & gate:**
  - **`scripts/verify_39b.py`** (gate ke-**22**, 48 pemeriksaan) — konteks diturunkan backend,
    bukti fiktif/kembar ditolak, aktor+waktu+alasan tersimpan, label dari SSOT, dan **wiring UI**
    (checklist terpasang, input berkas per baris, tidak ada peta label hardcode).
    Gate ini **membereskan sisa data ujinya sendiri** (hapus penyerahan+berkas uji lalu hitung
    ulang `doc_progress`).
  - **`scripts/mutasi_39b.py`** — uji-mutasi 10 mutasi × (memerah + pulih) = **20 pemeriksaan**.
  - `scripts/forensic_audit.py` — **`_router_helper_modules()`**: atribusi BACA lewat modul
    engine yang di-import router (termasuk import di dalam fungsi) → 10 temuan palsu
    "TIDAK ADA ENDPOINT BACA" hilang (**HIGH 2 → 0, MED 17 → 8**); `ENGINE_MANAGED` +12 koleksi.
  - `scripts/audit_endpoint_sweep.py` — **`QUERY_RESOLVERS`** (resolve id NYATA untuk
    `/doc/matrix`, `/doc/submissions`, `/settings/effective`).
  - `scripts/audit_forms_deep.py` — regex tipe input `[\w-]+` (kenali `datetime-local`) dan
    E3 tidak berlaku untuk `type=number` (3 false positive hilang).
- **Endpoint katalog (tambahan Fase 39b):** `GET /api/admin/migrations`;
  `GET /api/doc/matrix` (parameter `contexts` kini OPSIONAL).
- **Status verifikasi:** `run_all_gates.sh` **OVERALL PASS (22 gates)**, `mutasi_39b.py` 20/20,
  `poc_31..37` semua 0 FAIL, testing agent iterasi **58/59/60**.


## Fase 40 — IA & Design System V2
- **Backend:**
  - `listing.py` — kontrak query daftar (search escape, filter multi `$in`, whitelist sort,
    aging read-only via `attach_aging`). Dipakai leads/units/deals/customers/tasks/AR/
    documents/complaints.
  - `routers/work_router.py` — `GET /work/tasks` menerima `bucket` (overdue|today|upcoming|
    waiting|review), `sla=breached`, `unassigned=1`; angka chip ember dihitung dari query
    "wide". `_kpis()` menambahkan `drill` (URL daftar terfilter) pada SETIAP KPI, dan
    `team.drills` untuk angka tim.
  - `routers/ar_router.py` — `counts` per status memakai SSOT `reference.ar_status`
    (unpaid/partial/paid), bukan daftar karangan draft/open/void.
- **Frontend:**
  - `components/patterns/*` — DataTable (tanstack v9, sort/paginasi SERVER), DataTableToolbar
    (cari/kolom/densitas/ekspor/muat ulang), FilterBar (deklaratif), AgingCell, TabPage
    (`?tab=`/`?hub=`), KpiCard (`to` = drill wajib), MoneyText, TimelineFeed, ChartFrame.
  - `hooks/useListQuery.js` — status daftar (q/filter/sort/skip/limit) HIDUP DI URL.
  - Hub: `pages/BuildHubPage.js` (`/build`: Papan Unit · Progres & Mutu · Kalender ·
    Buku Harian & Punch · Kalibrasi), `pages/CustomersPage.js` (Pembeli · Deal & Unit),
    `pages/DocumentsPage.js` (Dokumen Transaksi · Perizinan, tab per izin nyata).
  - Daftar pro baru: `components/work/TasksListTab.js`, `components/complaints/ComplaintsListTab.js`,
    `components/finance/ArPanel.js` (migrasi), `components/customers/CustomersListTab.js`,
    `components/documents/DocumentsListTab.js`, `components/projects/AllUnitsTab.js`,
    `components/sales/DealsListTab.js`.
  - Navigasi: `config/navigationConfig.js` (26 item non-admin, 4 item comingSoon tanpa path,
    `countNavItems()`), `config/navMigrationMap.js` + `components/layout/NavMigrationDialog.js`
    (peta menu lama→baru DI DALAM aplikasi), `components/layout/Sidebar.js`.
  - Halaman kanonik: `pages/LeadProfilePage.js` (`/leads/:id`), `pages/CustomerProfilePage.js`
    (`/customers/:id`).
- **Rute alias yang dipertahankan:** `/deals`, `/construction`, `/build-calendar`,
  `/build-calibration`, `/field`, `/permits` (tidak lagi di sidebar).
- **Gates:** total **23** — baru: `verify_ia_v2.py` (peleburan menu tanpa fitur hilang, item
  Segera Hadir tanpa path, semua daftar utama tabel pro, peta menu tidak membusuk, dan
  **bukti API** bahwa angka KPI = jumlah baris hasil filternya). Uji-mutasi:
  `scripts/mutasi_40_ia.py` (10 mutasi, 20 pemeriksaan).
- **Dokumen:** `docs/v2/40_PETA_NAV_V2.md` (peta menu lama→baru + angka yang bisa diverifikasi).

## Fase 41 — Jam tahap (aging) jadi FIELD TERSIMPAN + ambang SLA dari Pusat Konfigurasi

**Masalah yang dibereskan:** sebelum fase ini `listing.attach_aging` menghitung ulang
`stage_entered_at` dari `stage_history` **di setiap request** → umur tahap tidak bisa difilter,
tidak bisa diagregasi, tidak bisa diberi index; dan ambang SLA adalah **angka mati di komponen**
(72 di Lead, 48 di Tugas & Komplain, 168 di Deal, 336 di Pembeli, 720 di AR) sehingga kalimat
"lewat SLA" di tabel adalah klaim tanpa dasar kebijakan yang tak bisa diubah tanpa deploy.

- **Backend:**
  - `stage_clock.py` — SATU mesin jam tahap: `clock_patch/patch_for/stamp` (tulis saat transisi),
    `state_of` (`ok|over|over2|none`), `attach` (umur total & umur tahap saat baca),
    `apply_sla_filter` (filter DI DATABASE; nilai tak dikenal → hasil KOSONG, bukan diabaikan),
    `reconcile` (isi/perbaiki dari bukti tercatat + tandai asalnya), `resync`/`resync_for_setting`
    (terapkan kebijakan SLA terbaru ke baris yang SUDAH ADA), `drill_for`, `aging_report`.
  - Field tersimpan di **7 koleksi** (leads, deals, tasks, complaints, customers, ar_invoices,
    documents): `stage_entered_at`, `stage_sla_hours`, `stage_due_at`, `stage_due2_at`,
    `stage_clock_stage`, `stage_clock_source` (`transition|history|reconcile:*|derived`).
  - `routers/aging_router.py` — `/api/aging/policy`, `/report`, `/overview`, `/reconcile`
    (RBAC: semua peran `view`, hanya owner/super_admin `manage`).
  - `seed_indexes.py` — index `org_id+stage_due_at` & `org_id+stage_entered_at` per koleksi
    (tanpa ini setiap filter "lewat SLA" = collection scan).
  - `engine.py` — job `stage_clock_tick` (60 detik) menyamakan jam tahap dengan status nyata.
  - `reference_p41.py` — grup SSOT `sla_state`, `aging_entity` (+ grup Fase 42, lihat bawah).
- **Frontend:**
  - `components/patterns/AgingCell.js` — TIDAK lagi punya ambang bawaan; menampilkan
    `stage_sla_hours` + `sla_state` yang dikirim server pada SETIAP baris. Warna bukan satu-satunya
    penanda (selalu ada teksnya).
  - `utils/agingFilter.js` — `slaFilter(options("sla_state"), extra)`: opsi filter dari SSOT
    (bukan salinan), `formatHours`, label & nada keadaan SLA.
  - `components/work/AgingReportTab.js` — tab **"Umur Tahap & SLA"** di hub Kerja: pemilih objek,
    4 KPI, tabel per tahap (SLA/jumlah/lewat/rata-rata/median/P90/terlama), panel lintas domain
    7 objek, semua angka punya tautan **drill dari backend**, tombol "Samakan jam tahap"
    (admin) & tautan ke Pusat Konfigurasi.
  - Filter "Umur / SLA" seragam di Lead, Tugas, Komplain, Deal, Pembeli, AR, Dokumen.

## Fase 42 — Mitra & Fee (master mitra, aturan fee, fee otomatis dari pemicu nyata)

- **Backend:**
  - `routers/partners_router.py` — `/api/partners` (CRUD + `/status` wajib beralasan,
    `/{id}` overview: kontrak+aturan+lead+tagihan), `/partners/rules` (CRUD + `/preview`
    + `/issue` manual), `/partners/analytics`, `/partners/conflicts` (+ `/resolve`).
    Data mitra tetap di koleksi **`agents`** supaya invarian GL `marketing_fee.py`
    (6-1200 beban / 2-1500 utang fee / 2-1300 utang PPh) tidak berubah.
  - `partner_fee.py` — mesin aturan **MURNI** (tanpa I/O, bisa diuji angka demi angka):
    7 dasar fee (persen harga, nominal per transaksi, nominal per tipe unit, berjenjang per
    jumlah, berjenjang per nilai, per lead terkualifikasi, gabungan), `price_of`, `tax_of`
    (beban = netto + PPh), `split_pct` (porsi per pemicu), `specificity`/`select`
    (**aturan bentrok DITOLAK**, tidak dipilih diam-diam), `validate_rule`.
  - `partner_engine.py` — `compute` (INV-09: tidak ada fee tanpa aturan berlaku, dengan alasan),
    `create_fee_for_trigger` (**idempoten** per mitra × deal × pemicu), `on_event`/`register`
    (dipasang ke `engine.HANDLERS` pada event yang SUDAH terbit — bukan event karangan),
    `attribute` (atribusi lead + sengketa), `refresh_stats`.
  - `partner_report.py` — analitik mitra dihitung dari data (lead, terkualifikasi, closing,
    fee, sisa utang).
  - `models_p41.py` — model request Fase 41+42; semua enum lewat validator SSOT.
  - `reference_p41.py` — grup SSOT: `partner_entity_type`, `partner_price_base`,
    `partner_tier_mode`, `partner_fee_period`, `partner_qualify_rule`, `partner_rule_status`,
    `partner_conflict_status`, **`partner_tax_type`**, + perluasan `agent_status`
    (suspended/expired) dan `marketing_fee_trigger` (6 pemicu Fase 42).
  - Koleksi baru: `partner_fee_rules`, `partner_attribution_conflicts`.
- **Frontend:**
  - `pages/PartnersPage.js` — hub `/partners` (TabPage `?hub=`): Master Mitra · Aturan Fee ·
    **Tagihan Fee (memakai `FeesPanel` yang sudah ada, bukan salinan)** · Sengketa Atribusi ·
    Analitik Mitra. `pages/PartnerProfilePage.js` — halaman kanonik `/partners/:id`.
  - `components/partners/*` — PartnersListTab, PartnerFormDialog, PartnerStatusDialog,
    FeeRulesTab, FeeRuleFormDialog, FeePreviewDialog, ConflictsTab, PartnerAnalyticsTab.
  - Menu **"Mitra & Fee"** dibuka di sidebar; rute alias **`/marketing-fee` TETAP hidup**
    (+ ada di `navMigrationMap.js`) supaya bookmark & tautan lama tidak rusak.
  - **Izin tombol memakai `can(resource, action)`** dari `GET /auth/me` (izin EFEKTIF), bukan
    daftar peran hardcode — sebab matriks RBAC bisa diubah admin lewat Pusat Konfigurasi.
    Pemisahan tugas: sales/marketing MENGAJUKAN fee, finance MENYETUJUI+MEMBAYAR (tombol
    "Ajukan Fee" nonaktif untuk finance, dengan penjelasan).
- **RBAC:** resource `aging` (semua peran `view_all`; `manage` hanya FULL_ACCESS) dan
  `partners` (sales hanya `view_all`; finance `view_all`+`update` untuk aturan fee tapi TIDAK
  boleh mendaftarkan mitra). Persetujuan/pembayaran tagihan tetap resource `marketing_fee`.
- **Gates:** total **25** — baru `verify_41.py` (jam tahap tersimpan & sinkron di 7 koleksi,
  ambang SLA dari Pusat Konfigurasi + bukti API bahwa mengubah setting mengubah angka baris,
  `?sla=over` dieksekusi di DB & angkanya = laporan, drill ke rute nyata, RBAC) dan
  `verify_partner.py` (menu dibuka tanpa merusak alias, pagar validasi aturan, fee dari pemicu
  NYATA + idempoten + INV-09, analitik = hitungan data, RBAC, **layar tidak menyalin matriks
  RBAC**). Uji-mutasi: `scripts/mutasi_41_42.py` (**16 mutasi, 32 pemeriksaan**), mendukung
  argumen selektif (`mutasi_41_42.py M7 M12`).

## Lanjutan Fase 42 — Satu pintu fee + izin layar = izin server (gate ke-26)

**Masalah yang dibereskan:** (a) DUA pintu untuk satu urusan fee — `/marketing-fee` punya
halaman sendiri (tab "Pengajuan Fee" + **"Master Agen"**) sementara `/partners` adalah hub
(tab "Tagihan Fee" + **"Master Mitra"**), jadi ada dua master mitra yang bisa berbeda diam-diam;
(b) **32 kemunculan daftar peran hardcode** (`[...].includes(user?.role)`) di 25 berkas frontend
— menyalin matriks RBAC ke layar, padahal matriksnya bisa diubah admin lewat Pusat Konfigurasi.

- **Satu pintu fee:**
  - `App.js` — rute `/marketing-fee` TETAP terdaftar (bookmark & notifikasi lama menyimpannya)
    tetapi kini `<Navigate to="/partners?hub=tagihan" replace />`.
  - Dihapus karena kembar: `pages/MarketingFeePage.js`, `components/marketingFee/AgentsPanel.js`,
    `components/marketingFee/AgentDialog.js`, dan testId mati di `constants/testIds/marketingFee.js`.
    `components/marketingFee/FeesPanel.js` TIDAK disalin — dipakai ulang sebagai isi tab.
  - `PAGE_META["/marketing-fee"]` DIPERTAHANKAN: `check_nav_map` CHECK 3 & 5 menuntut setiap
    rute punya meta, kalau tidak rute itu dianggap "dead page".
- **Izin layar = izin server:**
  - 24 layar memakai `can(resource, action)` dari `GET /auth/me` (helper Fase 39b di
    `context/AuthContext.js`, meniru `rbac._permitted`: `manage`/`all` = boleh apa saja,
    `view` dipenuhi `view_all`/`view_own`).
  - Pemetaan diambil dari `require_permission(...)` yang benar-benar dipakai backend, mis.
    tahan unit = `deals:create` (bukan `reservations`), template pembangunan =
    `construction:approve` (menyamai `SUPERVISOR_ROLES` backend), buka periode = `gl:approve`.
  - DUA pemakaian nama peran DIPERTAHANKAN dan wajib berpenanda `PENGECUALIAN SAH`:
    `pages/ConstructionPage.js` (tab BAWAAN per peran, bukan gerbang izin) dan
    `components/subcon/ClaimOpnameSheet.js` (meniru aturan empat-mata backend yang memang
    ditulis dengan nama peran).
- **Gates:** total **26** — baru `verify_rbac_ui.py`: (1) tidak ada matriks RBAC yang disalin
  ke layar (pengecualian wajib berpenjelasan), (2) setiap `can("r","a")` di layar benar-benar
  dipaksakan backend (130 pasangan `require_permission` dibaca dari sumbernya — menangkap salah
  ketik yang membuat tombol hilang selamanya tanpa error), (3) **bukti API**: peran tanpa izin
  dijawab 403 dan peran yang punya izin BUKAN 403. Uji-mutasi `mutasi_41_42.py` kini
  **21 mutasi / 42 pemeriksaan** (tambahan M10b, M17–M20), mendukung argumen selektif.
- **Cacat nyata yang ikut terbetulkan:** Manajer Keuangan tidak pernah melihat "Buka kembali
  periode" padahal punya `gl:manage`; Pelaksana Lapangan tidak pernah melihat "Perbarui Status"
  izin karena `permits:create` dan `permits:update` digabung jadi satu bendera.
- **Temuan terbuka (dilaporkan, bukan diperbaiki):** resource `reservations` ada di matriks RBAC
  tetapi tidak dipaksakan endpoint mana pun — dicetak `verify_rbac_ui` sebagai CATATAN.

## Fase 43 DITUTUP + Fase 44 — Analitik & BI (sesi lanjutan dari repo GitHub)

### Pemulihan lingkungan (wajib dibaca agen lanjutan)
`.env` tidak ada di git. Setelah `git clone`: tambahkan `JWT_SECRET` (acak) ke `backend/.env`
(+ `PORTAL_MASTER_OTP="000000"` untuk portal), `pip install APScheduler reportlab tzlocal`,
`yarn install` di `frontend/`, lalu `supervisorctl restart backend frontend`. Detail di
`memory/test_credentials.md`.

### Fase 43 (Kampanye & Biaya Iklan + Atribusi/CAPI) — penutupan
- **Gate ke-27 `scripts/verify_ads.py`** (11 kelompok pemeriksaan, semuanya lewat API/DB nyata):
  dry-run menolak 5 jenis baris cacat & tidak menulis apa pun; commit = tepat yang dilihat
  pemakai; impor ulang berkas sama = `unchanged`; nominal berubah = update + `history`;
  commit kedua tidak menulis ulang catatan audit; index unik kunci natural `ad_spend`
  DIBUKTIKAN menolak baris kembar (insert kembar lewat pymongo); metrik biaya jujun
  (missing/partial/complete, CPL/CAC/ROAS null bukan 0); atribusi tie-out dengan jumlah lead
  di database & biaya tidak dibagi ke adset; CAPI V2 (event_id 32 heks deterministik, dedup,
  hash 64 heks tanpa PII, mode simulasi bukan "Terkirim"); `/ads/health` hanya `filled` +
  tidak memuat nilai rahasia; `/ads/sync` menolak beralasan; 8 probe RBAC.
- **Uji-mutasi `scripts/mutasi_43.py`**: 19 mutasi / 38 pemeriksaan, semuanya tertangkap.
  Kunci PID + baseline wajib hijau (dua suite bersamaan pernah meninggalkan cacat "hantu"),
  dan mutasi backend me-restart backend eksplisit (bukan mengandalkan `--reload`).
- **Cacat data nyata yang diperbaiki:** `seed_phase22.py` menulis `conversion_events` langsung
  (tanpa `event_id`/`user_data`) → sekarang lewat `capi.record_conversion`; migrasi baru
  `migrations.capi_event_identity()` mem-backfill basis data yang sudah berjalan.

### Fase 44 (Analitik & BI) — menu "Segera Hadir" terakhir dibuka
| File | Peran |
|---|---|
| `backend/metrics/base.py` | KONTRAK hasil metrik + pemaksaan "0 ≠ belum ada data" |
| `backend/metrics/{sales,leads,marketing,project,team}.py` | 47 metrik (SLS/LED/MKT/PRJ/USR), 1 metrik = 1 fungsi murni + rumus di docstring |
| `backend/metrics/__init__.py` | registry/kamus metrik + `compute`/`compute_many` |
| `backend/analytics_engine.py` | susunan 5 dashboard persona + snapshot harian (rebuildable) |
| `backend/routers/analytics_router.py` | `/api/analytics/*` (15 endpoint) + RBAC & row-scope |
| `backend/reference_p44.py` | SSOT `metric_persona`, `metric_state`, `metric_unit`, `analytics_period`, `analytics_granularity`, `cac_component`, `analytics_dimension`, `demography_dimension` |
| `frontend/src/pages/BiPage.js` | hub `/bi`: 5 dashboard + Kamus Metrik (tab di URL `?hub=`) |
| `frontend/src/components/bi/*` | MetricCard/MetricValue (status kelengkapan), MetricChart (recharts), MetricDetailDialog (bahan hitung + ekspor CSV), DashboardShell, MetricDictionaryTab |

- **Endpoint:** `GET /api/analytics/{metrics,executive,sales/funnel,sales/cohort,sales/units-sold,
  leads/aging,leads/demography,marketing/performance,marketing/cac,project/budget-vs-actual,
  project/schedule-health,users/daily,users/leaderboard,snapshots,metric/{code},export/{metric}}`,
  `POST /api/analytics/snapshots/rebuild`.
- **Koleksi baru:** `metric_snapshots` (index unik `(org_id, code, period_key)`).
- **Scheduler:** `_bi_snapshot_tick` (cron 00:20 UTC) — snapshot percepatan, selalu bisa
  dihitung ulang (INV-14).
- **RBAC:** resource `analytics` — semua peran `view`, sales `view_own` (row-scope dipaksakan
  server lewat `owner_email`), `manage` (hitung ulang snapshot) terbatas pada supervisor/owner.
- **Gate ke-28 `scripts/verify_analytics.py`** + **`scripts/mutasi_44.py`** (15 mutasi /
  30 pemeriksaan). Gate memeriksa antara lain: cakupan tidak boleh disembunyikan (dibandingkan
  dengan FAKTA database: 40/47 lead berriwayat → LED-02/04 wajib "sebagian"), "angka = daftar"
  (LED-14 = jumlah baris `/leads?sla=over`), dan snapshot SELF-HEALING (gate merusak satu nilai
  snapshot lalu menuntut `rebuild` memperbaikinya).
- **Gate lama yang diperbarui jujur:** `verify_ia_v2` berhenti memakai angka mati 26 →
  membandingkan sidebar dengan **ledger pintu resmi** (`docs/v2/40_PETA_NAV_V2.md` §7, 29 pintu,
  anggaran 30) dan berhenti MEWAJIBKAN adanya item "Segera Hadir" (peta jalan menu sudah selesai);
  `validate_compliance` dipenuhi dengan memecah `models.py` → `models_procurement.py` (re-export).
- **Status:** `bash scripts/run_all_gates.sh` → **OVERALL PASS (28 gates)**; POC `poc/poc_44.py`
  hijau; E2E testing agent iterasi 65 (Fase 43) & 66 (Fase 44).

## Fase 45 & Fase 46 (sesi lanjutan dari repo GitHub `yawnabavasa/Sipro`)

### Pemulihan lingkungan (ULANGI setiap kali repo di-clone ke container baru)
```
# backend/.env — TIDAK ada di git
JWT_SECRET="<acak: python3 -c 'import secrets;print(secrets.token_urlsafe(48))'>"
PORTAL_MASTER_OTP="000000"
pip install APScheduler reportlab tzlocal      # sisanya sudah ada di image
cd frontend && yarn install
sudo supervisorctl restart backend frontend    # seed jalan saat startup (idempoten)
```
Verifikasi: `curl -s localhost:8001/api/health`, login `POST /api/auth/login`
(`superadmin@sipro.co.id` / `Sipro#2026`), lalu `bash scripts/run_all_gates.sh`.

### Fase 45 — Target Proyek & Budget/RAB (`docs/v2/32`)
| File | Peran |
|---|---|
| `backend/target_engine.py` | matematika target (FUNGSI MURNI): `keep_total`, `lock_past`, carry-over yang bisa dijelaskan |
| `backend/target_store.py` | penyimpanan/revisi target + ringkasan per proyek |
| `backend/budget_engine.py` / `budget_reports.py` | anggaran & realisasi (RAB operasional), laporan varian |
| `backend/reference_p45.py`, `models_p45.py`, `scheduler_p45.py` | SSOT + kontrak + tick `targets_recalc_tick` / `budget_alert_tick` |
| `backend/routers/targets_router.py` (`/api/targets`, 10 rute), `budget_router.py` (`/api/budget`, 14 rute) | API |
| `frontend/src/components/budget/*` | TargetPanel/TargetDialog/TargetPeriodTable/TargetSummaryCard, BudgetItemsPanel/RealizationPanel + dialog revisi/recalc |
| Gate ke-29 `scripts/verify_budget_target.py` + `scripts/mutasi_45.py` | guardrail |

### Fase 46 — Konsolidasi Proyek & Konstruksi (`docs/v2/29`)
| File | Peran |
|---|---|
| `backend/build_unit_board.py` | **Papan Unit per-UNIT**: baris untuk SEMUA unit (termasuk belum dijadwalkan), planned/deviation/days_late **null + `missing[]`** bila tidak ada jadwal, progres = Σ bobot item terverifikasi (satu kebenaran dengan `build_engine`) |
| `backend/build_readiness.py` | gerbang **Mulai Bangun**: `evaluate()` (alasan berkode + tingkat + cara perbaikan) & `start_build()` (ack + alasan ≥5 huruf → `start_gate_log`) |
| `backend/permit_scope.py` | rantai izin unit→blok→cluster→proyek + kesehatan izin (`ok/expiring/expired/in_process/missing`, "masa berlaku belum dicatat") |
| `backend/permit_alerts.py` | peringatan masa berlaku → notifikasi in-app **+ tugas Work Hub** |
| `backend/migrations_p46.py` | backfill `permits.scope=project` untuk data lama |
| `backend/reference_p46.py`, `models_p46.py`, `scheduler_p46.py` | SSOT (`permit_scope`, `permit_health`, `build_readiness_state`, `build_gate_code`) + kontrak + `permit_expiry_tick` |
| `backend/routers/build_board_router.py` | `GET /api/build/board/units`, `GET /api/build/unit/{id}/readiness`, `POST /api/build/unit/{id}/start` |
| `backend/routers/permits_router.py` | `/api/permits` + `GET /api/permits/coverage` + `POST /api/permits/alerts/scan` |
| `backend/seed_phase46.py` | izin bertingkat (PBG cluster aman, SLF blok 21 hari lagi, site plan unit KEDALUWARSA, ANDALALIN proyek masih diproses) + temuan/inspeksi per unit + **satu unit terjadwal yang belum dimulai** (agar gerbang bisa dicoba manusia) |
| `frontend/src/pages/BuildHubPage.js` | hub `/build` **6 tab**: `unit, kalender, lapangan, mutu, analitik, template` (tanpa pintu sidebar baru) |
| `frontend/src/components/build/UnitBoardTab.js` | tabel papan unit + filter + lencana kesiapan |
| `frontend/src/components/build/UnitBuildTab.js` + `UnitReadinessCard.js`, `UnitScheduleView.js`, `UnitQualityPanel.js` | Unit 360 → tab **Pembangunan** (kurva-S, langkah + submit/verify/reject/override, tombol Mulai Bangun + dialog ack/alasan) |
| `frontend/src/components/permits/PermitCoveragePanel.js`, `AddPermitDialog.js`, `PermitDetailSheet.js` | izin bertingkat di Unit 360 & `/projects/:id` |
| Gate ke-30 `scripts/verify_build_hub.py` + `scripts/mutasi_46.py` (16 mutasi) + `poc/poc_46.py` | guardrail |

### Dua cacat PERANGKAT UJI yang ditemukan uji-mutasi saat penutupan Fase 46
1. **Gate & POC dulu SEKALI PAKAI.** Bahan uji gerbang ("unit terjadwal yang belum berjalan")
   dipungut dari data seed. Begitu satu mutasi berhasil menekan start (mis. mutasi yang
   mematikan syarat `ack`), unit itu berubah menjadi *berjalan* dan gate berikutnya MERAH
   karena bahannya habis — bukan karena kode salah. Efek sampingnya berbahaya: mutasi
   N07–N16 tampak "tertangkap" **secara palsu**. Sekarang gate (`GATE46-01`) dan POC
   (`POC46-01/02`) **membuat sendiri** unit + jadwal lewat API nyata lalu membuangnya.
2. **N15 benar-benar LOLOS.** Gate memeriksa `"ForemanBoard" in isi_berkas`, dan baris
   `import ForemanBoard …` membuatnya tetap hijau walau komponennya dihapus dari JSX. Gate
   kini menuntut `<ForemanBoard` (benar-benar **dirender**).
Tambahan: mutasi N07 kini mematikan **dua lapis** validasi alasan (model permintaan +
`build_readiness.start_build`) karena mematikan satu lapis saja tidak mengubah perilaku
(mutan ekuivalen — hijau yang benar, bukan gate longgar), dan gate mendapat **uji positif**
(dengan ack + alasan layak, mulai bangun HARUS berhasil) supaya "tombol yang tak pernah bisa
dipakai" ikut tertangkap.

**Status:** `bash scripts/run_all_gates.sh` → **OVERALL PASS (30 gates)**;
`python3 scripts/mutasi_46.py` → **16/16 TERTANGKAP** + baseline hijau kembali;
`python3 poc/poc_46.py` → PASS; E2E testing agent iterasi **68 & 69** (tanpa bug kritis).

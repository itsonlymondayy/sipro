"""Index MongoDB (dipisah dari `seed.py`).

`seed.py` sudah menyentuh batas gate compliance (800 baris) sementara daftar index terus
bertambah setiap fase. Memindahkan seluruh `ensure_indexes()` ke file sendiri membuat
keduanya tetap terbaca: `seed.py` fokus pada DATA awal, file ini fokus pada INDEX.
"""
import logging

from db import db
from seed_phase31 import ensure_build_indexes

logger = logging.getLogger("sipro.seed")


async def ensure_indexes():
    await db.users.create_index("email", unique=True)
    await db.users.create_index("id", unique=True)
    # Fase 41 — jam tahap: filter "lewat SLA" & laporan umur tahap dijalankan DI DATABASE,
    # jadi field jam tahap wajib punya index (tanpa ini setiap filter = collection scan).
    for _col in ("leads", "deals", "tasks", "complaints", "customers", "ar_invoices",
                 "documents"):
        await db[_col].create_index([("org_id", 1), ("stage_due_at", 1)])
        await db[_col].create_index([("org_id", 1), ("stage_entered_at", 1)])
    # Fase 42 — mitra & aturan fee.
    await db.partner_fee_rules.create_index([("org_id", 1), ("status", 1)])
    await db.partner_fee_rules.create_index([("org_id", 1), ("code", 1)], unique=True)
    await db.partner_attribution_conflicts.create_index([("org_id", 1), ("status", 1)])
    await db.marketing_fees.create_index([("org_id", 1), ("agent_id", 1), ("deal_id", 1),
                                          ("trigger", 1)])
    await db.leads.create_index([("org_id", 1), ("partner_id", 1)])
    await db.events.create_index([("status", 1), ("created_at", 1)])
    await db.tasks.create_index([("org_id", 1), ("assigned_to", 1), ("status", 1)])
    await db.tasks.create_index([("org_id", 1), ("source_event", 1)])
    await db.activities.create_index([("org_id", 1), ("entity_type", 1), ("entity_id", 1)])
    await db.notifications.create_index([("org_id", 1), ("user_email", 1), ("read", 1)])
    await db.leads.create_index([("org_id", 1), ("assigned_to", 1), ("stage", 1)])
    await db.units.create_index([("org_id", 1), ("project_id", 1)])
    # Slice A
    await db.deals.create_index([("org_id", 1), ("assigned_to", 1), ("status", 1)])
    await db.deals.create_index([("org_id", 1), ("unit_id", 1)])
    await db.documents.create_index([("org_id", 1), ("assigned_to", 1)])
    await db.conversations.create_index([("org_id", 1), ("owner", 1)])
    await db.messages.create_index([("conversation_id", 1), ("created_at", 1)])
    await db.appointments.create_index([("org_id", 1), ("assigned_to", 1)])
    await db.lead_capture_events.create_index([("org_id", 1), ("dedup_key", 1)], unique=True)
    # Slice B
    await db.construction_phases.create_index([("org_id", 1), ("project_id", 1), ("order", 1)])
    await db.construction_logs.create_index([("org_id", 1), ("project_id", 1), ("created_at", -1)])
    await db.materials.create_index([("org_id", 1), ("project_id", 1), ("code", 1)])
    await db.material_txns.create_index([("org_id", 1), ("project_id", 1), ("material_id", 1)])
    # Slice Finance
    await db.finance_configs.create_index([("org_id", 1), ("key", 1)], unique=True)
    await db.payment_schemes.create_index([("org_id", 1), ("is_default", 1)])
    await db.commission_schemes.create_index([("org_id", 1), ("is_default", 1)])
    await db.ar_invoices.create_index([("org_id", 1), ("deal_id", 1)], unique=True)
    await db.ar_invoices.create_index([("org_id", 1), ("status", 1)])
    await db.receipts.create_index([("org_id", 1), ("deal_id", 1), ("created_at", -1)])
    await db.contract_liabilities.create_index([("org_id", 1), ("deal_id", 1)], unique=True)
    await db.ap_invoices.create_index([("org_id", 1), ("status", 1), ("due_date", 1)])
    await db.payments_out.create_index([("org_id", 1), ("created_at", -1)])
    await db.commissions.create_index([("org_id", 1), ("assigned_to", 1), ("status", 1)])
    await db.revenue_recognitions.create_index([("org_id", 1), ("deal_id", 1)], unique=True)
    # EPIC 1.5 — Customers / KYC / Financing / Files
    await db.customers.create_index([("org_id", 1), ("nik", 1)])
    await db.customers.create_index([("org_id", 1), ("created_at", -1)])
    await db.financing_apps.create_index([("org_id", 1), ("deal_id", 1)])
    await db.financing_apps.create_index([("org_id", 1), ("status", 1)])
    await db.files.create_index([("org_id", 1), ("owner_type", 1), ("owner_id", 1)])
    await db.file_blobs.create_index("path", unique=True)
    # EPIC M1 — Customer Portal
    await db.portal_users.create_index([("phone", 1)])
    await db.portal_users.create_index([("email", 1)])
    await db.portal_users.create_index("id", unique=True)
    await db.portal_otps.create_index("portal_user_id", unique=True)
    await db.complaints.create_index([("org_id", 1), ("customer_id", 1), ("created_at", -1)])
    await db.complaints.create_index([("org_id", 1), ("status", 1)])
    # Phase 10 — Permit / document tracker
    await db.permits.create_index([("org_id", 1), ("project_id", 1)])
    await db.permits.create_index([("org_id", 1), ("status", 1), ("deadline", 1)])
    # Phase 11 — Field ops: site diary + punch list
    await db.site_diaries.create_index([("org_id", 1), ("project_id", 1), ("log_date", -1)])
    await db.punch_items.create_index([("org_id", 1), ("project_id", 1), ("status", 1)])
    # Phase 12 — Procurement pillar (BoQ + Subcon/SPK + PO/GRN/3-way)
    await db.subcontractors.create_index([("org_id", 1), ("code", 1)], unique=True)
    await db.spk.create_index([("org_id", 1), ("project_id", 1)])
    await db.spk.create_index([("org_id", 1), ("subcontractor_id", 1)])
    await db.progress_claims.create_index([("org_id", 1), ("spk_id", 1)])
    await db.progress_claims.create_index([("org_id", 1), ("status", 1)])
    await db.change_orders.create_index([("org_id", 1), ("spk_id", 1)])
    await db.boq_items.create_index([("org_id", 1), ("project_id", 1), ("cost_code", 1)])
    await db.purchase_orders.create_index([("org_id", 1), ("project_id", 1), ("status", 1)])
    await db.purchase_orders.create_index([("org_id", 1), ("po_number", 1)])
    await db.grns.create_index([("org_id", 1), ("po_id", 1)])
    await db.ap_invoices.create_index([("org_id", 1), ("po_id", 1)])
    # Phase 13 — CoA / General Ledger
    await db.accounts.create_index([("org_id", 1), ("code", 1)], unique=True)
    await db.journal_entries.create_index([("org_id", 1), ("date", -1)])
    await db.journal_entries.create_index([("org_id", 1), ("source_event", 1)])

    await db.faktur_pajak.create_index([("org_id", 1), ("deal_id", 1)], unique=True)
    await db.faktur_pajak.create_index([("org_id", 1), ("issued_at", -1)])
    await db.journal_entries.create_index([("org_id", 1), ("lines.account_code", 1)])
    # Phase 14 — EPIC 1.2 Appointment & Survey | Phase 31/32 — index jadwal pembangunan
    # (dipisah ke seed_phase31 agar file ini tetap di bawah batas gate compliance)
    await db.appointments.create_index([("org_id", 1), ("scheduled_at", 1)])
    await db.surveys.create_index([("org_id", 1), ("assigned_to", 1), ("status", 1)])
    await db.surveys.create_index([("org_id", 1), ("lead_id", 1)])
    await db.surveys.create_index([("org_id", 1), ("appointment_id", 1)])
    await ensure_build_indexes()
    logger.info("Indexes ensured.")

"""Seed Fase 29 — DOMAIN KERJA: divisi, supervisor/staf, dan katalog jobdesk.

Kenapa perlu seed khusus? Sebelum fase ini sistem hanya punya 8 peran datar tanpa divisi,
sehingga Work Hub tidak bisa dipakai supervisor. Di sini:
  1. Divisi Digital Marketing mendapat SUPERVISOR + STAF (peran baru), dan Keuangan
     mendapat supervisor sendiri (dulu tidak ada — finance merangkap semuanya).
  2. Semua pengguna lama di-backfill `division` + `level` dari peta peran (idempoten,
     tidak menimpa nilai yang sudah diatur admin).
  3. Katalog jobdesk (38 pekerjaan lintas 4 divisi) disinkronkan ke `jobdesk_templates`
     supaya supervisor bisa mengubah SLA/prioritas/penerima/verifikasi tanpa ubah kode.
  4. Task berulang periode berjalan langsung dibuat agar papan divisi tidak kosong.
"""
import logging

import reference_p29 as p29
import wa_playbooks as wp
import workhub as wh
from core_utils import new_id, now_iso
from db import db, ORG_ID
from security import hash_password

logger = logging.getLogger("sipro.seed")

TEST_PASSWORD = "Sipro#2026"

# Pengguna baru: pemimpin & anggota divisi yang tadinya tidak terwakili.
NEW_USERS = [
    {"name": "Nadia DM", "email": "dmlead@sipro.co.id", "role": "dm_supervisor",
     "division": "digital_marketing", "level": "supervisor"},
    {"name": "Vino Digital", "email": "dm@sipro.co.id", "role": "dm_staff",
     "division": "digital_marketing", "level": "staff"},
    {"name": "Hesti Keuangan", "email": "finlead@sipro.co.id", "role": "finance_manager",
     "division": "finance", "level": "supervisor"},
]


async def seed_phase29(org_id: str = ORG_ID) -> dict:
    ts = now_iso()
    created = 0
    for u in NEW_USERS:
        res = await db.users.update_one(
            {"email": u["email"]},
            {"$setOnInsert": {
                "id": new_id(), "org_id": org_id, "name": u["name"], "email": u["email"],
                "role": u["role"], "phone": None, "password_hash": hash_password(TEST_PASSWORD),
                "division": u["division"], "level": u["level"], "supervisor_email": None,
                "is_active": True, "created_at": ts, "updated_at": ts,
            }}, upsert=True)
        created += 1 if res.upserted_id else 0

    # Backfill divisi/level pengguna lama (tanpa menimpa yang sudah diatur admin).
    placed = 0
    async for u in db.users.find({"org_id": org_id}, {"_id": 0, "email": 1, "role": 1,
                                                     "division": 1, "level": 1}):
        upd = {}
        if not u.get("division") and p29.ROLE_DIVISION.get(u.get("role")):
            upd["division"] = p29.ROLE_DIVISION[u["role"]]
        if not u.get("level"):
            upd["level"] = p29.ROLE_LEVEL.get(u.get("role"), "staff")
        if upd:
            upd["updated_at"] = ts
            await db.users.update_one({"email": u["email"]}, {"$set": upd})
            placed += 1

    # Tautkan staf ke supervisor divisinya (informasi eskalasi).
    linked = 0
    for div in [o["value"] for o in p29.GROUPS_P29["division"]["options"]]:
        sup = await wh.division_members(org_id, div, level="supervisor")
        if not sup:
            continue
        res = await db.users.update_many(
            {"org_id": org_id, "division": div, "level": "staff",
             "supervisor_email": {"$in": [None, ""]}},
            {"$set": {"supervisor_email": sup[0]["email"], "updated_at": ts}})
        linked += res.modified_count

    # Template WA tambahan yang dibutuhkan playbook Fase 29b (pengingat bayar & promo).
    extra_templates = [
        ("payment_reminder", "Pengingat Pembayaran", "utility",
         "Halo {{nama}}, kami ingatkan angsuran/DP unit Anda akan jatuh tempo. "
         "Mohon konfirmasi jadwal pembayaran ya. Terima kasih."),
        ("promo", "Promo Cluster", "marketing",
         "Halo {{nama}}, ada promo terbatas di cluster kami bulan ini: "
         "keringanan DP & hadiah langsung. Boleh kami kirimkan detailnya?"),
    ]
    tmpl_made = 0
    for code, name, cat, body in extra_templates:
        res = await db.wa_templates.update_one(
            {"org_id": org_id, "code": code},
            {"$setOnInsert": {
                "id": new_id(), "org_id": org_id, "code": code, "name": name,
                "category": cat, "language": "id", "body": body, "variables": ["nama"],
                "status": "approved", "created_by": "seed", "created_at": ts, "updated_at": ts,
            }}, upsert=True)
        tmpl_made += 1 if res.upserted_id else 0

    jobdesks = await wh.ensure_jobdesk_templates(org_id)
    playbooks = await wp.ensure_playbooks(org_id)
    recurring = await wh.recurring_tick(org_id)
    logger.info("Seed Fase 29: %s pengguna divisi baru, %s pengguna ditempatkan, %s jobdesk, "
                "%s playbook WA, %s template WA, %s tugas berulang periode ini",
                created, placed, jobdesks, playbooks, tmpl_made, recurring)
    return {"users": created, "placed": placed, "linked": linked, "jobdesks": jobdesks,
            "playbooks": playbooks, "templates": tmpl_made, "recurring": recurring}

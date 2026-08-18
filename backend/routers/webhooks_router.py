"""Webhooks (SIMULATION-first) for omnichannel lead capture.

Public endpoints (no auth) that accept sample payloads from multiple providers:
Meta Lead Ads, WhatsApp, Google Lead Form, TikTok Lead, a generic Web form, dan — sejak
Fase 43 — MITRA (token per mitra). Ads attribution (campaign/campaign_id/adset/ad/creative/
form + utm/fbclid/gclid) dibawa sampai ke lead + lead_capture_event. Saat kredensial nyata
tersedia, cukup set `channel_accounts.mode='live'` — kontrak capture-nya tidak berubah.

Fase 30c — TIDAK ADA LEAD YANG HILANG LAGI. Dulu payload cacat (JSON rusak, nomor HP
kosong, field salah nama) dibalas 422 dan menguap: uang iklan terbayar tetapi lead tidak
pernah masuk CRM dan tidak ada jejaknya. Sekarang setiap kegagalan disimpan di antrean
`lead_capture_failures`, memicu event `capture.failed` (tugas DM-02 + notifikasi
supervisor), dan bisa diperbaiki lalu diulang dari halaman Automasi & Channel.

Fase 43 — webhook MITRA (`docs/v2/25_PARTNER_SPEC.md` §4). Dua hal yang membuatnya berbeda
dari kanal lain dan karena itu ditulis eksplisit:
  1. Nomor telepon lead UNIK per organisasi (index `uq_leads_phone`). Jadi mitra kedua yang
     mengklaim nomor yang sudah ada TIDAK boleh membuat lead kedua — klaimnya dicatat lewat
     mesin atribusi mitra (`partner_engine.attribute`) yang memutuskan pemenangnya sesuai
     model (first/last touch) dan menyimpan SENGKETA bila perlu. Dulu tidak ada pintu masuk
     resmi untuk lead mitra sama sekali; atribusi bergantung pada ingatan orang.
  2. Mitra yang kontraknya habis / ditangguhkan DITOLAK dengan alasan — bukan diterima
     diam-diam lalu memunculkan tagihan fee yang tidak boleh ada.
"""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

import capture_failures as cf
import partner_engine as pengine
from core_utils import now_iso, today_iso_date
from db import db, ORG_ID
from engine import process_lead_capture
from models import WebhookLead

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


def _failed(provider: str, failure: dict, reason: str) -> JSONResponse:
    """202: kami MENERIMA panggilan provider, tetapi leadnya tertahan (bukan hilang)."""
    return JSONResponse(status_code=202, content={"data": {
        "captured": False, "lead_id": None, "duplicate": False,
        "failure_id": failure["id"], "reason": reason,
        "queued": "Antrean lead gagal masuk (Automasi & Channel → Gagal Masuk)",
        "mode": "simulation", "provider": provider}})


async def _parse(provider: str, request: Request, defaults: dict = None):
    """-> (payload bersih, JSONResponse kegagalan). Satu pintu validasi semua provider."""
    raw, parse_err = await cf.read_json(request)
    if parse_err:
        failure = await cf.record(provider, raw or {}, parse_err, kind=cf.KIND_DATA,
                                  org_id=ORG_ID)
        return None, _failed(provider, failure, parse_err)
    try:
        data = WebhookLead(**raw).model_dump()
    except ValidationError as e:
        first = (e.errors() or [{}])[0]
        loc = ".".join(str(x) for x in (first.get("loc") or []))
        reason = f"Payload tidak sesuai kontrak pada '{loc or 'payload'}': {first.get('msg')}"
        failure = await cf.record(provider, raw, reason, kind=cf.KIND_DATA, org_id=ORG_ID)
        return None, _failed(provider, failure, reason)
    data.setdefault("source", provider)
    for key, value in (defaults or {}).items():
        data[key] = value
    clean, err = cf.validate(data)
    if err:
        failure = await cf.record(provider, data, err, kind=cf.KIND_DATA, org_id=ORG_ID)
        return None, _failed(provider, failure, err)
    return clean, None


async def _capture(provider: str, request: Request, defaults: dict = None):
    """Satu pintu untuk semua provider: parse → validasi → proses → (atau antrekan)."""
    clean, failed = await _parse(provider, request, defaults)
    if failed:
        return failed
    try:
        lead_id, duplicate = await process_lead_capture(provider, clean, org_id=ORG_ID)
    except Exception as e:  # noqa: BLE001 - gangguan sementara: layak dicoba ulang otomatis
        reason = f"Gangguan saat memproses lead: {e}"
        failure = await cf.record(provider, clean, reason, kind=cf.KIND_TRANSIENT,
                                  org_id=ORG_ID)
        return _failed(provider, failure, reason)
    return {"data": {"lead_id": lead_id, "duplicate": duplicate, "captured": True,
                     "mode": "simulation", "provider": provider}}


@router.post("/meta-lead")
async def meta_lead(request: Request):
    return await _capture("meta_ads", request)


@router.post("/wa")
async def wa_inbound(request: Request):
    return await _capture("whatsapp", request)


@router.post("/google-lead")
async def google_lead(request: Request):
    return await _capture("google_lead", request)


@router.post("/tiktok-lead")
async def tiktok_lead(request: Request):
    return await _capture("tiktok_lead", request)


@router.post("/web")
async def web_form(request: Request):
    return await _capture("website", request)


@router.post("/partner/{partner_id}")
async def partner_lead(partner_id: str, request: Request, token: str = None):
    """Lead dari sistem MITRA. Wajib token mitra (header `X-Partner-Token` atau `?token=`)."""
    provided = token or request.headers.get("X-Partner-Token") or ""
    partner = await db.agents.find_one({"id": partner_id, "org_id": ORG_ID}, {"_id": 0})
    # Jawaban SAMA untuk mitra tak dikenal dan token salah: siapa pun yang menebak-nebak
    # tidak boleh bisa memetakan daftar mitra kami dari balasan endpoint publik.
    if not partner or not partner.get("webhook_token") \
            or provided != partner.get("webhook_token"):
        return JSONResponse(status_code=401, content={"detail": (
            "Token mitra tidak sah. Minta ulang token di halaman profil mitra "
            "(Mitra & Fee → profil mitra → Webhook Lead).")})
    ok, why = pengine.contract_active(partner, today_iso_date())
    if partner.get("status") != "active" or not ok:
        return JSONResponse(status_code=403, content={"detail": (
            f"Mitra {partner.get('name')} tidak sedang aktif ({partner.get('status')}"
            f"{'; ' + why if why else ''}) — lead baru dari mitra ini ditolak supaya tidak "
            "melahirkan hak fee yang tidak boleh ada.")})
    clean, failed = await _parse("partner", request,
                                 {"source": "partner", "partner_id": partner_id})
    if failed:
        return failed
    existing = await db.leads.find_one({"org_id": ORG_ID, "phone": clean["phone"]},
                                      {"_id": 0, "id": 1, "partner_id": 1, "name": 1})
    verdict = await pengine.attribute(partner_id=partner_id, phone=clean["phone"],
                                      org_id=ORG_ID,
                                      lead_id=(existing or {}).get("id"))
    if existing:
        # Nomor sudah ada: JANGAN membuat lead kedua (nomor unik per organisasi). Klaim
        # mitra tetap dicatat + pemenangnya ditetapkan mesin atribusi.
        ts = now_iso()
        await db.leads.update_one({"id": existing["id"]}, {"$set": {
            "partner_id": verdict["partner_id"],
            "partner_attribution_model": verdict["model"],
            "partner_attributed_at": ts, "updated_at": ts,
            "last_touch": {"at": ts, "provider": "partner", "source": "partner",
                           "campaign": clean.get("campaign"), "partner_id": partner_id},
        }})
        for pid in {partner_id, verdict.get("partner_id")}:
            if pid:
                await pengine.refresh_stats(pid, org_id=ORG_ID)
        return {"data": {
            "lead_id": existing["id"], "duplicate": True, "captured": False,
            "mode": "simulation", "provider": "partner",
            "attributed_to": verdict["partner_id"], "attribution_model": verdict["model"],
            "conflict_id": (verdict.get("conflict") or {}).get("id"),
            "note": ("Nomor ini sudah ada di CRM. Klaim mitra dicatat dan atribusinya "
                     f"diputuskan dengan model {verdict['model']} — tidak ada lead kembar "
                     "yang dibuat.")}}
    clean["partner_id"] = verdict["partner_id"]
    try:
        lead_id, duplicate = await process_lead_capture("partner", clean, org_id=ORG_ID)
    except Exception as e:  # noqa: BLE001
        reason = f"Gangguan saat memproses lead mitra: {e}"
        failure = await cf.record("partner", clean, reason, kind=cf.KIND_TRANSIENT,
                                  org_id=ORG_ID)
        return _failed("partner", failure, reason)
    await pengine.refresh_stats(verdict["partner_id"], org_id=ORG_ID)
    return {"data": {"lead_id": lead_id, "duplicate": duplicate, "captured": True,
                     "mode": "simulation", "provider": "partner",
                     "attributed_to": verdict["partner_id"],
                     "attribution_model": verdict["model"],
                     "conflict_id": (verdict.get("conflict") or {}).get("id")}}

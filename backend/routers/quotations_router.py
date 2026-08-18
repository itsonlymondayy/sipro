"""ROUTER PENAWARAN (Fase 47C) — prefix `/quotations`.

Pemisahan tugas:
  * sales boleh MEMBUAT, MEREVISI, MENGIRIM, dan MENGONVERSI penawaran miliknya
    (`quotations:create/update`, row-scope: hanya penawaran yang ia buat);
  * hanya manajer sales/direksi yang boleh MEMUTUSKAN diskon di atas kewenangan
    (`quotations:approve`) — kalau tidak, batas diskon hanya hiasan.
"""
from fastapi import APIRouter, Depends, HTTPException, Response

import quotation_engine as qe
from core_utils import parse_pagination, serialize_doc
from db import ORG_ID
from models_p47 import (QuotationCreateIn, QuotationDecisionIn, QuotationSendIn,
                       QuotationSimulateIn)
from pdf_utils import build_document_pdf
from rbac import SALES_SCOPED_ROLES, audit_log, require_permission

router = APIRouter(prefix="/quotations", tags=["quotations"])


def _org(user: dict) -> str:
    return user.get("org_id", ORG_ID)


def _own(user: dict) -> str:
    """Sales hanya melihat penawaran yang ia buat (row-scope dipaksa server)."""
    return user.get("email") if user.get("role") in SALES_SCOPED_ROLES else None


async def _guard_owner(org: str, quotation_id: str, user: dict) -> dict:
    q = await qe.get(org, quotation_id)
    if user.get("role") in SALES_SCOPED_ROLES and q.get("created_by") != user.get("email"):
        raise HTTPException(status_code=403,
                            detail="Penawaran ini milik sales lain.")
    return q


@router.post("/simulate")
async def simulate(payload: QuotationSimulateIn,
                   user: dict = Depends(require_permission("quotations", "create"))):
    """Hitung harga+termin+simulasi KPR TANPA menyimpan. KPR kosong = 'belum ada data'."""
    try:
        out = await qe.simulate(_org(user), unit_id=payload.unit_id,
                                addons=[a.model_dump() for a in payload.addons],
                                scheme_id=payload.scheme_id,
                                discount_amount=payload.discount_amount,
                                kpr=(payload.kpr.model_dump() if payload.kpr else None))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"data": serialize_doc(out)}


@router.get("")
async def listing(lead_id: str = None, unit_id: str = None, state: str = None,
                  skip: int = 0, limit: int = 25,
                  user: dict = Depends(require_permission("quotations", "view"))):
    skip, limit = parse_pagination(skip, limit)
    out = await qe.listing(_org(user), lead_id=lead_id, unit_id=unit_id, state=state,
                           owner_email=_own(user), skip=skip, limit=limit)
    return {"data": serialize_doc(out["data"]), "total": out["total"],
            "summary": out["summary"]}


@router.post("")
async def create(payload: QuotationCreateIn,
                 user: dict = Depends(require_permission("quotations", "create"))):
    try:
        doc = await qe.create(_org(user), lead_id=payload.lead_id, unit_id=payload.unit_id,
                              addons=[a.model_dump() for a in payload.addons],
                              scheme_id=payload.scheme_id,
                              discount_amount=payload.discount_amount,
                              kpr=(payload.kpr.model_dump() if payload.kpr else None),
                              valid_days=payload.valid_days, note=payload.note,
                              discount_reason=payload.discount_reason,
                              actor=user.get("email"))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await audit_log(user, "create", "quotations", doc["id"],
                    {"no": doc["no"], "net_price": doc["net_price"],
                     "discount": doc["discount_amount"]})
    return {"data": serialize_doc(doc),
            "message": ("Penawaran menunggu persetujuan diskon manajer."
                        if doc["state"] == "awaiting_approval" else "Penawaran dibuat.")}


@router.get("/{quotation_id}")
async def detail(quotation_id: str,
                 user: dict = Depends(require_permission("quotations", "view"))):
    try:
        return {"data": serialize_doc(await _guard_owner(_org(user), quotation_id, user))}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{quotation_id}/revise")
async def revise(quotation_id: str, payload: QuotationCreateIn,
                 user: dict = Depends(require_permission("quotations", "update"))):
    """Revisi = VERSI BARU; versi lama menjadi 'diganti revisi terbaru' dan tetap terbaca."""
    org = _org(user)
    try:
        old = await _guard_owner(org, quotation_id, user)
        doc = await qe.create(org, lead_id=payload.lead_id or old["lead_id"],
                              unit_id=payload.unit_id,
                              addons=[a.model_dump() for a in payload.addons],
                              scheme_id=payload.scheme_id,
                              discount_amount=payload.discount_amount,
                              kpr=(payload.kpr.model_dump() if payload.kpr else None),
                              valid_days=payload.valid_days, note=payload.note,
                              discount_reason=payload.discount_reason,
                              actor=user.get("email"), version_of=old)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await audit_log(user, "revise", "quotations", doc["id"],
                    {"from": quotation_id, "version": doc["version"]})
    return {"data": serialize_doc(doc), "message": f"Revisi v{doc['version']} dibuat."}


@router.post("/{quotation_id}/decision")
async def decision(quotation_id: str, payload: QuotationDecisionIn,
                   user: dict = Depends(require_permission("quotations", "approve"))):
    """Manajer menyetujui/menolak diskon (wajib beralasan)."""
    try:
        out = await qe.decide_discount(_org(user), quotation_id, user.get("email"),
                                       payload.approve, payload.reason)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await audit_log(user, "decide_discount", "quotations", quotation_id,
                    {"approve": payload.approve, "reason": payload.reason})
    return {"data": serialize_doc(out),
            "message": ("Diskon disetujui." if payload.approve else "Diskon ditolak.")}


@router.post("/{quotation_id}/send")
async def send(quotation_id: str, payload: QuotationSendIn,
               user: dict = Depends(require_permission("quotations", "update"))):
    """Kirim ke calon pembeli. Tanpa kredensial WhatsApp → status ditulis 'simulasi'."""
    org = _org(user)
    try:
        await _guard_owner(org, quotation_id, user)
        out = await qe.mark_sent(org, quotation_id, user.get("email"),
                                 channel=payload.channel or "whatsapp", note=payload.note)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"data": serialize_doc(out),
            "message": f"Pengiriman: {out['delivery'].get('status')}"}


@router.post("/{quotation_id}/convert")
async def convert(quotation_id: str,
                  user: dict = Depends(require_permission("quotations", "update"))):
    """Konversi penawaran menjadi reservasi unit (deal)."""
    org = _org(user)
    try:
        await _guard_owner(org, quotation_id, user)
        out = await qe.convert(org, quotation_id, user.get("email"))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await audit_log(user, "convert", "quotations", quotation_id,
                    {"deal_id": out["deal"]["id"]})
    return {"data": serialize_doc(out), "message": "Penawaran menjadi reservasi unit."}


@router.get("/{quotation_id}/pdf")
async def pdf(quotation_id: str,
              user: dict = Depends(require_permission("quotations", "view"))):
    """PDF penawaran — isinya PERSIS angka yang tersimpan (bukan dihitung ulang di render)."""
    org = _org(user)
    try:
        q = await _guard_owner(org, quotation_id, user)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    def rp(v):
        return "Rp " + f"{int(v or 0):,}".replace(",", ".")

    lines = [f"Calon pembeli : {q.get('lead_name') or '-'}",
             f"Unit : {q.get('unit_code') or '-'}",
             f"Harga unit : {rp(q.get('base_price'))}"]
    for a in q.get("addons") or []:
        lines.append(f"Tambahan {a.get('name')} : {rp(a.get('amount'))} ({a.get('formula')})")
    lines += [f"Total sebelum potongan : {rp(q.get('gross_price'))}",
              f"Potongan : {rp(q.get('discount_amount'))} ({q.get('discount_pct')}%)",
              f"Harga penawaran : {rp(q.get('net_price'))}",
              f"Skema pembayaran : {(q.get('scheme') or {}).get('name') or '-'}"]
    for t in q.get("terms") or []:
        lines.append(f"{t.get('label')} : {rp(t.get('amount'))} · jatuh tempo "
                     f"{str(t.get('due_date'))[:10]}")
    kpr = q.get("kpr") or {}
    if kpr.get("state") == "complete":
        lines.append(f"Estimasi KPR : {rp(kpr.get('monthly_installment'))}/bulan · "
                     f"{kpr.get('tenor_months')} bulan · bunga {kpr.get('annual_rate_pct')}%")
    else:
        lines.append("Estimasi KPR : belum bisa dihitung ("
                     + ", ".join(kpr.get("missing") or []).replace("_", " ")
                     + " belum diisi)")
    lines.append(f"Berlaku sampai : {q.get('valid_until')}")
    body = build_document_pdf(
        title="PENAWARAN HARGA UNIT", doc_number=f"{q.get('no')} v{q.get('version')}",
        content="\n".join(lines),
        signatures=[{"role": "Sales", "name": q.get("created_by"), "signed_at": None},
                    {"role": "Calon Pembeli", "name": q.get("lead_name"), "signed_at": None}])
    return Response(content=body, media_type="application/pdf", headers={
        "Content-Disposition": f'inline; filename="{q.get("no")}.pdf"'})

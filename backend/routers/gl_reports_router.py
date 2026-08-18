"""Laporan keuangan periodik + tutup periode (P25 — kelengkapan akuntansi).

Endpoint (RBAC resource `gl` — finance + owner/super_admin):
  GET  /gl/reports/worksheet         — Neraca Lajur (saldo awal|transaksi|penyesuaian|akhir|L/R|Neraca)
  GET  /gl/reports/income-statement  — Laba Rugi periodik + pembanding periode sebelumnya
  GET  /gl/reports/balance-sheet     — Neraca per tanggal (as_of) + klasifikasi lancar
  GET  /gl/reports/cash-flow         — Arus Kas metode langsung (operasi/investasi/pendanaan)
  GET  /gl/reports/projects          — Laba Rugi per proyek (segment)
  GET  /gl/reports/ratios            — Analisa rasio + interpretasi
  GET  /gl/reports/ledger            — buku besar berperiode (drill-down dari laporan)
  GET  /gl/periods                   — status periode (open/closed) + ringkasan
  POST /gl/periods/close             — tutup periode (finance)
  POST /gl/periods/reopen            — buka kembali periode (owner/super_admin — `approve`)

Semua GET memiliki query opsional (default: bulan berjalan) agar endpoint sweep 200.
"""
import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

import gl_engine as gl
import gl_periods as glp
import gl_reports as glr
from core_utils import serialize_doc
from db import db, ORG_ID
from rbac import require_permission, audit_log

router = APIRouter(prefix="/gl", tags=["gl-reports"])

PERIOD_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


class PeriodAction(BaseModel):
    period: str = Field(..., description="Periode YYYY-MM")
    note: str = None


def _validate_period(period: str) -> str:
    if not PERIOD_RE.match(period or ""):
        raise HTTPException(status_code=400, detail="Format periode harus YYYY-MM (mis. 2026-08).")
    return period


# ----------------------------- laporan -----------------------------
@router.get("/reports/worksheet")
async def get_worksheet(date_from: str = None, date_to: str = None,
                        user: dict = Depends(require_permission("gl", "view"))):
    org = user.get("org_id", ORG_ID)
    await gl.ensure_coa(org)
    return {"data": serialize_doc(await glr.worksheet(org, date_from, date_to))}


@router.get("/reports/income-statement")
async def get_income_statement(date_from: str = None, date_to: str = None, compare: bool = True,
                               user: dict = Depends(require_permission("gl", "view"))):
    org = user.get("org_id", ORG_ID)
    await gl.ensure_coa(org)
    return {"data": serialize_doc(await glr.income_statement(org, date_from, date_to, compare))}


@router.get("/reports/balance-sheet")
async def get_balance_sheet(as_of: str = None,
                            user: dict = Depends(require_permission("gl", "view"))):
    org = user.get("org_id", ORG_ID)
    await gl.ensure_coa(org)
    return {"data": serialize_doc(await glr.balance_sheet(org, as_of))}


@router.get("/reports/cash-flow")
async def get_cash_flow(date_from: str = None, date_to: str = None,
                        user: dict = Depends(require_permission("gl", "view"))):
    org = user.get("org_id", ORG_ID)
    await gl.ensure_coa(org)
    return {"data": serialize_doc(await glr.cash_flow(org, date_from, date_to))}


@router.get("/reports/projects")
async def get_project_report(date_from: str = None, date_to: str = None,
                             user: dict = Depends(require_permission("gl", "view"))):
    org = user.get("org_id", ORG_ID)
    await gl.ensure_coa(org)
    return {"data": serialize_doc(await glr.project_report(org, date_from, date_to))}


@router.get("/reports/ratios")
async def get_ratios(date_from: str = None, date_to: str = None,
                     user: dict = Depends(require_permission("gl", "view"))):
    org = user.get("org_id", ORG_ID)
    await gl.ensure_coa(org)
    return {"data": serialize_doc(await glr.ratios(org, date_from, date_to))}


@router.get("/reports/ledger")
async def get_period_ledger(account_code: str = None, date_from: str = None, date_to: str = None,
                            user: dict = Depends(require_permission("gl", "view"))):
    org = user.get("org_id", ORG_ID)
    await gl.ensure_coa(org)
    if not account_code:
        return {"data": {"account": None, "lines": [], "opening": 0, "closing": 0,
                         "total_debit": 0, "total_credit": 0, "period": None}}
    return {"data": serialize_doc(await glr.ledger(org, account_code, date_from, date_to))}


# ----------------------------- tutup periode -----------------------------
@router.get("/periods")
async def list_periods(limit: int = 18, user: dict = Depends(require_permission("gl", "view"))):
    org = user.get("org_id", ORG_ID)
    limit = max(1, min(int(limit or 18), 60))
    closed = await glp.closed_periods(org)
    counts = {}
    for je in await db.journal_entries.find({"org_id": org}, {"_id": 0, "date": 1}).to_list(200000):
        m = str(je.get("date"))[:7]
        if len(m) == 7:
            counts[m] = counts.get(m, 0) + 1
    months = sorted(set(counts) | set(closed), reverse=True)[:limit]
    meta = {p["period"]: p for p in await db.accounting_periods.find(
        {"org_id": org}, {"_id": 0}).to_list(1200)}
    rows = []
    for m in months:
        start, end = glr.month_range(m)
        pl = await glr._pl_block(org, start, end)
        info = meta.get(m) or {}
        rows.append({
            "period": m, "status": "closed" if m in closed else "open",
            "journals": counts.get(m, 0), "revenue": pl["total_revenue"],
            "expense": pl["total_expense"], "net_income": pl["net_income"],
            "closed_by": info.get("closed_by"), "closed_at": info.get("closed_at"),
            "reopened_by": info.get("reopened_by"), "reopened_at": info.get("reopened_at"),
            "note": info.get("note"),
        })
    return {"data": rows, "total": len(rows), "closed_count": len(closed)}


@router.post("/periods/close")
async def close_period(payload: PeriodAction,
                       user: dict = Depends(require_permission("gl", "update"))):
    org = user.get("org_id", ORG_ID)
    period = _validate_period(payload.period)
    if period in await glp.closed_periods(org):
        raise HTTPException(status_code=400, detail=f"Periode {period} sudah ditutup.")
    doc = await glp.close_period(org, period, user.get("email"), payload.note)
    await audit_log(user, "close", "accounting_periods", period, {"note": payload.note})
    return {"data": serialize_doc(doc)}


@router.post("/periods/reopen")
async def reopen_period(payload: PeriodAction,
                        user: dict = Depends(require_permission("gl", "approve"))):
    """Buka kembali periode — sengaja dibatasi (owner/super_admin) sebagai kontrol SoD."""
    org = user.get("org_id", ORG_ID)
    period = _validate_period(payload.period)
    if period not in await glp.closed_periods(org):
        raise HTTPException(status_code=400, detail=f"Periode {period} tidak dalam status tertutup.")
    doc = await glp.reopen_period(org, period, user.get("email"), payload.note)
    await audit_log(user, "reopen", "accounting_periods", period, {"note": payload.note})
    return {"data": serialize_doc(doc)}

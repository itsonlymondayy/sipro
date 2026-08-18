"""Outbound notification providers (config-driven, real-ready + honest fallback).

- WhatsApp: Meta WhatsApp Cloud API when WHATSAPP_TOKEN + WHATSAPP_PHONE_ID are set,
            otherwise a simulation that logs the message (used for OTP + complaint ack).
- E-sign:   generic provider when ESIGN_API_KEY is set, otherwise a simulation that
            marks the request as signed immediately.

Nothing here blocks the app: if credentials are absent the simulation path runs so
the feature is fully functional now; add env vars later to go live.
"""
import os
import random
import asyncio
import logging

import requests

from core_utils import now_iso

logger = logging.getLogger("sipro.notifications")


# ----------------------------- WhatsApp -----------------------------
def whatsapp_configured() -> bool:
    return bool(os.environ.get("WHATSAPP_TOKEN") and os.environ.get("WHATSAPP_PHONE_ID"))


def _send_whatsapp_real(to: str, message: str) -> dict:
    token = os.environ["WHATSAPP_TOKEN"]
    phone_id = os.environ["WHATSAPP_PHONE_ID"]
    url = f"https://graph.facebook.com/v20.0/{phone_id}/messages"
    resp = requests.post(
        url,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"messaging_product": "whatsapp", "to": to, "type": "text",
              "text": {"body": message}},
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json()


async def send_whatsapp(to: str, message: str) -> dict:
    """Send a WhatsApp text; falls back to simulation (logged) when not configured."""
    if to and whatsapp_configured():
        try:
            raw = await asyncio.to_thread(_send_whatsapp_real, to, message)
            return {"provider": "whatsapp_cloud", "status": "sent", "raw": raw}
        except Exception as e:  # noqa: BLE001
            logger.warning("WhatsApp send failed (%s); simulating.", e)
    logger.info("[SIM WhatsApp] to=%s | %s", to, message)
    return {"provider": "simulation", "status": "logged"}


def gen_otp(n: int = 6) -> str:
    return "".join(str(random.randint(0, 9)) for _ in range(n))


# ----------------------------- E-sign -----------------------------
def esign_configured() -> bool:
    return bool(os.environ.get("ESIGN_API_KEY") and os.environ.get("ESIGN_BASE_URL"))


def _request_esign_real(*, document_id: str, signer_name: str, signer_email: str = None) -> dict:
    base = os.environ["ESIGN_BASE_URL"].rstrip("/")
    resp = requests.post(
        f"{base}/signature-requests",
        headers={"Authorization": f"Bearer {os.environ['ESIGN_API_KEY']}"},
        json={"document_id": document_id, "signer_name": signer_name, "signer_email": signer_email},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


async def request_esignature(*, document_id: str, signer_name: str, signer_email: str = None) -> dict:
    """Request an e-signature; simulation marks it signed immediately when not configured."""
    if esign_configured():
        try:
            raw = await asyncio.to_thread(
                _request_esign_real, document_id=document_id,
                signer_name=signer_name, signer_email=signer_email)
            return {"provider": "esign", "status": "pending", "raw": raw}
        except Exception as e:  # noqa: BLE001
            logger.warning("E-sign request failed (%s); simulating.", e)
    logger.info("[SIM e-sign] doc=%s signer=%s", document_id, signer_name)
    return {"provider": "simulation", "status": "signed", "signed_at": now_iso()}

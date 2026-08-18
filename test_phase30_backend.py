#!/usr/bin/env python3
"""Phase 30 Backend API Quick Test - SIPRO.

Focused tests for Phase 30 features:
1. SLIK Pre-screening with evidence
2. Photo compression + watermark
3. Webhook capture failures

Uses public endpoint.
"""
import io
import os
import sys
import uuid
import requests

BASE = (os.environ.get("SIPRO_BASE") or "http://localhost:8001").rstrip("/") + "/api"
PW = "Sipro#2026"
PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    status = "✅" if cond else "❌"
    print(f"{status} {name}" + (f" — {detail}" if detail else ""))
    return bool(cond)


def login(email):
    try:
        r = requests.post(f"{BASE}/auth/login", 
                         json={"email": email, "password": PW}, timeout=30)
        r.raise_for_status()
        return {"Authorization": f"Bearer {r.json()['access_token']}"}
    except Exception as e:
        print(f"❌ Login failed for {email}: {e}")
        return None


def test_slik(sales_h):
    print("\n=== SLIK Pre-screening API ===")
    phone = f"+62813{uuid.uuid4().int % 10**8:08d}"
    r = requests.post(f"{BASE}/leads", headers=sales_h,
                     json={"name": "Test SLIK", "phone": phone, "source": "walk_in"}, timeout=30)
    if not check("Create lead", r.status_code == 200):
        return
    
    lead_id = r.json()["data"]["id"]
    r = requests.get(f"{BASE}/leads/{lead_id}/lifecycle", headers=sales_h, timeout=30)
    check("Get lifecycle", r.status_code == 200)
    
    r = requests.post(f"{BASE}/leads/{lead_id}/slik-prescreen", headers=sales_h,
                     json={"status": "clear"}, timeout=30)
    check("Clear without evidence rejected", r.status_code == 400)
    
    files = {"file": ("ideb.pdf", b"%PDF-1.4 Test\n", "application/pdf")}
    form = {"owner_type": "lead", "owner_id": lead_id, "optimize": "false"}
    r = requests.post(f"{BASE}/files/upload", headers=sales_h, files=files, data=form, timeout=60)
    if not check("Upload evidence", r.status_code == 200):
        return
    
    file_id = r.json()["data"]["id"]
    r = requests.post(f"{BASE}/leads/{lead_id}/slik-prescreen", headers=sales_h,
                     json={"status": "clear", "note": "OK", "evidence_file_ids": [file_id]}, timeout=30)
    check("Submit SLIK with evidence", r.status_code == 200)


def test_photo(site_h):
    print("\n=== Photo Optimization API ===")
    try:
        from PIL import Image
        img = Image.new("RGB", (2000, 1500), (100, 150, 200))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=95)
        photo_data = buf.getvalue()
    except ImportError:
        print("⚠️  PIL not available, skipping")
        return
    
    files = {"file": ("test.jpg", photo_data, "image/jpeg")}
    form = {"owner_type": "site_diary", "watermark": "Test · A-01", "optimize": "true"}
    r = requests.post(f"{BASE}/files/upload", headers=site_h, files=files, data=form, timeout=90)
    
    if check("Upload photo", r.status_code == 200):
        data = r.json()["data"]
        check("Optimized", data.get("optimized") is True)
        check("Watermark", data.get("watermark") is not None)
        check("Thumbnail", data.get("thumb_size", 0) > 0)


def test_capture(dmlead_h, sales_h):
    print("\n=== Capture Failures API ===")
    tag = uuid.uuid4().hex[:6]
    r = requests.post(f"{BASE}/webhooks/meta-lead",
                     json={"name": f"No Phone {tag}", "campaign": "Test"}, timeout=30)
    check("Bad webhook → 202", r.status_code == 202)
    
    r = requests.get(f"{BASE}/capture/failures", headers=dmlead_h, timeout=30)
    check("List failures (supervisor)", r.status_code == 200)
    
    r = requests.get(f"{BASE}/capture/failures", headers=sales_h, timeout=30)
    check("Sales blocked (RBAC)", r.status_code == 403)


def main():
    print("=" * 60)
    print("Phase 30 Backend API Quick Test")
    print("=" * 60)
    
    sales_h = login("sales@sipro.co.id")
    site_h = login("site@sipro.co.id")
    dmlead_h = login("dmlead@sipro.co.id")
    
    if not all([sales_h, site_h, dmlead_h]):
        print("\n❌ Login failed")
        return 1
    
    try:
        test_slik(sales_h)
        test_photo(site_h)
        test_capture(dmlead_h, sales_h)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    print(f"\n{'=' * 60}")
    print(f"RESULTS: {len(PASS)} PASS, {len(FAIL)} FAIL")
    print("=" * 60)
    
    if FAIL:
        print("\n❌ Failed:")
        for f in FAIL:
            print(f"  - {f}")
        return 1
    
    print("\n✅ All tests passed!")
    return 0


if __name__ == "__main__":
    sys.exit(main())

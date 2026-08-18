#!/usr/bin/env python3
"""Backend API Testing for SIPRO Fase 33 - RAB/BoQ <-> Opname & Termin Subkon

Tests all Fase 33 features:
- SPK scope management (add/remove items)
- Opname preview (claimable verified work)
- Claims submission (item-based vs lumpsum)
- Opname verification (PM can reduce lines with reason)
- Finance approval (creates AP bill)
- Anti-duplicate SPK (INV-33-3)
- Cost control (RAB budget vs contracted vs verified vs billed)
- RBAC (sales can't access, site can view but not POST)
"""
import sys
import requests
from datetime import datetime

BASE_URL = "https://sales-scope-verify.preview.emergentagent.com/api"
PASSWORD = "Sipro#2026"

class TestRunner:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.tokens = {}
        self.test_data = {}
        
    def test(self, name, condition, detail=""):
        """Run a single test assertion"""
        if condition:
            self.passed += 1
            print(f"  ✓ PASS: {name}")
            if detail:
                print(f"         {detail}")
        else:
            self.failed += 1
            print(f"  ✗ FAIL: {name}")
            if detail:
                print(f"         {detail}")
        return condition
    
    def login(self, email):
        """Login and store token"""
        try:
            r = requests.post(f"{BASE_URL}/auth/login", 
                            json={"email": email, "password": PASSWORD}, 
                            timeout=30)
            if r.status_code == 200:
                self.tokens[email] = r.json()["access_token"]
                print(f"  ✓ Logged in as {email}")
                return True
            else:
                print(f"  ✗ Login failed for {email}: {r.status_code}")
                return False
        except Exception as e:
            print(f"  ✗ Login error for {email}: {str(e)}")
            return False
    
    def headers(self, email):
        """Get auth headers for user"""
        return {"Authorization": f"Bearer {self.tokens.get(email, '')}"}
    
    def get(self, path, email, params=None):
        """GET request"""
        try:
            return requests.get(f"{BASE_URL}{path}", 
                              headers=self.headers(email),
                              params=params or {},
                              timeout=30)
        except Exception as e:
            print(f"  ✗ GET {path} error: {str(e)}")
            return None
    
    def post(self, path, email, data=None):
        """POST request"""
        try:
            return requests.post(f"{BASE_URL}{path}",
                               headers=self.headers(email),
                               json=data or {},
                               timeout=30)
        except Exception as e:
            print(f"  ✗ POST {path} error: {str(e)}")
            return None
    
    def delete(self, path, email):
        """DELETE request"""
        try:
            return requests.delete(f"{BASE_URL}{path}",
                                 headers=self.headers(email),
                                 timeout=30)
        except Exception as e:
            print(f"  ✗ DELETE {path} error: {str(e)}")
            return None
    
    def summary(self):
        """Print test summary"""
        total = self.passed + self.failed
        print("\n" + "="*70)
        print(f"TEST SUMMARY: {self.passed}/{total} passed")
        if self.failed > 0:
            print(f"FAILED: {self.failed} tests")
            return 1
        else:
            print("ALL TESTS PASSED ✓")
            return 0


def main():
    runner = TestRunner()
    
    print("="*70)
    print("SIPRO FASE 33 - BACKEND API TESTS")
    print("RAB/BoQ <-> Opname & Termin Subkontraktor")
    print("="*70)
    
    # ========== AUTHENTICATION ==========
    print("\n[1] AUTHENTICATION")
    if not runner.login("pm@sipro.co.id"):
        print("CRITICAL: PM login failed, stopping tests")
        return 1
    if not runner.login("site@sipro.co.id"):
        print("CRITICAL: Site login failed, stopping tests")
        return 1
    if not runner.login("finance@sipro.co.id"):
        print("CRITICAL: Finance login failed, stopping tests")
        return 1
    if not runner.login("sales@sipro.co.id"):
        print("CRITICAL: Sales login failed, stopping tests")
        return 1
    
    # ========== GET SPK IDs FIRST ==========
    print("\n[2] GETTING SPK IDs")
    r = runner.get("/subcon/spk", "pm@sipro.co.id")
    if not runner.test("GET /subcon/spk returns 200", r and r.status_code == 200):
        print("CRITICAL: Cannot get SPK list, stopping tests")
        return 1
    
    spks = r.json().get("data", [])
    spk_map = {spk.get("spk_number"): spk.get("id") for spk in spks}
    
    if "SPK/2026/0003" not in spk_map:
        print("CRITICAL: SPK/2026/0003 not found, stopping tests")
        return 1
    
    spk_003_id = spk_map["SPK/2026/0003"]
    spk_001_id = spk_map.get("SPK/2026/0001")
    spk_002_id = spk_map.get("SPK/2026/0002")
    
    print(f"  Found SPK/2026/0003 ID: {spk_003_id}")
    
    # ========== US-1: GET SPK SCOPE (PM) ==========
    print("\n[3] US-1: GET SPK SCOPE - PM can view scope with metrics")
    r = runner.get(f"/subcon/spk/{spk_003_id}/scope", "pm@sipro.co.id")
    if runner.test("GET /subcon/spk/{id}/scope returns 200", r and r.status_code == 200):
        data = r.json().get("data", [])
        summary = r.json().get("summary", {})
        spk = r.json().get("spk", {})
        blockers = r.json().get("blockers", [])
        
        runner.test("Scope has 10 rows", len(data) == 10, f"Got {len(data)} rows")
        runner.test("Scope value is Rp 66.000.000", summary.get("scope_value") == 66000000)
        runner.test("Verified value is Rp 30.000.000", summary.get("verified_value") == 30000000)
        runner.test("Claimable value is Rp 30.000.000", summary.get("claimable_value") == 30000000)
        runner.test("Billed value is Rp 0", summary.get("billed_value") == 0)
        runner.test("SPK mode is 'items'", spk.get("scope_mode") == "items")
        runner.test("Blockers list exists", len(blockers) > 0, f"Got {len(blockers)} blocker groups")
        
        # Store first scope item for later deletion test
        if data:
            runner.test_data["scope_item_id"] = data[0].get("id")
            runner.test_data["build_item_id"] = data[0].get("build_item_id")
    
    # ========== US-2: GET OPNAME PREVIEW ==========
    print("\n[4] US-2: GET OPNAME PREVIEW - Shows claimable verified work")
    r = runner.get(f"/subcon/spk/{spk_003_id}/opname", "pm@sipro.co.id")
    if runner.test("GET /subcon/spk/{id}/opname returns 200", r and r.status_code == 200):
        data = r.json().get("data", {})
        lines = data.get("lines", [])
        
        runner.test("Gross is Rp 30.000.000", data.get("gross") == 30000000)
        runner.test("Retention 5% is Rp 1.500.000", data.get("retention_est") == 1500000)
        runner.test("Net is Rp 28.500.000", data.get("net_est") == 28500000)
        runner.test("Has 5 claimable lines", len(lines) == 5, f"Got {len(lines)} lines")
        runner.test("Blockers explain why 5 works can't be claimed", len(data.get("blockers", [])) > 0)
    
    # ========== US-3: GET SCOPE CANDIDATES ==========
    print("\n[5] US-3: GET SCOPE CANDIDATES - Available work items")
    r = runner.get(f"/subcon/spk/{spk_003_id}/scope/candidates", "pm@sipro.co.id")
    if runner.test("GET /subcon/spk/{id}/scope/candidates returns 200", r and r.status_code == 200):
        data = r.json().get("data", {})
        units = data.get("units", [])
        
        runner.test("Candidates list returned", isinstance(units, list))
        runner.test("Contract value matches", data.get("contract_value") == 66000000)
        runner.test("Allocated matches scope", data.get("allocated") == 66000000)
        runner.test("Unallocated is 0 (fully allocated)", data.get("unallocated") == 0)
    
    # ========== US-4: RBAC - SALES CAN'T ACCESS SCOPE ==========
    print("\n[6] US-4: RBAC - Sales cannot access scope endpoints")
    r = runner.get(f"/subcon/spk/{spk_003_id}/scope", "sales@sipro.co.id")
    runner.test("Sales GET scope returns 403", r and r.status_code == 403)
    
    r = runner.get(f"/subcon/spk/{spk_003_id}/opname", "sales@sipro.co.id")
    runner.test("Sales GET opname returns 403", r and r.status_code == 403)
    
    # ========== US-5: RBAC - SITE CAN VIEW BUT NOT POST ==========
    print("\n[7] US-5: RBAC - Site can view but cannot POST scope")
    r = runner.get(f"/subcon/spk/{spk_003_id}/scope", "site@sipro.co.id")
    runner.test("Site can GET scope (200)", r and r.status_code == 200)
    
    r = runner.post(f"/subcon/spk/{spk_003_id}/scope", "site@sipro.co.id", 
                   {"lines": [{"build_item_id": "test", "value": 1000000}]})
    runner.test("Site POST scope returns 403", r and r.status_code == 403)
    
    # ========== US-6: SUBMIT ITEM-BASED CLAIM (SITE) ==========
    print("\n[8] US-6: SUBMIT ITEM-BASED CLAIM - Site submits claim")
    r = runner.post("/subcon/claims", "site@sipro.co.id", {
        "spk_id": spk_003_id,
        "period": "Termin pekerjaan terverifikasi",
        "note": "Test claim submission"
    })
    if runner.test("POST /subcon/claims returns 200", r and r.status_code == 200):
        claim = r.json().get("data", {})
        
        runner.test("Claim basis is 'items'", claim.get("basis") == "items")
        runner.test("Claim has 5 lines", len(claim.get("lines", [])) == 5)
        runner.test("Gross estimate is Rp 30.000.000", claim.get("gross_est") == 30000000)
        runner.test("Status is 'submitted'", claim.get("status") == "submitted")
        runner.test("No progress_pct field for item-based", "progress_pct" not in str(claim))
        
        runner.test_data["claim_id"] = claim.get("id")
        runner.test_data["claim_number"] = claim.get("claim_number")
    
    # ========== US-7: OPNAME - PM VERIFIES CLAIM ==========
    print("\n[9] US-7: OPNAME - PM verifies claim (reduce 1 line)")
    if "claim_id" in runner.test_data:
        claim_id = runner.test_data["claim_id"]
        
        # First, get the claim to see lines
        r = runner.get(f"/subcon/claims/{claim_id}", "pm@sipro.co.id")
        if r and r.status_code == 200:
            claim = r.json().get("data", {})
            lines = claim.get("lines", [])
            
            if len(lines) >= 2:
                # Exclude first line
                exclude_id = lines[0].get("scope_item_id")
                
                r = runner.post(f"/subcon/claims/{claim_id}/verify", "pm@sipro.co.id", {
                    "exclude": [exclude_id],
                    "reason": "Volume plester kurang 2 m2",
                    "note": "Opname test"
                })
                
                if runner.test("POST /subcon/claims/{id}/verify returns 200", r and r.status_code == 200):
                    verified = r.json().get("data", {})
                    
                    runner.test("Status changed to 'verified'", verified.get("status") == "verified")
                    runner.test("Excluded 1 item", verified.get("excluded_items") == 1)
                    runner.test("Gross reduced", verified.get("gross_est") < 30000000)
                    runner.test("Opname reason saved", verified.get("opname_reason") is not None)
    
    # ========== US-8: SOD - SUBMITTER CAN'T VERIFY OWN CLAIM ==========
    print("\n[10] US-8: SoD - Submitter cannot verify own claim")
    if "claim_id" in runner.test_data:
        r = runner.post(f"/subcon/claims/{runner.test_data['claim_id']}/verify", 
                       "site@sipro.co.id", {
            "exclude": [],
            "reason": "Test"
        })
        runner.test("Site (submitter) verify returns 403", r and r.status_code == 403)
    
    # ========== US-9: FINANCE APPROVES CLAIM ==========
    print("\n[11] US-9: FINANCE APPROVES CLAIM - Creates AP bill")
    if "claim_id" in runner.test_data:
        r = runner.post(f"/subcon/claims/{runner.test_data['claim_id']}/approve", 
                       "finance@sipro.co.id")
        
        if runner.test("POST /subcon/claims/{id}/approve returns 200", r and r.status_code == 200):
            approved = r.json().get("data", {})
            
            runner.test("Status changed to 'approved'", approved.get("status") == "approved")
            runner.test("Gross value set", approved.get("gross") > 0)
            runner.test("Retention held calculated", approved.get("retention_held") > 0)
            runner.test("Net value calculated", approved.get("net") > 0)
            runner.test("AP bill created", approved.get("ap_bill_id") is not None)
    
    # ========== US-10: PM CAN'T APPROVE CLAIM ==========
    print("\n[12] US-10: RBAC - PM cannot approve claims")
    # Create another claim for this test
    if spk_001_id:
        r = runner.post("/subcon/claims", "site@sipro.co.id", {
            "spk_id": spk_001_id,  # Lumpsum SPK
            "progress_pct": 50,
            "period": "Test claim for RBAC",
            "note": "Test"
        })
        if r and r.status_code == 200:
            test_claim_id = r.json().get("data", {}).get("id")
            
            r = runner.post(f"/subcon/claims/{test_claim_id}/approve", "pm@sipro.co.id")
            runner.test("PM approve returns 403", r and r.status_code == 403)
    
    # ========== US-11: AFTER APPROVAL, PAID ITEMS SHOW "SUDAH DITAGIH" ==========
    print("\n[12] US-11: After approval, paid items marked as billed")
    r = runner.get(f"/subcon/spk/{spk_003_id}/scope", "pm@sipro.co.id")
    if runner.test("GET scope after approval returns 200", r and r.status_code == 200):
        data = r.json().get("data", [])
        summary = r.json().get("summary", {})
        
        billed_items = [item for item in data if item.get("claim_id")]
        runner.test("Some items marked as billed", len(billed_items) > 0, 
                   f"Found {len(billed_items)} billed items")
        runner.test("Billed value increased", summary.get("billed_value") > 0)
        runner.test("Claimable value decreased", summary.get("claimable_value") < 30000000)
    
    # ========== US-12: OPNAME PREVIEW EXCLUDES BILLED ITEMS ==========
    print("\n[13] US-12: Opname preview excludes already billed items")
    r = runner.get(f"/subcon/spk/{spk_003_id}/opname", "pm@sipro.co.id")
    if runner.test("GET opname after approval returns 200", r and r.status_code == 200):
        data = r.json().get("data", {})
        lines = data.get("lines", [])
        
        runner.test("Claimable lines reduced", len(lines) < 5, 
                   f"Now {len(lines)} claimable (was 5)")
        runner.test("Gross reduced", data.get("gross") < 30000000)
    
    # ========== US-13: ANTI-DUPLICATE SPK (INV-33-3) ==========
    print("\n[14] US-13: Anti-duplicate - Same build_item_id can't be in 2 SPKs")
    if "build_item_id" in runner.test_data:
        # Try to add same build_item to another SPK
        r = runner.post(f"/subcon/spk/{spk_002_id}/scope", "pm@sipro.co.id", {
            "lines": [{
                "build_item_id": runner.test_data["build_item_id"],
                "value": 5000000
            }]
        })
        runner.test("Adding duplicate build_item returns 400", r and r.status_code == 400)
        if r:
            runner.test("Error mentions SPK number", "SPK/2026/0003" in r.text)
    
    # ========== US-14: CAN'T DELETE BILLED SCOPE ITEM ==========
    print("\n[15] US-14: Cannot delete scope item that's already billed")
    # Find a billed item
    r = runner.get(f"/subcon/spk/{spk_003_id}/scope", "pm@sipro.co.id")
    if r and r.status_code == 200:
        data = r.json().get("data", [])
        billed_item = next((item for item in data if item.get("claim_id")), None)
        
        if billed_item:
            r = runner.delete(f"/subcon/spk/SPK/2026/0003/scope/{billed_item['id']}", 
                            "pm@sipro.co.id")
            runner.test("DELETE billed scope item returns 400", r and r.status_code == 400)
            if r:
                runner.test("Error mentions claim number", "termin" in r.text.lower())
    
    # ========== US-15: LUMPSUM SPK WITHOUT SCOPE REQUIRES PROGRESS_PCT ==========
    print("\n[16] US-15: Lumpsum SPK without scope requires progress_pct")
    if spk_002_id:
        r = runner.post("/subcon/claims", "site@sipro.co.id", {
            "spk_id": spk_002_id,  # Draft lumpsum SPK without scope
            "period": "Test without pct",
            "note": "Should fail"
        })
        runner.test("Claim without progress_pct returns 400", r and r.status_code == 400)
        if r:
            runner.test("Error asks to fill scope or send pct", 
                       "lingkup" in r.text.lower() or "persen" in r.text.lower())
    
    # ========== US-16: ITEM-BASED SPK REJECTS MANUAL PROGRESS_PCT ==========
    print("\n[17] US-16: Item-based SPK rejects manual progress_pct")
    # This would be tested via PUT /subcon/spk/{id} endpoint if it exists
    # For now, we verify that claims don't accept progress_pct for item-based SPK
    r = runner.post("/subcon/claims", "site@sipro.co.id", {
        "spk_id": spk_003_id,
        "progress_pct": 60,  # Should be ignored/rejected
        "period": "Test manual pct",
        "note": "Should use items"
    })
    # Should either reject or ignore progress_pct
    if r and r.status_code == 200:
        claim = r.json().get("data", {})
        runner.test("Item-based claim ignores progress_pct", 
                   claim.get("basis") == "items")
    
    # ========== US-17: COST CONTROL - RAB BUDGET VS CONTRACTED ==========
    print("\n[18] US-17: Cost Control - RAB budget vs contracted vs verified")
    r = runner.get("/boq/control", "pm@sipro.co.id", {"project_id": "cluster-asri-a"})
    if runner.test("GET /boq/control returns 200", r and r.status_code == 200):
        data = r.json().get("data", {})
        totals = data.get("totals", {})
        
        runner.test("Budget is Rp 472.000.000", totals.get("budget") == 472000000)
        runner.test("Contracted is Rp 66.000.000", totals.get("contracted") == 66000000)
        runner.test("Verified is Rp 30.000.000", totals.get("verified") == 30000000)
        runner.test("Billed value updated", totals.get("billed") > 0)
        runner.test("Categories list exists", len(data.get("categories", [])) > 0)
        runner.test("Cost codes list exists", len(data.get("cost_codes", [])) > 0)
    
    # ========== US-18: PROJECT STEPS FOR RAB MAPPING ==========
    print("\n[19] US-18: Project steps for RAB mapping")
    r = runner.get("/boq/steps", "pm@sipro.co.id", {"project_id": "cluster-asri-a"})
    if runner.test("GET /boq/steps returns 200", r and r.status_code == 200):
        data = r.json().get("data", [])
        runner.test("Steps list returned", len(data) > 0, f"Got {len(data)} steps")
        if data:
            step = data[0]
            runner.test("Step has code", "step_code" in step)
            runner.test("Step has name", "step_name" in step)
    
    # ========== US-19: RBAC - SALES CAN'T ACCESS COST CONTROL ==========
    print("\n[20] US-19: RBAC - Sales cannot access cost control")
    r = runner.get("/boq/control", "sales@sipro.co.id", {"project_id": "cluster-asri-a"})
    runner.test("Sales GET /boq/control returns 403", r and r.status_code == 403)
    
    return runner.summary()


if __name__ == "__main__":
    sys.exit(main())

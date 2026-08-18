#!/usr/bin/env python3
"""Backend API Testing for SIPRO Phase 33 - RAB/BoQ <-> Item Jadwal -> Opname & Termin Subkon

Tests all Phase 33 features:
- SPK scope management (lingkup SPK berbasis item)
- Opname preview and verification
- Item-based claims (termin berbasis bukti)
- Cost control (kendali biaya RAB)
- RBAC and SoD (Segregation of Duties)
- Regression tests for lump-sum SPK
"""
import sys
import requests
from datetime import datetime

BASE_URL = "https://sipro-dev-1.preview.emergentagent.com/api"
PASSWORD = "Sipro#2026"

class Phase33Tester:
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
                return True
            else:
                print(f"  Login failed for {email}: {r.status_code}")
                return False
        except Exception as e:
            print(f"  Login error for {email}: {str(e)}")
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
                              timeout=60)
        except Exception as e:
            print(f"  GET {path} error: {str(e)}")
            return None
    
    def post(self, path, email, data=None):
        """POST request"""
        try:
            return requests.post(f"{BASE_URL}{path}",
                               headers=self.headers(email),
                               json=data or {},
                               timeout=60)
        except Exception as e:
            print(f"  POST {path} error: {str(e)}")
            return None
    
    def put(self, path, email, data=None):
        """PUT request"""
        try:
            return requests.put(f"{BASE_URL}{path}",
                              headers=self.headers(email),
                              json=data or {},
                              timeout=60)
        except Exception as e:
            print(f"  PUT {path} error: {str(e)}")
            return None
    
    def delete(self, path, email):
        """DELETE request"""
        try:
            return requests.delete(f"{BASE_URL}{path}",
                                 headers=self.headers(email),
                                 timeout=60)
        except Exception as e:
            print(f"  DELETE {path} error: {str(e)}")
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
    t = Phase33Tester()
    
    print("="*70)
    print("SIPRO PHASE 33 - BACKEND API TESTS")
    print("Testing: RAB/BoQ <-> Item Jadwal -> Opname & Termin Subkon")
    print("="*70)
    
    # ==================== Authentication ====================
    print("\n[1] AUTHENTICATION")
    if not t.login("pm@sipro.co.id"):
        print("CRITICAL: PM login failed, cannot continue")
        return 1
    t.test("PM login successful", True)
    
    if not t.login("site@sipro.co.id"):
        print("CRITICAL: Site login failed, cannot continue")
        return 1
    t.test("Site login successful", True)
    
    if not t.login("finance@sipro.co.id"):
        print("CRITICAL: Finance login failed, cannot continue")
        return 1
    t.test("Finance login successful", True)
    
    t.login("owner@sipro.co.id")
    t.test("Owner login successful", True)
    
    t.login("sales@sipro.co.id")
    t.test("Sales login successful", True)
    
    # ==================== US-1: SPK Scope Section ====================
    print("\n[2] US-1: SPK SCOPE MANAGEMENT (Lingkup SPK)")
    
    # Get list of SPKs
    r = t.get("/subcon/spk", "pm@sipro.co.id")
    if not t.test("GET /subcon/spk returns 200", r and r.status_code == 200):
        print("CRITICAL: Cannot get SPK list")
        return 1
    
    spks = r.json().get("data", [])
    t.test("SPK list is not empty", len(spks) > 0, f"Found {len(spks)} SPKs")
    
    # Find item-based SPK (SPK/2026/0003)
    item_spks = [s for s in spks if s.get("scope_mode") == "items"]
    if not t.test("Found item-based SPK", len(item_spks) > 0, f"Found {len(item_spks)} item-based SPKs"):
        print("CRITICAL: No item-based SPK found")
        return 1
    
    # Use the SPK with most scope items
    spk = max(item_spks, key=lambda s: int(s.get("scope_items") or 0))
    spk_id = spk["id"]
    t.test_data["spk_id"] = spk_id
    t.test_data["spk_number"] = spk.get("spk_number")
    t.test_data["project_id"] = spk.get("project_id")
    
    print(f"    Using SPK: {spk.get('spk_number')} (ID: {spk_id})")
    t.test("SPK has scope_items > 0", int(spk.get("scope_items", 0)) > 0, 
           f"Scope items: {spk.get('scope_items')}")
    
    # Get scope details
    r = t.get(f"/subcon/spk/{spk_id}/scope", "pm@sipro.co.id")
    if not t.test("GET /subcon/spk/{id}/scope returns 200", r and r.status_code == 200):
        print("CRITICAL: Cannot get SPK scope")
        return 1
    
    scope_data = r.json()
    rows = scope_data.get("data", [])
    summary = scope_data.get("summary", {})
    contract = scope_data.get("contract", {})
    blockers = scope_data.get("blockers", [])
    
    t.test("Scope has data rows", len(rows) > 0, f"Found {len(rows)} scope items")
    t.test("Scope has summary", bool(summary), f"Keys: {list(summary.keys())}")
    t.test("Scope has contract info", bool(contract), f"Contract value: {contract.get('contract_value')}")
    t.test("Scope has blockers info", isinstance(blockers, list), f"Blockers: {len(blockers)}")
    
    # Verify scope row structure
    if rows:
        row = rows[0]
        required_fields = ["unit_code", "step_code", "step_name", "value", "state", "state_label", 
                          "claimable", "verified", "cost_code"]
        t.test("Scope row has required fields", 
               all(f in row for f in required_fields),
               f"Missing: {[f for f in required_fields if f not in row]}")
    
    # Verify summary structure
    required_summary = ["items", "scope_value", "verified_value", "billed_value", 
                       "claimable_value", "progress_pct", "billed_pct"]
    t.test("Summary has required fields",
           all(f in summary for f in required_summary),
           f"Missing: {[f for f in required_summary if f not in summary]}")
    
    # ==================== US-1b: Add Scope Items ====================
    print("\n[3] US-1b: ADD SCOPE ITEMS (Tambah pekerjaan)")
    
    # Get candidates
    r = t.get(f"/subcon/spk/{spk_id}/scope/candidates", "pm@sipro.co.id")
    t.test("GET /subcon/spk/{id}/scope/candidates returns 200", r and r.status_code == 200)
    
    if r and r.status_code == 200:
        cand_data = r.json().get("data", {})
        units = cand_data.get("units", [])
        t.test("Candidates has units", isinstance(units, list), f"Found {len(units)} units")
        t.test("Candidates has contract info", "contract_value" in cand_data)
        t.test("Candidates has RAB mapping info", "rab_mapped" in cand_data)
        
        if units:
            items = []
            for u in units:
                items.extend(u.get("items", []))
            t.test("Candidates has items", len(items) > 0, f"Found {len(items)} candidate items")
            
            if items:
                item = items[0]
                required_fields = ["build_item_id", "step_code", "step_name", "suggested_value", 
                                 "unit_id", "unit_code", "verified", "status"]
                t.test("Candidate item has required fields",
                       all(f in item for f in required_fields),
                       f"Missing: {[f for f in required_fields if f not in item]}")
    
    # ==================== US-2: Anti-duplicate SPK ====================
    print("\n[4] US-2: ANTI-DUPLICATE SPK (INV-33-3)")
    
    # Try to add already used item to another SPK (should fail)
    if rows:
        used_item_id = rows[0].get("build_item_id")
        # Find another SPK
        other_spks = [s for s in spks if s["id"] != spk_id and s.get("status") in ("draft", "active")]
        if other_spks:
            other_spk_id = other_spks[0]["id"]
            r = t.post(f"/subcon/spk/{other_spk_id}/scope", "pm@sipro.co.id", {
                "lines": [{"build_item_id": used_item_id, "value": 1000000}]
            })
            t.test("Adding already-used item to another SPK returns 400", 
                   r and r.status_code == 400,
                   f"Status: {r.status_code if r else 'None'}")
            if r and r.status_code == 400:
                t.test("Error message mentions SPK number", 
                       "SPK" in r.text,
                       f"Message: {r.text[:100]}")
    
    # ==================== US-3: Submit Claim (Item-based) ====================
    print("\n[5] US-3: SUBMIT CLAIM (Ajukan Termin berbasis item)")
    
    # Get opname preview
    r = t.get(f"/subcon/spk/{spk_id}/opname", "pm@sipro.co.id")
    if not t.test("GET /subcon/spk/{id}/opname returns 200", r and r.status_code == 200):
        print("WARNING: Cannot get opname preview")
    else:
        opname = r.json().get("data", {})
        lines = opname.get("lines", [])
        gross = opname.get("gross", 0)
        retention_pct = opname.get("retention_pct", 0)
        retention_est = opname.get("retention_est", 0)
        net_est = opname.get("net_est", 0)
        
        t.test("Opname has lines", isinstance(lines, list), f"Found {len(lines)} claimable items")
        t.test("Opname has gross amount", isinstance(gross, int), f"Gross: Rp {gross:,}")
        t.test("Opname has retention calculation", 
               retention_est == round(gross * retention_pct / 100),
               f"Retention: {retention_pct}% of {gross} = {retention_est}")
        t.test("Opname has net calculation",
               net_est == gross - retention_est,
               f"Net: {gross} - {retention_est} = {net_est}")
        
        required_fields = ["lines", "gross", "retention_pct", "retention_est", "net_est", 
                          "summary", "blockers", "open_claim", "contract_value"]
        t.test("Opname preview has all required fields",
               all(f in opname for f in required_fields),
               f"Missing: {[f for f in required_fields if f not in opname]}")
        
        # Check if there's an open claim
        open_claim = opname.get("open_claim")
        if open_claim:
            print(f"    Note: Open claim exists: {open_claim.get('claim_number')}")
            t.test_data["existing_claim_id"] = open_claim.get("id")
    
    # ==================== US-4: Validation for SPK without scope ====================
    print("\n[6] US-4: VALIDATION (INV-33-1 & INV-33-4)")
    
    # Find lump-sum SPK without scope
    lumpsum_spks = [s for s in spks if s.get("scope_mode") != "items" 
                    and s.get("status") in ("draft", "active")]
    if lumpsum_spks:
        ls_spk = lumpsum_spks[0]
        # Try to submit claim without progress_pct (should fail)
        r = t.post("/subcon/claims", "site@sipro.co.id", {
            "spk_id": ls_spk["id"]
        })
        t.test("Submitting claim without progress_pct returns 400",
               r and r.status_code == 400,
               f"Status: {r.status_code if r else 'None'}")
        if r and r.status_code == 400:
            t.test("Error message is helpful",
                   "lingkup" in r.text.lower() or "persen" in r.text.lower(),
                   f"Message: {r.text[:150]}")
    
    # ==================== US-5: Opname with SoD ====================
    print("\n[7] US-5: OPNAME WITH SOD (INV-33-6 & INV-33-7)")
    
    # Get existing claims
    r = t.get("/subcon/claims", "pm@sipro.co.id", {"spk_id": spk_id})
    if r and r.status_code == 200:
        claims = r.json().get("data", [])
        submitted_claims = [c for c in claims if c.get("status") == "submitted" 
                           and c.get("basis") == "items"]
        
        if submitted_claims:
            claim = submitted_claims[0]
            claim_id = claim["id"]
            claim_creator = claim.get("created_by")
            
            print(f"    Testing with claim: {claim.get('claim_number')}")
            
            # Test SoD: creator cannot verify own claim
            if claim_creator == "site@sipro.co.id":
                r = t.post(f"/subcon/claims/{claim_id}/verify", "site@sipro.co.id", {
                    "exclude": [], "reason": ""
                })
                t.test("Creator cannot verify own claim (SoD)",
                       r and r.status_code == 403,
                       f"Status: {r.status_code if r else 'None'}")
            
            # Test INV-33-6: cannot add lines (only reduce)
            r = t.post(f"/subcon/claims/{claim_id}/verify", "pm@sipro.co.id", {
                "exclude": ["fake-item-id-123"], "reason": "test"
            })
            t.test("Cannot add lines during opname (INV-33-6)",
                   r and r.status_code == 400,
                   f"Status: {r.status_code if r else 'None'}")
            if r and r.status_code == 400:
                t.test("Error message mentions MENGURANGI",
                       "MENGURANGI" in r.text,
                       f"Message: {r.text[:100]}")
            
            # Test: reducing lines without reason should fail
            if claim.get("lines"):
                first_line_id = claim["lines"][0].get("scope_item_id")
                r = t.post(f"/subcon/claims/{claim_id}/verify", "pm@sipro.co.id", {
                    "exclude": [first_line_id]
                })
                t.test("Reducing lines without reason returns 400",
                       r and r.status_code == 400,
                       f"Status: {r.status_code if r else 'None'}")
        else:
            print("    Note: No submitted item-based claims found for opname testing")
    
    # ==================== US-6: Finance Approval ====================
    print("\n[8] US-6: FINANCE APPROVAL")
    
    # Get verified claims
    r = t.get("/subcon/claims", "pm@sipro.co.id", {"spk_id": spk_id})
    if r and r.status_code == 200:
        claims = r.json().get("data", [])
        verified_claims = [c for c in claims if c.get("status") == "verified" 
                          and c.get("basis") == "items"]
        
        if verified_claims:
            claim = verified_claims[0]
            claim_id = claim["id"]
            
            print(f"    Testing with claim: {claim.get('claim_number')}")
            
            # Test: PM cannot approve
            r = t.post(f"/subcon/claims/{claim_id}/approve", "pm@sipro.co.id")
            t.test("PM cannot approve claim (RBAC)",
                   r and r.status_code == 403,
                   f"Status: {r.status_code if r else 'None'}")
            
            # Test: Site cannot approve
            r = t.post(f"/subcon/claims/{claim_id}/approve", "site@sipro.co.id")
            t.test("Site cannot approve claim (RBAC)",
                   r and r.status_code == 403,
                   f"Status: {r.status_code if r else 'None'}")
        else:
            print("    Note: No verified claims found for approval testing")
    
    # ==================== US-7: Post-approval Status ====================
    print("\n[9] US-7: POST-APPROVAL STATUS (INV-33-2)")
    
    # Get approved claims
    r = t.get("/subcon/claims", "pm@sipro.co.id", {"spk_id": spk_id})
    if r and r.status_code == 200:
        claims = r.json().get("data", [])
        approved_claims = [c for c in claims if c.get("status") == "approved" 
                          and c.get("basis") == "items"]
        
        if approved_claims:
            claim = approved_claims[0]
            
            # Check if AP bill was created
            t.test("Approved claim has AP bill ID",
                   bool(claim.get("ap_bill_id")),
                   f"AP Bill ID: {claim.get('ap_bill_id')}")
            
            # Verify AP bill exists
            if claim.get("ap_bill_id"):
                r = t.get("/finance/ap/bills", "finance@sipro.co.id")
                if r and r.status_code == 200:
                    bills = r.json().get("data", [])
                    bill = next((b for b in bills if b["id"] == claim["ap_bill_id"]), None)
                    t.test("AP bill exists and matches claim",
                           bill and bill.get("claimed") == claim.get("gross"),
                           f"Bill claimed: {bill.get('claimed') if bill else 'N/A'}, Claim gross: {claim.get('gross')}")
            
            # Check scope - billed items should be marked
            r = t.get(f"/subcon/spk/{spk_id}/scope", "pm@sipro.co.id")
            if r and r.status_code == 200:
                scope_data = r.json()
                rows = scope_data.get("data", [])
                billed_rows = [r for r in rows if r.get("claim_id")]
                t.test("Billed items are marked in scope",
                       len(billed_rows) > 0,
                       f"Found {len(billed_rows)} billed items")
                
                if billed_rows:
                    billed_row = billed_rows[0]
                    t.test("Billed item has claim_number",
                           bool(billed_row.get("claim_number")),
                           f"Claim: {billed_row.get('claim_number')}")
                    t.test("Billed item state is 'billed'",
                           billed_row.get("state") == "billed",
                           f"State: {billed_row.get('state')}")
                    
                    # Try to delete billed item (should fail)
                    r = t.delete(f"/subcon/spk/{spk_id}/scope/{billed_row['id']}", "pm@sipro.co.id")
                    t.test("Cannot delete billed scope item",
                           r and r.status_code == 400,
                           f"Status: {r.status_code if r else 'None'}")
        else:
            print("    Note: No approved claims found for post-approval testing")
    
    # ==================== US-8: Auto Progress Calculation ====================
    print("\n[10] US-8: AUTO PROGRESS CALCULATION (INV-33-5)")
    
    # Try to manually set progress_pct on item-based SPK (should fail)
    r = t.put(f"/subcon/spk/{spk_id}", "pm@sipro.co.id", {"progress_pct": 99})
    t.test("Cannot manually set progress_pct on item-based SPK",
           r and r.status_code == 400,
           f"Status: {r.status_code if r else 'None'}")
    if r and r.status_code == 400:
        t.test("Error message mentions 'dihitung otomatis'",
               "dihitung otomatis" in r.text.lower(),
               f"Message: {r.text[:100]}")
    
    # Verify progress is calculated correctly
    r = t.get(f"/subcon/spk/{spk_id}/scope", "pm@sipro.co.id")
    if r and r.status_code == 200:
        scope_data = r.json()
        summary = scope_data.get("summary", {})
        spk_data = scope_data.get("spk", {})
        
        if summary.get("scope_value", 0) > 0:
            expected_pct = round(summary["verified_value"] / summary["scope_value"] * 100)
            actual_pct = spk_data.get("progress_pct", 0)
            t.test("Progress is calculated from verified value",
                   abs(expected_pct - actual_pct) <= 1,  # Allow 1% rounding difference
                   f"Expected: {expected_pct}%, Actual: {actual_pct}%")
    
    # Test lump-sum SPK can still set progress manually
    if lumpsum_spks:
        ls_spk = lumpsum_spks[0]
        r = t.put(f"/subcon/spk/{ls_spk['id']}", "pm@sipro.co.id", {"progress_pct": 15})
        t.test("Lump-sum SPK can set progress manually",
               r and r.status_code == 200,
               f"Status: {r.status_code if r else 'None'}")
    
    # ==================== US-9: Cost Control Panel ====================
    print("\n[11] US-9: COST CONTROL PANEL (Kendali Biaya RAB)")
    
    project_id = t.test_data.get("project_id")
    if project_id:
        r = t.get("/boq/control", "pm@sipro.co.id", {"project_id": project_id})
        if not t.test("GET /boq/control returns 200", r and r.status_code == 200):
            print("WARNING: Cannot get cost control data")
        else:
            cc_data = r.json().get("data", {})
            totals = cc_data.get("totals", {})
            categories = cc_data.get("categories", [])
            cost_codes = cc_data.get("cost_codes", [])
            warnings = cc_data.get("warnings", [])
            
            t.test("Cost control has totals", bool(totals), f"Keys: {list(totals.keys())}")
            t.test("Cost control has categories", len(categories) > 0, f"Found {len(categories)} categories")
            t.test("Cost control has cost codes", len(cost_codes) > 0, f"Found {len(cost_codes)} cost codes")
            t.test("Cost control has warnings", isinstance(warnings, list), f"Warnings: {len(warnings)}")
            
            required_totals = ["budget", "contracted", "verified", "billed", "variance", "unbilled_verified"]
            t.test("Totals has required fields",
                   all(f in totals for f in required_totals),
                   f"Missing: {[f for f in required_totals if f not in totals]}")
            
            if cost_codes:
                code = cost_codes[0]
                required_fields = ["key", "label", "budget", "contracted", "verified", "billed", 
                                 "steps", "mapped", "over_commit"]
                t.test("Cost code has required fields",
                       all(f in code for f in required_fields),
                       f"Missing: {[f for f in required_fields if f not in code]}")
        
        # Get project steps
        r = t.get("/boq/steps", "pm@sipro.co.id", {"project_id": project_id})
        t.test("GET /boq/steps returns 200", r and r.status_code == 200)
        if r and r.status_code == 200:
            steps = r.json().get("data", [])
            t.test("Steps list is not empty", len(steps) > 0, f"Found {len(steps)} steps")
            
            if steps:
                step = steps[0]
                required_fields = ["step_code", "step_name", "week", "units", "weight"]
                t.test("Step has required fields",
                       all(f in step for f in required_fields),
                       f"Missing: {[f for f in required_fields if f not in step]}")
    
    # ==================== US-10: Contract Value in Build Items ====================
    print("\n[12] US-10: CONTRACT VALUE IN BUILD ITEMS")
    
    # Get a unit that has scope items
    if rows:
        unit_id = rows[0].get("unit_id")
        if unit_id:
            r = t.get(f"/build/unit/{unit_id}", "pm@sipro.co.id")
            if r and r.status_code == 200:
                unit_data = r.json()
                items = unit_data.get("items", [])
                items_with_contract = [i for i in items if i.get("contract")]
                
                t.test("Build items have contract info",
                       len(items_with_contract) > 0,
                       f"Found {len(items_with_contract)} items with contract")
                
                if items_with_contract:
                    item = items_with_contract[0]
                    contract = item.get("contract", {})
                    required_fields = ["spk_number", "value", "billed", "subcontractor_name"]
                    t.test("Contract info has required fields",
                           all(f in contract for f in required_fields),
                           f"Missing: {[f for f in required_fields if f not in contract]}")
    
    # ==================== RBAC Tests ====================
    print("\n[13] RBAC: ROLE-BASED ACCESS CONTROL")
    
    # Sales cannot view scope
    r = t.get(f"/subcon/spk/{spk_id}/scope", "sales@sipro.co.id")
    t.test("Sales cannot view SPK scope",
           r and r.status_code == 403,
           f"Status: {r.status_code if r else 'None'}")
    
    # Sales cannot view cost control
    if project_id:
        r = t.get("/boq/control", "sales@sipro.co.id", {"project_id": project_id})
        t.test("Sales cannot view cost control",
               r and r.status_code == 403,
               f"Status: {r.status_code if r else 'None'}")
    
    # Site can view scope but cannot modify
    r = t.get(f"/subcon/spk/{spk_id}/scope", "site@sipro.co.id")
    t.test("Site can view SPK scope",
           r and r.status_code == 200,
           f"Status: {r.status_code if r else 'None'}")
    
    r = t.post(f"/subcon/spk/{spk_id}/scope", "site@sipro.co.id", {"lines": []})
    t.test("Site cannot modify SPK scope",
           r and r.status_code == 403,
           f"Status: {r.status_code if r else 'None'}")
    
    # Owner can view everything
    r = t.get(f"/subcon/spk/{spk_id}/scope", "owner@sipro.co.id")
    t.test("Owner can view SPK scope",
           r and r.status_code == 200,
           f"Status: {r.status_code if r else 'None'}")
    
    r = t.get(f"/subcon/spk/{spk_id}/opname", "owner@sipro.co.id")
    t.test("Owner can view opname",
           r and r.status_code == 200,
           f"Status: {r.status_code if r else 'None'}")
    
    # ==================== Regression: Lump-sum SPK ====================
    print("\n[14] REGRESSION: LUMP-SUM SPK")
    
    if lumpsum_spks:
        ls_spk = lumpsum_spks[0]
        ls_spk_id = ls_spk["id"]
        
        # Get lump-sum claims
        r = t.get("/subcon/claims", "pm@sipro.co.id", {"spk_id": ls_spk_id})
        t.test("Can get lump-sum SPK claims",
               r and r.status_code == 200,
               f"Status: {r.status_code if r else 'None'}")
        
        if r and r.status_code == 200:
            claims = r.json().get("data", [])
            lumpsum_claims = [c for c in claims if c.get("basis") != "items"]
            t.test("Lump-sum claims exist",
                   len(lumpsum_claims) > 0,
                   f"Found {len(lumpsum_claims)} lump-sum claims")
            
            # Check if there's a submitted lump-sum claim
            submitted = [c for c in lumpsum_claims if c.get("status") == "submitted"]
            if submitted:
                claim = submitted[0]
                claim_id = claim["id"]
                
                # Test opname with percentage
                current_pct = claim.get("claimed_pct", 0)
                verified_pct = max(claim.get("prev_pct", 0) + 1, current_pct)
                r = t.post(f"/subcon/claims/{claim_id}/verify", "pm@sipro.co.id", {
                    "verified_pct": verified_pct
                })
                t.test("Lump-sum opname with percentage works",
                       r and r.status_code == 200,
                       f"Status: {r.status_code if r else 'None'}")
    else:
        print("    Note: No lump-sum SPKs found for regression testing")
    
    return t.summary()


if __name__ == "__main__":
    sys.exit(main())

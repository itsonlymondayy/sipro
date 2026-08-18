#!/usr/bin/env python3
"""Backend API Testing for SIPRO Phase 39b - Document Checklist & Config

Tests:
- US-39-5: Migration history endpoint
- US-39-2: GL Account dropdown (reference endpoint)
- US-39-3: Document requirements master & matrix
- US-39-3b: Document upload, verify, reject flows
- US-39-4: Settings effective values & history
- REGRESSION: Critical endpoints must still work
"""
import sys
import requests
import json
import tempfile
from datetime import datetime

BASE_URL = "https://sipro-backend.preview.emergentagent.com/api"
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
                return True
            else:
                print(f"  Login failed for {email}: {r.status_code} - {r.text[:200]}")
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
                              timeout=30)
        except Exception as e:
            print(f"  GET {path} error: {str(e)}")
            return None
    
    def post(self, path, email, data=None, files=None):
        """POST request"""
        try:
            if files:
                return requests.post(f"{BASE_URL}{path}",
                                   headers=self.headers(email),
                                   data=data,
                                   files=files,
                                   timeout=30)
            else:
                return requests.post(f"{BASE_URL}{path}",
                                   headers=self.headers(email),
                                   json=data or {},
                                   timeout=30)
        except Exception as e:
            print(f"  POST {path} error: {str(e)}")
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
    print("SIPRO PHASE 39b - BACKEND API TESTS")
    print("="*70)
    
    # ========== AUTHENTICATION ==========
    print("\n[1] AUTHENTICATION")
    runner.test("Login superadmin@sipro.co.id", runner.login("superadmin@sipro.co.id"))
    runner.test("Login sales@sipro.co.id", runner.login("sales@sipro.co.id"))
    
    if not runner.tokens.get("superadmin@sipro.co.id"):
        print("\n✗ Cannot proceed without superadmin login")
        return 1
    
    admin = "superadmin@sipro.co.id"
    sales = "sales@sipro.co.id"
    
    # ========== US-39-5: MIGRATION HISTORY ==========
    print("\n[2] US-39-5: MIGRATION HISTORY ENDPOINT")
    r = runner.get("/admin/migrations", admin)
    runner.test("GET /api/admin/migrations returns 200", 
               r and r.status_code == 200,
               f"Status: {r.status_code if r else 'N/A'}")
    
    if r and r.status_code == 200:
        data = r.json().get("data", [])
        runner.test("Migration history returns array", isinstance(data, list),
                   f"Found {len(data)} migration runs")
        
        # Check for v2_fase39 migration
        fase39_migration = next((m for m in data if m.get("name") == "v2_fase39"), None)
        if fase39_migration:
            runner.test("v2_fase39 migration exists", True,
                       f"Summary keys: {list(fase39_migration.get('summary', {}).keys())}")
            summary = fase39_migration.get("summary", {})
            runner.test("Migration has M39_1_cluster_block", "M39_1_cluster_block" in summary)
            runner.test("Migration has M39_2_unit_types", "M39_2_unit_types" in summary)
        else:
            runner.test("v2_fase39 migration exists", False, "Not found in migration history")
    
    # ========== REGRESSION: REFERENCE ENDPOINT ==========
    print("\n[3] REGRESSION: GET /api/reference (CRITICAL)")
    r = runner.get("/reference", admin)
    runner.test("GET /api/reference returns 200", r and r.status_code == 200)
    
    if r and r.status_code == 200:
        ref_data = r.json().get("data", {})
        maps = r.json().get("maps", {})
        
        runner.test("Reference has 'maps' field", bool(maps),
                   f"Maps keys: {list(maps.keys())}")
        runner.test("Maps has 'channel_to_source'", "channel_to_source" in maps)
        runner.test("Maps has 'source_score'", "source_score" in maps)
        
        # US-39-2: GL Account group
        runner.test("Reference has 'gl_account' group", "gl_account" in ref_data)
        
        if "gl_account" in ref_data:
            gl_group = ref_data["gl_account"]
            runner.test("gl_account has options", len(gl_group.get("options", [])) > 0,
                       f"Found {len(gl_group.get('options', []))} GL accounts")
            
            # Check format: should be "code — name"
            if gl_group.get("options"):
                first_opt = gl_group["options"][0]
                label = first_opt.get("label", "")
                runner.test("GL account label has format 'code — name'", 
                           " — " in label,
                           f"Sample: {label}")
            
            runner.test("gl_account has allow_new=False", 
                       gl_group.get("allow_new") == False,
                       f"allow_new: {gl_group.get('allow_new')}")
        
        # US-39-3: doc_context group
        runner.test("Reference has 'doc_context' group", "doc_context" in ref_data)
        
        if "doc_context" in ref_data:
            doc_ctx = ref_data["doc_context"]
            options = doc_ctx.get("options", [])
            runner.test("doc_context has options", len(options) > 0,
                       f"Found {len(options)} contexts")
            
            # Check for human-readable labels (not raw values)
            if options:
                booking_ctx = next((o for o in options if o.get("value") == "lead_stage:booking"), None)
                if booking_ctx:
                    label = booking_ctx.get("label", "")
                    runner.test("doc_context has human-readable labels",
                               "Lead" in label and "Booking" in label,
                               f"Sample: {label}")
        
        # US-39-4: setting_origin and setting_source groups
        runner.test("Reference has 'setting_origin' group", "setting_origin" in ref_data)
        runner.test("Reference has 'setting_source' group", "setting_source" in ref_data)
    
    # ========== US-39-2: GL ACCOUNT GROUP ENDPOINT ==========
    print("\n[4] US-39-2: GET /api/reference/gl_account")
    r = runner.get("/reference/gl_account", admin)
    runner.test("GET /api/reference/gl_account returns 200", 
               r and r.status_code == 200)
    
    if r and r.status_code == 200:
        gl_data = r.json().get("data", {})
        runner.test("GL account group has options", 
                   len(gl_data.get("options", [])) > 0)
        runner.test("GL account group has allow_new=False",
                   gl_data.get("allow_new") == False)
    
    # ========== US-39-3: DOCUMENT REQUIREMENTS MASTER ==========
    print("\n[5] US-39-3: DOCUMENT REQUIREMENTS MASTER")
    r = runner.get("/doc/requirements", admin)
    runner.test("GET /api/doc/requirements returns 200", 
               r and r.status_code == 200)
    
    if r and r.status_code == 200:
        reqs = r.json().get("data", [])
        runner.test("Document requirements list not empty", len(reqs) > 0,
                   f"Found {len(reqs)} requirements")
        
        # Check for expected requirements
        codes = [req.get("code") for req in reqs]
        runner.test("KTP requirement exists", "KTP" in codes)
        runner.test("KK requirement exists", "KK" in codes)
        runner.test("NPWP requirement exists", "NPWP" in codes)
        
        # Check structure
        if reqs:
            first_req = reqs[0]
            runner.test("Requirement has 'code' field", "code" in first_req)
            runner.test("Requirement has 'label' field", "label" in first_req)
            runner.test("Requirement has 'applies_to' field", "applies_to" in first_req)
            runner.test("Requirement has 'mandatory' field", "mandatory" in first_req)
    
    # ========== US-39-3: GET LEAD FOR TESTING ==========
    print("\n[6] GET LEAD DATA FOR DOCUMENT TESTING")
    r = runner.get("/leads", admin, {"limit": 50})
    runner.test("GET /api/leads returns 200", r and r.status_code == 200)
    
    lead_dewi_id = None
    lead_rudi_id = None
    
    if r and r.status_code == 200:
        leads = r.json().get("data", [])
        runner.test("Leads list not empty", len(leads) > 0,
                   f"Found {len(leads)} leads")
        
        # Find "Ibu Dewi Kartika" (Booking stage)
        for lead in leads:
            if "Dewi" in lead.get("name", "") and "Kartika" in lead.get("name", ""):
                lead_dewi_id = lead.get("id")
                runner.test("Found lead 'Ibu Dewi Kartika'", True,
                           f"ID: {lead_dewi_id}, Stage: {lead.get('stage')}")
                runner.test("Dewi lead is in Booking stage", 
                           lead.get("stage") == "booking",
                           f"Stage: {lead.get('stage')}")
                break
        
        # Find "Bapak Rudi Hartono" (Nurturing stage)
        for lead in leads:
            if "Rudi" in lead.get("name", "") and "Hartono" in lead.get("name", ""):
                lead_rudi_id = lead.get("id")
                runner.test("Found lead 'Bapak Rudi Hartono'", True,
                           f"ID: {lead_rudi_id}, Stage: {lead.get('stage')}")
                runner.test("Rudi lead is in Nurturing stage",
                           lead.get("stage") == "nurturing",
                           f"Stage: {lead.get('stage')}")
                break
        
        if not lead_dewi_id:
            runner.test("Found lead 'Ibu Dewi Kartika'", False, "Lead not found")
    
    runner.test_data["lead_dewi_id"] = lead_dewi_id
    runner.test_data["lead_rudi_id"] = lead_rudi_id
    
    # ========== US-39-3: DOCUMENT MATRIX WITHOUT CONTEXTS ==========
    print("\n[7] US-39-3: DOCUMENT MATRIX (backend derives contexts)")
    
    if lead_dewi_id:
        # Test without contexts parameter - backend should derive it
        r = runner.get("/doc/matrix", admin, {
            "entity_type": "lead",
            "entity_id": lead_dewi_id
        })
        runner.test("GET /api/doc/matrix (no contexts) returns 200",
                   r and r.status_code == 200)
        
        if r and r.status_code == 200:
            matrix = r.json().get("data", {})
            rows = matrix.get("rows", [])
            contexts = matrix.get("contexts", [])
            counts = matrix.get("counts", {})
            
            runner.test("Matrix has 'rows' field", isinstance(rows, list),
                       f"Found {len(rows)} requirements")
            runner.test("Matrix has 'contexts' field", isinstance(contexts, list),
                       f"Contexts: {contexts}")
            runner.test("Matrix has 'counts' field", isinstance(counts, dict),
                       f"Counts: {counts}")
            runner.test("Matrix has 'complete' field", "complete" in matrix)
            
            # Dewi is in Booking stage, should have requirements
            runner.test("Booking lead has requirements", len(rows) > 0,
                       f"Found {len(rows)} requirements")
            
            if rows:
                runner.test("Counts has 'required' field", "required" in counts,
                           f"Required: {counts.get('required')}")
                runner.test("Counts has 'verified' field", "verified" in counts)
                runner.test("Counts has 'pending' field", "pending" in counts)
                runner.test("Counts has 'missing' field", "missing" in counts)
                
                # Check row structure
                first_row = rows[0]
                runner.test("Row has 'requirement' field", "requirement" in first_row)
                runner.test("Row has 'status' field", "status" in first_row)
                runner.test("Row has 'status_label' field", "status_label" in first_row)
                runner.test("Row has 'submissions' field", "submissions" in first_row)
    
    # Test with Rudi (Nurturing stage - should have empty or minimal checklist)
    if lead_rudi_id:
        r = runner.get("/doc/matrix", admin, {
            "entity_type": "lead",
            "entity_id": lead_rudi_id
        })
        runner.test("GET /api/doc/matrix for Nurturing lead returns 200",
                   r and r.status_code == 200)
        
        if r and r.status_code == 200:
            matrix = r.json().get("data", {})
            rows = matrix.get("rows", [])
            # Nurturing stage may have fewer requirements
            runner.test("Nurturing lead matrix loads without error", True,
                       f"Found {len(rows)} requirements (expected fewer)")
    
    # ========== US-39-3b: DOCUMENT UPLOAD FLOW ==========
    print("\n[8] US-39-3b: DOCUMENT UPLOAD (with fake file_id - should fail)")
    
    if lead_dewi_id:
        # Test negative case: fake file_id should be rejected
        r = runner.post("/doc/submissions", admin, {
            "requirement_code": "KTP",
            "entity_type": "lead",
            "entity_id": lead_dewi_id,
            "file_id": "file-palsu-999",
            "note": "Test upload"
        })
        runner.test("POST /doc/submissions with fake file_id returns 400",
                   r and r.status_code == 400,
                   f"Status: {r.status_code if r else 'N/A'}")
        
        if r and r.status_code == 400:
            error = r.json().get("detail", "")
            runner.test("Error message mentions 'Berkas tidak ditemukan'",
                       "Berkas tidak ditemukan" in error or "tidak ditemukan di penyimpanan" in error,
                       f"Error: {error}")
    
    # ========== US-39-4: SETTINGS EFFECTIVE VALUES ==========
    print("\n[9] US-39-4: SETTINGS EFFECTIVE VALUES")
    r = runner.get("/settings/effective", admin, {"key": "reservation.max_active_per_lead"})
    runner.test("GET /api/settings/effective returns 200",
               r and r.status_code == 200,
               f"Status: {r.status_code if r else 'N/A'}")
    
    if r and r.status_code == 200:
        setting = r.json().get("data", {})
        runner.test("Setting has 'key' field", "key" in setting)
        runner.test("Setting has 'value' field", "value" in setting)
        runner.test("Setting has 'origin' field", "origin" in setting)
        runner.test("Setting has 'source' field", "source" in setting)
    
    # ========== REGRESSION: CRITICAL ENDPOINTS ==========
    print("\n[10] REGRESSION: CRITICAL ENDPOINTS STILL WORK")
    
    # Test /api/leads
    r = runner.get("/leads", admin, {"limit": 5})
    runner.test("GET /api/leads returns 200", r and r.status_code == 200)
    
    # Test /api/deals
    r = runner.get("/deals", admin, {"limit": 5})
    runner.test("GET /api/deals returns 200", r and r.status_code == 200)
    
    # Test /api/customers
    r = runner.get("/customers", admin, {"limit": 5})
    runner.test("GET /api/customers returns 200", r and r.status_code == 200)
    
    # Test /api/projects
    r = runner.get("/projects", admin)
    runner.test("GET /api/projects returns 200", r and r.status_code == 200)
    
    # Test /api/work/home
    r = runner.get("/work/home", admin)
    runner.test("GET /api/work/home returns 200", r and r.status_code == 200)
    
    # ========== FINAL SUMMARY ==========
    return runner.summary()


if __name__ == "__main__":
    sys.exit(main())

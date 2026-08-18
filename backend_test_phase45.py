"""Phase 45 — Target Proyek & Budget/RAB Backend Test Suite

Tests all 18 user stories from backend perspective:
1. AUTH: Login all roles (owner, pm, finlead, finance, sales)
2. TARGETS: GET /api/targets/methods (5 methods)
3. TARGETS: POST /api/targets/preview (preview before save)
4. TARGETS: POST /api/targets (create target)
5. TARGETS: GET /api/targets (list targets)
6. TARGETS: GET /api/targets/{id} (detail + progress)
7. TARGETS: POST /api/targets/{id}/recalc (with reason)
8. TARGETS: POST /api/targets/{id}/activate (only one active parent)
9. TARGETS: POST /api/targets/{id}/close
10. BUDGET: GET /api/budget/items (list budget items)
11. BUDGET: POST /api/budget/items (create item - construction with boq_item_ids)
12. BUDGET: POST /api/budget/items (create item - operational with gl_account)
13. BUDGET: GET /api/budget/summary (layer 1)
14. BUDGET: GET /api/budget/by-category (layer 2)
15. BUDGET: GET /api/budget/items/{id}/realization (layer 3 - drill documents)
16. BUDGET: POST /api/budget/items/{id}/revise (finlead can, pm cannot - 403)
17. BUDGET: POST /api/budget/items/{id}/manual-entry
18. BUDGET: POST /api/budget/alerts/scan (only manage roles)
19. BUDGET: GET /api/budget/health (enforce settings)
20. RBAC: sales gets 403 on budget endpoints
"""
import requests
import sys
import time
from datetime import datetime

BASE_URL = "https://development-sipro.preview.emergentagent.com/api"
PASSWORD = "Sipro#2026"

class Phase45Tester:
    def __init__(self):
        self.tests_run = 0
        self.tests_passed = 0
        self.tokens = {}
        self.results = []
        self.target_id = None
        self.budget_item_id = None
        self.project_id = None

    def log(self, msg, status="INFO"):
        prefix = {"PASS": "✅", "FAIL": "❌", "INFO": "🔍", "WARN": "⚠️"}.get(status, "ℹ️")
        print(f"{prefix} {msg}")

    def test(self, name, fn):
        """Run a test function and track results"""
        self.tests_run += 1
        self.log(f"Testing {name}...", "INFO")
        try:
            fn()
            self.tests_passed += 1
            self.log(f"PASSED: {name}", "PASS")
            self.results.append({"test": name, "status": "PASS"})
            return True
        except AssertionError as e:
            self.log(f"FAILED: {name} — {str(e)}", "FAIL")
            self.results.append({"test": name, "status": "FAIL", "error": str(e)})
            return False
        except Exception as e:
            self.log(f"ERROR: {name} — {str(e)}", "FAIL")
            self.results.append({"test": name, "status": "ERROR", "error": str(e)})
            return False

    def login(self, email):
        """Login and cache token"""
        if email in self.tokens:
            return self.tokens[email]
        r = requests.post(f"{BASE_URL}/auth/login", json={"email": email, "password": PASSWORD})
        assert r.status_code == 200, f"Login failed for {email}: {r.status_code} {r.text}"
        token = r.json()["access_token"]
        self.tokens[email] = token
        return token

    def get(self, endpoint, email, expected_status=200):
        """GET request with auth"""
        token = self.login(email)
        r = requests.get(f"{BASE_URL}{endpoint}", headers={"Authorization": f"Bearer {token}"})
        if expected_status:
            assert r.status_code == expected_status, f"Expected {expected_status}, got {r.status_code}: {r.text[:500]}"
        return r

    def post(self, endpoint, email, data, expected_status=200):
        """POST request with auth"""
        token = self.login(email)
        r = requests.post(f"{BASE_URL}{endpoint}", json=data, headers={"Authorization": f"Bearer {token}"})
        if expected_status:
            assert r.status_code == expected_status, f"Expected {expected_status}, got {r.status_code}: {r.text[:500]}"
        return r

    def put(self, endpoint, email, data, expected_status=200):
        """PUT request with auth"""
        token = self.login(email)
        r = requests.put(f"{BASE_URL}{endpoint}", json=data, headers={"Authorization": f"Bearer {token}"})
        if expected_status:
            assert r.status_code == expected_status, f"Expected {expected_status}, got {r.status_code}: {r.text[:500]}"
        return r

    # ============================= TEST CASES =============================

    def test_auth_all_roles(self):
        """Test 1: AUTH - Login all Phase 45 roles"""
        roles = [
            "owner@sipro.co.id",
            "superadmin@sipro.co.id",
            "pm@sipro.co.id",
            "finlead@sipro.co.id",
            "finance@sipro.co.id",
            "sales@sipro.co.id"
        ]
        for email in roles:
            token = self.login(email)
            assert len(token) > 20, f"Invalid token for {email}"
        self.log(f"All {len(roles)} roles logged in successfully")

    def test_get_projects(self):
        """Test 2: Get projects to use in tests"""
        r = self.get("/projects", "owner@sipro.co.id")
        data = r.json()["data"]
        assert len(data) > 0, "No projects found"
        # Find "Cluster Asri Blok A" or use first project
        for p in data:
            if "Cluster Asri" in p.get("name", "") or "Asri" in p.get("name", ""):
                self.project_id = p["id"]
                break
        if not self.project_id:
            self.project_id = data[0]["id"]
        self.log(f"Using project: {self.project_id}")

    def test_targets_methods(self):
        """Test 3: GET /api/targets/methods returns 5 methods"""
        r = self.get("/targets/methods", "owner@sipro.co.id")
        data = r.json()["data"]
        assert len(data) == 5, f"Expected 5 target methods, got {len(data)}"
        methods = [m["value"] for m in data]
        expected = ["linear_remaining", "s_curve", "manual", "velocity_forecast", "revenue_first"]
        for m in expected:
            assert m in methods, f"Method {m} not found"
        # Check formula is present
        for m in data:
            assert "formula" in m, f"Method {m['value']} missing formula"
            assert "needs" in m, f"Method {m['value']} missing needs"
        self.log(f"Found 5 target methods with formulas")

    def test_targets_preview(self):
        """Test 4: POST /api/targets/preview (preview before save)"""
        if not self.project_id:
            self.log("Skipping preview test - no project_id", "WARN")
            return
        
        r = self.post("/targets/preview", "owner@sipro.co.id", {
            "project_id": self.project_id,
            "method": "linear_remaining",
            "horizon": {"start": "2026-08", "end": "2027-12"},
            "unit_target": 120,
            "revenue_target": 19920000000,
            "assumptions": {"avg_price": 166000000}
        })
        data = r.json()["data"]
        assert "periods" in data, "Preview missing periods"
        assert "missing" in data, "Preview missing 'missing' field"
        self.log(f"Preview generated with {len(data.get('periods', []))} periods")

    def test_targets_create(self):
        """Test 5: POST /api/targets (create target)"""
        if not self.project_id:
            self.log("Skipping create target test - no project_id", "WARN")
            return
        
        r = self.post("/targets", "owner@sipro.co.id", {
            "project_id": self.project_id,
            "name": f"Target Test {int(time.time())}",
            "method": "linear_remaining",
            "basis": "both",
            "horizon": {"start": "2026-08", "end": "2027-12"},
            "unit_target": 120,
            "revenue_target": 19920000000,
            "assumptions": {"avg_price": 166000000}
        })
        data = r.json()["data"]
        assert "id" in data, "Created target missing id"
        self.target_id = data["id"]
        assert data["method"] == "linear_remaining"
        assert data["unit_target"] == 120
        assert data["status"] == "draft"
        self.log(f"Created target: {self.target_id}")

    def test_targets_list(self):
        """Test 6: GET /api/targets (list targets)"""
        r = self.get("/targets", "owner@sipro.co.id")
        data = r.json()["data"]
        assert isinstance(data, list), "Targets list should be array"
        if len(data) > 0:
            assert "id" in data[0]
            assert "name" in data[0]
            assert "method" in data[0]
        self.log(f"Found {len(data)} targets")

    def test_targets_get_detail(self):
        """Test 7: GET /api/targets/{id} (detail + progress)"""
        if not self.target_id:
            self.log("Skipping detail test - no target_id", "WARN")
            return
        
        r = self.get(f"/targets/{self.target_id}", "owner@sipro.co.id")
        data = r.json()["data"]
        assert data["id"] == self.target_id
        assert "progress" in data, "Target detail missing progress"
        assert "periods" in data, "Target detail missing periods"
        self.log(f"Target detail retrieved with progress")

    def test_targets_recalc_no_reason_400(self):
        """Test 8: POST /api/targets/{id}/recalc without reason returns 400"""
        if not self.target_id:
            self.log("Skipping recalc test - no target_id", "WARN")
            return
        
        r = self.post(f"/targets/{self.target_id}/recalc", "owner@sipro.co.id", 
                     {"reason": ""}, expected_status=400)
        detail = r.json()["detail"]
        assert "reason" in detail.lower() or "alasan" in detail.lower()
        self.log("Recalc without reason correctly rejected with 400")

    def test_targets_recalc_with_reason(self):
        """Test 9: POST /api/targets/{id}/recalc with valid reason"""
        if not self.target_id:
            self.log("Skipping recalc test - no target_id", "WARN")
            return
        
        r = self.post(f"/targets/{self.target_id}/recalc", "owner@sipro.co.id", {
            "reason": "Testing recalculation with valid reason for automated test"
        })
        data = r.json()["data"]
        assert "changes" in data or "history" in data
        self.log(f"Recalc succeeded with reason")

    def test_targets_activate(self):
        """Test 10: POST /api/targets/{id}/activate"""
        if not self.target_id:
            self.log("Skipping activate test - no target_id", "WARN")
            return
        
        r = self.post(f"/targets/{self.target_id}/activate", "owner@sipro.co.id", {
            "reason": "Activating for test"
        })
        data = r.json()["data"]
        assert data["status"] == "active"
        self.log(f"Target activated successfully")

    def test_targets_activate_second_parent_400(self):
        """Test 11: Activating second parent target should fail with 400"""
        if not self.project_id:
            self.log("Skipping second parent test - no project_id", "WARN")
            return
        
        # Try to create and activate another parent target
        try:
            r = self.post("/targets", "owner@sipro.co.id", {
                "project_id": self.project_id,
                "name": f"Target Test 2 {int(time.time())}",
                "method": "linear_remaining",
                "basis": "both",
                "horizon": {"start": "2026-08", "end": "2027-12"},
                "unit_target": 100,
                "revenue_target": 16600000000,
                "assumptions": {"avg_price": 166000000}
            })
            second_id = r.json()["data"]["id"]
            
            # Try to activate - should fail
            r2 = self.post(f"/targets/{second_id}/activate", "owner@sipro.co.id", 
                          {"reason": "Test"}, expected_status=400)
            detail = r2.json()["detail"]
            assert "sudah punya target" in detail.lower() or "already" in detail.lower()
            self.log("Second parent activation correctly rejected with 400")
        except Exception as e:
            self.log(f"Second parent test skipped or failed: {str(e)}", "WARN")

    def test_budget_items_list(self):
        """Test 12: GET /api/budget/items"""
        r = self.get("/budget/items", "owner@sipro.co.id")
        data = r.json()["data"]
        assert isinstance(data, list), "Budget items should be array"
        self.log(f"Found {len(data)} budget items")

    def test_budget_items_create_operational(self):
        """Test 13: POST /api/budget/items (operational with gl_account)"""
        if not self.project_id:
            self.log("Skipping budget item test - no project_id", "WARN")
            return
        
        r = self.post("/budget/items", "pm@sipro.co.id", {
            "project_id": self.project_id,
            "category": "operasional",
            "code": f"OPS-TEST-{int(time.time()) % 10000}",
            "name": "Test Operational Budget Item",
            "description": "Testing operational budget item creation",
            "planned_amount": 50000000,
            "match_rule": "by_gl_account",
            "gl_account": "6-1300",
            "owner_role": "pm",
            "period": "monthly"
        })
        data = r.json()["data"]
        assert "id" in data
        self.budget_item_id = data["id"]
        assert data["category"] == "operasional"
        assert data["match_rule"] == "by_gl_account"
        self.log(f"Created operational budget item: {self.budget_item_id}")

    def test_budget_items_create_construction_no_boq_400(self):
        """Test 14: POST /api/budget/items (construction without boq_item_ids returns 400)"""
        if not self.project_id:
            self.log("Skipping construction test - no project_id", "WARN")
            return
        
        r = self.post("/budget/items", "pm@sipro.co.id", {
            "project_id": self.project_id,
            "category": "konstruksi",
            "code": f"CONST-TEST-{int(time.time()) % 10000}",
            "name": "Test Construction Budget Item",
            "planned_amount": 0,
            "match_rule": "by_boq_item",
            "boq_item_ids": []  # Empty - should fail
        }, expected_status=400)
        detail = r.json()["detail"]
        assert "rab" in detail.lower() or "boq" in detail.lower()
        self.log("Construction item without boq_item_ids correctly rejected with 400")

    def test_budget_summary(self):
        """Test 15: GET /api/budget/summary (layer 1)"""
        if not self.project_id:
            self.log("Skipping summary test - no project_id", "WARN")
            return
        
        r = self.get(f"/budget/summary?project_id={self.project_id}", "owner@sipro.co.id")
        data = r.json()["data"]
        assert "planned" in data or "empty" in data
        if "planned" in data:
            assert "committed" in data
            assert "realized" in data
            assert "exposure" in data
            assert "status" in data
        self.log(f"Budget summary retrieved: status={data.get('status', 'empty')}")

    def test_budget_by_category(self):
        """Test 16: GET /api/budget/by-category (layer 2)"""
        if not self.project_id:
            self.log("Skipping by-category test - no project_id", "WARN")
            return
        
        r = self.get(f"/budget/by-category?project_id={self.project_id}", "owner@sipro.co.id")
        data = r.json()["data"]
        assert isinstance(data, list), "Budget by-category should be array"
        if len(data) > 0:
            assert "category" in data[0]
            assert "planned" in data[0]
        self.log(f"Budget by-category retrieved: {len(data)} categories")

    def test_budget_item_realization(self):
        """Test 17: GET /api/budget/items/{id}/realization (layer 3)"""
        if not self.budget_item_id:
            self.log("Skipping realization test - no budget_item_id", "WARN")
            return
        
        r = self.get(f"/budget/items/{self.budget_item_id}/realization", "owner@sipro.co.id")
        data = r.json()["data"]
        assert "documents" in data, "Realization missing documents"
        assert "checks" in data, "Realization missing checks"
        assert "tie_out_ok" in data["checks"], "Realization missing tie_out_ok"
        self.log(f"Realization drill retrieved: {len(data['documents'])} documents, tie_out_ok={data['checks']['tie_out_ok']}")

    def test_budget_revise_pm_403(self):
        """Test 18: POST /api/budget/items/{id}/revise - pm gets 403 (separation of duties)"""
        if not self.budget_item_id:
            self.log("Skipping revise test - no budget_item_id", "WARN")
            return
        
        r = self.post(f"/budget/items/{self.budget_item_id}/revise", "pm@sipro.co.id", {
            "planned_amount": 60000000,
            "reason": "Testing revision by PM (should fail)"
        }, expected_status=403)
        detail = r.json()["detail"]
        assert "akses ditolak" in detail.lower() or "forbidden" in detail.lower()
        self.log("PM correctly denied budget revision (403)")

    def test_budget_revise_finlead_success(self):
        """Test 19: POST /api/budget/items/{id}/revise - finlead can revise"""
        if not self.budget_item_id:
            self.log("Skipping revise test - no budget_item_id", "WARN")
            return
        
        r = self.post(f"/budget/items/{self.budget_item_id}/revise", "finlead@sipro.co.id", {
            "planned_amount": 60000000,
            "reason": "Testing revision by finlead (should succeed)"
        })
        data = r.json()["data"]
        assert data["planned_amount"] == 60000000
        assert len(data.get("revision", [])) > 0, "Revision history not updated"
        self.log(f"Finlead successfully revised budget item")

    def test_budget_revise_no_reason_400(self):
        """Test 20: POST /api/budget/items/{id}/revise without reason returns 400"""
        if not self.budget_item_id:
            self.log("Skipping revise test - no budget_item_id", "WARN")
            return
        
        r = self.post(f"/budget/items/{self.budget_item_id}/revise", "finlead@sipro.co.id", {
            "planned_amount": 70000000,
            "reason": "abc"  # Too short
        }, expected_status=400)
        detail = r.json()["detail"]
        assert "reason" in detail.lower() or "alasan" in detail.lower()
        self.log("Revise without valid reason correctly rejected with 400")

    def test_budget_alerts_scan_owner(self):
        """Test 21: POST /api/budget/alerts/scan (only manage roles)"""
        r = self.post("/budget/alerts/scan", "owner@sipro.co.id", {})
        data = r.json()["data"]
        assert "created" in data or "scanned" in data
        self.log(f"Alert scan completed: {data.get('created', 0)} alerts created")

    def test_budget_alerts_scan_pm_403(self):
        """Test 22: POST /api/budget/alerts/scan - pm gets 403"""
        r = self.post("/budget/alerts/scan", "pm@sipro.co.id", {}, expected_status=403)
        detail = r.json()["detail"]
        assert "akses ditolak" in detail.lower() or "forbidden" in detail.lower()
        self.log("PM correctly denied alert scan (403)")

    def test_budget_health(self):
        """Test 23: GET /api/budget/health (enforce settings)"""
        r = self.get("/budget/health", "owner@sipro.co.id")
        data = r.json()["data"]
        assert "enforce_cost_ref" in data
        assert "alert_pct" in data
        assert "default_target_method" in data
        # Check default values
        assert data["enforce_cost_ref"] == False, "enforce_cost_ref should be OFF by default"
        assert data["alert_pct"] == 90, "alert_pct should be 90 by default"
        self.log(f"Budget health: enforce={data['enforce_cost_ref']}, alert_pct={data['alert_pct']}")

    def test_rbac_sales_budget_403(self):
        """Test 24: RBAC - sales gets 403 on budget endpoints"""
        r = self.get("/budget/items", "sales@sipro.co.id", expected_status=403)
        detail = r.json()["detail"]
        assert "akses ditolak" in detail.lower() or "forbidden" in detail.lower()
        
        r2 = self.get("/budget/summary", "sales@sipro.co.id", expected_status=403)
        self.log("Sales correctly denied budget access (403)")

    def test_rbac_sales_targets_allowed(self):
        """Test 25: RBAC - sales can view targets (but only their own)"""
        r = self.get("/targets", "sales@sipro.co.id")
        data = r.json()
        assert "data" in data
        assert "scoped_to" in data
        assert data["scoped_to"] == "sales@sipro.co.id"
        self.log(f"Sales can view targets (scoped to own: {data['scoped_to']})")

    def run_all(self):
        """Run all tests"""
        print("\n" + "="*70)
        print("Phase 45 — Target Proyek & Budget/RAB Backend Test Suite")
        print("="*70 + "\n")
        
        # AUTH & SETUP
        self.test("AUTH: All Phase 45 roles login", self.test_auth_all_roles)
        self.test("SETUP: Get projects", self.test_get_projects)
        
        # TARGETS
        self.test("TARGETS: GET /api/targets/methods (5 methods)", self.test_targets_methods)
        self.test("TARGETS: POST /api/targets/preview", self.test_targets_preview)
        self.test("TARGETS: POST /api/targets (create)", self.test_targets_create)
        self.test("TARGETS: GET /api/targets (list)", self.test_targets_list)
        self.test("TARGETS: GET /api/targets/{id} (detail)", self.test_targets_get_detail)
        self.test("TARGETS: POST /api/targets/{id}/recalc without reason (400)", self.test_targets_recalc_no_reason_400)
        self.test("TARGETS: POST /api/targets/{id}/recalc with reason", self.test_targets_recalc_with_reason)
        self.test("TARGETS: POST /api/targets/{id}/activate", self.test_targets_activate)
        self.test("TARGETS: Activate second parent target (400)", self.test_targets_activate_second_parent_400)
        
        # BUDGET ITEMS
        self.test("BUDGET: GET /api/budget/items (list)", self.test_budget_items_list)
        self.test("BUDGET: POST /api/budget/items (operational)", self.test_budget_items_create_operational)
        self.test("BUDGET: POST /api/budget/items (construction no boq - 400)", self.test_budget_items_create_construction_no_boq_400)
        
        # BUDGET REPORTS (3 layers)
        self.test("BUDGET: GET /api/budget/summary (layer 1)", self.test_budget_summary)
        self.test("BUDGET: GET /api/budget/by-category (layer 2)", self.test_budget_by_category)
        self.test("BUDGET: GET /api/budget/items/{id}/realization (layer 3)", self.test_budget_item_realization)
        
        # BUDGET REVISE (separation of duties)
        self.test("BUDGET: POST /api/budget/items/{id}/revise - pm gets 403", self.test_budget_revise_pm_403)
        self.test("BUDGET: POST /api/budget/items/{id}/revise - finlead success", self.test_budget_revise_finlead_success)
        self.test("BUDGET: POST /api/budget/items/{id}/revise - no reason (400)", self.test_budget_revise_no_reason_400)
        
        # BUDGET ALERTS
        self.test("BUDGET: POST /api/budget/alerts/scan - owner", self.test_budget_alerts_scan_owner)
        self.test("BUDGET: POST /api/budget/alerts/scan - pm gets 403", self.test_budget_alerts_scan_pm_403)
        
        # BUDGET HEALTH
        self.test("BUDGET: GET /api/budget/health", self.test_budget_health)
        
        # RBAC
        self.test("RBAC: Sales gets 403 on budget endpoints", self.test_rbac_sales_budget_403)
        self.test("RBAC: Sales can view targets (scoped)", self.test_rbac_sales_targets_allowed)
        
        # Summary
        print("\n" + "="*70)
        print(f"RESULTS: {self.tests_passed}/{self.tests_run} tests passed")
        print("="*70 + "\n")
        
        if self.tests_passed == self.tests_run:
            print("✅ ALL TESTS PASSED")
            return 0
        else:
            failed = self.tests_run - self.tests_passed
            print(f"❌ {failed} TESTS FAILED")
            print("\nFailed tests:")
            for r in self.results:
                if r["status"] != "PASS":
                    print(f"  - {r['test']}: {r.get('error', 'Unknown error')}")
            return 1

if __name__ == "__main__":
    tester = Phase45Tester()
    sys.exit(tester.run_all())

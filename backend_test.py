#!/usr/bin/env python3
"""Backend API Testing for SIPRO - RBAC & Fee Portal Unification

Tests for Phase 41/42 continuation:
- Unified fee portal: /marketing-fee redirects properly
- RBAC fixes: permissions match backend enforcement
- Key endpoints for all 13 roles
"""
import sys
import requests

# Use public endpoint from frontend/.env
BASE_URL = "https://sipro-dev-2.preview.emergentagent.com/api"
PASSWORD = "Sipro#2026"

class TestRunner:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.tokens = {}
        
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
                user_data = r.json().get("data", {})
                print(f"  ✓ Logged in as {email} (role: {user_data.get('role', 'unknown')})")
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
            print(f"  GET {path} error: {str(e)}")
            return None
    
    def post(self, path, email, json=None):
        """POST request"""
        try:
            return requests.post(f"{BASE_URL}{path}", 
                               headers=self.headers(email),
                               json=json or {},
                               timeout=30)
        except Exception as e:
            print(f"  POST {path} error: {str(e)}")
            return None
    
    def summary(self):
        """Print test summary"""
        total = self.passed + self.failed
        print("\n" + "="*60)
        print(f"TEST SUMMARY: {self.passed}/{total} passed")
        if self.failed > 0:
            print(f"FAILED: {self.failed} tests")
            return 1
        else:
            print("ALL TESTS PASSED ✓")
            return 0


def main():
    runner = TestRunner()
    
    print("="*60)
    print("SIPRO - RBAC & FEE PORTAL UNIFICATION - BACKEND TESTS")
    print("="*60)
    
    # ========== AUTHENTICATION - ALL 13 ROLES ==========
    print("\n[1] AUTHENTICATION - ALL 13 ROLES")
    roles = {
        "superadmin@sipro.co.id": "super_admin",
        "owner@sipro.co.id": "owner",
        "manager@sipro.co.id": "sales_manager",
        "marketing@sipro.co.id": "marketing_admin",
        "sales@sipro.co.id": "sales",
        "sales2@sipro.co.id": "sales",
        "finance@sipro.co.id": "finance",
        "finlead@sipro.co.id": "finance_manager",
        "pm@sipro.co.id": "project_manager",
        "site@sipro.co.id": "site_engineer",
        "dmlead@sipro.co.id": "dm_supervisor",
        "dm@sipro.co.id": "dm_staff",
    }
    
    for email in roles.keys():
        runner.test(f"Login {email}", runner.login(email))
    
    if not runner.tokens.get("superadmin@sipro.co.id"):
        print("\n✗ Cannot proceed without superadmin login")
        return 1
    
    # ========== GET /auth/me - EFFECTIVE PERMISSIONS ==========
    print("\n[2] GET /auth/me - EFFECTIVE PERMISSIONS")
    
    # Test superadmin has wildcard permissions
    r = runner.get("/auth/me", "superadmin@sipro.co.id")
    runner.test("GET /auth/me returns 200 for superadmin", r and r.status_code == 200)
    if r and r.status_code == 200:
        data = r.json().get("data", {})
        perms = data.get("permissions", {})
        runner.test("Superadmin has wildcard permissions {'*': ['*']}", 
                   perms.get("*") == ["*"],
                   f"Got: {perms}")
    
    # Test finance manager has gl:manage
    r = runner.get("/auth/me", "finlead@sipro.co.id")
    if r and r.status_code == 200:
        data = r.json().get("data", {})
        perms = data.get("permissions", {})
        gl_perms = perms.get("gl", [])
        runner.test("Finance manager has gl:manage permission",
                   "manage" in gl_perms,
                   f"GL permissions: {gl_perms}")
    
    # Test site engineer has permits:update but not permits:create
    r = runner.get("/auth/me", "site@sipro.co.id")
    if r and r.status_code == 200:
        data = r.json().get("data", {})
        perms = data.get("permissions", {})
        permits_perms = perms.get("permits", [])
        runner.test("Site engineer has permits:update",
                   "update" in permits_perms,
                   f"Permits permissions: {permits_perms}")
        runner.test("Site engineer does NOT have permits:create",
                   "create" not in permits_perms,
                   f"Permits permissions: {permits_perms}")
    
    # Test sales has view permissions but not create for projects
    r = runner.get("/auth/me", "sales@sipro.co.id")
    if r and r.status_code == 200:
        data = r.json().get("data", {})
        perms = data.get("permissions", {})
        projects_perms = perms.get("projects", [])
        runner.test("Sales has view permission for projects",
                   any(p in projects_perms for p in ["view", "view_all", "view_own"]),
                   f"Projects permissions: {projects_perms}")
        runner.test("Sales does NOT have create permission for projects",
                   "create" not in projects_perms,
                   f"Projects permissions: {projects_perms}")
    
    # ========== RBAC ENFORCEMENT - B1: BUTTONS THAT WERE MISSING ==========
    print("\n[3] RBAC B1 - FINANCE MANAGER CAN REOPEN PERIODS")
    
    # Finance manager should be able to reopen periods (has gl:manage which includes approve)
    r = runner.post("/gl/periods/reopen", "finlead@sipro.co.id", {"period": "1900-01"})
    runner.test("Finance manager CAN reopen period (NOT 403)",
               r and r.status_code != 403,
               f"Status: {r.status_code if r else 'N/A'} (400 expected for invalid period, not 403)")
    
    # Regular finance should NOT be able to reopen
    r = runner.post("/gl/periods/reopen", "finance@sipro.co.id", {"period": "1900-01"})
    runner.test("Regular finance CANNOT reopen period (403)",
               r and r.status_code == 403,
               f"Status: {r.status_code if r else 'N/A'}")
    
    # ========== RBAC ENFORCEMENT - B2: TWO PERMISSIONS SPLIT ==========
    print("\n[4] RBAC B2 - SITE ENGINEER: UPDATE BUT NOT CREATE PERMITS")
    
    # Site engineer should NOT be able to create permits
    r = runner.post("/permits", "site@sipro.co.id", {})
    runner.test("Site engineer CANNOT create permit (403)",
               r and r.status_code == 403,
               f"Status: {r.status_code if r else 'N/A'}")
    
    # PM should be able to create permits
    r = runner.post("/permits", "pm@sipro.co.id", {})
    runner.test("Project manager CAN create permit (NOT 403)",
               r and r.status_code != 403,
               f"Status: {r.status_code if r else 'N/A'} (400 expected for empty payload, not 403)")
    
    # ========== RBAC ENFORCEMENT - B3: PM BUTTONS STILL PRESENT ==========
    print("\n[5] RBAC B3 - PROJECT MANAGER HAS EXPECTED PERMISSIONS")
    
    # PM should be able to create projects
    r = runner.post("/projects", "pm@sipro.co.id", {})
    runner.test("PM CAN create project (NOT 403)",
               r and r.status_code != 403,
               f"Status: {r.status_code if r else 'N/A'}")
    
    # PM should be able to create BOQ items
    r = runner.post("/boq/items", "pm@sipro.co.id", {})
    runner.test("PM CAN create BOQ item (NOT 403)",
               r and r.status_code != 403,
               f"Status: {r.status_code if r else 'N/A'}")
    
    # ========== RBAC ENFORCEMENT - B4: SALES CANNOT CREATE ==========
    print("\n[6] RBAC B4 - SALES CANNOT CREATE (VIEW ONLY)")
    
    # Sales should NOT be able to create projects
    r = runner.post("/projects", "sales@sipro.co.id", {})
    runner.test("Sales CANNOT create project (403)",
               r and r.status_code == 403,
               f"Status: {r.status_code if r else 'N/A'}")
    
    # Sales should NOT be able to create BOQ items
    r = runner.post("/boq/items", "sales@sipro.co.id", {})
    runner.test("Sales CANNOT create BOQ item (403)",
               r and r.status_code == 403,
               f"Status: {r.status_code if r else 'N/A'}")
    
    # Sales should NOT be able to create partners
    r = runner.post("/partners", "sales@sipro.co.id", {})
    runner.test("Sales CANNOT create partner (403)",
               r and r.status_code == 403,
               f"Status: {r.status_code if r else 'N/A'}")
    
    # But sales CAN view partners
    r = runner.get("/partners", "sales@sipro.co.id")
    runner.test("Sales CAN view partners (200)",
               r and r.status_code == 200,
               f"Status: {r.status_code if r else 'N/A'}")
    
    # Sales CAN reserve units (deals:create)
    r = runner.post("/deals/reserve", "sales@sipro.co.id", {})
    runner.test("Sales CAN reserve unit (NOT 403)",
               r and r.status_code != 403,
               f"Status: {r.status_code if r else 'N/A'} (400 expected for empty payload, not 403)")
    
    # ========== RBAC ENFORCEMENT - B5: ADMIN AREA ==========
    print("\n[7] RBAC B5 - ADMIN AREA ACCESS CONTROL")
    
    # Sales should NOT access admin area
    r = runner.get("/admin/users", "sales@sipro.co.id")
    runner.test("Sales CANNOT access /admin/users (403)",
               r and r.status_code == 403,
               f"Status: {r.status_code if r else 'N/A'}")
    
    # Superadmin CAN access admin area
    r = runner.get("/admin/users", "superadmin@sipro.co.id")
    runner.test("Superadmin CAN access /admin/users (200)",
               r and r.status_code == 200,
               f"Status: {r.status_code if r else 'N/A'}")
    
    r = runner.get("/admin/permissions", "superadmin@sipro.co.id")
    runner.test("Superadmin CAN access /admin/permissions (200)",
               r and r.status_code == 200,
               f"Status: {r.status_code if r else 'N/A'}")
    
    # ========== FEE SEPARATION OF DUTIES - B7 ==========
    print("\n[8] FEE SEPARATION OF DUTIES - B7")
    
    # Finance should NOT be able to issue fee (marketing_fee:create)
    r = runner.post("/partners/rules/issue", "finance@sipro.co.id", {})
    runner.test("Finance CANNOT issue fee (403 - separation of duties)",
               r and r.status_code == 403,
               f"Status: {r.status_code if r else 'N/A'}")
    
    # Sales/Manager CAN issue fee
    r = runner.post("/partners/rules/issue", "manager@sipro.co.id", {})
    runner.test("Manager CAN issue fee (NOT 403)",
               r and r.status_code != 403,
               f"Status: {r.status_code if r else 'N/A'} (400 expected for empty payload, not 403)")
    
    # ========== PARTNERS & FEE ENDPOINTS ==========
    print("\n[9] PARTNERS & FEE ENDPOINTS")
    
    # Get partners list
    r = runner.get("/partners", "superadmin@sipro.co.id")
    runner.test("GET /partners returns 200", r and r.status_code == 200)
    
    # Get fee rules
    r = runner.get("/partners/rules", "superadmin@sipro.co.id")
    runner.test("GET /partners/rules returns 200", r and r.status_code == 200)
    
    # Get partner analytics
    r = runner.get("/partners/analytics", "superadmin@sipro.co.id")
    runner.test("GET /partners/analytics returns 200", r and r.status_code == 200)
    
    # ========== AGING REPORT - REGRESI-3 ==========
    print("\n[10] AGING REPORT - PHASE 41 NOT BROKEN")
    
    # All roles should be able to view aging report
    r = runner.get("/work/home", "superadmin@sipro.co.id")
    runner.test("GET /work/home returns 200", r and r.status_code == 200)
    
    # Only owner/super_admin can reconcile aging
    r = runner.post("/aging/reconcile", "sales@sipro.co.id", {})
    runner.test("Sales CANNOT reconcile aging (403)",
               r and r.status_code == 403,
               f"Status: {r.status_code if r else 'N/A'}")
    
    r = runner.post("/aging/reconcile", "superadmin@sipro.co.id", {})
    runner.test("Superadmin CAN reconcile aging (NOT 403)",
               r and r.status_code != 403,
               f"Status: {r.status_code if r else 'N/A'}")
    
    # ========== REGRESSION TESTS ==========
    print("\n[11] REGRESSION - EXISTING ENDPOINTS")
    
    # Test key endpoints still work
    endpoints = [
        ("/projects", "pm@sipro.co.id"),
        ("/leads", "manager@sipro.co.id"),
        ("/customers", "manager@sipro.co.id"),
        ("/deals", "sales@sipro.co.id"),
        ("/build/summary", "pm@sipro.co.id"),
        ("/materials", "pm@sipro.co.id"),
        ("/permits", "pm@sipro.co.id"),
        ("/boq/items", "pm@sipro.co.id"),
        ("/subcon/contractors", "pm@sipro.co.id"),
        ("/procurement/orders", "pm@sipro.co.id"),
        ("/accounting/coa", "finance@sipro.co.id"),
        ("/gl/journals", "finance@sipro.co.id"),
    ]
    
    for path, email in endpoints:
        r = runner.get(path, email, {"limit": 10})
        runner.test(f"GET {path} returns 200 for {email.split('@')[0]}", 
                   r and r.status_code == 200,
                   f"Status: {r.status_code if r else 'N/A'}")
    
    # ========== FINAL SUMMARY ==========
    return runner.summary()


if __name__ == "__main__":
    sys.exit(main())

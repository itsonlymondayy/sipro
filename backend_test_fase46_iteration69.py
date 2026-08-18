"""Backend API tests for FASE 46 iteration 69 — testing leftovers from iteration 68.

Focus: 'Mulai Bangun' flow, work submission, verification, permits, and RBAC.
"""
import requests
import sys
import time
from typing import Optional

BASE_URL = "https://sipro-next.preview.emergentagent.com/api"
PASSWORD = "Sipro#2026"

class TestRunner:
    def __init__(self):
        self.tests_run = 0
        self.tests_passed = 0
        self.tests_failed = 0
        self.pm_token = None
        self.site_token = None
        self.sales_token = None
        self.unit_a05_id = None
        self.unit_a01_id = None
        self.project_id = None
        
    def log(self, msg: str, level: str = "info"):
        prefix = {"info": "ℹ️", "success": "✅", "error": "❌", "warn": "⚠️"}
        print(f"{prefix.get(level, 'ℹ️')} {msg}")
    
    def test(self, name: str, fn):
        """Run a single test"""
        self.tests_run += 1
        self.log(f"Test {self.tests_run}: {name}", "info")
        try:
            fn()
            self.tests_passed += 1
            self.log(f"PASSED: {name}", "success")
            return True
        except AssertionError as e:
            self.tests_failed += 1
            self.log(f"FAILED: {name} - {str(e)}", "error")
            return False
        except Exception as e:
            self.tests_failed += 1
            self.log(f"ERROR: {name} - {str(e)}", "error")
            return False
    
    def login(self, email: str) -> Optional[str]:
        """Login and return token"""
        try:
            r = requests.post(f"{BASE_URL}/auth/login", 
                            json={"email": email, "password": PASSWORD},
                            timeout=10)
            if r.status_code == 200:
                token = r.json().get("access_token")
                if token:
                    self.log(f"Login successful: {email}", "success")
                    return token
                else:
                    self.log(f"Login response missing access_token for {email}", "error")
                    return None
            else:
                self.log(f"Login failed for {email}: {r.status_code}", "error")
                return None
        except Exception as e:
            self.log(f"Login error for {email}: {str(e)}", "error")
            return None
    
    def get(self, endpoint: str, token: Optional[str] = None, params: dict = None, 
            expect_status: int = 200, timeout: int = 10):
        """GET request with optional auth"""
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        r = requests.get(f"{BASE_URL}{endpoint}", headers=headers, params=params, 
                        timeout=timeout)
        if r.status_code != expect_status:
            raise AssertionError(f"Expected {expect_status}, got {r.status_code}: {r.text[:200]}")
        return r.json() if r.status_code == 200 else r
    
    def post(self, endpoint: str, token: Optional[str] = None, data: dict = None,
            expect_status: int = 200, timeout: int = 10):
        """POST request with optional auth"""
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        r = requests.post(f"{BASE_URL}{endpoint}", headers=headers, json=data, 
                         timeout=timeout)
        if r.status_code != expect_status:
            raise AssertionError(f"Expected {expect_status}, got {r.status_code}: {r.text[:200]}")
        return r.json() if r.status_code in [200, 201] else r
    
    def run_all(self):
        """Run all tests in sequence"""
        self.log("=" * 80, "info")
        self.log("FASE 46 Iteration 69 Backend Tests - Leftovers from iteration 68", "info")
        self.log("=" * 80, "info")
        
        # 1. Authentication
        self.log("\n--- 1. AUTHENTICATION ---", "info")
        self.test("Login as pm@sipro.co.id", lambda: self._test_login_pm())
        self.test("Login as site@sipro.co.id", lambda: self._test_login_site())
        self.test("Login as sales@sipro.co.id", lambda: self._test_login_sales())
        
        if not self.pm_token:
            self.log("Cannot proceed without PM token", "error")
            return
        
        # 2. Get unit board and find A-05 and A-01
        self.log("\n--- 2. UNIT BOARD & SCHEDULED UNITS ---", "info")
        self.test("GET /build/board/units - find A-05 (scheduled, not started)", 
                 lambda: self._test_find_units())
        
        # 3. Readiness check for A-05
        if self.unit_a05_id:
            self.log("\n--- 3. READINESS CHECK FOR A-05 ---", "info")
            self.test("GET /build/unit/{id}/readiness - A-05 should be 'warning' state",
                     lambda: self._test_readiness_a05())
        
        # 4. RBAC tests with retries
        self.log("\n--- 4. RBAC TESTS (with retries) ---", "info")
        self.test("Sales 403 on GET /build/board/units", 
                 lambda: self._test_rbac_sales_board())
        self.test("Sales 403 on GET /permits", 
                 lambda: self._test_rbac_sales_permits())
        if self.unit_a05_id:
            self.test("Sales 403 on GET /permits/coverage?unit_id=...",
                     lambda: self._test_rbac_sales_coverage())
        self.test("No token 401 on GET /build/board/units",
                 lambda: self._test_rbac_no_token())
        if self.unit_a05_id:
            self.test("Site engineer 403 on POST /build/unit/{id}/start",
                     lambda: self._test_rbac_site_start())
        
        # 5. Permit coverage
        if self.unit_a05_id:
            self.log("\n--- 5. PERMIT COVERAGE ---", "info")
            self.test("GET /permits/coverage?unit_id=A-05",
                     lambda: self._test_permit_coverage())
        
        # 6. Summary
        self.log("\n" + "=" * 80, "info")
        self.log(f"Tests run: {self.tests_run}", "info")
        self.log(f"Tests passed: {self.tests_passed}", "success")
        self.log(f"Tests failed: {self.tests_failed}", "error" if self.tests_failed else "info")
        self.log(f"Success rate: {self.tests_passed}/{self.tests_run} "
                f"({100*self.tests_passed//self.tests_run if self.tests_run else 0}%)", "info")
        self.log("=" * 80, "info")
        
        return 0 if self.tests_failed == 0 else 1
    
    # Test implementations
    def _test_login_pm(self):
        self.pm_token = self.login("pm@sipro.co.id")
        assert self.pm_token, "PM login failed"
    
    def _test_login_site(self):
        self.site_token = self.login("site@sipro.co.id")
        assert self.site_token, "Site login failed"
    
    def _test_login_sales(self):
        self.sales_token = self.login("sales@sipro.co.id")
        assert self.sales_token, "Sales login failed"
    
    def _test_find_units(self):
        data = self.get("/build/board/units", self.pm_token)
        units = data.get("data", [])
        summary = data.get("summary", {})
        
        self.log(f"Found {len(units)} units total", "info")
        self.log(f"Summary: {summary.get('warning_to_start', 0)} warning_to_start, "
                f"{summary.get('scheduled', 0)} scheduled", "info")
        
        # Find A-05 (should be scheduled but not started, readiness = warning)
        a05 = next((u for u in units if u.get("code") == "A-05"), None)
        if a05:
            self.unit_a05_id = a05.get("unit_id")
            self.project_id = a05.get("project_id")
            self.log(f"Found A-05: unit_id={self.unit_a05_id}, readiness={a05.get('readiness')}, "
                    f"construction_status={a05.get('construction_status')}", "info")
            assert a05.get("readiness") == "warning", \
                f"A-05 should have readiness='warning', got '{a05.get('readiness')}'"
            assert a05.get("construction_status") in ["not_started", "scheduled"], \
                f"A-05 should be 'not_started' or 'scheduled', got '{a05.get('construction_status')}'"
        else:
            self.log("A-05 not found in unit board", "warn")
        
        # Find A-01 or A-02 (should be running)
        a01 = next((u for u in units if u.get("code") in ["A-01", "A-02"] 
                   and u.get("construction_status") in ["in_progress", "at_risk"]), None)
        if a01:
            self.unit_a01_id = a01.get("unit_id")
            self.log(f"Found running unit {a01.get('code')}: unit_id={self.unit_a01_id}", "info")
        
        assert summary.get("warning_to_start", 0) >= 1, \
            "Expected at least 1 unit with warning_to_start (A-05 or A-03)"
    
    def _test_readiness_a05(self):
        data = self.get(f"/build/unit/{self.unit_a05_id}/readiness", self.pm_token)
        readiness = data.get("data", {})
        
        state = readiness.get("state")
        can_start = readiness.get("can_start")
        needs_ack = readiness.get("needs_ack")
        warnings = readiness.get("warnings", [])
        blockers = readiness.get("blockers", [])
        
        self.log(f"A-05 readiness: state={state}, can_start={can_start}, "
                f"needs_ack={needs_ack}, warnings={len(warnings)}, blockers={len(blockers)}", 
                "info")
        
        assert state == "warning", f"Expected state='warning', got '{state}'"
        assert can_start == True, "A-05 should be able to start (with acknowledgement)"
        assert needs_ack == True, "A-05 should need acknowledgement"
        assert len(warnings) > 0, "A-05 should have warnings"
        assert len(blockers) == 0, "A-05 should have no blockers"
        
        # Check warnings have proper structure
        for w in warnings:
            assert "code" in w, "Warning should have 'code'"
            assert "detail" in w, "Warning should have 'detail'"
            assert "severity" in w, "Warning should have 'severity'"
            self.log(f"  Warning: {w.get('code')} - {w.get('detail')[:80]}", "info")
    
    def _test_rbac_sales_board(self):
        """Sales should get 403 on build board"""
        for attempt in range(3):
            try:
                self.get("/build/board/units", self.sales_token, expect_status=403, timeout=15)
                return
            except Exception as e:
                if attempt < 2:
                    self.log(f"Retry {attempt+1}/3 for sales board RBAC", "warn")
                    time.sleep(2)
                else:
                    raise
    
    def _test_rbac_sales_permits(self):
        """Sales should get 403 on permits list"""
        for attempt in range(3):
            try:
                self.get("/permits", self.sales_token, expect_status=403, timeout=15)
                return
            except Exception as e:
                if attempt < 2:
                    self.log(f"Retry {attempt+1}/3 for sales permits RBAC", "warn")
                    time.sleep(2)
                else:
                    raise
    
    def _test_rbac_sales_coverage(self):
        """Sales should get 403 on permit coverage"""
        for attempt in range(3):
            try:
                self.get("/permits/coverage", self.sales_token, 
                        params={"unit_id": self.unit_a05_id}, 
                        expect_status=403, timeout=15)
                return
            except Exception as e:
                if attempt < 2:
                    self.log(f"Retry {attempt+1}/3 for sales coverage RBAC", "warn")
                    time.sleep(2)
                else:
                    raise
    
    def _test_rbac_no_token(self):
        """No token should get 401"""
        for attempt in range(3):
            try:
                self.get("/build/board/units", None, expect_status=401, timeout=15)
                return
            except Exception as e:
                if attempt < 2:
                    self.log(f"Retry {attempt+1}/3 for no-token RBAC", "warn")
                    time.sleep(2)
                else:
                    raise
    
    def _test_rbac_site_start(self):
        """Site engineer should get 403 on start build"""
        for attempt in range(3):
            try:
                self.post(f"/build/unit/{self.unit_a05_id}/start", self.site_token,
                         data={"ack": True, "reason": "Test reason from site engineer"},
                         expect_status=403, timeout=15)
                return
            except Exception as e:
                if attempt < 2:
                    self.log(f"Retry {attempt+1}/3 for site start RBAC", "warn")
                    time.sleep(2)
                else:
                    raise
    
    def _test_permit_coverage(self):
        """Test permit coverage for A-05"""
        data = self.get("/permits/coverage", self.pm_token, 
                       params={"unit_id": self.unit_a05_id})
        cov = data.get("data", {})
        
        chain = cov.get("chain", {})
        permits = cov.get("permits", [])
        
        self.log(f"Permit coverage: {len(permits)} permits, chain={chain.get('labels')}", "info")
        
        assert "chain" in cov, "Coverage should have 'chain'"
        assert "permits" in cov, "Coverage should have 'permits'"
        assert "state" in cov, "Coverage should have 'state'"
        
        # Check chain resolution
        labels = chain.get("labels", {})
        assert "project" in labels, "Chain should resolve project"

if __name__ == "__main__":
    runner = TestRunner()
    sys.exit(runner.run_all())

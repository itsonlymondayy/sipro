"""SIPRO Backend API Testing - EPIC M4 Multi-Tenant Only

Focused test suite for EPIC M4 multi-tenant features:
- Org management RBAC
- Tenant onboarding
- Org-switch isolation
- Suspended tenant
"""
import requests
import sys
from datetime import datetime

class M4Tester:
    def __init__(self, base_url="https://development-resume.preview.emergentagent.com/api"):
        self.base_url = base_url
        self.tokens = {}
        self.tests_run = 0
        self.tests_passed = 0
        self.failed_tests = []

    def log(self, msg, level="INFO"):
        print(f"[{level}] {msg}")

    def run_test(self, name, method, endpoint, expected_status, data=None, token=None, params=None):
        """Run a single API test"""
        url = f"{self.base_url}/{endpoint}"
        headers = {'Content-Type': 'application/json'}
        if token:
            headers['Authorization'] = f'Bearer {token}'

        self.tests_run += 1
        self.log(f"\n🔍 Test #{self.tests_run}: {name}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, params=params, timeout=10)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=10)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=headers, timeout=10)

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                self.log(f"✅ PASS - Status: {response.status_code}", "PASS")
                try:
                    return True, response.json()
                except:
                    return True, {}
            else:
                self.log(f"❌ FAIL - Expected {expected_status}, got {response.status_code}", "FAIL")
                self.log(f"   Response: {response.text[:300]}", "FAIL")
                self.failed_tests.append({"test": name, "expected": expected_status, "got": response.status_code, "response": response.text[:200]})
                return False, {}

        except Exception as e:
            self.log(f"❌ FAIL - Error: {str(e)}", "FAIL")
            self.failed_tests.append({"test": name, "error": str(e)})
            return False, {}

    def test_login(self, email, password, should_succeed=True):
        """Test login"""
        expected = 200 if should_succeed else 403
        success, response = self.run_test(
            f"Login: {email} (expect {expected})",
            "POST",
            "auth/login",
            expected,
            data={"email": email, "password": password}
        )
        if success and should_succeed:
            if 'access_token' in response:
                self.tokens[email] = response['access_token']
                self.log(f"   Token saved for {email}, role: {response.get('data', {}).get('role')}")
                return True
        return success

    def test_orgs_list(self, email, expected_is_super_admin=False):
        """Test GET /admin/orgs"""
        token = self.tokens.get(email)
        success, response = self.run_test(
            f"GET /admin/orgs by {email} (expect is_super_admin={expected_is_super_admin})",
            "GET",
            "admin/orgs",
            200,
            token=token
        )
        if success and 'data' in response:
            orgs = response.get('data', [])
            is_super = response.get('is_super_admin', False)
            self.log(f"   Orgs: {len(orgs)}, is_super_admin: {is_super}")
            for org in orgs:
                stats = org.get('stats', {})
                self.log(f"   - {org.get('name')} ({org.get('id')}): users={stats.get('users')}, leads={stats.get('leads')}, deals={stats.get('deals')}, projects={stats.get('projects')}")
            return True, orgs, is_super
        return False, [], False

    def test_orgs_create(self, email, org_name, owner_name, owner_email, owner_password):
        """Test POST /admin/orgs"""
        token = self.tokens.get(email)
        success, response = self.run_test(
            f"POST /admin/orgs (name={org_name}, owner={owner_email}) by {email}",
            "POST",
            "admin/orgs",
            200,
            data={"name": org_name, "owner_name": owner_name, "owner_email": owner_email, "owner_password": owner_password},
            token=token
        )
        if success and 'data' in response:
            org = response['data']
            self.log(f"   Created org: {org.get('name')} ({org.get('id')}), owner: {org.get('owner_email')}")
            return True, org.get('id'), owner_email
        return False, None, None

    def test_orgs_update(self, email, org_id, status):
        """Test PUT /admin/orgs/{org_id}"""
        token = self.tokens.get(email)
        success, response = self.run_test(
            f"PUT /admin/orgs/{org_id} (status={status}) by {email}",
            "PUT",
            f"admin/orgs/{org_id}",
            200,
            data={"status": status},
            token=token
        )
        if success and 'data' in response:
            org = response['data']
            self.log(f"   Updated org: {org.get('name')}, status: {org.get('status')}")
            return True
        return False

    def test_orgs_switch(self, email, org_id):
        """Test POST /admin/orgs/{org_id}/switch"""
        token = self.tokens.get(email)
        success, response = self.run_test(
            f"POST /admin/orgs/{org_id}/switch by {email}",
            "POST",
            f"admin/orgs/{org_id}/switch",
            200,
            token=token
        )
        if success and 'data' in response:
            new_token = response.get('access_token')
            active_org_id = response['data'].get('active_org_id')
            is_home = response['data'].get('is_home', False)
            self.log(f"   Switched to: {active_org_id}, is_home: {is_home}")
            if new_token:
                self.tokens[email] = new_token
                self.log(f"   ✓ Token updated")
            return True, active_org_id
        return False, None

    def test_auth_me(self, email, expected_org_id=None):
        """Test GET /auth/me"""
        token = self.tokens.get(email)
        success, response = self.run_test(
            f"GET /auth/me by {email}",
            "GET",
            "auth/me",
            200,
            token=token
        )
        if success and 'data' in response:
            user = response['data']
            org_id = user.get('org_id')
            is_switched = user.get('is_switched', False)
            active_org = user.get('active_org', {})
            self.log(f"   User: {user.get('name')}, org_id: {org_id}, is_switched: {is_switched}")
            self.log(f"   Active org: {active_org.get('name')} ({active_org.get('id')})")
            if expected_org_id and org_id != expected_org_id:
                self.log(f"   ✗ org_id mismatch: expected {expected_org_id}, got {org_id}", "FAIL")
                return False
            return True
        return False

    def test_leads_count(self, email, expected_total):
        """Test GET /leads - verify data isolation"""
        token = self.tokens.get(email)
        success, response = self.run_test(
            f"GET /leads by {email} (expect total={expected_total})",
            "GET",
            "leads",
            200,
            token=token
        )
        if success and 'data' in response:
            total = response.get('total', 0)
            self.log(f"   Total leads: {total}")
            if total == expected_total:
                self.log(f"   ✓ Lead count matches expected: {expected_total}")
                return True
            else:
                self.log(f"   ✗ Lead count mismatch: expected {expected_total}, got {total}", "FAIL")
                return False
        return False

    def test_rbac_denial(self, email, endpoint, expected_status=403):
        """Test RBAC denial"""
        token = self.tokens.get(email)
        return self.run_test(
            f"RBAC Denial: {email} -> {endpoint} (expect {expected_status})",
            "GET",
            endpoint,
            expected_status,
            token=token
        )[0]

    def run_all_tests(self):
        """Run all EPIC M4 tests"""
        self.log("="*80)
        self.log("EPIC M4 - MULTI-TENANT ORG MANAGEMENT TESTS")
        self.log("="*80)
        
        # Login users
        self.log("\n--- Login Test Users ---")
        self.test_login("superadmin@sipro.co.id", "Sipro#2026")
        self.test_login("owner@sipro.co.id", "Sipro#2026")
        self.test_login("manager@sipro.co.id", "Sipro#2026")
        self.test_login("sales@sipro.co.id", "Sipro#2026")
        self.test_login("finance@sipro.co.id", "Sipro#2026")
        
        # Test 1: List orgs - RBAC
        self.log("\n--- Test 1: List Organizations (RBAC) ---")
        success, super_orgs, is_super = self.test_orgs_list("superadmin@sipro.co.id", expected_is_super_admin=True)
        success, owner_orgs, is_owner_super = self.test_orgs_list("owner@sipro.co.id", expected_is_super_admin=False)
        
        if len(super_orgs) >= 2:
            self.log(f"   ✓ super_admin sees {len(super_orgs)} orgs (expected >=2)")
        else:
            self.log(f"   ✗ super_admin sees {len(super_orgs)} orgs (expected >=2)", "FAIL")
        
        if len(owner_orgs) == 1:
            self.log(f"   ✓ owner sees {len(owner_orgs)} org (expected 1)")
        else:
            self.log(f"   ✗ owner sees {len(owner_orgs)} orgs (expected 1)", "FAIL")
        
        # Test 2: sales cannot access /admin/orgs
        self.log("\n--- Test 2: RBAC Denial - sales cannot list orgs ---")
        self.test_rbac_denial("sales@sipro.co.id", "admin/orgs")
        
        # Test 3: Create tenant
        self.log("\n--- Test 3: Tenant Onboarding (super_admin only) ---")
        timestamp = datetime.now().strftime("%H%M%S")
        new_org_name = f"PT Test Properti {timestamp}"
        new_owner_email = f"owner_test_{timestamp}@test.co.id"
        success, new_org_id, new_owner_email = self.test_orgs_create(
            "superadmin@sipro.co.id", new_org_name, f"Owner Test {timestamp}", new_owner_email, "Sipro#2026"
        )
        
        # Test 4: Duplicate owner email (400)
        if success and new_owner_email:
            self.log("\n--- Test 4: Duplicate Owner Email (expect 400) ---")
            self.run_test(
                f"POST /admin/orgs with duplicate owner email (expect 400)",
                "POST", "admin/orgs", 400,
                data={"name": "Dup Org", "owner_name": "Dup", "owner_email": new_owner_email, "owner_password": "Sipro#2026"},
                token=self.tokens.get("superadmin@sipro.co.id")
            )
        
        # Test 5: Short password (400)
        self.log("\n--- Test 5: Short Password Validation (expect 400) ---")
        self.run_test(
            f"POST /admin/orgs with short password (expect 400)",
            "POST", "admin/orgs", 400,
            data={"name": "Short Pwd Org", "owner_name": "Test", "owner_email": "short@test.co.id", "owner_password": "12345"},
            token=self.tokens.get("superadmin@sipro.co.id")
        )
        
        # Test 6: owner/sales cannot create tenant (403)
        self.log("\n--- Test 6: RBAC Denial - owner/sales cannot create tenant ---")
        self.run_test(
            f"POST /admin/orgs by owner (expect 403)",
            "POST", "admin/orgs", 403,
            data={"name": "Unauth Org", "owner_name": "Test", "owner_email": "unauth@test.co.id", "owner_password": "Sipro#2026"},
            token=self.tokens.get("owner@sipro.co.id")
        )
        self.run_test(
            f"POST /admin/orgs by sales (expect 403)",
            "POST", "admin/orgs", 403,
            data={"name": "Unauth Org", "owner_name": "Test", "owner_email": "unauth2@test.co.id", "owner_password": "Sipro#2026"},
            token=self.tokens.get("sales@sipro.co.id")
        )
        
        # Test 7: Org-switch isolation (CORE)
        self.log("\n--- Test 7: Org-Switch Isolation (CORE) ---")
        
        # 7a: super_admin in SIPRO - 2 leads
        self.log("\n   7a: super_admin in SIPRO context (home)")
        self.test_auth_me("superadmin@sipro.co.id", expected_org_id="org-sipro")
        self.test_leads_count("superadmin@sipro.co.id", 2)
        
        # 7b: Switch to org-nusa - 0 leads
        self.log("\n   7b: Switch to org-nusa (empty tenant)")
        success, active_org = self.test_orgs_switch("superadmin@sipro.co.id", "org-nusa")
        if success:
            self.test_auth_me("superadmin@sipro.co.id", expected_org_id="org-nusa")
            self.test_leads_count("superadmin@sipro.co.id", 0)
        
        # 7c: Switch back to org-sipro - 2 leads
        self.log("\n   7c: Switch back to org-sipro (home)")
        success, active_org = self.test_orgs_switch("superadmin@sipro.co.id", "org-sipro")
        if success:
            self.test_auth_me("superadmin@sipro.co.id", expected_org_id="org-sipro")
            self.test_leads_count("superadmin@sipro.co.id", 2)
        
        # Test 8: owner/sales cannot switch (403)
        self.log("\n--- Test 8: RBAC Denial - owner/sales cannot switch orgs ---")
        self.run_test(
            f"POST /admin/orgs/org-nusa/switch by owner (expect 403)",
            "POST", "admin/orgs/org-nusa/switch", 403,
            token=self.tokens.get("owner@sipro.co.id")
        )
        self.run_test(
            f"POST /admin/orgs/org-nusa/switch by sales (expect 403)",
            "POST", "admin/orgs/org-nusa/switch", 403,
            token=self.tokens.get("sales@sipro.co.id")
        )
        
        # Test 9: Suspend tenant
        self.log("\n--- Test 9: Suspend Tenant (super_admin only) ---")
        self.test_orgs_update("superadmin@sipro.co.id", "org-nusa", "suspended")
        
        # Test 10: Login to suspended org (403)
        self.log("\n--- Test 10: Login to Suspended Org (expect 403) ---")
        self.test_login("owner@nusaproperti.co.id", "Sipro#2026", should_succeed=False)
        
        # Test 11: Re-activate tenant
        self.log("\n--- Test 11: Re-activate Tenant ---")
        self.test_orgs_update("superadmin@sipro.co.id", "org-nusa", "active")
        
        # Test 12: Login to re-activated org (200)
        self.log("\n--- Test 12: Login to Re-activated Org (expect 200) ---")
        self.test_login("owner@nusaproperti.co.id", "Sipro#2026", should_succeed=True)
        
        # Test 13: owner/sales cannot update org status (403)
        self.log("\n--- Test 13: RBAC Denial - owner/sales cannot update org status ---")
        self.run_test(
            f"PUT /admin/orgs/org-nusa by owner (expect 403)",
            "PUT", "admin/orgs/org-nusa", 403,
            data={"status": "active"},
            token=self.tokens.get("owner@sipro.co.id")
        )
        self.run_test(
            f"PUT /admin/orgs/org-nusa by sales (expect 403)",
            "PUT", "admin/orgs/org-nusa", 403,
            data={"status": "active"},
            token=self.tokens.get("sales@sipro.co.id")
        )
        
        # Test 14: Login new tenant owner
        if new_owner_email:
            self.log("\n--- Test 14: Login New Tenant Owner ---")
            self.test_login(new_owner_email, "Sipro#2026", should_succeed=True)
            self.test_auth_me(new_owner_email)
            self.test_leads_count(new_owner_email, 0)
        
        # Summary
        self.log("\n" + "="*80)
        self.log("TEST SUMMARY")
        self.log("="*80)
        self.log(f"Total tests run: {self.tests_run}")
        self.log(f"Tests passed: {self.tests_passed}")
        self.log(f"Tests failed: {self.tests_run - self.tests_passed}")
        self.log(f"Success rate: {(self.tests_passed/self.tests_run*100):.1f}%")
        
        if self.failed_tests:
            self.log("\n❌ FAILED TESTS:")
            for fail in self.failed_tests:
                error_msg = fail.get('error', f"Expected {fail.get('expected')}, got {fail.get('got')}")
                self.log(f"   - {fail.get('test')}: {error_msg}")
                if 'response' in fail:
                    self.log(f"     Response: {fail['response']}")
        
        return 0 if self.tests_passed == self.tests_run else 1


def main():
    tester = M4Tester()
    return tester.run_all_tests()


if __name__ == "__main__":
    sys.exit(main())

"""Backend API tests for Phase 19 — Tax → GL journal integration (setoran).

Tests:
1. Login as finance@sipro.co.id
2. Verify seeded paid PPh record with NTPN + GL journals
3. Test status transitions: pending → reported (accrual journal)
4. Test status transitions: reported → paid (setoran journal with NTPN)
5. Test NTPN validation (400 error when missing)
6. Test idempotency (no duplicate journals)
7. Verify trial balance is balanced
8. Check GL accounts exist (2-1300, 6-1400)
9. Regression tests
"""
import requests
import sys
from datetime import datetime

BASE_URL = "https://sleepy-sammet-6.preview.emergentagent.com/api"

class Phase19Tester:
    def __init__(self):
        self.token = None
        self.tests_run = 0
        self.tests_passed = 0
        self.failed_tests = []

    def log(self, msg, level="INFO"):
        prefix = {"INFO": "ℹ️", "PASS": "✅", "FAIL": "❌", "WARN": "⚠️"}
        print(f"{prefix.get(level, 'ℹ️')} {msg}")

    def test(self, name, method, endpoint, expected_status, data=None, headers=None):
        """Run a single API test."""
        url = f"{BASE_URL}/{endpoint}"
        h = {"Content-Type": "application/json"}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        if headers:
            h.update(headers)

        self.tests_run += 1
        self.log(f"Testing {name}...", "INFO")

        try:
            if method == "GET":
                response = requests.get(url, headers=h, params=data, timeout=15)
            elif method == "POST":
                response = requests.post(url, json=data, headers=h, timeout=15)
            elif method == "PUT":
                response = requests.put(url, json=data, headers=h, timeout=15)
            else:
                raise ValueError(f"Unsupported method: {method}")

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                self.log(f"PASSED - {name} (status: {response.status_code})", "PASS")
            else:
                self.failed_tests.append(f"{name}: expected {expected_status}, got {response.status_code}")
                self.log(f"FAILED - {name}: expected {expected_status}, got {response.status_code}", "FAIL")
                if response.text:
                    self.log(f"Response: {response.text[:200]}", "WARN")

            return success, response.json() if response.text else {}

        except Exception as e:
            self.failed_tests.append(f"{name}: {str(e)}")
            self.log(f"FAILED - {name}: {str(e)}", "FAIL")
            return False, {}

    def run_all_tests(self):
        """Execute all Phase 19 tests."""
        self.log("=" * 60, "INFO")
        self.log("Phase 19 Backend Testing — Tax → GL Integration", "INFO")
        self.log("=" * 60, "INFO")

        # 1. Login as finance@sipro.co.id
        self.log("\n[1] Testing Authentication", "INFO")
        success, resp = self.test(
            "Login as finance@sipro.co.id",
            "POST", "auth/login", 200,
            data={"email": "finance@sipro.co.id", "password": "Sipro#2026"}
        )
        if not success:
            self.log("Login failed - cannot proceed with tests", "FAIL")
            return self.print_summary()

        # Check for token in response (might be access_token or token)
        self.token = resp.get("access_token") or resp.get("token") or (resp.get("data", {}) or {}).get("token")
        if not self.token:
            self.log(f"No token received - response: {resp}", "FAIL")
            return self.print_summary()
        self.log(f"Token received: {self.token[:20]}...", "INFO")

        # 2. Verify seeded paid PPh record with NTPN + GL journals
        self.log("\n[2] Verifying Seeded Paid PPh Record", "INFO")
        success, resp = self.test(
            "GET /api/tax/records?status=paid",
            "GET", "tax/records", 200,
            data={"status": "paid"}
        )
        paid_records = resp.get("data", [])
        if not paid_records:
            self.log("No paid tax records found - seed may have failed", "WARN")
        else:
            seeded = paid_records[0]
            self.log(f"Found paid record: {seeded.get('type')} - {seeded.get('amount')}", "INFO")
            if seeded.get("ntpn"):
                self.log(f"NTPN: {seeded.get('ntpn')}", "PASS")
                self.tests_passed += 1
            else:
                self.failed_tests.append("Seeded record missing NTPN")
                self.log("Seeded record missing NTPN", "FAIL")
            
            if seeded.get("gl_accrual_entry_no"):
                self.log(f"GL Accrual Entry: {seeded.get('gl_accrual_entry_no')}", "PASS")
                self.tests_passed += 1
            else:
                self.failed_tests.append("Seeded record missing gl_accrual_entry_no")
                self.log("Seeded record missing gl_accrual_entry_no", "FAIL")
            
            if seeded.get("gl_setor_entry_no"):
                self.log(f"GL Setor Entry: {seeded.get('gl_setor_entry_no')}", "PASS")
                self.tests_passed += 1
            else:
                self.failed_tests.append("Seeded record missing gl_setor_entry_no")
                self.log("Seeded record missing gl_setor_entry_no", "FAIL")

        # 3. Verify GL journals exist
        self.log("\n[3] Verifying GL Journals", "INFO")
        success, resp = self.test(
            "GET /api/gl/journals?source_type=tax_accrual",
            "GET", "gl/journals", 200,
            data={"source_type": "tax_accrual"}
        )
        accrual_journals = resp.get("data", [])
        if accrual_journals:
            self.log(f"Found {len(accrual_journals)} tax_accrual journal(s)", "PASS")
            self.tests_passed += 1
        else:
            self.failed_tests.append("No tax_accrual journals found")
            self.log("No tax_accrual journals found", "FAIL")

        success, resp = self.test(
            "GET /api/gl/journals?source_type=tax_setor",
            "GET", "gl/journals", 200,
            data={"source_type": "tax_setor"}
        )
        setor_journals = resp.get("data", [])
        if setor_journals:
            self.log(f"Found {len(setor_journals)} tax_setor journal(s)", "PASS")
            self.tests_passed += 1
            # Check if NTPN is in memo
            first_setor = setor_journals[0]
            if "NTPN" in first_setor.get("memo", ""):
                self.log(f"Setor journal memo contains NTPN: {first_setor.get('memo')}", "PASS")
                self.tests_passed += 1
            else:
                self.failed_tests.append("Setor journal memo missing NTPN")
                self.log("Setor journal memo missing NTPN", "FAIL")
        else:
            self.failed_tests.append("No tax_setor journals found")
            self.log("No tax_setor journals found", "FAIL")

        # 4. Test status transition: pending → reported (accrual journal)
        self.log("\n[4] Testing Status Transition: pending → reported", "INFO")
        success, resp = self.test(
            "GET /api/tax/records (all)",
            "GET", "tax/records", 200,
            data={"limit": 200}
        )
        all_records = resp.get("data", [])
        pending_records = [r for r in all_records if r.get("status") == "pending"]
        
        if not pending_records:
            self.log("No pending records found - cannot test transition", "WARN")
        else:
            test_record = pending_records[0]
            self.log(f"Testing with record: {test_record.get('id')} ({test_record.get('type')})", "INFO")
            
            success, resp = self.test(
                "PUT /api/tax/records/{id} status='reported'",
                "PUT", f"tax/records/{test_record['id']}", 200,
                data={"status": "reported", "report_date": datetime.now().strftime("%Y-%m-%d")}
            )
            if success:
                updated = resp.get("data", {})
                if updated.get("gl_accrual_entry_no"):
                    self.log(f"Accrual journal created: {updated.get('gl_accrual_entry_no')}", "PASS")
                    self.tests_passed += 1
                else:
                    self.failed_tests.append("Status 'reported' did not create gl_accrual_entry_no")
                    self.log("Status 'reported' did not create gl_accrual_entry_no", "FAIL")
                
                if updated.get("gl_setor_entry_no") is None:
                    self.log("gl_setor_entry_no is null (correct for 'reported')", "PASS")
                    self.tests_passed += 1
                else:
                    self.failed_tests.append("Status 'reported' should not have gl_setor_entry_no")
                    self.log("Status 'reported' should not have gl_setor_entry_no", "FAIL")

                # 5. Test status transition: reported → paid (setoran journal with NTPN)
                self.log("\n[5] Testing Status Transition: reported → paid (with NTPN)", "INFO")
                test_ntpn = f"TEST{datetime.now().strftime('%Y%m%d%H%M%S')}"
                success, resp = self.test(
                    "PUT /api/tax/records/{id} status='paid' with NTPN",
                    "PUT", f"tax/records/{test_record['id']}", 200,
                    data={"status": "paid", "ntpn": test_ntpn, "paid_date": datetime.now().strftime("%Y-%m-%d")}
                )
                if success:
                    updated = resp.get("data", {})
                    if updated.get("gl_setor_entry_no"):
                        self.log(f"Setoran journal created: {updated.get('gl_setor_entry_no')}", "PASS")
                        self.tests_passed += 1
                    else:
                        self.failed_tests.append("Status 'paid' did not create gl_setor_entry_no")
                        self.log("Status 'paid' did not create gl_setor_entry_no", "FAIL")

                    # 6. Test idempotency - PUT same record to 'paid' again
                    self.log("\n[6] Testing Idempotency (duplicate PUT to 'paid')", "INFO")
                    # Count current setor journals
                    success, resp = self.test(
                        "GET /api/gl/journals?source_type=tax_setor (before duplicate)",
                        "GET", "gl/journals", 200,
                        data={"source_type": "tax_setor"}
                    )
                    count_before = len(resp.get("data", []))
                    
                    # Try to update again
                    success, resp = self.test(
                        "PUT /api/tax/records/{id} status='paid' (duplicate)",
                        "PUT", f"tax/records/{test_record['id']}", 200,
                        data={"status": "paid", "ntpn": test_ntpn, "paid_date": datetime.now().strftime("%Y-%m-%d")}
                    )
                    
                    # Count after
                    success, resp = self.test(
                        "GET /api/gl/journals?source_type=tax_setor (after duplicate)",
                        "GET", "gl/journals", 200,
                        data={"source_type": "tax_setor"}
                    )
                    count_after = len(resp.get("data", []))
                    
                    if count_before == count_after:
                        self.log(f"Idempotency verified: journal count unchanged ({count_before})", "PASS")
                        self.tests_passed += 1
                    else:
                        self.failed_tests.append(f"Idempotency failed: journal count increased from {count_before} to {count_after}")
                        self.log(f"Idempotency failed: journal count increased from {count_before} to {count_after}", "FAIL")

        # 7. Test NTPN validation (400 error when missing)
        self.log("\n[7] Testing NTPN Validation (400 error when missing)", "INFO")
        pending_for_ntpn_test = [r for r in all_records if r.get("status") == "pending"]
        if len(pending_for_ntpn_test) > 1:
            test_record_ntpn = pending_for_ntpn_test[1]
            success, resp = self.test(
                "PUT /api/tax/records/{id} status='paid' WITHOUT NTPN",
                "PUT", f"tax/records/{test_record_ntpn['id']}", 400,
                data={"status": "paid", "paid_date": datetime.now().strftime("%Y-%m-%d")}
            )
            if success:
                self.log("NTPN validation working: 400 error returned", "PASS")
            else:
                self.log("NTPN validation may not be working correctly", "WARN")
        else:
            self.log("Not enough pending records to test NTPN validation", "WARN")

        # 8. Verify trial balance is balanced
        self.log("\n[8] Verifying Trial Balance", "INFO")
        success, resp = self.test(
            "GET /api/gl/trial-balance",
            "GET", "gl/trial-balance", 200
        )
        if success:
            tb = resp.get("data", {})
            if tb.get("balanced"):
                self.log(f"Trial balance is BALANCED ✓", "PASS")
                self.log(f"Total Debit: Rp {tb.get('total_debit', 0):,}", "INFO")
                self.log(f"Total Credit: Rp {tb.get('total_credit', 0):,}", "INFO")
                self.tests_passed += 1
            else:
                self.failed_tests.append(f"Trial balance NOT balanced: debit={tb.get('total_debit')}, credit={tb.get('total_credit')}")
                self.log(f"Trial balance NOT balanced: debit={tb.get('total_debit')}, credit={tb.get('total_credit')}", "FAIL")

        # 9. Check GL accounts exist (2-1300, 6-1400)
        self.log("\n[9] Verifying GL Accounts", "INFO")
        success, resp = self.test(
            "GET /api/gl/accounts",
            "GET", "gl/accounts", 200
        )
        if success:
            accounts = resp.get("data", [])
            account_codes = [a.get("code") for a in accounts]
            
            if "2-1300" in account_codes:
                utang_pajak = next(a for a in accounts if a.get("code") == "2-1300")
                self.log(f"Account 2-1300 exists: {utang_pajak.get('name')} ({utang_pajak.get('type')})", "PASS")
                self.tests_passed += 1
            else:
                self.failed_tests.append("Account 2-1300 (Utang Pajak) not found")
                self.log("Account 2-1300 (Utang Pajak) not found", "FAIL")
            
            if "6-1400" in account_codes:
                beban_pajak = next(a for a in accounts if a.get("code") == "6-1400")
                self.log(f"Account 6-1400 exists: {beban_pajak.get('name')} ({beban_pajak.get('type')})", "PASS")
                self.tests_passed += 1
            else:
                self.failed_tests.append("Account 6-1400 (Beban Pajak) not found")
                self.log("Account 6-1400 (Beban Pajak) not found", "FAIL")

        # 10. Regression tests
        self.log("\n[10] Regression Tests", "INFO")
        self.test("GET /api/tax/summary", "GET", "tax/summary", 200)
        self.test("GET /api/tax/faktur", "GET", "tax/faktur", 200)
        self.test("GET /api/gl/journals", "GET", "gl/journals", 200)
        self.test("GET /api/gl/balance-sheet", "GET", "gl/balance-sheet", 200)

        # Test login with other roles
        self.log("\n[11] Testing Login with Other Roles", "INFO")
        success, resp = self.test(
            "Login as owner@sipro.co.id",
            "POST", "auth/login", 200,
            data={"email": "owner@sipro.co.id", "password": "Sipro#2026"}
        )

        return self.print_summary()

    def print_summary(self):
        """Print test summary and return exit code."""
        self.log("\n" + "=" * 60, "INFO")
        self.log("TEST SUMMARY", "INFO")
        self.log("=" * 60, "INFO")
        self.log(f"Total Tests: {self.tests_run}", "INFO")
        self.log(f"Passed: {self.tests_passed}", "PASS")
        self.log(f"Failed: {len(self.failed_tests)}", "FAIL" if self.failed_tests else "INFO")
        
        if self.failed_tests:
            self.log("\nFailed Tests:", "FAIL")
            for i, failure in enumerate(self.failed_tests, 1):
                self.log(f"{i}. {failure}", "FAIL")
        
        success_rate = (self.tests_passed / self.tests_run * 100) if self.tests_run > 0 else 0
        self.log(f"\nSuccess Rate: {success_rate:.1f}%", "PASS" if success_rate >= 80 else "FAIL")
        
        return 0 if success_rate >= 80 else 1


def main():
    tester = Phase19Tester()
    return tester.run_all_tests()


if __name__ == "__main__":
    sys.exit(main())

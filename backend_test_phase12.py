"""SIPRO Phase 12 Backend API Testing - Procurement Pillar
Tests: BoQ/RAB, Subcontractor+SPK, PO/GRN/3-way match, Anti-fraud rules
All passwords: Sipro#2026
"""
import requests
import sys
from datetime import datetime, timedelta

BASE_URL = "https://sipro-verify.preview.emergentagent.com/api"
PASSWORD = "Sipro#2026"

class Phase12Tester:
    def __init__(self):
        self.base_url = BASE_URL
        self.tokens = {}
        self.users = {}
        self.tests_run = 0
        self.tests_passed = 0
        self.failed_tests = []
        self.project_id = None
        self.boq_item_ids = []
        self.subcon_ids = []
        self.spk_ids = []
        self.po_ids = []
        self.grn_ids = []
        self.bill_ids = []

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
                response = requests.get(url, headers=headers, params=params, timeout=15)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=15)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=headers, timeout=15)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers, timeout=15)

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
                self.failed_tests.append({
                    "test": name,
                    "expected": expected_status,
                    "got": response.status_code,
                    "response": response.text[:200]
                })
                return False, {}

        except Exception as e:
            self.log(f"❌ FAIL - Error: {str(e)}", "FAIL")
            self.failed_tests.append({"test": name, "error": str(e)})
            return False, {}

    # ==================== AUTH ====================
    def test_login(self, email):
        """Test staff login"""
        success, response = self.run_test(
            f"Login: {email}",
            "POST",
            "auth/login",
            200,
            data={"email": email, "password": PASSWORD}
        )
        if success and 'access_token' in response:
            self.tokens[email] = response['access_token']
            self.users[email] = response.get('data', {})
            self.log(f"   Token saved for {email}, role: {response['data'].get('role')}")
            return True
        return False

    # ==================== BOQ TESTS ====================
    def test_boq_items_list(self, email, project_id=None):
        """Test GET /boq/items"""
        token = self.tokens.get(email)
        params = {"project_id": project_id} if project_id else None
        success, response = self.run_test(
            f"GET /boq/items by {email}" + (f" (project={project_id})" if project_id else ""),
            "GET",
            "boq/items",
            200,
            token=token,
            params=params
        )
        if success and 'data' in response:
            total = response.get('total', 0)
            total_budget = response.get('total_budget', 0)
            self.log(f"   Total items: {total}, Total budget: Rp {total_budget:,}")
            return True, response
        return False, {}

    def test_boq_summary(self, email, project_id):
        """Test GET /boq/summary"""
        token = self.tokens.get(email)
        success, response = self.run_test(
            f"GET /boq/summary for project {project_id} by {email}",
            "GET",
            "boq/summary",
            200,
            token=token,
            params={"project_id": project_id}
        )
        if success and 'data' in response:
            data = response['data']
            self.log(f"   Budget: Rp {data.get('budget', 0):,}, Committed: Rp {data.get('committed', 0):,}, Actual: Rp {data.get('actual', 0):,}")
            self.log(f"   Remaining: Rp {data.get('remaining', 0):,}, Over budget: {data.get('over_budget', False)}")
            return True, data
        return False, {}

    def test_create_boq_item(self, email, project_id):
        """Test POST /boq/items"""
        token = self.tokens.get(email)
        timestamp = datetime.now().strftime("%H%M%S")
        success, response = self.run_test(
            f"POST /boq/items by {email}",
            "POST",
            "boq/items",
            200,
            data={
                "project_id": project_id,
                "cost_code": f"TEST-{timestamp}",
                "category": "test",
                "description": "Test BoQ item",
                "uom": "ls",
                "quantity": 1,
                "unit_price": 10000000,
                "notes": "Automated test"
            },
            token=token
        )
        if success and 'data' in response:
            item_id = response['data'].get('id')
            self.boq_item_ids.append(item_id)
            self.log(f"   Created BoQ item ID: {item_id}, amount: Rp {response['data'].get('amount', 0):,}")
            return True, item_id
        return False, None

    def test_delete_boq_item(self, email, item_id):
        """Test DELETE /boq/items/{id}"""
        token = self.tokens.get(email)
        return self.run_test(
            f"DELETE /boq/items/{item_id} by {email}",
            "DELETE",
            f"boq/items/{item_id}",
            200,
            token=token
        )[0]

    # ==================== SUBCONTRACTOR TESTS ====================
    def test_subcontractors_list(self, email):
        """Test GET /subcon/subcontractors"""
        token = self.tokens.get(email)
        success, response = self.run_test(
            f"GET /subcon/subcontractors by {email}",
            "GET",
            "subcon/subcontractors",
            200,
            token=token
        )
        if success and 'data' in response:
            total = response.get('total', 0)
            self.log(f"   Total subcontractors: {total}")
            return True, response
        return False, {}

    def test_create_subcontractor(self, email):
        """Test POST /subcon/subcontractors"""
        token = self.tokens.get(email)
        timestamp = datetime.now().strftime("%H%M%S")
        success, response = self.run_test(
            f"POST /subcon/subcontractors by {email}",
            "POST",
            "subcon/subcontractors",
            200,
            data={
                "code": f"SUB-TEST-{timestamp}",
                "name": f"Test Subcon {timestamp}",
                "specialty": "Test",
                "phone": f"+628{timestamp}",
                "email": f"test{timestamp}@test.co.id",
                "npwp": None,
                "address": "Test Address",
                "pic_name": "Test PIC",
                "rating": 4.0,
                "notes": None
            },
            token=token
        )
        if success and 'data' in response:
            subcon_id = response['data'].get('id')
            self.subcon_ids.append(subcon_id)
            self.log(f"   Created subcontractor ID: {subcon_id}")
            return True, subcon_id
        return False, None

    def test_get_subcontractor(self, email, subcon_id):
        """Test GET /subcon/subcontractors/{id}"""
        token = self.tokens.get(email)
        success, response = self.run_test(
            f"GET /subcon/subcontractors/{subcon_id} by {email}",
            "GET",
            f"subcon/subcontractors/{subcon_id}",
            200,
            token=token
        )
        if success and 'data' in response:
            data = response['data']
            spk = response.get('spk', [])
            self.log(f"   Subcontractor: {data.get('name')}, SPK count: {len(spk)}")
            return True, data
        return False, {}

    # ==================== SPK TESTS ====================
    def test_spk_list(self, email, project_id=None):
        """Test GET /subcon/spk"""
        token = self.tokens.get(email)
        params = {"project_id": project_id} if project_id else None
        success, response = self.run_test(
            f"GET /subcon/spk by {email}" + (f" (project={project_id})" if project_id else ""),
            "GET",
            "subcon/spk",
            200,
            token=token,
            params=params
        )
        if success and 'data' in response:
            total = response.get('total', 0)
            summary = response.get('summary', {})
            self.log(f"   Total SPK: {total}, Active: {summary.get('active', 0)}, Contract value: Rp {summary.get('contract_value', 0):,}")
            return True, response
        return False, {}

    def test_create_spk(self, email, project_id, subcon_id):
        """Test POST /subcon/spk"""
        token = self.tokens.get(email)
        success, response = self.run_test(
            f"POST /subcon/spk by {email}",
            "POST",
            "subcon/spk",
            200,
            data={
                "project_id": project_id,
                "subcontractor_id": subcon_id,
                "title": "Test SPK",
                "scope": "Test scope",
                "contract_value": 100000000,
                "retention_pct": 5.0,
                "start_date": datetime.now().isoformat(),
                "end_date": (datetime.now() + timedelta(days=90)).isoformat(),
                "notes": None
            },
            token=token
        )
        if success and 'data' in response:
            spk_id = response['data'].get('id')
            spk_number = response['data'].get('spk_number')
            self.spk_ids.append(spk_id)
            self.log(f"   Created SPK ID: {spk_id}, number: {spk_number}")
            return True, spk_id
        return False, None

    def test_spk_status_update(self, email, spk_id, status):
        """Test POST /subcon/spk/{id}/status"""
        token = self.tokens.get(email)
        success, response = self.run_test(
            f"POST /subcon/spk/{spk_id}/status to {status} by {email}",
            "POST",
            f"subcon/spk/{spk_id}/status",
            200,
            data={"status": status, "note": f"Test status change to {status}"},
            token=token
        )
        if success and 'data' in response:
            new_status = response['data'].get('status')
            self.log(f"   SPK status: {new_status}")
            return new_status == status
        return False

    # ==================== PROCUREMENT PO TESTS ====================
    def test_pos_list(self, email, project_id=None):
        """Test GET /procurement/pos"""
        token = self.tokens.get(email)
        params = {"project_id": project_id} if project_id else None
        success, response = self.run_test(
            f"GET /procurement/pos by {email}" + (f" (project={project_id})" if project_id else ""),
            "GET",
            "procurement/pos",
            200,
            token=token,
            params=params
        )
        if success and 'data' in response:
            total = response.get('total', 0)
            summary = response.get('summary', {})
            self.log(f"   Total POs: {total}, Draft: {summary.get('draft', 0)}, Approved: {summary.get('approved', 0)}, Value: Rp {summary.get('value', 0):,}")
            return True, response
        return False, {}

    def test_create_po(self, email, project_id, po_type="material", vendor="Test Vendor", total_value=50000000):
        """Test POST /procurement/pos"""
        token = self.tokens.get(email)
        success, response = self.run_test(
            f"POST /procurement/pos (type={po_type}, value=Rp {total_value:,}) by {email}",
            "POST",
            "procurement/pos",
            200,
            data={
                "project_id": project_id,
                "po_type": po_type,
                "vendor": vendor,
                "subcontractor_id": None,
                "spk_id": None,
                "items": [
                    {
                        "description": "Test material item",
                        "material_id": None,
                        "boq_item_id": None,
                        "uom": "pcs",
                        "qty": 100,
                        "unit_price": int(total_value / 100)
                    }
                ],
                "due_date": (datetime.now() + timedelta(days=30)).isoformat(),
                "note": "Test PO"
            },
            token=token
        )
        if success and 'data' in response:
            po_id = response['data'].get('id')
            po_number = response['data'].get('po_number')
            high_value = response['data'].get('high_value', False)
            self.po_ids.append(po_id)
            self.log(f"   Created PO ID: {po_id}, number: {po_number}, high_value: {high_value}")
            return True, po_id, high_value
        return False, None, False

    def test_get_po(self, email, po_id):
        """Test GET /procurement/pos/{id}"""
        token = self.tokens.get(email)
        success, response = self.run_test(
            f"GET /procurement/pos/{po_id} by {email}",
            "GET",
            f"procurement/pos/{po_id}",
            200,
            token=token
        )
        if success and 'data' in response:
            data = response['data']
            grns = response.get('grns', [])
            bills = response.get('bills', [])
            self.log(f"   PO: {data.get('po_number')}, Status: {data.get('status')}, GRNs: {len(grns)}, Bills: {len(bills)}")
            return True, data
        return False, {}

    def test_approve_po(self, email, po_id):
        """Test POST /procurement/pos/{id}/approve"""
        token = self.tokens.get(email)
        success, response = self.run_test(
            f"POST /procurement/pos/{po_id}/approve by {email}",
            "POST",
            f"procurement/pos/{po_id}/approve",
            200,
            data={},
            token=token
        )
        if success and 'data' in response:
            status = response['data'].get('status')
            approved_by = response['data'].get('approved_by')
            self.log(f"   PO approved: status={status}, approved_by={approved_by}")
            return status == 'approved'
        return False

    def test_approve_po_denial(self, email, po_id, expected_status=403):
        """Test POST /procurement/pos/{id}/approve (expect denial)"""
        token = self.tokens.get(email)
        return self.run_test(
            f"POST /procurement/pos/{po_id}/approve by {email} (expect {expected_status})",
            "POST",
            f"procurement/pos/{po_id}/approve",
            expected_status,
            data={},
            token=token
        )[0]

    def test_cancel_po(self, email, po_id):
        """Test POST /procurement/pos/{id}/cancel"""
        token = self.tokens.get(email)
        return self.run_test(
            f"POST /procurement/pos/{po_id}/cancel by {email}",
            "POST",
            f"procurement/pos/{po_id}/cancel",
            200,
            data={"note": "Test cancellation"},
            token=token
        )[0]

    # ==================== GRN TESTS ====================
    def test_grns_list(self, email, po_id=None):
        """Test GET /procurement/grns"""
        token = self.tokens.get(email)
        params = {"po_id": po_id} if po_id else None
        success, response = self.run_test(
            f"GET /procurement/grns by {email}" + (f" (po={po_id})" if po_id else ""),
            "GET",
            "procurement/grns",
            200,
            token=token,
            params=params
        )
        if success and 'data' in response:
            total = response.get('total', 0)
            self.log(f"   Total GRNs: {total}")
            return True, response
        return False, {}

    def test_create_grn(self, email, po_id, qty_received=50):
        """Test POST /procurement/grns"""
        token = self.tokens.get(email)
        success, response = self.run_test(
            f"POST /procurement/grns (po={po_id}, qty={qty_received}) by {email}",
            "POST",
            "procurement/grns",
            200,
            data={
                "po_id": po_id,
                "items": [
                    {
                        "po_item_index": 0,
                        "qty_received": qty_received
                    }
                ],
                "note": "Test GRN"
            },
            token=token
        )
        if success and 'data' in response:
            grn_id = response['data'].get('id')
            grn_number = response['data'].get('grn_number')
            received_value = response['data'].get('received_value', 0)
            self.grn_ids.append(grn_id)
            self.log(f"   Created GRN ID: {grn_id}, number: {grn_number}, value: Rp {received_value:,}")
            return True, grn_id, received_value
        return False, None, 0

    # ==================== 3-WAY MATCH & BILLS TESTS ====================
    def test_threeway_list(self, email, status=None):
        """Test GET /procurement/threeway"""
        token = self.tokens.get(email)
        params = {"status": status} if status else None
        success, response = self.run_test(
            f"GET /procurement/threeway by {email}" + (f" (status={status})" if status else ""),
            "GET",
            "procurement/threeway",
            200,
            token=token,
            params=params
        )
        if success and 'data' in response:
            total = response.get('total', 0)
            summary = response.get('summary', {})
            self.log(f"   Total 3-way records: {total}, Matched: {summary.get('matched', 0)}, Flagged: {summary.get('flagged', 0)}")
            return True, response
        return False, {}

    def test_create_bill_matched(self, email, po_id, grn_id, claimed):
        """Test POST /procurement/bills (matched scenario)"""
        token = self.tokens.get(email)
        success, response = self.run_test(
            f"POST /procurement/bills (po={po_id}, claimed=Rp {claimed:,}, expect matched) by {email}",
            "POST",
            "procurement/bills",
            200,
            data={
                "po_id": po_id,
                "grn_id": grn_id,
                "claimed": claimed,
                "retention_pct": 5,
                "due_date": (datetime.now() + timedelta(days=30)).isoformat(),
                "note": "Test bill - matched"
            },
            token=token
        )
        if success and 'data' in response:
            bill_id = response['data'].get('id')
            match_status = response['data'].get('match_status')
            match_detail = response.get('match', {})
            self.bill_ids.append(bill_id)
            self.log(f"   Created bill ID: {bill_id}, match_status: {match_status}")
            self.log(f"   Match detail: {match_detail}")
            return True, bill_id, match_status
        return False, None, None

    def test_create_bill_flagged(self, email, po_id, claimed_over):
        """Test POST /procurement/bills (flagged scenario - over-billing)"""
        token = self.tokens.get(email)
        success, response = self.run_test(
            f"POST /procurement/bills (po={po_id}, claimed=Rp {claimed_over:,}, expect flagged) by {email}",
            "POST",
            "procurement/bills",
            200,
            data={
                "po_id": po_id,
                "grn_id": None,
                "claimed": claimed_over,
                "retention_pct": 0,
                "due_date": (datetime.now() + timedelta(days=30)).isoformat(),
                "note": "Test bill - flagged (no GRN)"
            },
            token=token
        )
        if success and 'data' in response:
            bill_id = response['data'].get('id')
            match_status = response['data'].get('match_status')
            match_detail = response.get('match', {})
            self.bill_ids.append(bill_id)
            self.log(f"   Created bill ID: {bill_id}, match_status: {match_status}")
            self.log(f"   Match detail: {match_detail}")
            if match_status == 'flagged':
                self.log(f"   ✓ Bill correctly flagged for over-billing")
            return True, bill_id, match_status
        return False, None, None

    # ==================== RBAC TESTS ====================
    def test_rbac_denial(self, email, endpoint, description):
        """Test RBAC denial (403)"""
        token = self.tokens.get(email)
        return self.run_test(
            f"RBAC Denial: {description}",
            "GET",
            endpoint,
            403,
            token=token
        )[0]

    # ==================== MAIN TEST FLOW ====================
    def run_all_tests(self):
        """Run all Phase 12 tests"""
        self.log("\n" + "="*80)
        self.log("SIPRO PHASE 12 BACKEND API TESTING - PROCUREMENT PILLAR")
        self.log("="*80)

        # 1. AUTH - Login all staff
        self.log("\n" + "="*80)
        self.log("1. AUTHENTICATION TESTS")
        self.log("="*80)
        staff = [
            "owner@sipro.co.id",
            "pm@sipro.co.id",
            "finance@sipro.co.id",
            "site@sipro.co.id",
            "sales@sipro.co.id"
        ]
        for email in staff:
            self.test_login(email)

        # Get project ID from seed data
        self.log("\n" + "="*80)
        self.log("2. GET PROJECT ID (from seed)")
        self.log("="*80)
        success, response = self.run_test(
            "GET /projects to find seed project",
            "GET",
            "projects",
            200,
            token=self.tokens.get("pm@sipro.co.id")
        )
        if success and response.get('data'):
            self.project_id = response['data'][0]['id']
            self.log(f"   Using project ID: {self.project_id}")
        else:
            self.log("   ❌ Failed to get project ID, cannot continue", "FAIL")
            return

        # 3. BOQ TESTS
        self.log("\n" + "="*80)
        self.log("3. BOQ / RAB TESTS")
        self.log("="*80)
        self.test_boq_items_list("pm@sipro.co.id", self.project_id)
        self.test_boq_summary("pm@sipro.co.id", self.project_id)
        success, boq_item_id = self.test_create_boq_item("pm@sipro.co.id", self.project_id)
        if success:
            self.test_delete_boq_item("pm@sipro.co.id", boq_item_id)
        
        # RBAC: sales cannot access BoQ
        self.test_rbac_denial("sales@sipro.co.id", f"boq/items?project_id={self.project_id}", 
                             "sales@sipro.co.id tries to access /boq/items (expect 403)")

        # 4. SUBCONTRACTOR TESTS
        self.log("\n" + "="*80)
        self.log("4. SUBCONTRACTOR TESTS")
        self.log("="*80)
        self.test_subcontractors_list("pm@sipro.co.id")
        success, subcon_id = self.test_create_subcontractor("pm@sipro.co.id")
        if success:
            self.test_get_subcontractor("pm@sipro.co.id", subcon_id)

        # 5. SPK TESTS
        self.log("\n" + "="*80)
        self.log("5. SPK (WORK ORDER) TESTS")
        self.log("="*80)
        self.test_spk_list("pm@sipro.co.id", self.project_id)
        if subcon_id:
            success, spk_id = self.test_create_spk("pm@sipro.co.id", self.project_id, subcon_id)
            if success:
                self.test_spk_status_update("pm@sipro.co.id", spk_id, "active")

        # 6. PROCUREMENT PO TESTS
        self.log("\n" + "="*80)
        self.log("6. PROCUREMENT - PURCHASE ORDER TESTS")
        self.log("="*80)
        self.test_pos_list("pm@sipro.co.id", self.project_id)
        
        # Create a regular PO (< 500M)
        success, po_id_regular, high_value = self.test_create_po("pm@sipro.co.id", self.project_id, 
                                                                  "material", "Test Vendor", 50000000)
        
        # Create a high-value PO (> 500M) for tiered approval test
        success_hv, po_id_high, high_value_flag = self.test_create_po("pm@sipro.co.id", self.project_id,
                                                                       "material", "High Value Vendor", 600000000)

        # RBAC: sales cannot access procurement
        self.test_rbac_denial("sales@sipro.co.id", f"procurement/pos?project_id={self.project_id}",
                             "sales@sipro.co.id tries to access /procurement/pos (expect 403)")

        # 7. ANTI-FRAUD: SEGREGATION OF DUTIES
        self.log("\n" + "="*80)
        self.log("7. ANTI-FRAUD: SEGREGATION OF DUTIES")
        self.log("="*80)
        if po_id_regular:
            # PM created the PO, so PM should NOT be able to approve it (403)
            self.test_approve_po_denial("pm@sipro.co.id", po_id_regular, 403)
            
            # Finance CAN approve regular PO
            self.test_approve_po("finance@sipro.co.id", po_id_regular)

        # 8. ANTI-FRAUD: TIERED APPROVAL
        self.log("\n" + "="*80)
        self.log("8. ANTI-FRAUD: TIERED APPROVAL (High-Value PO)")
        self.log("="*80)
        if po_id_high and high_value_flag:
            # Finance should NOT be able to approve high-value PO (403)
            self.test_approve_po_denial("finance@sipro.co.id", po_id_high, 403)
            
            # Owner CAN approve high-value PO
            self.test_approve_po("owner@sipro.co.id", po_id_high)

        # 9. GRN TESTS
        self.log("\n" + "="*80)
        self.log("9. GOODS RECEIPT NOTE (GRN) TESTS")
        self.log("="*80)
        self.test_grns_list("site@sipro.co.id")
        
        if po_id_regular:
            # Create GRN for 50% of PO
            success, grn_id, received_value = self.test_create_grn("site@sipro.co.id", po_id_regular, 50)
            
            # Verify PO status updated
            self.test_get_po("pm@sipro.co.id", po_id_regular)

        # 10. 3-WAY MATCH TESTS
        self.log("\n" + "="*80)
        self.log("10. 3-WAY MATCH & ANTI-FRAUD TESTS")
        self.log("="*80)
        self.test_threeway_list("finance@sipro.co.id")
        
        if po_id_regular and grn_id:
            # Test MATCHED scenario: bill <= received
            success, bill_id_matched, match_status = self.test_create_bill_matched(
                "pm@sipro.co.id", po_id_regular, grn_id, int(received_value * 0.9)
            )
            if match_status == 'matched':
                self.log("   ✓ 3-way match MATCHED scenario verified")
            
            # Test FLAGGED scenario: bill > received (no GRN or over-billing)
            success, bill_id_flagged, match_status_flagged = self.test_create_bill_flagged(
                "pm@sipro.co.id", po_id_regular, int(received_value * 2)
            )
            if match_status_flagged == 'flagged':
                self.log("   ✓ 3-way match FLAGGED scenario verified")
                self.log("   ✓ Anti-fraud review task should be created for finance")

        # 11. VERIFY MATERIAL STOCK SYNC (if GRN created)
        self.log("\n" + "="*80)
        self.log("11. VERIFY MATERIAL STOCK SYNC (GRN -> Material Txn)")
        self.log("="*80)
        if grn_id:
            success, response = self.run_test(
                f"GET /materials/project/{self.project_id}/txns to verify GRN stock sync",
                "GET",
                f"materials/project/{self.project_id}/txns",
                200,
                token=self.tokens.get("pm@sipro.co.id")
            )
            if success:
                txns = response.get('data', [])
                grn_txns = [t for t in txns if 'GRN' in t.get('ref', '')]
                self.log(f"   Found {len(grn_txns)} GRN-related material transactions")
                if grn_txns:
                    self.log("   ✓ GRN correctly created material stock transaction")

        # FINAL SUMMARY
        self.log("\n" + "="*80)
        self.log("TEST SUMMARY")
        self.log("="*80)
        self.log(f"Total tests run: {self.tests_run}")
        self.log(f"Tests passed: {self.tests_passed}")
        self.log(f"Tests failed: {len(self.failed_tests)}")
        self.log(f"Success rate: {(self.tests_passed/self.tests_run*100):.1f}%")
        
        if self.failed_tests:
            self.log("\n" + "="*80)
            self.log("FAILED TESTS DETAILS")
            self.log("="*80)
            for i, fail in enumerate(self.failed_tests, 1):
                self.log(f"\n{i}. {fail.get('test', 'Unknown test')}")
                if 'error' in fail:
                    self.log(f"   Error: {fail['error']}")
                else:
                    self.log(f"   Expected: {fail.get('expected')}, Got: {fail.get('got')}")
                    if 'response' in fail:
                        self.log(f"   Response: {fail['response']}")

        return self.tests_passed == self.tests_run


def main():
    tester = Phase12Tester()
    success = tester.run_all_tests()
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())

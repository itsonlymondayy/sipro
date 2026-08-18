"""SIPRO Backend API Testing - Phase 23 (EPIC 1.7 Omnichannel)

Tests:
1. Broadcast RBAC & endpoints (preview, create, list, get)
2. CAPI feedback loop (conversions, attribution)
3. Keyword-intent NBA (inbox/{conv_id}/nba)
4. Regression: core endpoints still work

All passwords: Sipro#2026
"""
import requests
import sys
from datetime import datetime

class Phase23Tester:
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
                response = requests.get(url, headers=headers, params=params, timeout=15)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=15)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=headers, timeout=15)

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

    def test_login(self, email, password="Sipro#2026"):
        """Test login and store token"""
        success, response = self.run_test(
            f"Login: {email}",
            "POST",
            "auth/login",
            200,
            data={"email": email, "password": password}
        )
        if success and 'access_token' in response:
            self.tokens[email] = response['access_token']
            self.log(f"   Token saved for {email}, role: {response.get('data', {}).get('role')}")
            return True
        return False

    # ==================== BROADCAST TESTS ====================
    def test_broadcast_preview(self, email):
        """Test POST /broadcasts/preview"""
        token = self.tokens.get(email)
        segment = {
            "lead_stages": ["nurturing"],
            "score_bands": [],
            "sources": ["meta_ads"],
            "campaigns": [],
            "include_customers": False
        }
        success, response = self.run_test(
            f"Broadcast Preview ({email})",
            "POST",
            "broadcasts/preview",
            200,
            data={"segment": segment},
            token=token
        )
        if success:
            data = response.get('data', {})
            self.log(f"   Preview: {data.get('total', 0)} recipients (lead: {data.get('by_kind', {}).get('lead', 0)}, customer: {data.get('by_kind', {}).get('customer', 0)})")
            return True, data
        return False, {}

    def test_broadcast_create(self, email):
        """Test POST /broadcasts (create & simulate send)"""
        token = self.tokens.get(email)
        segment = {
            "lead_stages": ["nurturing"],
            "score_bands": [],
            "sources": ["meta_ads"],
            "campaigns": [],
            "include_customers": False
        }
        success, response = self.run_test(
            f"Create Broadcast ({email})",
            "POST",
            "broadcasts",
            200,
            data={
                "name": f"Test Broadcast {datetime.now().strftime('%H%M%S')}",
                "template_code": "reengage",
                "segment": segment
            },
            token=token
        )
        if success:
            data = response.get('data', {})
            self.log(f"   Broadcast created: {data.get('id')}, sent to {data.get('total')} recipients")
            return True, data.get('id')
        return False, None

    def test_broadcast_list(self, email):
        """Test GET /broadcasts"""
        token = self.tokens.get(email)
        success, response = self.run_test(
            f"List Broadcasts ({email})",
            "GET",
            "broadcasts",
            200,
            token=token
        )
        if success:
            data = response.get('data', [])
            self.log(f"   Found {len(data)} broadcasts")
            return True, data
        return False, []

    def test_broadcast_get(self, email, broadcast_id):
        """Test GET /broadcasts/{id}"""
        token = self.tokens.get(email)
        success, response = self.run_test(
            f"Get Broadcast Detail ({email})",
            "GET",
            f"broadcasts/{broadcast_id}",
            200,
            token=token
        )
        if success:
            data = response.get('data', {})
            broadcast = data.get('broadcast', {})
            recipients = data.get('recipients', [])
            self.log(f"   Broadcast: {broadcast.get('name')}, {len(recipients)} recipients")
            return True, data
        return False, {}

    def test_broadcast_rbac_403(self, email):
        """Test that sales role gets 403 on broadcasts"""
        token = self.tokens.get(email)
        success, response = self.run_test(
            f"Broadcast RBAC 403 ({email})",
            "POST",
            "broadcasts/preview",
            403,
            data={"segment": {}},
            token=token
        )
        return success

    # ==================== CAPI FEEDBACK LOOP TESTS ====================
    def test_conversions_list(self, email):
        """Test GET /capture-events/conversions"""
        token = self.tokens.get(email)
        success, response = self.run_test(
            f"List CAPI Conversions ({email})",
            "GET",
            "capture-events/conversions",
            200,
            token=token
        )
        if success:
            data = response.get('data', [])
            by_event = response.get('by_event', {})
            self.log(f"   Found {len(data)} conversion events, by_event: {by_event}")
            # Check for seeded 'Lead' conversion for meta_ads
            meta_lead = [c for c in data if c.get('platform') == 'meta' and c.get('event_name') == 'Lead']
            if meta_lead:
                self.log(f"   ✓ Found seeded Meta Lead conversion")
            return True, data
        return False, []

    def test_attribution(self, email):
        """Test GET /capture-events/attribution"""
        token = self.tokens.get(email)
        success, response = self.run_test(
            f"Attribution Funnel ({email})",
            "GET",
            "capture-events/attribution",
            200,
            token=token
        )
        if success:
            data = response.get('data', {})
            rows = data.get('rows', [])
            totals = data.get('totals', {})
            self.log(f"   Attribution rows: {len(rows)}, totals: leads={totals.get('leads')}, conversions={totals.get('conversions')}")
            # Check that rows include conversions/conversion_value
            if rows:
                first = rows[0]
                if 'conversions' in first and 'conversion_value' in first:
                    self.log(f"   ✓ Rows include conversions & conversion_value")
                else:
                    self.log(f"   ⚠ Rows missing conversions/conversion_value fields", "WARN")
            return True, data
        return False, {}

    # ==================== KEYWORD-INTENT NBA TESTS ====================
    def test_inbox_nba(self, email, conv_id):
        """Test GET /inbox/{conv_id}/nba"""
        token = self.tokens.get(email)
        success, response = self.run_test(
            f"Inbox NBA ({email}, conv={conv_id})",
            "GET",
            f"inbox/{conv_id}/nba",
            200,
            token=token
        )
        if success:
            data = response.get('data', {})
            intents = data.get('intents', [])
            suggestions = data.get('suggestions', [])
            window_open = data.get('window_open', False)
            self.log(f"   Intents: {intents}, Suggestions: {len(suggestions)}, Window: {window_open}")
            return True, data
        return False, {}

    def test_inbox_list(self, email):
        """Test GET /inbox (to get conversation IDs)"""
        token = self.tokens.get(email)
        success, response = self.run_test(
            f"List Inbox Conversations ({email})",
            "GET",
            "inbox",
            200,
            token=token
        )
        if success:
            data = response.get('data', [])
            self.log(f"   Found {len(data)} conversations")
            return True, data
        return False, []

    # ==================== REGRESSION TESTS ====================
    def test_dashboard(self, email):
        """Test GET /dashboard"""
        token = self.tokens.get(email)
        success, response = self.run_test(
            f"Dashboard ({email})",
            "GET",
            "dashboard",
            200,
            token=token
        )
        return success

    def test_leads_list(self, email):
        """Test GET /leads"""
        token = self.tokens.get(email)
        success, response = self.run_test(
            f"List Leads ({email})",
            "GET",
            "leads",
            200,
            token=token
        )
        if success:
            data = response.get('data', [])
            self.log(f"   Found {len(data)} leads")
            return True, data
        return False, []

    def test_deals_list(self, email):
        """Test GET /deals"""
        token = self.tokens.get(email)
        success, response = self.run_test(
            f"List Deals ({email})",
            "GET",
            "deals",
            200,
            token=token
        )
        return success

    def test_customers_list(self, email):
        """Test GET /customers"""
        token = self.tokens.get(email)
        success, response = self.run_test(
            f"List Customers ({email})",
            "GET",
            "customers",
            200,
            token=token
        )
        return success

    def test_finance_ar(self, email):
        """Test GET /finance/ar"""
        token = self.tokens.get(email)
        success, response = self.run_test(
            f"Finance AR ({email})",
            "GET",
            "finance/ar",
            200,
            token=token
        )
        return success

    def test_automation_rules(self, email):
        """Test GET /automation-rules"""
        token = self.tokens.get(email)
        success, response = self.run_test(
            f"List Automation Rules ({email})",
            "GET",
            "automation-rules",
            200,
            token=token
        )
        if success:
            data = response.get('data', [])
            self.log(f"   Found {len(data)} automation rules")
            return True, data
        return False, []

    def test_wa_templates(self, email):
        """Test GET /wa-templates"""
        token = self.tokens.get(email)
        success, response = self.run_test(
            f"List WA Templates ({email})",
            "GET",
            "wa-templates",
            200,
            token=token
        )
        if success:
            data = response.get('data', [])
            self.log(f"   Found {len(data)} WA templates")
            return True, data
        return False, []

    def test_channels(self, email):
        """Test GET /channels"""
        token = self.tokens.get(email)
        success, response = self.run_test(
            f"List Channels ({email})",
            "GET",
            "channels",
            200,
            token=token
        )
        if success:
            data = response.get('data', [])
            self.log(f"   Found {len(data)} channels")
            return True, data
        return False, []

    def print_summary(self):
        """Print test summary"""
        print("\n" + "="*70)
        print("📊 TEST SUMMARY")
        print("="*70)
        print(f"Total Tests: {self.tests_run}")
        print(f"Passed: {self.tests_passed} ✅")
        print(f"Failed: {len(self.failed_tests)} ❌")
        print(f"Success Rate: {(self.tests_passed/self.tests_run*100) if self.tests_run else 0:.1f}%")
        
        if self.failed_tests:
            print("\n❌ FAILED TESTS:")
            for i, fail in enumerate(self.failed_tests, 1):
                print(f"\n{i}. {fail.get('test', 'Unknown')}")
                if 'error' in fail:
                    print(f"   Error: {fail['error']}")
                else:
                    print(f"   Expected: {fail.get('expected')}, Got: {fail.get('got')}")
                    if 'response' in fail:
                        print(f"   Response: {fail['response']}")
        
        print("\n" + "="*70)
        return len(self.failed_tests) == 0


def main():
    print("="*70)
    print("🚀 SIPRO Phase 23 Backend API Testing")
    print("   EPIC 1.7 Omnichannel: Broadcast, CAPI, NBA")
    print("="*70)
    
    tester = Phase23Tester()
    
    # Test users
    owner = "owner@sipro.co.id"
    manager = "manager@sipro.co.id"
    marketing = "marketing@sipro.co.id"
    sales = "sales@sipro.co.id"
    finance = "finance@sipro.co.id"
    
    print("\n" + "="*70)
    print("PHASE 1: AUTHENTICATION")
    print("="*70)
    
    # Login all users
    for email in [owner, manager, marketing, sales, finance]:
        if not tester.test_login(email):
            print(f"\n❌ CRITICAL: Login failed for {email}, stopping tests")
            return 1
    
    print("\n" + "="*70)
    print("PHASE 2: BROADCAST BACKEND (RBAC + CRUD)")
    print("="*70)
    
    # Test broadcast preview (manager)
    success, preview_data = tester.test_broadcast_preview(manager)
    
    # Test broadcast create (manager)
    success, broadcast_id = tester.test_broadcast_create(manager)
    
    # Test broadcast list (manager)
    success, broadcasts = tester.test_broadcast_list(manager)
    
    # Test broadcast get detail (use seeded broadcast or newly created)
    if broadcasts:
        # Use first broadcast (should be seeded 'Aktivasi Ulang Cluster Asri (Meta)')
        test_broadcast_id = broadcasts[0].get('id')
        tester.test_broadcast_get(manager, test_broadcast_id)
    elif broadcast_id:
        tester.test_broadcast_get(manager, broadcast_id)
    
    # Test RBAC: sales should get 403
    tester.test_broadcast_rbac_403(sales)
    
    # Test that marketing_admin also has access
    tester.test_broadcast_preview(marketing)
    
    # Test that owner bypasses RBAC
    tester.test_broadcast_preview(owner)
    
    print("\n" + "="*70)
    print("PHASE 3: CAPI FEEDBACK LOOP")
    print("="*70)
    
    # Test conversions list
    tester.test_conversions_list(manager)
    
    # Test attribution funnel
    tester.test_attribution(manager)
    
    print("\n" + "="*70)
    print("PHASE 4: KEYWORD-INTENT NBA")
    print("="*70)
    
    # Get inbox conversations first
    success, convs = tester.test_inbox_list(manager)
    
    if convs:
        # Test NBA on first conversation
        conv_id = convs[0].get('id')
        tester.test_inbox_nba(manager, conv_id)
    else:
        print("⚠ No conversations found, skipping NBA test")
    
    print("\n" + "="*70)
    print("PHASE 5: REGRESSION TESTS")
    print("="*70)
    
    # Test core endpoints still work
    tester.test_dashboard(owner)
    tester.test_leads_list(manager)
    tester.test_deals_list(manager)
    tester.test_customers_list(manager)
    tester.test_finance_ar(finance)
    
    # Test omnichannel endpoints still work
    tester.test_automation_rules(manager)
    tester.test_wa_templates(manager)
    tester.test_channels(manager)
    
    # Test inbox still works
    tester.test_inbox_list(sales)
    
    # Print summary
    all_passed = tester.print_summary()
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())

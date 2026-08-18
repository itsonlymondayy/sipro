"""
Test Fase 28c — Bukti Kerja Berpasangan (Sebelum → Sesudah)
Backend API testing for before-after repair evidence feature.
"""
import requests
import sys
import io
from PIL import Image, ImageDraw

BASE_URL = "https://sipro-frontend-lint.preview.emergentagent.com/api"
PASSWORD = "Sipro#2026"

class Phase28cTester:
    def __init__(self):
        self.tests_run = 0
        self.tests_passed = 0
        self.failed = []
        self.tokens = {}
        self.project_id = None
        self.unit_id = None
        self.punch_id = None
        self.file_ids = []
        
    def log(self, msg, level="INFO"):
        prefix = "✅" if level == "PASS" else "❌" if level == "FAIL" else "ℹ️"
        print(f"{prefix} {msg}")
    
    def test(self, name, method, endpoint, expected_status, data=None, token=None, files=None):
        """Run single API test"""
        url = f"{BASE_URL}/{endpoint}"
        headers = {}
        if token:
            headers['Authorization'] = f'Bearer {token}'
        if not files:
            headers['Content-Type'] = 'application/json'
        
        self.tests_run += 1
        self.log(f"\n[{self.tests_run}] {name}")
        
        try:
            if method == 'GET':
                r = requests.get(url, headers=headers, timeout=15)
            elif method == 'POST':
                if files:
                    r = requests.post(url, headers=headers, files=files, data=data, timeout=30)
                else:
                    r = requests.post(url, json=data, headers=headers, timeout=15)
            elif method == 'PUT':
                r = requests.put(url, json=data, headers=headers, timeout=15)
            
            success = r.status_code == expected_status
            if success:
                self.tests_passed += 1
                self.log(f"Status {r.status_code} ✓", "PASS")
                try:
                    return True, r.json()
                except Exception:
                    return True, {}
            else:
                self.log(f"Expected {expected_status}, got {r.status_code}: {r.text[:200]}", "FAIL")
                self.failed.append(name)
                return False, {}
        except Exception as e:
            self.log(f"Error: {str(e)}", "FAIL")
            self.failed.append(name)
            return False, {}
    
    def login(self, email):
        """Login and store token"""
        success, resp = self.test(f"Login {email}", "POST", "auth/login", 200,
                                   data={"email": email, "password": PASSWORD})
        if success and 'access_token' in resp:
            self.tokens[email] = resp['access_token']
            return True
        return False
    
    def make_photo(self, label):
        """Create test photo"""
        img = Image.new("RGB", (480, 300), (80, 120, 160))
        d = ImageDraw.Draw(img)
        d.rectangle([10, 10, 470, 290], outline=(255, 255, 255), width=2)
        d.text((30, 130), label, fill=(255, 255, 255))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return buf
    
    def run_all(self):
        """Run all tests"""
        print("\n" + "="*70)
        print("FASE 28c — BACKEND API TESTING: Bukti Kerja Berpasangan")
        print("="*70)
        
        # 1. Login as PM
        if not self.login("pm@sipro.co.id"):
            self.log("Login failed, cannot continue", "FAIL")
            return
        
        pm_token = self.tokens["pm@sipro.co.id"]
        
        # 2. Get project
        success, resp = self.test("Get projects", "GET", "projects", 200, token=pm_token)
        if not success or not resp.get('data'):
            self.log("No projects found", "FAIL")
            return
        self.project_id = resp['data'][0]['id']
        self.log(f"Using project: {self.project_id}")
        
        # 3. Get units via site-plan
        success, resp = self.test("Get site-plan with units", "GET", f"site-plan/{self.project_id}", 200, token=pm_token)
        if not success or not resp.get('data', {}).get('units'):
            self.log("No units found", "FAIL")
            return
        self.unit_id = resp['data']['units'][0]['id']
        self.log(f"Using unit: {self.unit_id}")
        
        # 4. Upload BEFORE photo (temuan)
        photo_before = self.make_photo("SEBELUM: Retak dinding")
        success, resp = self.test("Upload BEFORE photo", "POST", "files/upload", 200,
                                   token=pm_token,
                                   files={"file": ("before.png", photo_before, "image/png")},
                                   data={"owner_type": "punch_item", "owner_id": self.project_id})
        if not success or not resp.get('data', {}).get('id'):
            self.log("Failed to upload BEFORE photo", "FAIL")
            return
        file_id_before = resp['data']['id']
        self.file_ids.append(file_id_before)
        self.log(f"BEFORE photo uploaded: {file_id_before}")
        
        # 5. Create punch item with BEFORE photo
        success, resp = self.test("Create punch with BEFORE photo", "POST", "field/punchlist", 200,
                                   token=pm_token,
                                   data={
                                       "project_id": self.project_id,
                                       "unit_id": self.unit_id,
                                       "title": "Retak rambut dinding kamar utama",
                                       "description": "Retak horizontal sepanjang 30cm",
                                       "severity": "medium",
                                       "category": "finishing",
                                       "photos": [file_id_before]
                                   })
        if not success or not resp.get('data', {}).get('id'):
            self.log("Failed to create punch item", "FAIL")
            return
        self.punch_id = resp['data']['id']
        self.log(f"Punch item created: {self.punch_id}")
        
        # 6. Verify punch has BEFORE photo
        success, resp = self.test("Get punch detail", "GET", f"field/punchlist/{self.punch_id}", 200, token=pm_token)
        if success:
            photos = resp.get('data', {}).get('photos', [])
            if file_id_before in photos:
                self.log(f"✓ BEFORE photo present in punch: {photos}", "PASS")
                self.tests_passed += 1
            else:
                self.log(f"✗ BEFORE photo NOT found in punch photos: {photos}", "FAIL")
                self.failed.append("Verify BEFORE photo in punch")
        
        # 7. Upload AFTER photo (perbaikan)
        photo_after = self.make_photo("SESUDAH: Sudah diaci & dicat")
        success, resp = self.test("Upload AFTER photo", "POST", "files/upload", 200,
                                   token=pm_token,
                                   files={"file": ("after.png", photo_after, "image/png")},
                                   data={"owner_type": "punch_item", "owner_id": self.project_id})
        if not success or not resp.get('data', {}).get('id'):
            self.log("Failed to upload AFTER photo", "FAIL")
            return
        file_id_after = resp['data']['id']
        self.file_ids.append(file_id_after)
        self.log(f"AFTER photo uploaded: {file_id_after}")
        
        # 8. Update punch status with AFTER photo and note
        success, resp = self.test("Update punch status with AFTER photo", "POST",
                                   f"field/punchlist/{self.punch_id}/status", 200,
                                   token=pm_token,
                                   data={
                                       "status": "closed",
                                       "photos": [file_id_after],
                                       "note": "Sudah diaci dan dicat ulang"
                                   })
        if not success:
            self.log("Failed to update punch status", "FAIL")
            return
        
        # 9. Verify fix_photos and fix_note
        success, resp = self.test("Verify fix_photos & fix_note", "GET", f"field/punchlist/{self.punch_id}", 200, token=pm_token)
        if success:
            data = resp.get('data', {})
            fix_photos = data.get('fix_photos', [])
            fix_note = data.get('fix_note', '')
            
            if file_id_after in fix_photos:
                self.log(f"✓ AFTER photo in fix_photos: {fix_photos}", "PASS")
                self.tests_passed += 1
            else:
                self.log(f"✗ AFTER photo NOT in fix_photos: {fix_photos}", "FAIL")
                self.failed.append("Verify AFTER photo in fix_photos")
            
            if "diaci" in fix_note.lower():
                self.log(f"✓ fix_note present: {fix_note}", "PASS")
                self.tests_passed += 1
            else:
                self.log(f"✗ fix_note missing or incorrect: {fix_note}", "FAIL")
                self.failed.append("Verify fix_note")
        
        # 10. Get unit detail and check repairs array
        success, resp = self.test("Get unit detail with repairs", "GET",
                                   f"site-plan/{self.project_id}/unit/{self.unit_id}", 200, token=pm_token)
        if success:
            repairs = resp.get('data', {}).get('construction', {}).get('repairs', [])
            self.log(f"Found {len(repairs)} repair pairs")
            
            if len(repairs) > 0:
                self.log("✓ Repairs array present", "PASS")
                self.tests_passed += 1
                
                # Find our punch in repairs
                our_repair = None
                for r in repairs:
                    if r.get('punch_id') == self.punch_id:
                        our_repair = r
                        break
                
                if our_repair:
                    self.log(f"✓ Found our punch in repairs: {our_repair.get('title')}", "PASS")
                    self.tests_passed += 1
                    
                    # Check before photos
                    before = our_repair.get('before', [])
                    if len(before) > 0:
                        self.log(f"✓ BEFORE photos present: {len(before)}", "PASS")
                        self.tests_passed += 1
                    else:
                        self.log("✗ BEFORE photos missing", "FAIL")
                        self.failed.append("BEFORE photos in repairs")
                    
                    # Check after photos
                    after = our_repair.get('after', [])
                    if len(after) > 0:
                        self.log(f"✓ AFTER photos present: {len(after)}", "PASS")
                        self.tests_passed += 1
                    else:
                        self.log("✗ AFTER photos missing", "FAIL")
                        self.failed.append("AFTER photos in repairs")
                    
                    # Check resolved status
                    if our_repair.get('resolved') is True:
                        self.log("✓ Repair marked as resolved", "PASS")
                        self.tests_passed += 1
                    else:
                        self.log(f"✗ Repair NOT resolved: {our_repair.get('resolved')}", "FAIL")
                        self.failed.append("Repair resolved status")
                    
                    # Check note
                    if "diaci" in str(our_repair.get('note', '')).lower():
                        self.log(f"✓ Repair note present: {our_repair.get('note')}", "PASS")
                        self.tests_passed += 1
                    else:
                        self.log(f"✗ Repair note missing: {our_repair.get('note')}", "FAIL")
                        self.failed.append("Repair note")
                    
                    # Check dates
                    if our_repair.get('opened_at') and our_repair.get('fixed_at'):
                        self.log(f"✓ Dates present: opened={our_repair.get('opened_at')}, fixed={our_repair.get('fixed_at')}", "PASS")
                        self.tests_passed += 1
                    else:
                        self.log("✗ Dates missing", "FAIL")
                        self.failed.append("Repair dates")
                else:
                    self.log("✗ Our punch NOT found in repairs array", "FAIL")
                    self.failed.append("Find punch in repairs")
            else:
                self.log("✗ No repairs found", "FAIL")
                self.failed.append("Repairs array empty")
        
        # 11. Test portal endpoint
        self.log("\n--- Testing Portal Endpoint ---")
        
        # Login to portal
        success, resp = self.test("Portal: Request OTP", "POST", "portal/auth/request-otp", 200,
                                   data={"identifier": "+628121111111"})
        if success:
            success, resp = self.test("Portal: Verify OTP", "POST", "portal/auth/verify-otp", 200,
                                       data={"identifier": "+628121111111", "code": "000000"})
            if success and 'token' in resp:
                portal_token = resp['token']
                self.log(f"Portal login successful")
                
                # Get portal progress
                success, resp = self.test("Portal: Get progress with repairs", "GET", "portal/progress", 200,
                                           token=portal_token)
                if success:
                    data = resp.get('data', [])
                    if len(data) > 0:
                        repairs = data[0].get('repairs', [])
                        self.log(f"Portal: Found {len(repairs)} repair pairs")
                        
                        if len(repairs) > 0:
                            self.log("✓ Portal repairs present", "PASS")
                            self.tests_passed += 1
                            
                            # Check privacy - should NOT have internal IDs
                            r = repairs[0]
                            allowed_keys = {"punch_id", "title", "severity", "status", "resolved", 
                                          "note", "opened_at", "fixed_at", "before", "after"}
                            actual_keys = set(r.keys())
                            
                            if actual_keys <= allowed_keys:
                                self.log(f"✓ Portal privacy OK: only allowed keys present", "PASS")
                                self.tests_passed += 1
                            else:
                                extra = actual_keys - allowed_keys
                                self.log(f"✗ Portal privacy BREACH: extra keys {extra}", "FAIL")
                                self.failed.append("Portal privacy")
                        else:
                            self.log("✗ Portal repairs empty", "FAIL")
                            self.failed.append("Portal repairs")
                    else:
                        self.log("No portal data", "FAIL")
        
        # Print summary
        print("\n" + "="*70)
        print(f"RESULTS: {self.tests_passed}/{self.tests_run} tests passed")
        if self.failed:
            print(f"\nFailed tests ({len(self.failed)}):")
            for f in self.failed:
                print(f"  - {f}")
        print("="*70)
        
        return 0 if not self.failed else 1

if __name__ == "__main__":
    tester = Phase28cTester()
    sys.exit(tester.run_all())

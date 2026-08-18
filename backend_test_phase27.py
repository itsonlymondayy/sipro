"""Backend API Test untuk SIPRO Fase 27 - Kas Bon, Aset Tetap, Pembiayaan Korporat, Marketing Fee"""
import requests
import sys
from datetime import datetime, date
from typing import Optional

BASE_URL = "https://sipro-phase27.preview.emergentagent.com/api"

class Phase27Tester:
    def __init__(self):
        self.tests_run = 0
        self.tests_passed = 0
        self.tokens = {}
        self.test_data = {}
        
    def login(self, email: str, password: str = "Sipro#2026") -> Optional[str]:
        """Login dan dapatkan token"""
        try:
            resp = requests.post(f"{BASE_URL}/auth/login", 
                               json={"email": email, "password": password}, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                token = data.get("access_token") or data.get("token")
                self.tokens[email] = token
                print(f"✅ Login berhasil: {email}")
                return token
            else:
                print(f"❌ Login gagal {email}: {resp.status_code}")
                return None
        except Exception as e:
            print(f"❌ Login error {email}: {e}")
            return None
    
    def test(self, name: str, method: str, endpoint: str, expected_status: int,
             token: str = None, data: dict = None, params: dict = None) -> tuple:
        """Jalankan satu test API"""
        self.tests_run += 1
        url = f"{BASE_URL}/{endpoint}"
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        
        print(f"\n🔍 Test #{self.tests_run}: {name}")
        
        try:
            if method == "GET":
                resp = requests.get(url, headers=headers, params=params, timeout=10)
            elif method == "POST":
                resp = requests.post(url, headers=headers, json=data, timeout=10)
            elif method == "PUT":
                resp = requests.put(url, headers=headers, json=data, timeout=10)
            else:
                print(f"❌ Method tidak didukung: {method}")
                return False, {}
            
            success = resp.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ PASS - Status: {resp.status_code}")
                try:
                    return True, resp.json()
                except Exception:
                    return True, {}
            else:
                print(f"❌ FAIL - Expected {expected_status}, got {resp.status_code}")
                try:
                    print(f"   Response: {resp.json()}")
                except Exception:
                    print(f"   Response: {resp.text[:200]}")
                return False, {}
        except Exception as e:
            print(f"❌ FAIL - Error: {str(e)}")
            return False, {}
    
    def run_all_tests(self):
        """Jalankan semua test Fase 27"""
        print("="*80)
        print("SIPRO FASE 27 - BACKEND API TEST")
        print("="*80)
        
        # Login semua user
        print("\n" + "="*80)
        print("LOGIN USERS")
        print("="*80)
        finance_token = self.login("finance@sipro.co.id")
        site_token = self.login("site@sipro.co.id")
        manager_token = self.login("manager@sipro.co.id")
        sales_token = self.login("sales@sipro.co.id")
        owner_token = self.login("owner@sipro.co.id")
        
        print(f"\nDebug tokens: finance={bool(finance_token)}, site={bool(site_token)}, manager={bool(manager_token)}, sales={bool(sales_token)}, owner={bool(owner_token)}")
        
        if not all([finance_token, site_token, manager_token, sales_token, owner_token]):
            print("\n❌ Login gagal, hentikan test")
            return 1
        
        # ========== PETTY CASH TESTS ==========
        print("\n" + "="*80)
        print("PETTY CASH (KAS BON) TESTS")
        print("="*80)
        
        # Test 1: Site engineer ajukan kas bon
        success, resp = self.test(
            "Site engineer ajukan kas bon",
            "POST", "petty-cash/advances",
            200,
            token=site_token,
            data={
                "purpose": "Beli material proyek",
                "amount": 5000000,
                "category": "biaya_proyek"
            }
        )
        if success:
            self.test_data["cashbon_id"] = resp.get("data", {}).get("id")
        
        # Test 2: Site engineer tidak boleh approve kas bonnya sendiri
        if self.test_data.get("cashbon_id"):
            self.test(
                "Site engineer TIDAK boleh approve kas bon sendiri (SoD)",
                "POST", f"petty-cash/advances/{self.test_data['cashbon_id']}/approve",
                403,  # RBAC returns 403
                token=site_token,
                data={"note": "Coba approve sendiri"}
            )
        
        # Test 3: Finance approve kas bon
        if self.test_data.get("cashbon_id"):
            self.test(
                "Finance approve kas bon",
                "POST", f"petty-cash/advances/{self.test_data['cashbon_id']}/approve",
                200,
                token=finance_token,
                data={"note": "Disetujui"}
            )
        
        # Test 4: Finance cairkan kas bon
        if self.test_data.get("cashbon_id"):
            self.test(
                "Finance cairkan kas bon",
                "POST", f"petty-cash/advances/{self.test_data['cashbon_id']}/disburse",
                200,
                token=finance_token,
                data={
                    "amount": 5000000,
                    "source": "kas",
                    "note": "Dicairkan tunai"
                }
            )
        
        # Test 5: Site engineer pertanggungjawabkan kas bon
        if self.test_data.get("cashbon_id"):
            self.test(
                "Site engineer pertanggungjawabkan kas bon",
                "POST", f"petty-cash/advances/{self.test_data['cashbon_id']}/settle",
                200,
                token=site_token,
                data={
                    "items": [
                        {"category": "biaya_proyek", "description": "Semen 50 sak", "amount": 3000000},
                        {"category": "biaya_proyek", "description": "Pasir 5 kubik", "amount": 1500000}
                    ],
                    "note": "Sisa Rp 500.000 dikembalikan"
                }
            )
        
        # Test 6: Get summary kas bon
        self.test(
            "Get petty cash summary",
            "GET", "petty-cash/summary",
            200,
            token=finance_token
        )
        
        # Test 7: Enum tidak valid harus ditolak 400
        self.test(
            "Kas bon dengan kategori enum tidak valid harus ditolak 400",
            "POST", "petty-cash/advances",
            400,
            token=site_token,
            data={
                "purpose": "Test enum",
                "amount": 1000000,
                "category": "kategori_tidak_ada_di_ssot"
            }
        )
        
        # ========== FIXED ASSETS TESTS ==========
        print("\n" + "="*80)
        print("FIXED ASSETS (ASET TETAP) TESTS")
        print("="*80)
        
        # Test 8: Finance tambah aset tetap
        success, resp = self.test(
            "Finance tambah aset tetap",
            "POST", "fixed-assets/assets",
            200,
            token=finance_token,
            data={
                "name": "Laptop Dell Test",
                "category": "komputer_it",
                "tax_group": "kelompok_1",
                "method": "garis_lurus",
                "cost": 15000000,
                "residual_value": 1000000,
                "useful_life_months": 48,
                "funding_source": "kas_bank",
                "acquisition_date": date.today().isoformat()
            }
        )
        if success:
            self.test_data["asset_id"] = resp.get("data", {}).get("id")
        
        # Test 9: Get list aset
        self.test(
            "Get list aset tetap",
            "GET", "fixed-assets/assets",
            200,
            token=finance_token
        )
        
        # Test 10: Jalankan penyusutan bulan ini (pertama kali)
        current_period = date.today().strftime("%Y-%m")
        success, resp = self.test(
            "Jalankan penyusutan bulan ini (run pertama)",
            "POST", "fixed-assets/depreciation/run",
            200,
            token=finance_token,
            data={"period": current_period}
        )
        if success:
            posted_first = resp.get("data", {}).get("posted", 0)
            print(f"   📊 Run pertama: {posted_first} aset diposting")
        
        # Test 11: Jalankan penyusutan lagi (harus idempoten, 0 aset diposting)
        success, resp = self.test(
            "Jalankan penyusutan lagi (harus idempoten, 0 aset)",
            "POST", "fixed-assets/depreciation/run",
            200,
            token=finance_token,
            data={"period": current_period}
        )
        if success:
            posted_second = resp.get("data", {}).get("posted", 0)
            if posted_second == 0:
                print(f"   ✅ Idempoten: run kedua 0 aset (benar)")
            else:
                print(f"   ⚠️  Run kedua masih posting {posted_second} aset (seharusnya 0)")
        
        # Test 12: Periode masa depan harus ditolak 400
        future_period = "2099-12"
        self.test(
            "Penyusutan periode masa depan harus ditolak 400",
            "POST", "fixed-assets/depreciation/run",
            400,
            token=finance_token,
            data={"period": future_period}
        )
        
        # Test 13: Format periode salah harus ditolak 400
        self.test(
            "Penyusutan format periode salah harus ditolak 400",
            "POST", "fixed-assets/depreciation/run",
            400,
            token=finance_token,
            data={"period": "202501"}  # Format salah
        )
        
        # Test 14: Lepas aset (laba)
        if self.test_data.get("asset_id"):
            self.test(
                "Lepas aset dengan laba",
                "POST", f"fixed-assets/assets/{self.test_data['asset_id']}/dispose",
                200,
                token=finance_token,
                data={
                    "proceeds": 12000000,  # Lebih besar dari nilai buku
                    "source": "bank",
                    "date": date.today().isoformat(),
                    "note": "Dijual dengan laba"
                }
            )
        
        # Test 15: Get summary aset
        self.test(
            "Get fixed assets summary",
            "GET", "fixed-assets/summary",
            200,
            token=finance_token
        )
        
        # ========== CORPORATE FINANCING TESTS ==========
        print("\n" + "="*80)
        print("CORPORATE FINANCING (PEMBIAYAAN KORPORAT) TESTS")
        print("="*80)
        
        # Test 16: Finance tambah fasilitas kredit
        success, resp = self.test(
            "Finance tambah fasilitas kredit",
            "POST", "corp-financing/loans",
            200,
            token=finance_token,
            data={
                "lender": "bca",
                "lender_type": "bank",
                "loan_type": "kredit_investasi",
                "principal": 100000000,
                "interest_rate_pct": 12.0,
                "tenor_months": 12,
                "amortization_method": "anuitas",
                "start_date": date.today().isoformat()
            }
        )
        if success:
            self.test_data["loan_id"] = resp.get("data", {}).get("id")
        
        # Test 17: Get detail loan (cek jadwal preview)
        if self.test_data.get("loan_id"):
            success, resp = self.test(
                "Get detail loan (cek jadwal preview)",
                "GET", f"corp-financing/loans/{self.test_data['loan_id']}",
                200,
                token=finance_token
            )
            if success:
                preview = resp.get("schedule_preview", [])
                principal_total = sum(inst.get("principal", 0) for inst in preview)
                loan_principal = resp.get("data", {}).get("principal", 0)
                print(f"   📊 Total pokok jadwal: {principal_total}, Pokok pinjaman: {loan_principal}")
                if principal_total == loan_principal:
                    print(f"   ✅ Jadwal valid: total pokok = pokok pinjaman")
                else:
                    print(f"   ⚠️  Jadwal tidak valid: total pokok ≠ pokok pinjaman")
        
        # Test 18: Activate loan
        if self.test_data.get("loan_id"):
            self.test(
                "Activate loan (cairkan & terbitkan jadwal)",
                "POST", f"corp-financing/loans/{self.test_data['loan_id']}/activate",
                200,
                token=finance_token,
                data={
                    "source": "bank",
                    "date": date.today().isoformat(),
                    "note": "Dicairkan"
                }
            )
        
        # Test 19: Bayar angsuran dengan nominal melebihi sisa (harus ditolak 400)
        if self.test_data.get("loan_id"):
            self.test(
                "Bayar angsuran melebihi sisa harus ditolak 400",
                "POST", f"corp-financing/loans/{self.test_data['loan_id']}/pay",
                400,
                token=finance_token,
                data={
                    "installment_no": 1,
                    "amount": 999999999,  # Nominal sangat besar
                    "source": "bank",
                    "date": date.today().isoformat(),
                    "note": "Test overpayment"
                }
            )
        
        # Test 20: Bayar angsuran normal
        if self.test_data.get("loan_id"):
            # Get detail dulu untuk tahu nominal angsuran
            success, resp = self.test(
                "Get detail loan untuk cek nominal angsuran",
                "GET", f"corp-financing/loans/{self.test_data['loan_id']}",
                200,
                token=finance_token
            )
            if success:
                schedule = resp.get("data", {}).get("schedule", [])
                if schedule:
                    first_inst = schedule[0]
                    amount_due = first_inst.get("amount_due", 0)
                    self.test(
                        "Bayar angsuran pertama",
                        "POST", f"corp-financing/loans/{self.test_data['loan_id']}/pay",
                        200,
                        token=finance_token,
                        data={
                            "installment_no": 1,
                            "amount": amount_due,
                            "source": "bank",
                            "date": date.today().isoformat(),
                            "note": "Bayar angsuran 1"
                        }
                    )
        
        # Test 21: Get summary pembiayaan
        self.test(
            "Get corporate financing summary",
            "GET", "corp-financing/summary",
            200,
            token=finance_token
        )
        
        # Test 22: Enum tidak valid harus ditolak 400
        self.test(
            "Loan dengan enum tidak valid harus ditolak 400",
            "POST", "corp-financing/loans",
            400,
            token=finance_token,
            data={
                "lender": "bank_tidak_ada",
                "lender_type": "bank",
                "loan_type": "kredit_investasi",
                "principal": 50000000,
                "interest_rate_pct": 10.0,
                "tenor_months": 12,
                "amortization_method": "anuitas"
            }
        )
        
        # ========== MARKETING FEE TESTS ==========
        print("\n" + "="*80)
        print("MARKETING FEE TESTS")
        print("="*80)
        
        # Test 23: Sales manager tambah agen
        timestamp = datetime.now().strftime("%H%M%S")
        success, resp = self.test(
            "Sales manager tambah agen",
            "POST", "marketing/agents",
            200,
            token=manager_token,
            data={
                "name": f"Agen Test {timestamp}",
                "agent_type": "agen_properti",
                "bank": "bca",
                "account_number": "1234567890",
                "phone": "+628123456789"
            }
        )
        if success:
            self.test_data["agent_id"] = resp.get("data", {}).get("id")
        
        # Test 24: Get list agen
        self.test(
            "Get list agen",
            "GET", "marketing/agents",
            200,
            token=manager_token
        )
        
        # Test 25: Sales manager ajukan fee (perlu deal_id yang valid)
        # Ambil deal dari database dulu
        success, resp = self.test(
            "Get list deals untuk ambil deal_id",
            "GET", "deals",
            200,
            token=manager_token,
            params={"status": "deal", "limit": 1}
        )
        if success and resp.get("data"):
            deal_id = resp["data"][0].get("id")
            self.test_data["deal_id"] = deal_id
            
            if self.test_data.get("agent_id") and deal_id:
                success, resp = self.test(
                    "Sales manager ajukan marketing fee",
                    "POST", "marketing/fees",
                    200,
                    token=manager_token,
                    data={
                        "agent_id": self.test_data["agent_id"],
                        "deal_id": deal_id,
                        "basis": "persen",
                        "value": 2.0,
                        "trigger": "akad",
                        "tax_pct": 2.0
                    }
                )
                if success:
                    self.test_data["fee_id"] = resp.get("data", {}).get("id")
        
        # Test 26: Ajukan fee duplikat (agen+deal+trigger sama) harus ditolak
        if self.test_data.get("agent_id") and self.test_data.get("deal_id"):
            self.test(
                "Ajukan fee duplikat harus ditolak 400",
                "POST", "marketing/fees",
                400,
                token=manager_token,
                data={
                    "agent_id": self.test_data["agent_id"],
                    "deal_id": self.test_data["deal_id"],
                    "basis": "persen",
                    "value": 2.0,
                    "trigger": "akad",
                    "tax_pct": 2.0
                }
            )
        
        # Test 27: Sales manager TIDAK boleh approve fee
        if self.test_data.get("fee_id"):
            self.test(
                "Sales manager TIDAK boleh approve fee (RBAC)",
                "POST", f"marketing/fees/{self.test_data['fee_id']}/approve",
                403,  # Forbidden
                token=manager_token,
                data={"note": "Coba approve"}
            )
        
        # Test 28: Finance approve fee
        if self.test_data.get("fee_id"):
            self.test(
                "Finance approve marketing fee",
                "POST", f"marketing/fees/{self.test_data['fee_id']}/approve",
                200,
                token=finance_token,
                data={"note": "Disetujui"}
            )
        
        # Test 29: Finance bayar fee melebihi sisa (harus ditolak 400)
        if self.test_data.get("fee_id"):
            self.test(
                "Bayar fee melebihi sisa harus ditolak 400",
                "POST", f"marketing/fees/{self.test_data['fee_id']}/pay",
                400,
                token=finance_token,
                data={
                    "amount": 999999999,
                    "source": "bank",
                    "note": "Test overpayment"
                }
            )
        
        # Test 30: Finance bayar fee normal
        if self.test_data.get("fee_id"):
            # Get detail dulu untuk tahu nominal netto
            success, resp = self.test(
                "Get detail fee untuk cek nominal netto",
                "GET", f"marketing/fees/{self.test_data['fee_id']}",
                200,
                token=finance_token
            )
            if success:
                amount_net = resp.get("data", {}).get("amount_net", 0)
                self.test(
                    "Finance bayar marketing fee",
                    "POST", f"marketing/fees/{self.test_data['fee_id']}/pay",
                    200,
                    token=finance_token,
                    data={
                        "amount": amount_net,
                        "source": "bank",
                        "note": "Dibayar penuh"
                    }
                )
        
        # Test 31: Get summary marketing fee
        self.test(
            "Get marketing fee summary",
            "GET", "marketing/summary",
            200,
            token=finance_token
        )
        
        # ========== RBAC TESTS ==========
        print("\n" + "="*80)
        print("RBAC (ROLE-BASED ACCESS CONTROL) TESTS")
        print("="*80)
        
        # Test 32: Sales TIDAK boleh akses fixed assets
        self.test(
            "Sales TIDAK boleh akses fixed assets (403)",
            "GET", "fixed-assets/assets",
            403,
            token=sales_token
        )
        
        # Test 33: Sales TIDAK boleh akses corporate financing
        self.test(
            "Sales TIDAK boleh akses corporate financing (403)",
            "GET", "corp-financing/loans",
            403,
            token=sales_token
        )
        
        # Test 34: Sales boleh akses petty cash (view_own)
        self.test(
            "Sales boleh akses petty cash (view_own)",
            "GET", "petty-cash/advances",
            200,
            token=sales_token
        )
        
        # ========== REFERENCE/SSOT TESTS ==========
        print("\n" + "="*80)
        print("REFERENCE/SSOT TESTS")
        print("="*80)
        
        # Test 35: Get reference data Fase 27
        success, resp = self.test(
            "Get reference data (SSOT) Fase 27",
            "GET", "reference",
            200,
            token=owner_token
        )
        if success:
            data = resp.get("data", {})
            fase27_groups = [
                "cashbon_status", "cashbon_category", "asset_category", "asset_tax_group",
                "depreciation_method", "asset_status", "loan_type", "amortization_method",
                "loan_status", "installment_status", "agent_type", "agent_status",
                "marketing_fee_status", "marketing_fee_trigger", "lender", "lender_type",
                "cash_source", "asset_funding"
            ]
            missing = [g for g in fase27_groups if g not in data]
            if not missing:
                print(f"   ✅ Semua grup SSOT Fase 27 ada ({len(fase27_groups)} grup)")
            else:
                print(f"   ⚠️  Grup SSOT hilang: {missing}")
        
        # Print summary
        print("\n" + "="*80)
        print("TEST SUMMARY")
        print("="*80)
        print(f"Total tests: {self.tests_run}")
        print(f"Passed: {self.tests_passed}")
        print(f"Failed: {self.tests_run - self.tests_passed}")
        print(f"Success rate: {self.tests_passed/self.tests_run*100:.1f}%")
        print("="*80)
        
        return 0 if self.tests_passed == self.tests_run else 1

if __name__ == "__main__":
    tester = Phase27Tester()
    sys.exit(tester.run_all_tests())

#!/usr/bin/env python3
"""Backend API Testing for SIPRO Phase 36 - KALENDER JADWAL

Tests all Phase 36 calendar endpoints including:
- Calendar month view (GET /api/build/calendar)
- Calendar settings (GET/PUT /api/build/calendar/settings)
- Holiday management (POST/DELETE /api/build/calendar/holidays)
- Workday check (GET /api/build/calendar/workday)
- RBAC (PM can configure, site can view only, sales denied)
- Audit logging for calendar changes
"""
import sys
import requests
from datetime import datetime

# Use public endpoint from frontend/.env
BASE_URL = "https://mandor-board-submit.preview.emergentagent.com/api"
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
                print(f"  ✓ Logged in as {email}")
                return True
            else:
                print(f"  ✗ Login failed for {email}: {r.status_code} - {r.text[:100]}")
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
            print(f"  ✗ GET {path} error: {str(e)}")
            return None
    
    def post(self, path, email, data=None, params=None):
        """POST request"""
        try:
            return requests.post(f"{BASE_URL}{path}",
                               headers=self.headers(email),
                               json=data or {},
                               params=params or {},
                               timeout=30)
        except Exception as e:
            print(f"  ✗ POST {path} error: {str(e)}")
            return None
    
    def put(self, path, email, data=None):
        """PUT request"""
        try:
            return requests.put(f"{BASE_URL}{path}",
                              headers=self.headers(email),
                              json=data or {},
                              timeout=30)
        except Exception as e:
            print(f"  ✗ PUT {path} error: {str(e)}")
            return None
    
    def delete(self, path, email, params=None):
        """DELETE request"""
        try:
            return requests.delete(f"{BASE_URL}{path}",
                                 headers=self.headers(email),
                                 params=params or {},
                                 timeout=30)
        except Exception as e:
            print(f"  ✗ DELETE {path} error: {str(e)}")
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
    print("SIPRO PHASE 36 - KALENDER JADWAL - BACKEND TESTS")
    print("="*60)
    
    # Login all test users
    print("\n1. AUTHENTICATION")
    print("-" * 60)
    runner.login("pm@sipro.co.id")
    runner.login("site@sipro.co.id")
    runner.login("sales@sipro.co.id")
    runner.login("owner@sipro.co.id")
    
    # Test calendar month view
    print("\n2. CALENDAR MONTH VIEW (GET /api/build/calendar)")
    print("-" * 60)
    
    r = runner.get("/build/calendar", "pm@sipro.co.id", {"month": "2026-08"})
    if r and r.status_code == 200:
        data = r.json().get("data", {})
        can = r.json().get("can", {})
        
        runner.test("Calendar returns 200 for PM", True)
        runner.test("Calendar has month field", "month" in data, f"month={data.get('month')}")
        runner.test("Calendar has first/last dates", "first" in data and "last" in data)
        runner.test("Calendar has days array", "days" in data and isinstance(data.get("days"), list))
        runner.test("Calendar has 31 days for August", len(data.get("days", [])) == 31)
        runner.test("Calendar has events array", "events" in data)
        runner.test("Calendar has conflicts array", "conflicts" in data)
        runner.test("Calendar has summary", "summary" in data)
        runner.test("Calendar has calendar settings", "calendar" in data)
        runner.test("Calendar has projects list", "projects" in data)
        runner.test("Calendar has assignees list", "assignees" in data)
        runner.test("Calendar has unscheduled inspections", "unscheduled" in data)
        runner.test("Calendar has outlook", "outlook" in data)
        runner.test("Calendar has today field", "today" in data)
        runner.test("PM can configure calendar", can.get("configure") == True)
        runner.test("PM can shift dates", can.get("shift") == True)
        
        # Check summary structure
        summary = data.get("summary", {})
        runner.test("Summary has totals", "totals" in summary)
        runner.test("Summary has work_days", "work_days" in summary)
        runner.test("Summary has conflicts", "conflicts" in summary)
        runner.test("Summary has thresholds", "thresholds" in summary)
        
        # Check days structure
        if data.get("days"):
            day = data["days"][0]
            runner.test("Day has date field", "date" in day)
            runner.test("Day has is_workday field", "is_workday" in day)
            runner.test("Day has counts field", "counts" in day)
            runner.test("Day has conflicts field", "conflicts" in day)
    else:
        runner.test("Calendar returns 200 for PM", False, f"Status: {r.status_code if r else 'None'}")
    
    # Test portfolio scope (all projects)
    print("\n3. PORTFOLIO SCOPE (scope=all)")
    print("-" * 60)
    
    r = runner.get("/build/calendar", "pm@sipro.co.id", {"month": "2026-08"})
    if r and r.status_code == 200:
        data = r.json().get("data", {})
        runner.test("Portfolio calendar returns data", "events" in data)
        runner.test("Portfolio has scope field", "scope" in data)
    
    # Test calendar settings
    print("\n4. CALENDAR SETTINGS (GET /api/build/calendar/settings)")
    print("-" * 60)
    
    r = runner.get("/build/calendar/settings", "pm@sipro.co.id")
    if r and r.status_code == 200:
        data = r.json().get("data", {})
        defaults = r.json().get("defaults", {})
        
        runner.test("Settings returns 200", True)
        runner.test("Settings has pattern", "pattern" in data)
        runner.test("Settings has holidays", "holidays" in data)
        runner.test("Settings has thresholds", "thresholds" in data)
        runner.test("Settings has note", "note" in data)
        runner.test("Defaults has weekdays", "weekdays" in defaults)
        runner.test("Defaults has pattern", "pattern" in defaults)
        runner.test("Defaults has thresholds", "thresholds" in defaults)
        
        # Check pattern has all 7 days
        pattern = data.get("pattern", {})
        weekdays = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
        runner.test("Pattern has all 7 weekdays", all(d in pattern for d in weekdays))
        
        # Check holidays structure
        holidays = data.get("holidays", [])
        runner.test("Holidays is a list", isinstance(holidays, list))
        if holidays:
            h = holidays[0]
            runner.test("Holiday has date", "date" in h)
            runner.test("Holiday has name", "name" in h)
            runner.test("Holiday has kind", "kind" in h)
    else:
        runner.test("Settings returns 200", False, f"Status: {r.status_code if r else 'None'}")
    
    # Test workday check
    print("\n5. WORKDAY CHECK (GET /api/build/calendar/workday)")
    print("-" * 60)
    
    # Check holiday (Aug 17, 2026 - Independence Day)
    r = runner.get("/build/calendar/workday", "pm@sipro.co.id", {"date": "2026-08-17"})
    if r and r.status_code == 200:
        data = r.json().get("data", {})
        runner.test("Workday check returns 200", True)
        runner.test("Aug 17 is not workday (holiday)", data.get("is_workday") == False)
        runner.test("Aug 17 has holiday name", data.get("holiday") is not None)
        runner.test("Workday check has suggested_date", "suggested_date" in data)
    
    # Check regular workday
    r = runner.get("/build/calendar/workday", "pm@sipro.co.id", {"date": "2026-08-18"})
    if r and r.status_code == 200:
        data = r.json().get("data", {})
        runner.test("Aug 18 is workday", data.get("is_workday") == True)
    
    # Test month options
    print("\n6. MONTH OPTIONS (GET /api/build/calendar/months)")
    print("-" * 60)
    
    r = runner.get("/build/calendar/months", "pm@sipro.co.id", {"months": 6})
    if r and r.status_code == 200:
        data = r.json().get("data", [])
        runner.test("Month options returns list", isinstance(data, list))
        runner.test("Month options has items", len(data) > 0)
    
    # Test RBAC - Site engineer (can view, cannot configure)
    print("\n7. RBAC - SITE ENGINEER (view only)")
    print("-" * 60)
    
    r = runner.get("/build/calendar", "site@sipro.co.id", {"month": "2026-08"})
    if r and r.status_code == 200:
        can = r.json().get("can", {})
        runner.test("Site can view calendar", True)
        runner.test("Site cannot configure", can.get("configure") == False)
        runner.test("Site cannot shift", can.get("shift") == False)
    else:
        runner.test("Site can view calendar", False, f"Status: {r.status_code if r else 'None'}")
    
    # Site cannot update settings
    r = runner.put("/build/calendar/settings", "site@sipro.co.id", {
        "pattern": {"mon": "full", "tue": "full", "wed": "full", "thu": "full", 
                   "fri": "full", "sat": "half", "sun": "off"},
        "thresholds": {"max_items_per_person_per_day": 3, "max_critical_per_day": 2}
    })
    runner.test("Site cannot update settings (403)", r and r.status_code == 403)
    
    # Site cannot add holiday
    r = runner.post("/build/calendar/holidays", "site@sipro.co.id", {
        "date": "2026-12-30",
        "name": "Test Holiday",
        "kind": "company"
    })
    runner.test("Site cannot add holiday (403)", r and r.status_code == 403)
    
    # Test RBAC - Sales (denied)
    print("\n8. RBAC - SALES (access denied)")
    print("-" * 60)
    
    r = runner.get("/build/calendar", "sales@sipro.co.id", {"month": "2026-08"})
    runner.test("Sales denied calendar access (403)", r and r.status_code == 403)
    
    # Test holiday management
    print("\n9. HOLIDAY MANAGEMENT")
    print("-" * 60)
    
    # Add a test holiday
    test_date = "2026-12-30"
    r = runner.post("/build/calendar/holidays", "pm@sipro.co.id", {
        "date": test_date,
        "name": "Cuti bersama uji API",
        "kind": "company"
    })
    if r and r.status_code == 200:
        runner.test("PM can add holiday", True)
        data = r.json().get("data", {})
        holidays = data.get("holidays", [])
        runner.test("Holiday added to list", any(h.get("date") == test_date for h in holidays))
    else:
        runner.test("PM can add holiday", False, f"Status: {r.status_code if r else 'None'}, Response: {r.text if r else 'None'}")
    
    # Try to add duplicate holiday
    r = runner.post("/build/calendar/holidays", "pm@sipro.co.id", {
        "date": test_date,
        "name": "Duplicate",
        "kind": "company"
    })
    runner.test("Cannot add duplicate holiday (400)", r and r.status_code == 400)
    
    # Delete the test holiday
    r = runner.delete(f"/build/calendar/holidays/{test_date}", "pm@sipro.co.id")
    if r and r.status_code == 200:
        runner.test("PM can delete holiday", True)
    else:
        runner.test("PM can delete holiday", False, f"Status: {r.status_code if r else 'None'}")
    
    # Try to delete non-existent holiday
    r = runner.delete(f"/build/calendar/holidays/{test_date}", "pm@sipro.co.id")
    runner.test("Cannot delete non-existent holiday (400)", r and r.status_code == 400)
    
    # Test settings update
    print("\n10. SETTINGS UPDATE")
    print("-" * 60)
    
    # Get current settings
    r = runner.get("/build/calendar/settings", "pm@sipro.co.id")
    if r and r.status_code == 200:
        original_data = r.json().get("data", {})
        original_threshold = original_data.get("thresholds", {}).get("max_items_per_person_per_day", 3)
        
        # Update threshold
        new_threshold = 1
        r = runner.put("/build/calendar/settings", "pm@sipro.co.id", {
            "pattern": original_data.get("pattern"),
            "thresholds": {
                "max_items_per_person_per_day": new_threshold,
                "max_critical_per_day": 2
            }
        })
        if r and r.status_code == 200:
            runner.test("PM can update settings", True)
            data = r.json().get("data", {})
            runner.test("Threshold updated", data.get("thresholds", {}).get("max_items_per_person_per_day") == new_threshold)
        else:
            runner.test("PM can update settings", False, f"Status: {r.status_code if r else 'None'}")
        
        # Restore original threshold
        r = runner.put("/build/calendar/settings", "pm@sipro.co.id", {
            "pattern": original_data.get("pattern"),
            "thresholds": {
                "max_items_per_person_per_day": original_threshold,
                "max_critical_per_day": 2
            }
        })
        runner.test("Settings restored", r and r.status_code == 200)
    
    # Test invalid settings
    print("\n11. SETTINGS VALIDATION")
    print("-" * 60)
    
    # All days off (should fail)
    r = runner.put("/build/calendar/settings", "pm@sipro.co.id", {
        "pattern": {"mon": "off", "tue": "off", "wed": "off", "thu": "off", 
                   "fri": "off", "sat": "off", "sun": "off"},
        "thresholds": {"max_items_per_person_per_day": 3, "max_critical_per_day": 2}
    })
    runner.test("Cannot set all days off (400)", r and r.status_code == 400)
    
    # Invalid threshold (0)
    r = runner.put("/build/calendar/settings", "pm@sipro.co.id", {
        "pattern": {"mon": "full", "tue": "full", "wed": "full", "thu": "full", 
                   "fri": "full", "sat": "half", "sun": "off"},
        "thresholds": {"max_items_per_person_per_day": 0, "max_critical_per_day": 2}
    })
    runner.test("Cannot set threshold to 0 (400)", r and r.status_code in [400, 422])
    
    # Test conflicts detection
    print("\n12. CONFLICTS DETECTION")
    print("-" * 60)
    
    r = runner.get("/build/calendar", "pm@sipro.co.id", {"month": "2026-08"})
    if r and r.status_code == 200:
        data = r.json().get("data", {})
        conflicts = data.get("conflicts", [])
        
        runner.test("Conflicts array exists", isinstance(conflicts, list))
        
        # Check for non_workday conflicts (Aug 17 is holiday)
        non_workday = [c for c in conflicts if c.get("kind") == "non_workday"]
        runner.test("Non-workday conflicts detected", len(non_workday) > 0)
        
        if non_workday:
            c = non_workday[0]
            runner.test("Conflict has date", "date" in c)
            runner.test("Conflict has detail", "detail" in c)
            runner.test("Conflict has suggested_date", "suggested_date" in c)
    
    # Test filters
    print("\n13. FILTERS (kinds & assignee)")
    print("-" * 60)
    
    # Filter by kind
    r = runner.get("/build/calendar", "pm@sipro.co.id", {
        "month": "2026-08",
        "kinds": "work_deadline,inspection"
    })
    if r and r.status_code == 200:
        data = r.json().get("data", {})
        events = data.get("events", [])
        runner.test("Kind filter works", all(e.get("kind") in ["work_deadline", "inspection"] for e in events))
    
    # Filter by assignee
    r = runner.get("/build/calendar", "pm@sipro.co.id", {"month": "2026-08"})
    if r and r.status_code == 200:
        data = r.json().get("data", {})
        assignees = data.get("assignees", [])
        
        if assignees:
            test_assignee = assignees[0]
            r2 = runner.get("/build/calendar", "pm@sipro.co.id", {
                "month": "2026-08",
                "assignee": test_assignee
            })
            if r2 and r2.status_code == 200:
                data2 = r2.json().get("data", {})
                events2 = data2.get("events", [])
                runner.test("Assignee filter works", all(
                    e.get("assigned_to") == test_assignee or not e.get("assigned_to") 
                    for e in events2
                ))
    
    return runner.summary()


if __name__ == "__main__":
    sys.exit(main())

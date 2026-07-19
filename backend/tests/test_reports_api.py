"""
Test suite for Reports Page API endpoints
Tests planned-vs-actual overview and portfolio budget analysis APIs
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://calc-audit-review.preview.emergentagent.com')


class TestReportsAPI:
    """Reports Page API tests - planned vs actual overview and AI portfolio analysis"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup - get auth token for super_admin user"""
        # Login as super_admin
        login_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            data={"username": "don@ddconsult.tech", "password": "Welcome123!"},
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        
        login_data = login_response.json()
        self.token = login_data["access_token"]
        self.user_role = login_data["user"]["role"]
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        
    def test_auth_login_super_admin(self):
        """Test login with super_admin credentials"""
        assert self.token is not None
        assert self.user_role == "super_admin"
        print(f"✅ Login successful - role: {self.user_role}")
        
    def test_planned_vs_actual_overview_returns_200(self):
        """Test /api/reports/planned-vs-actual/overview returns 200"""
        response = requests.get(
            f"{BASE_URL}/api/reports/planned-vs-actual/overview",
            headers=self.headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print("✅ GET /api/reports/planned-vs-actual/overview returns 200")
        
    def test_planned_vs_actual_overview_structure(self):
        """Test overview endpoint returns correct structure with summary and projects"""
        response = requests.get(
            f"{BASE_URL}/api/reports/planned-vs-actual/overview",
            headers=self.headers
        )
        data = response.json()
        
        # Verify summary exists with expected fields
        assert "summary" in data, "Missing 'summary' field"
        summary = data["summary"]
        
        expected_summary_fields = [
            "total_projects", "total_budget", "total_actual", "total_planned",
            "overall_variance", "overall_pct_used",
            "projects_on_track", "projects_at_risk", "projects_over_budget", "projects_no_budget"
        ]
        for field in expected_summary_fields:
            assert field in summary, f"Missing '{field}' in summary"
            
        print(f"✅ Summary has all required fields: {list(summary.keys())}")
        
        # Verify projects list
        assert "projects" in data, "Missing 'projects' field"
        assert isinstance(data["projects"], list), "'projects' should be a list"
        print(f"✅ Projects list present with {len(data['projects'])} items")
        
    def test_planned_vs_actual_project_row_structure(self):
        """Test each project row has required fields for table display"""
        response = requests.get(
            f"{BASE_URL}/api/reports/planned-vs-actual/overview",
            headers=self.headers
        )
        data = response.json()
        
        if len(data["projects"]) > 0:
            project = data["projects"][0]
            expected_project_fields = [
                "project_id", "project_name", "client_name", "status",
                "budgeted_hours", "planned_hours", "actual_hours",
                "variance_hours", "budget_used_pct", "health"
            ]
            for field in expected_project_fields:
                assert field in project, f"Missing '{field}' in project row"
            
            # Verify health values are valid
            valid_health_values = ["on_track", "at_risk", "over_budget", "no_budget"]
            assert project["health"] in valid_health_values, f"Invalid health value: {project['health']}"
            
            print(f"✅ Project row has all required fields: {list(project.keys())}")
            print(f"   Sample: {project['project_name']} - Budget: {project['budgeted_hours']}h, Actual: {project['actual_hours']}h, Health: {project['health']}")
        else:
            pytest.skip("No projects available to test row structure")
            
    def test_portfolio_budget_analysis_returns_200(self):
        """Test /api/ai/portfolio-budget-analysis returns 200"""
        response = requests.get(
            f"{BASE_URL}/api/ai/portfolio-budget-analysis",
            headers=self.headers,
            timeout=60  # AI endpoint may take longer
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print("✅ GET /api/ai/portfolio-budget-analysis returns 200")
        
    def test_portfolio_budget_analysis_structure(self):
        """Test AI analysis endpoint returns narrative, alerts, recommendations, highlights"""
        response = requests.get(
            f"{BASE_URL}/api/ai/portfolio-budget-analysis",
            headers=self.headers,
            timeout=60
        )
        data = response.json()
        
        # Verify required AI analysis fields
        assert "narrative" in data, "Missing 'narrative' field"
        assert isinstance(data["narrative"], str), "'narrative' should be a string"
        assert len(data["narrative"]) > 0, "'narrative' should not be empty"
        
        assert "alerts" in data, "Missing 'alerts' field"
        assert isinstance(data["alerts"], list), "'alerts' should be a list"
        
        assert "recommendations" in data, "Missing 'recommendations' field"
        assert isinstance(data["recommendations"], list), "'recommendations' should be a list"
        
        assert "project_highlights" in data, "Missing 'project_highlights' field"
        assert isinstance(data["project_highlights"], list), "'project_highlights' should be a list"
        
        print(f"✅ AI Analysis structure valid")
        print(f"   Narrative: {data['narrative'][:100]}...")
        print(f"   Alerts: {len(data['alerts'])}, Recommendations: {len(data['recommendations'])}, Highlights: {len(data['project_highlights'])}")
        
    def test_alert_structure(self):
        """Test alert items have severity, title, and message"""
        response = requests.get(
            f"{BASE_URL}/api/ai/portfolio-budget-analysis",
            headers=self.headers,
            timeout=60
        )
        data = response.json()
        
        if len(data.get("alerts", [])) > 0:
            alert = data["alerts"][0]
            assert "severity" in alert, "Alert missing 'severity'"
            assert "title" in alert, "Alert missing 'title'"
            assert "message" in alert, "Alert missing 'message'"
            
            valid_severities = ["critical", "warning", "info"]
            assert alert["severity"] in valid_severities, f"Invalid severity: {alert['severity']}"
            
            print(f"✅ Alert structure valid: {alert['severity']} - {alert['title']}")
        else:
            print("⚠️ No alerts to test (may be expected if portfolio is healthy)")
            
    def test_recommendation_structure(self):
        """Test recommendation items have priority, title, and action"""
        response = requests.get(
            f"{BASE_URL}/api/ai/portfolio-budget-analysis",
            headers=self.headers,
            timeout=60
        )
        data = response.json()
        
        if len(data.get("recommendations", [])) > 0:
            rec = data["recommendations"][0]
            assert "priority" in rec, "Recommendation missing 'priority'"
            assert "title" in rec, "Recommendation missing 'title'"
            assert "action" in rec, "Recommendation missing 'action'"
            
            valid_priorities = ["high", "medium", "low"]
            assert rec["priority"] in valid_priorities, f"Invalid priority: {rec['priority']}"
            
            print(f"✅ Recommendation structure valid: {rec['priority']} - {rec['title']}")
        else:
            print("⚠️ No recommendations to test")


class TestReportsAPIRoleAccess:
    """Test role-based API access for reports endpoints"""
    
    def test_resource_user_can_access_overview(self):
        """Test resource role user can access overview endpoint (not admin-restricted)"""
        # Login as resource user
        login_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            data={"username": "amrit@ddconsult.tech", "password": "Welcome123!"},
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        
        token = login_response.json()["access_token"]
        role = login_response.json()["user"]["role"]
        assert role == "resource", f"Expected resource role, got {role}"
        
        headers = {"Authorization": f"Bearer {token}"}
        
        # Test overview endpoint
        response = requests.get(
            f"{BASE_URL}/api/reports/planned-vs-actual/overview",
            headers=headers
        )
        # API allows access for any authenticated user
        assert response.status_code == 200, f"Resource user should be able to access overview API"
        print(f"✅ Resource user can access overview API (status {response.status_code})")
        
    def test_unauthenticated_user_blocked(self):
        """Test unauthenticated requests are blocked"""
        response = requests.get(
            f"{BASE_URL}/api/reports/planned-vs-actual/overview"
        )
        assert response.status_code == 401, f"Expected 401 for unauthenticated request, got {response.status_code}"
        print("✅ Unauthenticated requests correctly blocked with 401")


class TestSummaryCardData:
    """Test that summary card data is accurate and matches project data"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup - get auth token"""
        login_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            data={"username": "don@ddconsult.tech", "password": "Welcome123!"},
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        self.token = login_response.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
        
    def test_summary_totals_match_project_sum(self):
        """Verify summary totals match sum of individual project data"""
        response = requests.get(
            f"{BASE_URL}/api/reports/planned-vs-actual/overview",
            headers=self.headers
        )
        data = response.json()
        
        # Calculate sums from projects
        projects = data["projects"]
        calculated_budget = sum(p.get("budgeted_hours", 0) for p in projects)
        calculated_actual = sum(p.get("actual_hours", 0) for p in projects)
        
        # Compare with summary
        summary = data["summary"]
        assert abs(summary["total_budget"] - calculated_budget) < 0.1, "Budget total mismatch"
        assert abs(summary["total_actual"] - calculated_actual) < 0.1, "Actual total mismatch"
        
        print(f"✅ Summary totals match project sums")
        print(f"   Budget: {summary['total_budget']}h (calculated: {calculated_budget}h)")
        print(f"   Actual: {summary['total_actual']}h (calculated: {calculated_actual}h)")
        
    def test_health_counts_match(self):
        """Verify health status counts in summary match actual project counts"""
        response = requests.get(
            f"{BASE_URL}/api/reports/planned-vs-actual/overview",
            headers=self.headers
        )
        data = response.json()
        
        projects = data["projects"]
        summary = data["summary"]
        
        on_track_count = sum(1 for p in projects if p["health"] == "on_track")
        at_risk_count = sum(1 for p in projects if p["health"] == "at_risk")
        over_budget_count = sum(1 for p in projects if p["health"] == "over_budget")
        no_budget_count = sum(1 for p in projects if p["health"] == "no_budget")
        
        assert summary["projects_on_track"] == on_track_count, "On Track count mismatch"
        assert summary["projects_at_risk"] == at_risk_count, "At Risk count mismatch"
        assert summary["projects_over_budget"] == over_budget_count, "Over Budget count mismatch"
        assert summary["projects_no_budget"] == no_budget_count, "No Budget count mismatch"
        
        print(f"✅ Health counts match: on_track={on_track_count}, at_risk={at_risk_count}, over_budget={over_budget_count}, no_budget={no_budget_count}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

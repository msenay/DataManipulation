"""Test metrics endpoints and calculations."""
import pytest
from fastapi.testclient import TestClient


class TestMetrics:
    """Test metrics endpoints and tenant isolation."""

    @pytest.fixture(autouse=True)
    def setup_test_data(self, client: TestClient, tenant_headers):
        """Set up test transactions for metrics testing."""
        # Create transactions for tenant 1
        tenant1_transactions = [
            {"user_id": "user1", "product_category": "electronics", "amount": "299.99", "currency": "USD"},
            {"user_id": "user1", "product_category": "electronics", "amount": "199.99", "currency": "USD"},
            {"user_id": "user2", "product_category": "books", "amount": "29.99", "currency": "USD"},
            {"user_id": "user2", "product_category": "books", "amount": "19.99", "currency": "USD"},
            {"user_id": "user3", "product_category": "clothing", "amount": "89.99", "currency": "USD"},
        ]
        
        for transaction in tenant1_transactions:
            response = client.post(
                "/v1/transactions",
                json=transaction,
                headers=tenant_headers["tenant_1"]
            )
            assert response.status_code == 201
        
        # Create transactions for tenant 2 (for isolation testing)
        tenant2_transactions = [
            {"user_id": "user4", "product_category": "electronics", "amount": "399.99", "currency": "USD"},
            {"user_id": "user5", "product_category": "sports", "amount": "129.99", "currency": "USD"},
        ]
        
        for transaction in tenant2_transactions:
            response = client.post(
                "/v1/transactions",
                json=transaction,
                headers=tenant_headers["tenant_2"]
            )
            assert response.status_code == 201

    def test_summary_metrics_correct_values(self, client: TestClient, tenant_headers):
        """Test that summary metrics return correct calculated values."""
        response = client.get("/v1/metrics/summary", headers=tenant_headers["tenant_1"])
        assert response.status_code == 200
        
        data = response.json()
        
        # Expected: 5 transactions totaling $639.95 (299.99 + 199.99 + 29.99 + 19.99 + 89.99)
        assert data["total_count"] >= 5  # At least 5 from our test data
        assert "total_amount" in data
        assert "average_amount" in data
        assert data["currency"] == "USD"
        
        # Verify average calculation (if we only have our test data)
        if data["total_count"] == 5:
            expected_total = 299.99 + 199.99 + 29.99 + 19.99 + 89.99
            assert float(data["total_amount"]) == expected_total
            assert float(data["average_amount"]) == expected_total / 5

    def test_summary_metrics_tenant_isolation(self, client: TestClient, tenant_headers):
        """Test that summary metrics are tenant-isolated."""
        # Get metrics for tenant 1
        response1 = client.get("/v1/metrics/summary", headers=tenant_headers["tenant_1"])
        assert response1.status_code == 200
        tenant1_data = response1.json()
        
        # Get metrics for tenant 2
        response2 = client.get("/v1/metrics/summary", headers=tenant_headers["tenant_2"])
        assert response2.status_code == 200
        tenant2_data = response2.json()
        
        # They should be different (assuming different transaction volumes)
        assert tenant1_data["total_count"] != tenant2_data["total_count"] or \
               tenant1_data["total_amount"] != tenant2_data["total_amount"]

    def test_category_metrics_correct_sorting(self, client: TestClient, tenant_headers):
        """Test that category metrics are sorted by total amount descending."""
        response = client.get("/v1/metrics/by-category", headers=tenant_headers["tenant_1"])
        assert response.status_code == 200
        
        categories = response.json()
        assert len(categories) >= 3  # electronics, books, clothing from our test data
        
        # Verify sorting (descending by total_amount)
        for i in range(len(categories) - 1):
            current_amount = float(categories[i]["total_amount"])
            next_amount = float(categories[i + 1]["total_amount"])
            assert current_amount >= next_amount, "Categories should be sorted by total_amount desc"
        
        # Find our expected categories
        category_names = [cat["category"] for cat in categories]
        assert "electronics" in category_names
        assert "books" in category_names
        assert "clothing" in category_names
        
        # Verify electronics has the highest total (299.99 + 199.99 = 499.98)
        electronics_cat = next(cat for cat in categories if cat["category"] == "electronics")
        assert electronics_cat["count"] >= 2
        if electronics_cat["count"] == 2:  # Only our test data
            assert float(electronics_cat["total_amount"]) == 499.98

    def test_category_metrics_calculations(self, client: TestClient, tenant_headers):
        """Test that category metrics calculations are correct."""
        response = client.get("/v1/metrics/by-category", headers=tenant_headers["tenant_1"])
        assert response.status_code == 200
        
        categories = response.json()
        
        for category in categories:
            # Verify average calculation
            total_amount = float(category["total_amount"])
            count = category["count"]
            expected_average = total_amount / count
            actual_average = float(category["average_amount"])
            
            # Allow for small floating point differences
            assert abs(actual_average - expected_average) < 0.01

    def test_user_metrics_success(self, client: TestClient, tenant_headers):
        """Test successful user metrics retrieval."""
        response = client.get("/v1/metrics/user/user1", headers=tenant_headers["tenant_1"])
        assert response.status_code == 200
        
        data = response.json()
        assert data["user_id"] == "user1"
        assert data["count"] >= 2  # user1 has 2 transactions in our test data
        assert "total_amount" in data
        assert "average_amount" in data
        
        # If only our test data exists
        if data["count"] == 2:
            expected_total = 299.99 + 199.99
            assert float(data["total_amount"]) == expected_total
            assert float(data["average_amount"]) == expected_total / 2

    def test_user_metrics_not_found_404(self, client: TestClient, tenant_headers):
        """Test that nonexistent user returns 404."""
        response = client.get("/v1/metrics/user/nonexistent_user", headers=tenant_headers["tenant_1"])
        assert response.status_code == 404
        assert "No transactions found" in response.json()["detail"]

    def test_user_metrics_cross_tenant_404(self, client: TestClient, tenant_headers):
        """Test that cross-tenant user access returns 404."""
        # user4 exists in tenant 2 but not tenant 1
        response = client.get("/v1/metrics/user/user4", headers=tenant_headers["tenant_1"])
        assert response.status_code == 404
        assert "No transactions found" in response.json()["detail"]

    def test_comprehensive_metrics_structure(self, client: TestClient, tenant_headers):
        """Test that comprehensive metrics return correct structure."""
        response = client.get("/v1/metrics", headers=tenant_headers["tenant_1"])
        assert response.status_code == 200
        
        data = response.json()
        
        # Check structure
        assert "tenant_id" in data
        assert "overall" in data
        assert "by_category" in data
        assert "by_user" in data
        
        # Check tenant ID
        assert data["tenant_id"] == "123e4567-e89b-12d3-a456-426614174000"
        
        # Check overall section
        overall = data["overall"]
        assert "total_count" in overall
        assert "total_amount" in overall
        assert "average_amount" in overall
        assert "currency" in overall
        
        # Check categories section
        categories = data["by_category"]
        assert isinstance(categories, list)
        if categories:  # If we have data
            assert "category" in categories[0]
            assert "count" in categories[0]
            assert "total_amount" in categories[0]
            assert "average_amount" in categories[0]
        
        # Check users section
        users = data["by_user"]
        assert isinstance(users, list)
        if users:  # If we have data
            assert "user_id" in users[0]
            assert "count" in users[0]
            assert "total_amount" in users[0]
            assert "average_amount" in users[0]

    def test_metrics_date_filtering(self, client: TestClient, tenant_headers):
        """Test that metrics endpoints respect date filtering."""
        # Test with a future date range (should return empty/zero results)
        future_start = "2030-01-01T00:00:00Z"
        future_end = "2030-12-31T23:59:59Z"
        
        response = client.get(
            f"/v1/metrics/summary?start_ts={future_start}&end_ts={future_end}",
            headers=tenant_headers["tenant_1"]
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["total_count"] == 0
        assert float(data["total_amount"]) == 0.0
        
        # Test category metrics with date filter
        response = client.get(
            f"/v1/metrics/by-category?start_ts={future_start}&end_ts={future_end}",
            headers=tenant_headers["tenant_1"]
        )
        assert response.status_code == 200
        
        categories = response.json()
        assert len(categories) == 0

    def test_metrics_tenant_isolation_comprehensive(self, client: TestClient, tenant_headers):
        """Test comprehensive tenant isolation across all metrics endpoints."""
        endpoints = [
            "/v1/metrics/summary",
            "/v1/metrics/by-category", 
            "/v1/metrics",
        ]
        
        for endpoint in endpoints:
            # Get data for tenant 1
            response1 = client.get(endpoint, headers=tenant_headers["tenant_1"])
            assert response1.status_code == 200
            
            # Get data for tenant 2
            response2 = client.get(endpoint, headers=tenant_headers["tenant_2"])
            assert response2.status_code == 200
            
            # Data should be different (assuming different transaction data)
            assert response1.json() != response2.json(), f"Tenant isolation failed for {endpoint}"

    def test_metrics_empty_tenant(self, client: TestClient, tenant_headers):
        """Test metrics behavior for tenant with no transactions."""
        # Use tenant 3 which should have no transactions
        response = client.get("/v1/metrics/summary", headers=tenant_headers["tenant_3"])
        assert response.status_code == 200
        
        data = response.json()
        assert data["total_count"] == 0
        assert float(data["total_amount"]) == 0.0
        assert data["average_amount"] is None
        
        # Category metrics should be empty
        response = client.get("/v1/metrics/by-category", headers=tenant_headers["tenant_3"])
        assert response.status_code == 200
        assert response.json() == []
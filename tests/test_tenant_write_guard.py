"""Test tenant write-guard error handling."""
import pytest
from fastapi.testclient import TestClient


class TestTenantWriteGuard:
    """Test tenant write-guard error mapping to HTTP 422."""

    def test_tenant_mismatch_in_request_body_422(self, client: TestClient, tenant_headers):
        """Test that tenant mismatch in request body returns 422."""
        transaction_data = {
            "user_id": "test_user",
            "product_category": "electronics",
            "amount": "199.99",
            "currency": "USD",
            "tenant_id": "456e7890-e89b-12d3-a456-426614174001"  # Different from header
        }
        
        response = client.post(
            "/v1/transactions",
            json=transaction_data,
            headers=tenant_headers["tenant_1"]  # Different tenant in header
        )
        
        assert response.status_code == 422
        detail = response.json()["detail"]
        assert "tenant" in detail.lower()
        assert "mismatch" in detail.lower()

    def test_health_endpoint_no_tenant_required(self, client: TestClient):
        """Test that health endpoint works without tenant header."""
        response = client.get("/v1/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "healthy"

    def test_all_non_health_endpoints_require_tenant(self, client: TestClient):
        """Test that all endpoints except health require tenant header."""
        endpoints_to_test = [
            ("GET", "/v1/me"),
            ("GET", "/v1/transactions"),
            ("POST", "/v1/transactions"),
            ("GET", "/v1/transactions/123e4567-e89b-12d3-a456-426614174000"),
            ("PUT", "/v1/transactions/123e4567-e89b-12d3-a456-426614174000"),
            ("DELETE", "/v1/transactions/123e4567-e89b-12d3-a456-426614174000"),
            ("POST", "/v1/transactions/import"),
            ("GET", "/v1/metrics"),
            ("GET", "/v1/metrics/summary"),
            ("GET", "/v1/metrics/by-category"),
            ("GET", "/v1/metrics/user/test_user"),
        ]
        
        for method, endpoint in endpoints_to_test:
            response = client.request(method, endpoint)
            assert response.status_code == 400, f"Failed for {method} {endpoint}"
            assert "x-tenant-id header is required" in response.json()["detail"]

    def test_cross_tenant_transaction_access_404(self, client: TestClient, tenant_headers):
        """Test that cross-tenant transaction access returns 404 (doesn't leak existence)."""
        # Create transaction for tenant 1
        transaction_data = {
            "user_id": "cross_tenant_test",
            "product_category": "electronics",
            "amount": "199.99",
            "currency": "USD"
        }
        
        create_response = client.post(
            "/v1/transactions",
            json=transaction_data,
            headers=tenant_headers["tenant_1"]
        )
        assert create_response.status_code == 201
        transaction_id = create_response.json()["id"]
        
        # Try to access from tenant 2 - should get 404
        get_response = client.get(
            f"/v1/transactions/{transaction_id}",
            headers=tenant_headers["tenant_2"]
        )
        assert get_response.status_code == 404
        assert "not found" in get_response.json()["detail"].lower()
        
        # Try to update from tenant 2 - should get 404
        update_response = client.put(
            f"/v1/transactions/{transaction_id}",
            json={"amount": "299.99"},
            headers=tenant_headers["tenant_2"]
        )
        assert update_response.status_code == 404
        
        # Try to delete from tenant 2 - should get 404
        delete_response = client.delete(
            f"/v1/transactions/{transaction_id}",
            headers=tenant_headers["tenant_2"]
        )
        assert delete_response.status_code == 404

    def test_nonexistent_transaction_404(self, client: TestClient, tenant_headers):
        """Test that nonexistent transaction returns 404."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        
        # GET should return 404
        response = client.get(
            f"/v1/transactions/{fake_id}",
            headers=tenant_headers["tenant_1"]
        )
        assert response.status_code == 404
        
        # PUT should return 404
        response = client.put(
            f"/v1/transactions/{fake_id}",
            json={"amount": "299.99"},
            headers=tenant_headers["tenant_1"]
        )
        assert response.status_code == 404
        
        # DELETE should return 404
        response = client.delete(
            f"/v1/transactions/{fake_id}",
            headers=tenant_headers["tenant_1"]
        )
        assert response.status_code == 404

    def test_user_metrics_cross_tenant_404(self, client: TestClient, tenant_headers):
        """Test that user metrics for cross-tenant users return 404."""
        # Create transaction for tenant 1
        transaction_data = {
            "user_id": "tenant1_exclusive_user",
            "product_category": "electronics",
            "amount": "199.99",
            "currency": "USD"
        }
        
        response = client.post(
            "/v1/transactions",
            json=transaction_data,
            headers=tenant_headers["tenant_1"]
        )
        assert response.status_code == 201
        
        # Try to get user metrics from tenant 2 - should return 404
        response = client.get(
            "/v1/metrics/user/tenant1_exclusive_user",
            headers=tenant_headers["tenant_2"]
        )
        assert response.status_code == 404
        assert "No transactions found" in response.json()["detail"]
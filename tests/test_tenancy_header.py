"""Test tenant header validation."""
import pytest
from fastapi.testclient import TestClient


class TestTenancyHeader:
    """Test tenant header validation and processing."""

    def test_missing_header_returns_400(self, client: TestClient):
        """Test that missing x-tenant-id header returns 400."""
        response = client.get("/v1/me")
        assert response.status_code == 400
        assert "x-tenant-id header is required" in response.json()["detail"]

    def test_empty_header_returns_400(self, client: TestClient):
        """Test that empty x-tenant-id header returns 400."""
        response = client.get("/v1/me", headers={"x-tenant-id": ""})
        assert response.status_code == 400
        assert "x-tenant-id header is required" in response.json()["detail"]

    def test_invalid_uuid_returns_422(self, client: TestClient):
        """Test that invalid UUID format returns 422."""
        invalid_uuids = [
            "not-a-uuid",
            "123-456-789",
            "123e4567-e89b-12d3-a456",  # Too short
            "123e4567-e89b-12d3-a456-426614174000-extra",  # Too long
            "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",  # Invalid characters
        ]
        
        for invalid_uuid in invalid_uuids:
            response = client.get("/v1/me", headers={"x-tenant-id": invalid_uuid})
            assert response.status_code == 422, f"Failed for UUID: {invalid_uuid}"
            assert "Invalid tenant ID format" in response.json()["detail"]

    def test_valid_uuid_returns_200(self, client: TestClient, tenant_headers):
        """Test that valid UUID returns 200 with normalized format."""
        response = client.get("/v1/me", headers=tenant_headers["tenant_1"])
        assert response.status_code == 200
        
        data = response.json()
        assert "tenant_id" in data
        assert data["tenant_id"] == "123e4567-e89b-12d3-a456-426614174000"

    def test_uuid_normalization_to_lowercase(self, client: TestClient):
        """Test that UUIDs are normalized to lowercase."""
        uppercase_uuid = "123E4567-E89B-12D3-A456-426614174000"
        expected_lowercase = "123e4567-e89b-12d3-a456-426614174000"
        
        response = client.get("/v1/me", headers={"x-tenant-id": uppercase_uuid})
        assert response.status_code == 200
        
        data = response.json()
        assert data["tenant_id"] == expected_lowercase

    def test_uuid_with_whitespace_is_trimmed(self, client: TestClient):
        """Test that UUIDs with whitespace are trimmed."""
        uuid_with_spaces = "  123e4567-e89b-12d3-a456-426614174000  "
        expected_clean = "123e4567-e89b-12d3-a456-426614174000"
        
        response = client.get("/v1/me", headers={"x-tenant-id": uuid_with_spaces})
        assert response.status_code == 200
        
        data = response.json()
        assert data["tenant_id"] == expected_clean

    def test_health_endpoint_no_tenant_required(self, client: TestClient):
        """Test that health endpoint doesn't require tenant header."""
        response = client.get("/v1/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "healthy"

    def test_all_transaction_endpoints_require_tenant(self, client: TestClient):
        """Test that all transaction endpoints require tenant header."""
        endpoints = [
            ("GET", "/v1/transactions"),
            ("POST", "/v1/transactions"),
            ("GET", "/v1/transactions/123e4567-e89b-12d3-a456-426614174000"),
            ("PUT", "/v1/transactions/123e4567-e89b-12d3-a456-426614174000"),
            ("DELETE", "/v1/transactions/123e4567-e89b-12d3-a456-426614174000"),
        ]
        
        for method, endpoint in endpoints:
            response = client.request(method, endpoint)
            assert response.status_code == 400, f"Failed for {method} {endpoint}"
            assert "x-tenant-id header is required" in response.json()["detail"]

    def test_all_metrics_endpoints_require_tenant(self, client: TestClient):
        """Test that all metrics endpoints require tenant header."""
        endpoints = [
            "/v1/metrics",
            "/v1/metrics/summary", 
            "/v1/metrics/by-category",
            "/v1/metrics/user/test_user",
        ]
        
        for endpoint in endpoints:
            response = client.get(endpoint)
            assert response.status_code == 400, f"Failed for {endpoint}"
            assert "x-tenant-id header is required" in response.json()["detail"]

    def test_import_endpoint_requires_tenant(self, client: TestClient):
        """Test that import endpoint requires tenant header."""
        response = client.post("/v1/transactions/import")
        assert response.status_code == 400
        assert "x-tenant-id header is required" in response.json()["detail"]

    def test_multiple_tenant_headers_uses_first(self, client: TestClient):
        """Test behavior when multiple tenant headers are provided."""
        headers = {
            "x-tenant-id": "123e4567-e89b-12d3-a456-426614174000"
        }
        
        response = client.get("/v1/me", headers=headers)
        assert response.status_code == 200
        
        data = response.json()
        assert data["tenant_id"] == "123e4567-e89b-12d3-a456-426614174000"
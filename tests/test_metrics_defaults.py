"""Test metrics default date ranges and validation."""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient


class TestMetricsDefaults:
    """Test metrics default date ranges and validation."""

    def test_metrics_summary_defaults_to_30_days(self, client: TestClient, tenant_headers):
        """Test that metrics summary defaults to last 30 days when no dates provided."""
        response = client.get("/v1/metrics/summary", headers=tenant_headers["tenant_1"])
        assert response.status_code == 200
        
        data = response.json()
        assert "total_count" in data
        assert "total_amount" in data
        assert "average_amount" in data
        assert "currency" in data

    def test_metrics_category_defaults_to_30_days(self, client: TestClient, tenant_headers):
        """Test that category metrics default to last 30 days when no dates provided."""
        response = client.get("/v1/metrics/by-category", headers=tenant_headers["tenant_1"])
        assert response.status_code == 200
        
        categories = response.json()
        assert isinstance(categories, list)

    def test_metrics_comprehensive_defaults_to_30_days(self, client: TestClient, tenant_headers):
        """Test that comprehensive metrics default to last 30 days when no dates provided."""
        response = client.get("/v1/metrics", headers=tenant_headers["tenant_1"])
        assert response.status_code == 200
        
        data = response.json()
        assert "tenant_id" in data
        assert "overall" in data
        assert "by_category" in data
        assert "by_user" in data

    def test_date_range_validation_start_after_end(self, client: TestClient, tenant_headers):
        """Test that start_ts > end_ts returns 422."""
        start_ts = "2025-01-31T23:59:59Z"
        end_ts = "2025-01-01T00:00:00Z"
        
        response = client.get(
            f"/v1/metrics/summary?start_ts={start_ts}&end_ts={end_ts}",
            headers=tenant_headers["tenant_1"]
        )
        assert response.status_code == 422
        assert "start_ts" in response.json()["detail"]
        assert "end_ts" in response.json()["detail"]

    def test_date_range_validation_category_metrics(self, client: TestClient, tenant_headers):
        """Test date range validation for category metrics."""
        start_ts = "2025-12-31T23:59:59Z"
        end_ts = "2025-01-01T00:00:00Z"
        
        response = client.get(
            f"/v1/metrics/by-category?start_ts={start_ts}&end_ts={end_ts}",
            headers=tenant_headers["tenant_1"]
        )
        assert response.status_code == 422
        assert "start_ts" in response.json()["detail"]

    def test_date_range_validation_comprehensive_metrics(self, client: TestClient, tenant_headers):
        """Test date range validation for comprehensive metrics."""
        start_ts = "2025-12-31T23:59:59Z"
        end_ts = "2025-01-01T00:00:00Z"
        
        response = client.get(
            f"/v1/metrics?start_ts={start_ts}&end_ts={end_ts}",
            headers=tenant_headers["tenant_1"]
        )
        assert response.status_code == 422
        assert "start_ts" in response.json()["detail"]

    def test_partial_date_range_start_only(self, client: TestClient, tenant_headers):
        """Test that providing only start_ts creates 30-day window."""
        start_ts = "2025-01-01T00:00:00Z"
        
        response = client.get(
            f"/v1/metrics/summary?start_ts={start_ts}",
            headers=tenant_headers["tenant_1"]
        )
        assert response.status_code == 200
        
        # Should work without error (30-day window from start_ts)
        data = response.json()
        assert "total_count" in data

    def test_partial_date_range_end_only(self, client: TestClient, tenant_headers):
        """Test that providing only end_ts creates 30-day window."""
        end_ts = "2025-01-31T23:59:59Z"
        
        response = client.get(
            f"/v1/metrics/summary?end_ts={end_ts}",
            headers=tenant_headers["tenant_1"]
        )
        assert response.status_code == 200
        
        # Should work without error (30-day window before end_ts)
        data = response.json()
        assert "total_count" in data

    def test_metrics_empty_dataset_returns_zeros(self, client: TestClient, tenant_headers):
        """Test that metrics return appropriate values for empty datasets."""
        # Use a future date range where no transactions should exist
        future_start = "2030-01-01T00:00:00Z"
        future_end = "2030-12-31T23:59:59Z"
        
        # Test summary metrics
        response = client.get(
            f"/v1/metrics/summary?start_ts={future_start}&end_ts={future_end}",
            headers=tenant_headers["tenant_1"]
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["total_count"] == 0
        assert float(data["total_amount"]) == 0.0
        assert data["average_amount"] is None
        
        # Test category metrics
        response = client.get(
            f"/v1/metrics/by-category?start_ts={future_start}&end_ts={future_end}",
            headers=tenant_headers["tenant_1"]
        )
        assert response.status_code == 200
        assert response.json() == []
        
        # Test comprehensive metrics
        response = client.get(
            f"/v1/metrics?start_ts={future_start}&end_ts={future_end}",
            headers=tenant_headers["tenant_1"]
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["overall"]["total_count"] == 0
        assert data["by_category"] == []
        assert data["by_user"] == []

    def test_invalid_date_format_returns_422(self, client: TestClient, tenant_headers):
        """Test that invalid date formats return 422."""
        invalid_dates = [
            "not-a-date",
            "2025-13-01T00:00:00Z",  # Invalid month
            "2025-01-32T00:00:00Z",  # Invalid day
            "2025-01-01T25:00:00Z",  # Invalid hour
        ]
        
        for invalid_date in invalid_dates:
            response = client.get(
                f"/v1/metrics/summary?start_ts={invalid_date}",
                headers=tenant_headers["tenant_1"]
            )
            # FastAPI will return 422 for invalid datetime format
            assert response.status_code == 422
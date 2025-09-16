"""Test transaction operations and tenant isolation."""
import pytest
from fastapi.testclient import TestClient


class TestTransactionCRUD:
    """Test transaction CRUD operations."""

    def test_create_transaction_success(self, client: TestClient, tenant_headers, sample_transaction_data):
        """Test successful transaction creation."""
        response = client.post(
            "/v1/transactions",
            json=sample_transaction_data["valid"],
            headers=tenant_headers["tenant_1"]
        )
        
        assert response.status_code == 201
        data = response.json()
        
        # Check required fields
        assert "id" in data
        assert data["tenant_id"] == "123e4567-e89b-12d3-a456-426614174000"
        assert data["user_id"] == "test_user_001"
        assert data["product_category"] == "electronics"
        assert data["amount"] == "199.99"
        assert data["currency"] == "USD"
        assert "ts" in data

    def test_create_transaction_no_tenant_in_body(self, client: TestClient, tenant_headers):
        """Test that tenant_id is not required in request body."""
        transaction_data = {
            "user_id": "test_user_002",
            "product_category": "books",
            "amount": "29.99",
            "currency": "EUR"
        }
        
        response = client.post(
            "/v1/transactions",
            json=transaction_data,
            headers=tenant_headers["tenant_1"]
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["tenant_id"] == "123e4567-e89b-12d3-a456-426614174000"

    def test_create_transaction_mismatched_tenant_422(self, client: TestClient, tenant_headers):
        """Test that mismatched tenant_id in body returns 422."""
        transaction_data = {
            "user_id": "test_user_003",
            "product_category": "electronics",
            "amount": "199.99",
            "currency": "USD",
            "tenant_id": "456e7890-e89b-12d3-a456-426614174001"  # Different from header
        }
        
        response = client.post(
            "/v1/transactions",
            json=transaction_data,
            headers=tenant_headers["tenant_1"]  # Different tenant
        )
        
        assert response.status_code == 422
        assert "Tenant ID mismatch" in response.json()["detail"]

    def test_create_transaction_validation_errors(self, client: TestClient, tenant_headers, sample_transaction_data):
        """Test various validation errors."""
        test_cases = [
            (sample_transaction_data["invalid_amount"], "decimal_parsing"),
            (sample_transaction_data["missing_fields"], "missing"),
            (sample_transaction_data["empty_user_id"], "string_too_short"),
            (sample_transaction_data["invalid_currency"], "string_too_long"),
        ]
        
        for invalid_data, expected_error_type in test_cases:
            response = client.post(
                "/v1/transactions",
                json=invalid_data,
                headers=tenant_headers["tenant_1"]
            )
            
            assert response.status_code == 422
            # Check that the response contains validation errors
            assert "detail" in response.json()

    def test_list_transactions_tenant_isolation(self, client: TestClient, tenant_headers):
        """Test that transaction listing is tenant-isolated."""
        # Create transactions for different tenants
        transaction_data = {
            "user_id": "test_user_isolation",
            "product_category": "test",
            "amount": "100.00",
            "currency": "USD"
        }
        
        # Create transaction for tenant 1
        response1 = client.post(
            "/v1/transactions",
            json=transaction_data,
            headers=tenant_headers["tenant_1"]
        )
        assert response1.status_code == 201
        tenant1_transaction = response1.json()
        
        # Create transaction for tenant 2
        response2 = client.post(
            "/v1/transactions",
            json=transaction_data,
            headers=tenant_headers["tenant_2"]
        )
        assert response2.status_code == 201
        tenant2_transaction = response2.json()
        
        # List transactions for tenant 1
        list_response1 = client.get("/v1/transactions", headers=tenant_headers["tenant_1"])
        assert list_response1.status_code == 200
        tenant1_transactions = list_response1.json()
        
        # List transactions for tenant 2
        list_response2 = client.get("/v1/transactions", headers=tenant_headers["tenant_2"])
        assert list_response2.status_code == 200
        tenant2_transactions = list_response2.json()
        
        # Verify isolation
        tenant1_ids = [t["id"] for t in tenant1_transactions]
        tenant2_ids = [t["id"] for t in tenant2_transactions]
        
        assert tenant1_transaction["id"] in tenant1_ids
        assert tenant1_transaction["id"] not in tenant2_ids
        assert tenant2_transaction["id"] in tenant2_ids
        assert tenant2_transaction["id"] not in tenant1_ids

    def test_list_transactions_filters_and_pagination(self, client: TestClient, tenant_headers):
        """Test transaction listing filters and pagination."""
        # Create multiple transactions
        for i in range(5):
            transaction_data = {
                "user_id": f"user_{i}",
                "product_category": "electronics" if i % 2 == 0 else "books",
                "amount": f"{100 + i}.99",
                "currency": "USD"
            }
            
            response = client.post(
                "/v1/transactions",
                json=transaction_data,
                headers=tenant_headers["tenant_1"]
            )
            assert response.status_code == 201

        # Test pagination
        response = client.get(
            "/v1/transactions?limit=3&offset=0",
            headers=tenant_headers["tenant_1"]
        )
        assert response.status_code == 200
        transactions = response.json()
        assert len(transactions) <= 3

        # Test user filter
        response = client.get(
            "/v1/transactions?user_id=user_0",
            headers=tenant_headers["tenant_1"]
        )
        assert response.status_code == 200
        transactions = response.json()
        for transaction in transactions:
            assert transaction["user_id"] == "user_0"

    def test_get_transaction_by_id_success(self, client: TestClient, tenant_headers):
        """Test successful transaction retrieval by ID."""
        # Create a transaction
        transaction_data = {
            "user_id": "test_user_get",
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
        created_transaction = create_response.json()
        
        # Retrieve the transaction
        get_response = client.get(
            f"/v1/transactions/{created_transaction['id']}",
            headers=tenant_headers["tenant_1"]
        )
        assert get_response.status_code == 200
        
        retrieved_transaction = get_response.json()
        assert retrieved_transaction["id"] == created_transaction["id"]
        assert retrieved_transaction["user_id"] == transaction_data["user_id"]

    def test_get_transaction_cross_tenant_404(self, client: TestClient, tenant_headers):
        """Test that cross-tenant transaction access returns 404."""
        # Create transaction for tenant 1
        transaction_data = {
            "user_id": "test_user_cross_tenant",
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
        created_transaction = create_response.json()
        
        # Try to access from tenant 2
        get_response = client.get(
            f"/v1/transactions/{created_transaction['id']}",
            headers=tenant_headers["tenant_2"]
        )
        assert get_response.status_code == 404
        assert "not found" in get_response.json()["detail"].lower()

    def test_get_nonexistent_transaction_404(self, client: TestClient, tenant_headers):
        """Test that nonexistent transaction returns 404."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        
        response = client.get(
            f"/v1/transactions/{fake_id}",
            headers=tenant_headers["tenant_1"]
        )
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_update_transaction_success(self, client: TestClient, tenant_headers):
        """Test successful transaction update."""
        # Create a transaction
        transaction_data = {
            "user_id": "test_user_update",
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
        created_transaction = create_response.json()
        
        # Update the transaction
        update_data = {
            "amount": "299.99",
            "product_category": "premium_electronics"
        }
        
        update_response = client.put(
            f"/v1/transactions/{created_transaction['id']}",
            json=update_data,
            headers=tenant_headers["tenant_1"]
        )
        assert update_response.status_code == 200
        
        updated_transaction = update_response.json()
        assert updated_transaction["amount"] == "299.99"
        assert updated_transaction["product_category"] == "premium_electronics"
        assert updated_transaction["user_id"] == transaction_data["user_id"]  # Unchanged

    def test_delete_transaction_success(self, client: TestClient, tenant_headers):
        """Test successful transaction deletion."""
        # Create a transaction
        transaction_data = {
            "user_id": "test_user_delete",
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
        created_transaction = create_response.json()
        
        # Delete the transaction
        delete_response = client.delete(
            f"/v1/transactions/{created_transaction['id']}",
            headers=tenant_headers["tenant_1"]
        )
        assert delete_response.status_code == 204
        
        # Verify it's deleted
        get_response = client.get(
            f"/v1/transactions/{created_transaction['id']}",
            headers=tenant_headers["tenant_1"]
        )
        assert get_response.status_code == 404


class TestTransactionImport:
    """Test transaction import functionality."""

    def test_json_import_success(self, client: TestClient, tenant_headers):
        """Test successful JSON array import."""
        import_data = [
            {
                "user_id": "import_user_1",
                "product_category": "electronics",
                "amount": "199.99",
                "currency": "USD"
            },
            {
                "user_id": "import_user_2",
                "product_category": "books",
                "amount": "29.99",
                "currency": "EUR"
            }
        ]
        
        response = client.post(
            "/v1/transactions/import",
            json=import_data,
            headers=tenant_headers["tenant_1"]
        )
        
        assert response.status_code == 200
        result = response.json()
        
        assert result["ingested"] == 2
        assert result["skipped"] == 0
        assert len(result["errors"]) == 0

    def test_csv_import_success(self, client: TestClient, tenant_headers, sample_csv_data):
        """Test successful CSV import."""
        files = {"file": ("test.csv", sample_csv_data["valid"], "text/csv")}
        
        response = client.post(
            "/v1/transactions/import",
            files=files,
            headers=tenant_headers["tenant_1"]
        )
        
        assert response.status_code == 200
        result = response.json()
        
        assert result["ingested"] == 3
        assert result["skipped"] == 0
        assert len(result["errors"]) == 0

    def test_csv_import_with_tenant_mismatch(self, client: TestClient, tenant_headers, sample_csv_data):
        """Test CSV import with mixed tenant IDs produces correct skip counts."""
        files = {"file": ("test.csv", sample_csv_data["mixed_tenants"], "text/csv")}
        
        response = client.post(
            "/v1/transactions/import",
            files=files,
            headers=tenant_headers["tenant_1"]  # Using tenant 1 header
        )
        
        assert response.status_code == 200
        result = response.json()
        
        # Should ingest records matching tenant 1, skip tenant 2 record
        assert result["ingested"] == 2  # 2 records for tenant 1
        assert result["skipped"] == 1   # 1 record for tenant 2
        assert len(result["errors"]) == 1
        assert "Tenant ID mismatch" in result["errors"][0]["reason"]

    def test_csv_import_with_validation_errors(self, client: TestClient, tenant_headers, sample_csv_data):
        """Test CSV import with validation errors produces correct error reporting."""
        files = {"file": ("test.csv", sample_csv_data["with_errors"], "text/csv")}
        
        response = client.post(
            "/v1/transactions/import",
            files=files,
            headers=tenant_headers["tenant_1"]
        )
        
        assert response.status_code == 200
        result = response.json()
        
        assert result["ingested"] == 1  # Only the valid record
        assert result["skipped"] == 3   # 3 invalid records
        assert len(result["errors"]) == 3
        
        # Check error reasons
        error_reasons = [error["reason"] for error in result["errors"]]
        assert any("Missing required field" in reason for reason in error_reasons)
        assert any("Invalid amount format" in reason for reason in error_reasons)
        assert any("Invalid currency format" in reason for reason in error_reasons)

    def test_import_invalid_file_type(self, client: TestClient, tenant_headers):
        """Test that non-CSV files are rejected."""
        files = {"file": ("test.txt", "not a csv", "text/plain")}
        
        response = client.post(
            "/v1/transactions/import",
            files=files,
            headers=tenant_headers["tenant_1"]
        )
        
        assert response.status_code == 400
        assert "CSV file" in response.json()["detail"]

    def test_import_no_data_provided(self, client: TestClient, tenant_headers):
        """Test that request with no file or JSON returns 400."""
        response = client.post(
            "/v1/transactions/import",
            headers=tenant_headers["tenant_1"]
        )
        
        assert response.status_code == 400
        assert "CSV file" in response.json()["detail"] or "JSON array" in response.json()["detail"]
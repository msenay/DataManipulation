#!/usr/bin/env python3
"""
Comprehensive API Test Script for FastAPI Multi-Tenant Transaction System

This script tests all endpoints and functionality of the multi-tenant API.
Run this after starting the application with Docker Compose or uvicorn.

Usage:
    python test_api.py [--base-url http://localhost:8000]
"""

import argparse
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from uuid import uuid4

import requests


class Colors:
    """ANSI color codes for pretty output."""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    PURPLE = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    END = '\033[0m'


class APITester:
    """Comprehensive API testing class."""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        
        # Test tenant UUIDs
        self.tenants = {
            "tenant_1": "123e4567-e89b-12d3-a456-426614174000",
            "tenant_2": "456e7890-e89b-12d3-a456-426614174001", 
            "tenant_3": "789e0123-e89b-12d3-a456-426614174002"
        }
        
        # Track created transactions for cleanup
        self.created_transactions: Dict[str, List[str]] = {
            tenant: [] for tenant in self.tenants.keys()
        }
        
        self.test_results = []
    
    def log(self, message: str, color: str = Colors.WHITE, level: str = "INFO"):
        """Log a message with color and timestamp."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"{color}[{timestamp}] {level}: {message}{Colors.END}")
    
    def test_result(self, test_name: str, success: bool, details: str = ""):
        """Record and display test result."""
        status = f"{Colors.GREEN}✅ PASS" if success else f"{Colors.RED}❌ FAIL"
        self.test_results.append((test_name, success, details))
        details_str = f" - {details}" if details else ""
        self.log(f"{status}{Colors.END} {test_name}{details_str}")
    
    def make_request(self, method: str, endpoint: str, tenant: Optional[str] = None, 
                    data: Optional[Dict] = None, files: Optional[Dict] = None,
                    params: Optional[Dict] = None) -> requests.Response:
        """Make an API request with optional tenant header."""
        url = f"{self.base_url}{endpoint}"
        headers = {"Content-Type": "application/json"}
        
        if tenant:
            headers["x-tenant-id"] = self.tenants[tenant]
        
        if files:
            headers.pop("Content-Type", None)  # Let requests set this for multipart
        
        try:
            response = self.session.request(
                method=method,
                url=url,
                headers=headers,
                json=data,
                files=files,
                params=params,
                timeout=10
            )
            return response
        except requests.exceptions.RequestException as e:
            self.log(f"Request failed: {e}", Colors.RED, "ERROR")
            raise
    
    def test_health_endpoint(self):
        """Test health endpoint (no authentication required)."""
        self.log("Testing health endpoint...", Colors.CYAN)
        
        response = self.make_request("GET", "/v1/health")
        success = response.status_code == 200
        
        if success:
            data = response.json()
            details = f"Status: {data.get('status')}, Service: {data.get('service')}"
        else:
            details = f"Status: {response.status_code}, Response: {response.text}"
        
        self.test_result("Health Check", success, details)
        return success
    
    def test_tenant_validation(self):
        """Test tenant header validation."""
        self.log("Testing tenant validation...", Colors.CYAN)
        
        # Test missing header (should be 400)
        response = self.make_request("GET", "/v1/me")
        success1 = response.status_code == 400
        self.test_result("Missing tenant header → 400", success1, 
                        f"Got {response.status_code}: {response.json().get('detail', '')}")
        
        # Test invalid UUID (should be 422)
        headers = {"x-tenant-id": "invalid-uuid"}
        response = self.session.get(f"{self.base_url}/v1/me", headers=headers)
        success2 = response.status_code == 422
        self.test_result("Invalid UUID → 422", success2,
                        f"Got {response.status_code}: {response.json().get('detail', '')}")
        
        # Test valid UUID (should be 200 with normalization)
        headers = {"x-tenant-id": "123E4567-E89B-12D3-A456-426614174000"}  # Uppercase
        response = self.session.get(f"{self.base_url}/v1/me", headers=headers)
        success3 = response.status_code == 200
        
        if success3:
            data = response.json()
            normalized_uuid = data.get("tenant_id", "")
            is_lowercase = normalized_uuid == normalized_uuid.lower()
            success3 = success3 and is_lowercase
            details = f"Normalized to: {normalized_uuid}"
        else:
            details = f"Got {response.status_code}"
        
        self.test_result("Valid UUID → 200 + normalization", success3, details)
        
        return success1 and success2 and success3
    
    def test_transaction_crud(self):
        """Test transaction CRUD operations."""
        self.log("Testing transaction CRUD operations...", Colors.CYAN)
        
        # Test transaction creation
        transaction_data = {
            "user_id": "test_user_001",
            "product_category": "electronics",
            "amount": "299.99",
            "currency": "USD"
        }
        
        response = self.make_request("POST", "/v1/transactions", "tenant_1", transaction_data)
        success_create = response.status_code == 201
        
        if success_create:
            created_transaction = response.json()
            transaction_id = created_transaction["id"]
            self.created_transactions["tenant_1"].append(transaction_id)
            details = f"Created transaction: {transaction_id}"
        else:
            details = f"Status: {response.status_code}, Error: {response.text}"
            transaction_id = None
        
        self.test_result("Create transaction", success_create, details)
        
        if not transaction_id:
            return False
        
        # Test transaction retrieval
        response = self.make_request("GET", f"/v1/transactions/{transaction_id}", "tenant_1")
        success_get = response.status_code == 200
        
        if success_get:
            retrieved = response.json()
            details = f"Retrieved: {retrieved['user_id']}, Amount: {retrieved['amount']}"
        else:
            details = f"Status: {response.status_code}"
        
        self.test_result("Get transaction by ID", success_get, details)
        
        # Test transaction update
        update_data = {"amount": "399.99", "product_category": "premium_electronics"}
        response = self.make_request("PUT", f"/v1/transactions/{transaction_id}", "tenant_1", update_data)
        success_update = response.status_code == 200
        
        if success_update:
            updated = response.json()
            details = f"Updated amount: {updated['amount']}, category: {updated['product_category']}"
        else:
            details = f"Status: {response.status_code}"
        
        self.test_result("Update transaction", success_update, details)
        
        # Test transaction listing
        response = self.make_request("GET", "/v1/transactions", "tenant_1", params={"limit": 5})
        success_list = response.status_code == 200
        
        if success_list:
            transactions = response.json()
            details = f"Retrieved {len(transactions)} transactions"
        else:
            details = f"Status: {response.status_code}"
        
        self.test_result("List transactions", success_list, details)
        
        return success_create and success_get and success_update and success_list
    
    def test_tenant_isolation(self):
        """Test tenant isolation."""
        self.log("Testing tenant isolation...", Colors.CYAN)
        
        # Create transaction for tenant 1
        transaction_data = {
            "user_id": "isolation_test_user",
            "product_category": "isolation_test",
            "amount": "100.00",
            "currency": "USD"
        }
        
        response = self.make_request("POST", "/v1/transactions", "tenant_1", transaction_data)
        if response.status_code != 201:
            self.test_result("Tenant isolation setup", False, "Failed to create test transaction")
            return False
        
        transaction_id = response.json()["id"]
        self.created_transactions["tenant_1"].append(transaction_id)
        
        # Try to access from different tenant (should be 404)
        response = self.make_request("GET", f"/v1/transactions/{transaction_id}", "tenant_2")
        success_isolation = response.status_code == 404
        
        details = f"Cross-tenant access returned {response.status_code} (expected 404)"
        self.test_result("Cross-tenant access prevention", success_isolation, details)
        
        # Verify tenant 1 can still access it
        response = self.make_request("GET", f"/v1/transactions/{transaction_id}", "tenant_1")
        success_own_access = response.status_code == 200
        
        details = f"Own tenant access returned {response.status_code} (expected 200)"
        self.test_result("Own tenant access", success_own_access, details)
        
        return success_isolation and success_own_access
    
    def test_data_import(self):
        """Test CSV and JSON data import."""
        self.log("Testing data import functionality...", Colors.CYAN)
        
        # Test JSON import
        json_data = [
            {
                "user_id": "import_user_001",
                "product_category": "books",
                "amount": "29.99",
                "currency": "USD"
            },
            {
                "user_id": "import_user_002",
                "product_category": "electronics", 
                "amount": "199.99",
                "currency": "EUR"
            }
        ]
        
        response = self.make_request("POST", "/v1/transactions/import", "tenant_1", json_data)
        success_json = response.status_code == 200
        
        if success_json:
            result = response.json()
            details = f"Ingested: {result['ingested']}, Skipped: {result['skipped']}, Errors: {len(result['errors'])}"
        else:
            details = f"Status: {response.status_code}, Error: {response.text}"
        
        self.test_result("JSON import", success_json, details)
        
        # Test CSV import with sample data
        csv_content = """user_id,product_category,amount,currency,ts
csv_user_001,electronics,399.99,USD,2025-01-01T10:00:00Z
csv_user_002,books,24.99,EUR,2025-01-01T11:00:00Z
csv_user_003,clothing,79.99,USD,2025-01-01T12:00:00Z"""
        
        files = {"file": ("test_import.csv", csv_content, "text/csv")}
        response = self.make_request("POST", "/v1/transactions/import", "tenant_1", files=files)
        success_csv = response.status_code == 200
        
        if success_csv:
            result = response.json()
            details = f"Ingested: {result['ingested']}, Skipped: {result['skipped']}, Errors: {len(result['errors'])}"
        else:
            details = f"Status: {response.status_code}, Error: {response.text}"
        
        self.test_result("CSV import", success_csv, details)
        
        return success_json and success_csv
    
    def test_metrics_and_analytics(self):
        """Test metrics and analytics endpoints."""
        self.log("Testing metrics and analytics...", Colors.CYAN)
        
        # Test summary metrics
        response = self.make_request("GET", "/v1/metrics/summary", "tenant_1")
        success_summary = response.status_code == 200
        
        if success_summary:
            data = response.json()
            details = f"Count: {data['total_count']}, Amount: {data['total_amount']}, Currency: {data['currency']}"
        else:
            details = f"Status: {response.status_code}"
        
        self.test_result("Summary metrics", success_summary, details)
        
        # Test category metrics
        response = self.make_request("GET", "/v1/metrics/by-category", "tenant_1")
        success_category = response.status_code == 200
        
        if success_category:
            categories = response.json()
            details = f"Found {len(categories)} categories"
            if categories:
                top_category = categories[0]
                details += f", Top: {top_category['category']} (${top_category['total_amount']})"
        else:
            details = f"Status: {response.status_code}"
        
        self.test_result("Category metrics", success_category, details)
        
        # Test user metrics (try to find a user with transactions)
        response = self.make_request("GET", "/v1/transactions", "tenant_1", params={"limit": 1})
        if response.status_code == 200 and response.json():
            user_id = response.json()[0]["user_id"]
            
            response = self.make_request("GET", f"/v1/metrics/user/{user_id}", "tenant_1")
            success_user = response.status_code == 200
            
            if success_user:
                data = response.json()
                details = f"User: {data['user_id']}, Transactions: {data['count']}, Total: ${data['total_amount']}"
            else:
                details = f"Status: {response.status_code}"
        else:
            success_user = True  # No transactions to test with
            details = "No transactions found to test user metrics"
        
        self.test_result("User metrics", success_user, details)
        
        # Test comprehensive metrics
        response = self.make_request("GET", "/v1/metrics", "tenant_1")
        success_comprehensive = response.status_code == 200
        
        if success_comprehensive:
            data = response.json()
            details = f"Tenant: {data['tenant_id']}, Categories: {len(data['by_category'])}, Users: {len(data['by_user'])}"
        else:
            details = f"Status: {response.status_code}"
        
        self.test_result("Comprehensive metrics", success_comprehensive, details)
        
        return success_summary and success_category and success_user and success_comprehensive
    
    def test_date_range_validation(self):
        """Test date range validation in metrics."""
        self.log("Testing date range validation...", Colors.CYAN)
        
        # Test invalid date range (start > end)
        params = {
            "start_ts": "2025-12-31T23:59:59Z",
            "end_ts": "2025-01-01T00:00:00Z"
        }
        
        response = self.make_request("GET", "/v1/metrics/summary", "tenant_1", params=params)
        success = response.status_code == 422
        
        if success:
            details = f"Correctly rejected invalid range: {response.json().get('detail', '')}"
        else:
            details = f"Expected 422, got {response.status_code}"
        
        self.test_result("Date range validation", success, details)
        
        # Test valid date range
        now = datetime.now(timezone.utc)
        start_ts = (now - timedelta(days=7)).isoformat()
        end_ts = now.isoformat()
        
        params = {"start_ts": start_ts, "end_ts": end_ts}
        response = self.make_request("GET", "/v1/metrics/summary", "tenant_1", params=params)
        success_valid = response.status_code == 200
        
        details = f"Valid range returned {response.status_code}"
        self.test_result("Valid date range", success_valid, details)
        
        return success and success_valid
    
    def test_error_handling(self):
        """Test various error scenarios."""
        self.log("Testing error handling...", Colors.CYAN)
        
        # Test tenant mismatch in request body
        bad_data = {
            "user_id": "test_user",
            "product_category": "test",
            "amount": "99.99",
            "currency": "USD",
            "tenant_id": self.tenants["tenant_2"]  # Different from header
        }
        
        response = self.make_request("POST", "/v1/transactions", "tenant_1", bad_data)
        success_mismatch = response.status_code == 422
        details = f"Tenant mismatch returned {response.status_code}"
        self.test_result("Tenant mismatch → 422", success_mismatch, details)
        
        # Test validation errors
        invalid_data = {
            "user_id": "",  # Too short
            "product_category": "test",
            "amount": "invalid",  # Not a number
            "currency": "TOOLONG"  # Too long
        }
        
        response = self.make_request("POST", "/v1/transactions", "tenant_1", invalid_data)
        success_validation = response.status_code == 422
        details = f"Validation errors returned {response.status_code}"
        self.test_result("Validation errors → 422", success_validation, details)
        
        # Test nonexistent resource
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = self.make_request("GET", f"/v1/transactions/{fake_id}", "tenant_1")
        success_404 = response.status_code == 404
        details = f"Nonexistent resource returned {response.status_code}"
        self.test_result("Nonexistent resource → 404", success_404, details)
        
        return success_mismatch and success_validation and success_404
    
    def test_pagination_and_filtering(self):
        """Test pagination and filtering."""
        self.log("Testing pagination and filtering...", Colors.CYAN)
        
        # Create some test data first
        for i in range(3):
            data = {
                "user_id": f"page_test_user_{i}",
                "product_category": "pagination_test",
                "amount": f"{100 + i}.99",
                "currency": "USD"
            }
            response = self.make_request("POST", "/v1/transactions", "tenant_1", data)
            if response.status_code == 201:
                self.created_transactions["tenant_1"].append(response.json()["id"])
        
        # Test pagination
        response = self.make_request("GET", "/v1/transactions", "tenant_1", 
                                   params={"limit": 2, "offset": 0})
        success_pagination = response.status_code == 200
        
        if success_pagination:
            transactions = response.json()
            details = f"Retrieved {len(transactions)} transactions (limit=2)"
        else:
            details = f"Status: {response.status_code}"
        
        self.test_result("Pagination", success_pagination, details)
        
        # Test user filtering
        response = self.make_request("GET", "/v1/transactions", "tenant_1",
                                   params={"user_id": "page_test_user_0"})
        success_filter = response.status_code == 200
        
        if success_filter:
            transactions = response.json()
            user_matches = all(t["user_id"] == "page_test_user_0" for t in transactions)
            details = f"Found {len(transactions)} transactions for specific user, all match: {user_matches}"
            success_filter = success_filter and user_matches
        else:
            details = f"Status: {response.status_code}"
        
        self.test_result("User filtering", success_filter, details)
        
        return success_pagination and success_filter
    
    def test_multi_tenant_isolation(self):
        """Test complete multi-tenant isolation."""
        self.log("Testing multi-tenant isolation...", Colors.CYAN)
        
        # Create transactions for different tenants
        tenant_data = {}
        for tenant_key in ["tenant_1", "tenant_2"]:
            data = {
                "user_id": f"isolation_user_{tenant_key}",
                "product_category": "isolation_test",
                "amount": "150.00",
                "currency": "USD"
            }
            
            response = self.make_request("POST", "/v1/transactions", tenant_key, data)
            if response.status_code == 201:
                tenant_data[tenant_key] = response.json()["id"]
                self.created_transactions[tenant_key].append(tenant_data[tenant_key])
        
        if len(tenant_data) != 2:
            self.test_result("Multi-tenant isolation setup", False, "Failed to create test data")
            return False
        
        # Test that tenant 1 can't see tenant 2's transaction
        response = self.make_request("GET", f"/v1/transactions/{tenant_data['tenant_2']}", "tenant_1")
        success_isolation = response.status_code == 404
        details = f"Tenant 1 accessing Tenant 2's transaction: {response.status_code} (expected 404)"
        self.test_result("Transaction isolation", success_isolation, details)
        
        # Test metrics isolation
        response1 = self.make_request("GET", "/v1/metrics/summary", "tenant_1")
        response2 = self.make_request("GET", "/v1/metrics/summary", "tenant_2")
        
        if response1.status_code == 200 and response2.status_code == 200:
            data1 = response1.json()
            data2 = response2.json()
            
            # They should have different counts or amounts
            different_metrics = (data1["total_count"] != data2["total_count"] or 
                               data1["total_amount"] != data2["total_amount"])
            
            details = f"T1: {data1['total_count']} txns, T2: {data2['total_count']} txns - Isolated: {different_metrics}"
            self.test_result("Metrics isolation", different_metrics, details)
        else:
            different_metrics = False
            details = "Failed to get metrics for comparison"
            self.test_result("Metrics isolation", False, details)
        
        return success_isolation and different_metrics
    
    def test_import_validation(self):
        """Test import validation and error reporting."""
        self.log("Testing import validation...", Colors.CYAN)
        
        # Test CSV with mixed tenants and validation errors
        csv_with_errors = f"""user_id,product_category,amount,currency,tenant_id
valid_user,electronics,299.99,USD,{self.tenants['tenant_1']}
,books,19.99,EUR,{self.tenants['tenant_1']}
invalid_user,electronics,not_a_number,USD,{self.tenants['tenant_1']}
other_tenant_user,sports,99.99,USD,{self.tenants['tenant_2']}"""
        
        files = {"file": ("validation_test.csv", csv_with_errors, "text/csv")}
        response = self.make_request("POST", "/v1/transactions/import", "tenant_1", files=files)
        
        success = response.status_code == 200
        if success:
            result = response.json()
            # Should ingest 1, skip 3 (1 empty user_id, 1 invalid amount, 1 wrong tenant)
            expected_pattern = result["ingested"] >= 1 and result["skipped"] >= 3
            details = f"Ingested: {result['ingested']}, Skipped: {result['skipped']}, Errors: {len(result['errors'])}"
            success = success and expected_pattern
        else:
            details = f"Status: {response.status_code}"
        
        self.test_result("Import validation", success, details)
        
        return success
    
    def test_edge_cases(self):
        """Test edge cases and boundary conditions."""
        self.log("Testing edge cases...", Colors.CYAN)
        
        # Test very large amount
        large_amount_data = {
            "user_id": "edge_case_user",
            "product_category": "expensive",
            "amount": "999999.99",  # Maximum allowed
            "currency": "USD"
        }
        
        response = self.make_request("POST", "/v1/transactions", "tenant_1", large_amount_data)
        success_large = response.status_code == 201
        
        if success_large:
            self.created_transactions["tenant_1"].append(response.json()["id"])
            details = "Large amount accepted"
        else:
            details = f"Status: {response.status_code}"
        
        self.test_result("Large amount handling", success_large, details)
        
        # Test currency normalization
        currency_data = {
            "user_id": "currency_test_user",
            "product_category": "currency_test",
            "amount": "50.00",
            "currency": "eur"  # Lowercase, should be normalized to EUR
        }
        
        response = self.make_request("POST", "/v1/transactions", "tenant_1", currency_data)
        success_currency = response.status_code == 201
        
        if success_currency:
            created = response.json()
            normalized_currency = created["currency"]
            is_uppercase = normalized_currency == "EUR"
            details = f"Currency normalized to: {normalized_currency} (correct: {is_uppercase})"
            success_currency = is_uppercase
            self.created_transactions["tenant_1"].append(created["id"])
        else:
            details = f"Status: {response.status_code}"
        
        self.test_result("Currency normalization", success_currency, details)
        
        return success_large and success_currency
    
    def test_performance_and_limits(self):
        """Test performance and limits."""
        self.log("Testing performance and limits...", Colors.CYAN)
        
        # Test pagination limits (should reject limits > 100 with 422)
        response = self.make_request("GET", "/v1/transactions", "tenant_1", 
                                   params={"limit": 150})  # Above max of 100
        success_limit = response.status_code == 422  # Should reject invalid limit
        
        if success_limit:
            details = "Correctly rejected limit > 100 with 422"
        else:
            details = f"Expected 422 for limit > 100, got {response.status_code}"
        
        # Test valid limit
        response = self.make_request("GET", "/v1/transactions", "tenant_1", 
                                   params={"limit": 50})  # Valid limit
        success_valid_limit = response.status_code == 200
        
        if success_valid_limit:
            transactions = response.json()
            details += f" | Valid limit (50): got {len(transactions)} transactions"
        else:
            details += f" | Valid limit failed: {response.status_code}"
            success_limit = False
        
        self.test_result("Pagination limits", success_limit, details)
        
        # Test response time for metrics (should be fast)
        start_time = time.time()
        response = self.make_request("GET", "/v1/metrics/summary", "tenant_1")
        response_time = (time.time() - start_time) * 1000  # Convert to ms
        
        success_performance = response.status_code == 200 and response_time < 1000  # Under 1 second
        details = f"Response time: {response_time:.2f}ms (good: {response_time < 1000})"
        self.test_result("Metrics performance", success_performance, details)
        
        return success_limit and success_valid_limit and success_performance
    
    def cleanup_test_data(self):
        """Clean up created test data."""
        self.log("Cleaning up test data...", Colors.YELLOW)
        
        cleanup_count = 0
        for tenant_key, transaction_ids in self.created_transactions.items():
            for transaction_id in transaction_ids:
                try:
                    response = self.make_request("DELETE", f"/v1/transactions/{transaction_id}", tenant_key)
                    if response.status_code == 204:
                        cleanup_count += 1
                except:
                    pass  # Ignore cleanup errors
        
        self.log(f"Cleaned up {cleanup_count} test transactions", Colors.YELLOW)
    
    def run_all_tests(self):
        """Run all tests and display summary."""
        self.log("Starting comprehensive API testing...", Colors.BOLD + Colors.BLUE)
        self.log(f"Testing against: {self.base_url}", Colors.BLUE)
        
        print(f"\n{Colors.BOLD}{'='*80}{Colors.END}")
        print(f"{Colors.BOLD}{Colors.BLUE}  FastAPI Multi-Tenant Transaction System - API Test Suite  {Colors.END}")
        print(f"{Colors.BOLD}{'='*80}{Colors.END}\n")
        
        # Check if server is reachable
        try:
            response = requests.get(f"{self.base_url}/v1/health", timeout=5)
            if response.status_code != 200:
                self.log(f"Server not reachable at {self.base_url}", Colors.RED, "ERROR")
                return False
        except requests.exceptions.RequestException:
            self.log(f"Cannot connect to server at {self.base_url}", Colors.RED, "ERROR")
            self.log("Make sure the server is running with: uvicorn app.main:app --host 0.0.0.0 --port 8000", Colors.YELLOW)
            return False
        
        # Run all test categories
        test_categories = [
            ("Health Endpoint", self.test_health_endpoint),
            ("Tenant Validation", self.test_tenant_validation),
            ("Transaction CRUD", self.test_transaction_crud),
            ("Tenant Isolation", self.test_tenant_isolation),
            ("Data Import", self.test_data_import),
            ("Metrics & Analytics", self.test_metrics_and_analytics),
            ("Date Range Validation", self.test_date_range_validation),
            ("Error Handling", self.test_error_handling),
            ("Edge Cases", self.test_edge_cases),
            ("Performance & Limits", self.test_performance_and_limits),
        ]
        
        category_results = []
        
        for category_name, test_func in test_categories:
            print(f"\n{Colors.PURPLE}🧪 {category_name}{Colors.END}")
            print("-" * 50)
            
            try:
                result = test_func()
                category_results.append((category_name, result))
            except Exception as e:
                self.log(f"Test category failed with exception: {e}", Colors.RED, "ERROR")
                category_results.append((category_name, False))
        
        # Cleanup
        print(f"\n{Colors.YELLOW}🧹 Cleanup{Colors.END}")
        print("-" * 50)
        self.cleanup_test_data()
        
        # Display summary
        self.display_summary(category_results)
        
        # Return overall success
        return all(result for _, result in category_results)
    
    def display_summary(self, category_results: List[tuple]):
        """Display test summary."""
        print(f"\n{Colors.BOLD}{'='*80}{Colors.END}")
        print(f"{Colors.BOLD}{Colors.BLUE}                           TEST SUMMARY                           {Colors.END}")
        print(f"{Colors.BOLD}{'='*80}{Colors.END}")
        
        # Category summary
        total_categories = len(category_results)
        passed_categories = sum(1 for _, result in category_results if result)
        
        print(f"\n{Colors.BOLD}📊 Category Results:{Colors.END}")
        for category, result in category_results:
            status = f"{Colors.GREEN}✅ PASS" if result else f"{Colors.RED}❌ FAIL"
            print(f"  {status}{Colors.END} {category}")
        
        # Individual test summary
        total_tests = len(self.test_results)
        passed_tests = sum(1 for _, success, _ in self.test_results if success)
        
        print(f"\n{Colors.BOLD}🧪 Individual Test Results:{Colors.END}")
        print(f"  Total Tests: {total_tests}")
        print(f"  Passed: {Colors.GREEN}{passed_tests}{Colors.END}")
        print(f"  Failed: {Colors.RED}{total_tests - passed_tests}{Colors.END}")
        print(f"  Success Rate: {Colors.GREEN if passed_tests == total_tests else Colors.YELLOW}{(passed_tests/total_tests)*100:.1f}%{Colors.END}")
        
        # Overall result
        overall_success = passed_categories == total_categories
        overall_status = f"{Colors.GREEN}🎉 ALL TESTS PASSED!" if overall_success else f"{Colors.RED}❌ SOME TESTS FAILED"
        
        print(f"\n{Colors.BOLD}🏆 Overall Result:{Colors.END}")
        print(f"  {overall_status}{Colors.END}")
        
        if overall_success:
            print(f"\n{Colors.GREEN}{Colors.BOLD}✨ The FastAPI Multi-Tenant Transaction System is working perfectly!{Colors.END}")
            print(f"{Colors.GREEN}   All core functionality verified:{Colors.END}")
            print(f"{Colors.GREEN}   • Multi-tenant isolation ✓{Colors.END}")
            print(f"{Colors.GREEN}   • Transaction CRUD ✓{Colors.END}")
            print(f"{Colors.GREEN}   • Data import (CSV/JSON) ✓{Colors.END}")
            print(f"{Colors.GREEN}   • Analytics & metrics ✓{Colors.END}")
            print(f"{Colors.GREEN}   • Error handling ✓{Colors.END}")
            print(f"{Colors.GREEN}   • Security & validation ✓{Colors.END}")
        else:
            print(f"\n{Colors.RED}❌ Some functionality needs attention. Check the failed tests above.{Colors.END}")
        
        print(f"\n{Colors.BOLD}{'='*80}{Colors.END}")


def main():
    """Main function to run the test suite."""
    parser = argparse.ArgumentParser(description="Test FastAPI Multi-Tenant Transaction System")
    parser.add_argument("--base-url", default="http://localhost:8000", 
                       help="Base URL of the API (default: http://localhost:8000)")
    
    args = parser.parse_args()
    
    tester = APITester(args.base_url)
    success = tester.run_all_tests()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
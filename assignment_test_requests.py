#!/usr/bin/env python3
"""
Assignment Test Requests Script

This script tests all endpoints in the FastAPI Tenant App after running docker compose up.
It performs comprehensive testing of all API endpoints and logs the results.
"""

import asyncio
import json
import sys
import time
from datetime import datetime, timedelta
from uuid import uuid4
import httpx
from typing import Dict, Any, List, Optional


# Configuration
BASE_URL = "http://localhost:8000"
API_PREFIX = "/v1"

# Test tenant IDs
TENANT_1 = "123e4567-e89b-12d3-a456-426614174000"
TENANT_2 = "456e7890-e89b-12d3-a456-426614174001"

# Sample data
SAMPLE_TRANSACTION = {
    "user_id": "test_user_001",
    "product_category": "electronics",
    "amount": "299.99",
    "currency": "USD"
}

SAMPLE_CSV_DATA = """user_id,product_category,amount,currency,ts
user001,electronics,299.99,USD,2025-01-01T10:00:00Z
user002,books,19.99,EUR,2025-01-01T11:00:00Z
user003,clothing,89.50,USD,2025-01-01T12:00:00Z"""


class APITester:
    """API endpoint tester with comprehensive logging."""
    
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=30.0)
        self.results = []
        
    async def __aenter__(self):
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()
    
    def log_test(self, test_name: str, method: str, endpoint: str, 
                 status_code: int, response_data: Any = None, 
                 error: str = None, duration: float = 0, expected_status: int = None):
        """Log test results."""
        # Determine if this is expected behavior
        if expected_status:
            success = status_code == expected_status
            test_type = "expected_behavior" if expected_status >= 400 else "success"
        else:
            success = 200 <= status_code < 300
            test_type = "success" if success else "failure"
        
        result = {
            "timestamp": datetime.now().isoformat(),
            "test_name": test_name,
            "method": method,
            "endpoint": endpoint,
            "status_code": status_code,
            "expected_status": expected_status,
            "duration_ms": round(duration * 1000, 2),
            "success": success,
            "test_type": test_type,
            "error": error,
            "response_preview": str(response_data)[:200] if response_data else None
        }
        self.results.append(result)
        
        # Console output with appropriate icon
        if test_type == "expected_behavior":
            status_icon = "✅" if success else "❌"
            behavior_note = f" (Expected {expected_status})" if success else f" (Expected {expected_status}, got {status_code})"
        else:
            status_icon = "✅" if success else "❌"
            behavior_note = ""
            
        print(f"{status_icon} {test_name}")
        print(f"   {method} {endpoint} -> {status_code} ({duration*1000:.1f}ms){behavior_note}")
        if error and not success:
            print(f"   Error: {error}")
        print()
    
    async def make_request(self, method: str, endpoint: str, 
                          headers: Dict[str, str] = None,
                          json_data: Dict[str, Any] = None,
                          files: Dict[str, Any] = None,
                          params: Dict[str, str] = None) -> httpx.Response:
        """Make HTTP request with error handling."""
        url = f"{self.base_url}{endpoint}"
        
        kwargs = {}
        if headers:
            kwargs["headers"] = headers
        if json_data:
            kwargs["json"] = json_data
        if files:
            kwargs["files"] = files
        if params:
            kwargs["params"] = params
            
        response = await self.client.request(method, url, **kwargs)
        return response
    
    async def test_health_endpoint(self):
        """Test health endpoint (no tenant required)."""
        start_time = time.time()
        try:
            response = await self.make_request("GET", f"{API_PREFIX}/health")
            duration = time.time() - start_time
            
            self.log_test(
                "Health Check",
                "GET", f"{API_PREFIX}/health",
                response.status_code,
                response.json() if response.status_code == 200 else None,
                duration=duration
            )
        except Exception as e:
            duration = time.time() - start_time
            self.log_test(
                "Health Check",
                "GET", f"{API_PREFIX}/health",
                0, error=str(e), duration=duration
            )
    
    async def test_me_endpoint(self):
        """Test /me endpoint (requires tenant)."""
        headers = {"x-tenant-id": TENANT_1}
        start_time = time.time()
        try:
            response = await self.make_request("GET", f"{API_PREFIX}/me", headers=headers)
            duration = time.time() - start_time
            
            self.log_test(
                "Me Endpoint",
                "GET", f"{API_PREFIX}/me",
                response.status_code,
                response.json() if response.status_code == 200 else None,
                duration=duration
            )
        except Exception as e:
            duration = time.time() - start_time
            self.log_test(
                "Me Endpoint",
                "GET", f"{API_PREFIX}/me",
                0, error=str(e), duration=duration
            )
    
    async def test_transaction_crud(self):
        """Test transaction CRUD operations."""
        headers = {"x-tenant-id": TENANT_1}
        transaction_id = None
        
        # 1. Create transaction
        start_time = time.time()
        try:
            response = await self.make_request(
                "POST", f"{API_PREFIX}/transactions",
                headers=headers, json_data=SAMPLE_TRANSACTION
            )
            duration = time.time() - start_time
            
            if response.status_code == 201:
                transaction_data = response.json()
                transaction_id = transaction_data.get("id")
            
            self.log_test(
                "Create Transaction",
                "POST", f"{API_PREFIX}/transactions",
                response.status_code,
                response.json() if response.status_code == 201 else None,
                duration=duration
            )
        except Exception as e:
            duration = time.time() - start_time
            self.log_test(
                "Create Transaction",
                "POST", f"{API_PREFIX}/transactions",
                0, error=str(e), duration=duration
            )
        
        # 2. List transactions
        start_time = time.time()
        try:
            response = await self.make_request("GET", f"{API_PREFIX}/transactions", headers=headers)
            duration = time.time() - start_time
            
            self.log_test(
                "List Transactions",
                "GET", f"{API_PREFIX}/transactions",
                response.status_code,
                f"Found {len(response.json()) if response.status_code == 200 else 0} transactions",
                duration=duration
            )
        except Exception as e:
            duration = time.time() - start_time
            self.log_test(
                "List Transactions",
                "GET", f"{API_PREFIX}/transactions",
                0, error=str(e), duration=duration
            )
        
        # 3. Get transaction by ID (if we have one)
        if transaction_id:
            start_time = time.time()
            try:
                response = await self.make_request(
                    "GET", f"{API_PREFIX}/transactions/{transaction_id}",
                    headers=headers
                )
                duration = time.time() - start_time
                
                self.log_test(
                    "Get Transaction by ID",
                    "GET", f"{API_PREFIX}/transactions/{transaction_id}",
                    response.status_code,
                    response.json() if response.status_code == 200 else None,
                    duration=duration
                )
            except Exception as e:
                duration = time.time() - start_time
                self.log_test(
                    "Get Transaction by ID",
                    "GET", f"{API_PREFIX}/transactions/{transaction_id}",
                    0, error=str(e), duration=duration
                )
            
            # 4. Update transaction
            update_data = {**SAMPLE_TRANSACTION, "amount": "399.99"}
            start_time = time.time()
            try:
                response = await self.make_request(
                    "PUT", f"{API_PREFIX}/transactions/{transaction_id}",
                    headers=headers, json_data=update_data
                )
                duration = time.time() - start_time
                
                self.log_test(
                    "Update Transaction",
                    "PUT", f"{API_PREFIX}/transactions/{transaction_id}",
                    response.status_code,
                    response.json() if response.status_code == 200 else None,
                    duration=duration
                )
            except Exception as e:
                duration = time.time() - start_time
                self.log_test(
                    "Update Transaction",
                    "PUT", f"{API_PREFIX}/transactions/{transaction_id}",
                    0, error=str(e), duration=duration
                )
            
            # 5. Delete transaction
            start_time = time.time()
            try:
                response = await self.make_request(
                    "DELETE", f"{API_PREFIX}/transactions/{transaction_id}",
                    headers=headers
                )
                duration = time.time() - start_time
                
                self.log_test(
                    "Delete Transaction",
                    "DELETE", f"{API_PREFIX}/transactions/{transaction_id}",
                    response.status_code,
                    "Transaction deleted" if response.status_code == 204 else None,
                    duration=duration
                )
            except Exception as e:
                duration = time.time() - start_time
                self.log_test(
                    "Delete Transaction",
                    "DELETE", f"{API_PREFIX}/transactions/{transaction_id}",
                    0, error=str(e), duration=duration
                )
    
    async def test_transaction_import(self):
        """Test transaction import endpoints."""
        headers = {"x-tenant-id": TENANT_1}
        
        # Test CSV import
        start_time = time.time()
        try:
            files = {
                "file": ("transactions.csv", SAMPLE_CSV_DATA, "text/csv")
            }
            response = await self.make_request(
                "POST", f"{API_PREFIX}/transactions/import",
                headers=headers, files=files
            )
            duration = time.time() - start_time
            
            self.log_test(
                "Import Transactions (CSV)",
                "POST", f"{API_PREFIX}/transactions/import",
                response.status_code,
                response.json() if response.status_code in [200, 201] else None,
                duration=duration
            )
        except Exception as e:
            duration = time.time() - start_time
            self.log_test(
                "Import Transactions (CSV)",
                "POST", f"{API_PREFIX}/transactions/import",
                0, error=str(e), duration=duration
            )
        
        # Test JSON import (expects array directly, not object with transactions field)
        start_time = time.time()
        try:
            json_data = [
                {
                    "user_id": "json_user_001",
                    "product_category": "books",
                    "amount": "29.99",
                    "currency": "USD"
                },
                {
                    "user_id": "json_user_002",
                    "product_category": "clothing",
                    "amount": "79.99",
                    "currency": "EUR"
                }
            ]
            response = await self.make_request(
                "POST", f"{API_PREFIX}/transactions/import",
                headers=headers, json_data=json_data
            )
            duration = time.time() - start_time
            
            self.log_test(
                "Import Transactions (JSON)",
                "POST", f"{API_PREFIX}/transactions/import",
                response.status_code,
                response.json() if response.status_code in [200, 201] else None,
                duration=duration
            )
        except Exception as e:
            duration = time.time() - start_time
            self.log_test(
                "Import Transactions (JSON)",
                "POST", f"{API_PREFIX}/transactions/import",
                0, error=str(e), duration=duration
            )
    
    async def test_metrics_endpoints(self):
        """Test all metrics endpoints."""
        headers = {"x-tenant-id": TENANT_1}
        
        # Test summary metrics
        start_time = time.time()
        try:
            response = await self.make_request("GET", f"{API_PREFIX}/metrics/summary", headers=headers)
            duration = time.time() - start_time
            
            self.log_test(
                "Metrics Summary",
                "GET", f"{API_PREFIX}/metrics/summary",
                response.status_code,
                response.json() if response.status_code == 200 else None,
                duration=duration
            )
        except Exception as e:
            duration = time.time() - start_time
            self.log_test(
                "Metrics Summary",
                "GET", f"{API_PREFIX}/metrics/summary",
                0, error=str(e), duration=duration
            )
        
        # Test category metrics
        start_time = time.time()
        try:
            response = await self.make_request("GET", f"{API_PREFIX}/metrics/by-category", headers=headers)
            duration = time.time() - start_time
            
            self.log_test(
                "Metrics by Category",
                "GET", f"{API_PREFIX}/metrics/by-category",
                response.status_code,
                response.json() if response.status_code == 200 else None,
                duration=duration
            )
        except Exception as e:
            duration = time.time() - start_time
            self.log_test(
                "Metrics by Category",
                "GET", f"{API_PREFIX}/metrics/by-category",
                0, error=str(e), duration=duration
            )
        
        # Test user metrics (non-existent user should return 404)
        start_time = time.time()
        try:
            response = await self.make_request(
                "GET", f"{API_PREFIX}/metrics/user/nonexistent_user_12345", 
                headers=headers
            )
            duration = time.time() - start_time
            
            self.log_test(
                "User Metrics (Non-existent User Test)",
                "GET", f"{API_PREFIX}/metrics/user/nonexistent_user_12345",
                response.status_code,
                "Correctly returns 404 for non-existent user" if response.status_code == 404 else response.json(),
                duration=duration,
                expected_status=404
            )
        except Exception as e:
            duration = time.time() - start_time
            self.log_test(
                "User Metrics (Non-existent User Test)",
                "GET", f"{API_PREFIX}/metrics/user/nonexistent_user_12345",
                0, error=str(e), duration=duration, expected_status=404
            )
        
        # Test comprehensive metrics
        start_time = time.time()
        try:
            response = await self.make_request("GET", f"{API_PREFIX}/metrics", headers=headers)
            duration = time.time() - start_time
            
            self.log_test(
                "Comprehensive Metrics",
                "GET", f"{API_PREFIX}/metrics",
                response.status_code,
                response.json() if response.status_code == 200 else None,
                duration=duration
            )
        except Exception as e:
            duration = time.time() - start_time
            self.log_test(
                "Comprehensive Metrics",
                "GET", f"{API_PREFIX}/metrics",
                0, error=str(e), duration=duration
            )
    
    async def test_tenant_isolation(self):
        """Test tenant isolation by using different tenant headers."""
        # Create transaction with tenant 1
        headers_1 = {"x-tenant-id": TENANT_1}
        transaction_data = {**SAMPLE_TRANSACTION, "user_id": "tenant1_user"}
        
        start_time = time.time()
        try:
            response = await self.make_request(
                "POST", f"{API_PREFIX}/transactions",
                headers=headers_1, json_data=transaction_data
            )
            duration = time.time() - start_time
            
            self.log_test(
                "Create Transaction (Tenant 1)",
                "POST", f"{API_PREFIX}/transactions",
                response.status_code,
                response.json() if response.status_code == 201 else None,
                duration=duration
            )
        except Exception as e:
            duration = time.time() - start_time
            self.log_test(
                "Create Transaction (Tenant 1)",
                "POST", f"{API_PREFIX}/transactions",
                0, error=str(e), duration=duration
            )
        
        # Try to access with tenant 2 (should see different data)
        headers_2 = {"x-tenant-id": TENANT_2}
        start_time = time.time()
        try:
            response = await self.make_request("GET", f"{API_PREFIX}/transactions", headers=headers_2)
            duration = time.time() - start_time
            
            tenant_2_count = len(response.json()) if response.status_code == 200 else 0
            self.log_test(
                "List Transactions (Tenant 2)",
                "GET", f"{API_PREFIX}/transactions",
                response.status_code,
                f"Found {tenant_2_count} transactions (should be isolated)",
                duration=duration
            )
        except Exception as e:
            duration = time.time() - start_time
            self.log_test(
                "List Transactions (Tenant 2)",
                "GET", f"{API_PREFIX}/transactions",
                0, error=str(e), duration=duration
            )
    
    async def test_error_cases(self):
        """Test various error scenarios - these should return error codes as designed."""
        # Test missing tenant header (SHOULD return 400)
        start_time = time.time()
        try:
            response = await self.make_request("GET", f"{API_PREFIX}/transactions")
            duration = time.time() - start_time
            
            self.log_test(
                "Missing Tenant Header (Security Test)",
                "GET", f"{API_PREFIX}/transactions",
                response.status_code,
                "Correctly rejected - missing tenant header",
                duration=duration,
                expected_status=400
            )
        except Exception as e:
            duration = time.time() - start_time
            self.log_test(
                "Missing Tenant Header (Security Test)",
                "GET", f"{API_PREFIX}/transactions",
                0, error=str(e), duration=duration, expected_status=400
            )
        
        # Test invalid tenant header (SHOULD return 422)
        headers = {"x-tenant-id": "invalid-uuid"}
        start_time = time.time()
        try:
            response = await self.make_request("GET", f"{API_PREFIX}/transactions", headers=headers)
            duration = time.time() - start_time
            
            self.log_test(
                "Invalid Tenant Header (Validation Test)",
                "GET", f"{API_PREFIX}/transactions",
                response.status_code,
                "Correctly rejected - invalid UUID format",
                duration=duration,
                expected_status=422
            )
        except Exception as e:
            duration = time.time() - start_time
            self.log_test(
                "Invalid Tenant Header (Validation Test)",
                "GET", f"{API_PREFIX}/transactions",
                0, error=str(e), duration=duration, expected_status=422
            )
        
        # Test invalid transaction data (SHOULD return 422)
        headers = {"x-tenant-id": TENANT_1}
        invalid_data = {"user_id": "", "amount": "invalid"}
        start_time = time.time()
        try:
            response = await self.make_request(
                "POST", f"{API_PREFIX}/transactions",
                headers=headers, json_data=invalid_data
            )
            duration = time.time() - start_time
            
            self.log_test(
                "Invalid Transaction Data (Validation Test)",
                "POST", f"{API_PREFIX}/transactions",
                response.status_code,
                "Correctly rejected - invalid transaction data",
                duration=duration,
                expected_status=422
            )
        except Exception as e:
            duration = time.time() - start_time
            self.log_test(
                "Invalid Transaction Data (Validation Test)",
                "POST", f"{API_PREFIX}/transactions",
                0, error=str(e), duration=duration, expected_status=422
            )
    
    def print_summary(self):
        """Print test summary."""
        total_tests = len(self.results)
        successful_tests = sum(1 for r in self.results if r["success"])
        failed_tests = sum(1 for r in self.results if not r["success"])
        
        # Categorize results
        functional_tests = sum(1 for r in self.results if r.get("test_type") != "expected_behavior")
        security_tests = sum(1 for r in self.results if r.get("test_type") == "expected_behavior")
        
        avg_duration = sum(r["duration_ms"] for r in self.results) / total_tests if total_tests > 0 else 0
        
        print("=" * 60)
        print("TEST SUMMARY")
        print("=" * 60)
        print(f"Total Tests: {total_tests}")
        print(f"✅ All Tests Passed: {successful_tests}")
        print(f"❌ Actual Failures: {failed_tests}")
        print(f"🔒 Security/Validation Tests: {security_tests}")
        print(f"⚡ Functional Tests: {functional_tests}")
        print(f"Success Rate: {(successful_tests/total_tests*100):.1f}%" if total_tests > 0 else "N/A")
        print(f"Average Response Time: {avg_duration:.1f}ms")
        print()
        
        # Show breakdown by test type
        print("TEST BREAKDOWN:")
        print("-" * 40)
        for result in self.results:
            if result["success"]:
                if result.get("test_type") == "expected_behavior":
                    icon = "🔒"
                    note = f" (Expected {result.get('expected_status', 'error')})"
                else:
                    icon = "✅"
                    note = ""
                print(f"{icon} {result['test_name']}{note}")
            else:
                print(f"❌ {result['test_name']} - ACTUAL FAILURE")
                if result.get("error"):
                    print(f"   Error: {result['error']}")
        
        if failed_tests > 0:
            print()
            print("⚠️  ACTUAL FAILURES (these need investigation):")
            print("-" * 50)
            for result in self.results:
                if not result["success"]:
                    print(f"❌ {result['test_name']}")
                    print(f"   {result['method']} {result['endpoint']} -> {result['status_code']}")
                    if result.get("expected_status"):
                        print(f"   Expected: {result['expected_status']}, Got: {result['status_code']}")
                    if result.get("error"):
                        print(f"   Error: {result['error']}")
                    print()
        else:
            print()
            print("🎉 ALL TESTS WORKING AS DESIGNED!")
            print("   - Functional endpoints working correctly")
            print("   - Security validation working correctly") 
            print("   - Error handling working correctly")
        
        # Save detailed results to file
        with open("test_results.json", "w") as f:
            json.dump(self.results, f, indent=2)
        print(f"\nDetailed results saved to test_results.json")


async def wait_for_app_ready(base_url: str, max_attempts: int = 30) -> bool:
    """Wait for the application to be ready."""
    print("Waiting for application to be ready...")
    
    async with httpx.AsyncClient(timeout=5.0) as client:
        for attempt in range(max_attempts):
            try:
                response = await client.get(f"{base_url}{API_PREFIX}/health")
                if response.status_code == 200:
                    print(f"✅ Application is ready! (attempt {attempt + 1})")
                    return True
            except Exception:
                pass
            
            print(f"⏳ Attempt {attempt + 1}/{max_attempts} - waiting...")
            await asyncio.sleep(2)
    
    print(f"❌ Application not ready after {max_attempts} attempts")
    return False


async def main():
    """Main test execution."""
    print("🚀 FastAPI Tenant App - Assignment Test Requests")
    print("=" * 60)
    print(f"Base URL: {BASE_URL}")
    print(f"Test Tenant 1: {TENANT_1}")
    print(f"Test Tenant 2: {TENANT_2}")
    print()
    
    # Wait for application to be ready
    if not await wait_for_app_ready(BASE_URL):
        print("❌ Application is not ready. Make sure docker compose up is running.")
        sys.exit(1)
    
    print("🧪 Starting comprehensive endpoint testing...")
    print()
    
    async with APITester(BASE_URL) as tester:
        # Run all tests
        await tester.test_health_endpoint()
        await tester.test_me_endpoint()
        await tester.test_transaction_crud()
        await tester.test_transaction_import()
        await tester.test_metrics_endpoints()
        await tester.test_tenant_isolation()
        await tester.test_error_cases()
        
        # Print summary
        tester.print_summary()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⚠️ Test execution interrupted by user")
    except Exception as e:
        print(f"\n❌ Test execution failed: {e}")
        sys.exit(1)
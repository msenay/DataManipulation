"""Test configuration and fixtures."""
import asyncio
from typing import AsyncGenerator, Generator
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import AsyncSessionLocal
from app.main import app

# Test tenant UUIDs
TENANT_1 = UUID("123e4567-e89b-12d3-a456-426614174000")
TENANT_2 = UUID("456e7890-e89b-12d3-a456-426614174001") 
TENANT_3 = UUID("789e0123-e89b-12d3-a456-426614174002")

# Test database URL (in-memory SQLite)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def test_engine():
    """Create test database engine."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
        echo=False
    )
    
    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    # Clean up
    await engine.dispose()


@pytest.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a fresh database session for each test."""
    async with AsyncSessionLocal.begin() as session:
        yield session
        await session.rollback()


@pytest.fixture
def client() -> TestClient:
    """Create FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def tenant_headers():
    """Return headers for different tenants."""
    return {
        "tenant_1": {"x-tenant-id": str(TENANT_1)},
        "tenant_2": {"x-tenant-id": str(TENANT_2)},
        "tenant_3": {"x-tenant-id": str(TENANT_3)},
    }


@pytest.fixture
def sample_transaction_data():
    """Return sample transaction data for testing."""
    return {
        "valid": {
            "user_id": "test_user_001",
            "product_category": "electronics",
            "amount": "199.99",
            "currency": "USD"
        },
        "invalid_amount": {
            "user_id": "test_user_001", 
            "product_category": "electronics",
            "amount": "invalid",
            "currency": "USD"
        },
        "missing_fields": {
            "user_id": "test_user_001"
        },
        "empty_user_id": {
            "user_id": "",
            "product_category": "electronics", 
            "amount": "199.99",
            "currency": "USD"
        },
        "invalid_currency": {
            "user_id": "test_user_001",
            "product_category": "electronics",
            "amount": "199.99", 
            "currency": "INVALID"
        }
    }


@pytest.fixture
def sample_csv_data():
    """Return sample CSV data for import testing."""
    return {
        "valid": """user_id,product_category,amount,currency,ts
user001,electronics,299.99,USD,2025-01-01T10:00:00Z
user002,books,19.99,EUR,2025-01-01T11:00:00Z
user003,clothing,89.50,USD,2025-01-01T12:00:00Z""",
        
        "mixed_tenants": f"""user_id,product_category,amount,currency,tenant_id
user001,electronics,299.99,USD,{TENANT_1}
user002,books,19.99,EUR,{TENANT_2}
user003,clothing,89.50,USD,{TENANT_1}""",
        
        "with_errors": """user_id,product_category,amount,currency
user001,electronics,299.99,USD
,books,19.99,EUR
user003,clothing,invalid,USD
user004,electronics,99.99,TOOLONG""",
        
        "empty": """user_id,product_category,amount,currency
""",
        
        "no_headers": """user001,electronics,299.99,USD
user002,books,19.99,EUR"""
    }
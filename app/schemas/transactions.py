"""Transaction schemas for request/response validation."""
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.logging import get_logger

logger = get_logger(__name__)


class TransactionCreate(BaseModel):
    """Schema for creating a new transaction."""
    
    # Optional tenant_id - will be validated against header if present
    tenant_id: Optional[UUID] = Field(None, description="Tenant ID (will be set from header if not provided)")
    
    # Required transaction fields
    user_id: str = Field(..., min_length=1, max_length=255, description="User identifier")
    product_category: str = Field(..., min_length=1, max_length=255, description="Product category")
    amount: Decimal = Field(..., decimal_places=2, description="Transaction amount")
    currency: str = Field(..., min_length=3, max_length=3, description="Currency code (ISO 4217)")
    ts: Optional[datetime] = Field(None, description="Transaction timestamp (UTC, defaults to now)")
    
    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: str) -> str:
        """Validate and normalize currency code."""
        if not v:
            raise ValueError("Currency code is required")
        
        # Convert to uppercase
        currency_upper = v.upper()
        
        # Basic validation - should be 3 characters
        if len(currency_upper) != 3:
            raise ValueError("Currency code must be exactly 3 characters")
        
        # Basic check for valid characters (letters only)
        if not currency_upper.isalpha():
            raise ValueError("Currency code must contain only letters")
        
        return currency_upper
    
    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v: Decimal) -> Decimal:
        """Validate transaction amount."""
        if v is None:
            raise ValueError("Amount is required")
        
        # Ensure it's a Decimal
        if not isinstance(v, Decimal):
            v = Decimal(str(v))
        
        # Check for reasonable bounds
        if v <= 0:
            raise ValueError("Amount must be positive")
        
        if v > Decimal('999999999.99'):
            raise ValueError("Amount too large")
        
        # Ensure proper decimal places
        return v.quantize(Decimal('0.01'))
    
    @field_validator("ts")
    @classmethod
    def validate_timestamp(cls, v: Optional[datetime]) -> Optional[datetime]:
        """Validate timestamp."""
        if v is None:
            return None
        
        # Ensure timezone awareness (convert to UTC if naive)
        if v.tzinfo is None:
            logger.warning("Received naive datetime, assuming UTC")
            v = v.replace(tzinfo=datetime.now().astimezone().tzinfo)
        
        return v

    class Config:
        # Enable JSON schema generation with examples
        json_schema_extra = {
            "example": {
                "user_id": "user123",
                "product_category": "electronics",
                "amount": "199.99",
                "currency": "USD",
                "ts": "2024-01-01T12:00:00Z"
            }
        }


class TransactionOut(BaseModel):
    """Schema for transaction responses."""
    
    id: UUID = Field(..., description="Transaction ID")
    tenant_id: UUID = Field(..., description="Tenant ID")
    user_id: str = Field(..., description="User identifier")
    product_category: str = Field(..., description="Product category")
    amount: Decimal = Field(..., description="Transaction amount")
    currency: str = Field(..., description="Currency code")
    ts: datetime = Field(..., description="Transaction timestamp (UTC)")
    
    class Config:
        from_attributes = True  # Enable ORM mode for SQLAlchemy models
        json_encoders = {
            UUID: str,
            Decimal: str,
            datetime: lambda v: v.isoformat() if v else None,
        }
        json_schema_extra = {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "tenant_id": "123e4567-e89b-12d3-a456-426614174001",
                "user_id": "user123",
                "product_category": "electronics",
                "amount": "199.99",
                "currency": "USD",
                "ts": "2024-01-01T12:00:00Z"
            }
        }


class TransactionUpdate(BaseModel):
    """Schema for updating a transaction."""
    
    # All fields optional for partial updates
    user_id: Optional[str] = Field(None, min_length=1, max_length=255)
    product_category: Optional[str] = Field(None, min_length=1, max_length=255)
    amount: Optional[Decimal] = Field(None, decimal_places=2)
    currency: Optional[str] = Field(None, min_length=3, max_length=3)
    ts: Optional[datetime] = None
    
    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: Optional[str]) -> Optional[str]:
        """Validate and normalize currency code."""
        if v is None:
            return None
        return TransactionCreate.validate_currency(v)
    
    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        """Validate transaction amount."""
        if v is None:
            return None
        return TransactionCreate.validate_amount(v)
    
    @field_validator("ts")
    @classmethod
    def validate_timestamp(cls, v: Optional[datetime]) -> Optional[datetime]:
        """Validate timestamp."""
        if v is None:
            return None
        return TransactionCreate.validate_timestamp(v)
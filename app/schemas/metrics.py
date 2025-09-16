"""Metrics schemas for transaction summaries and analytics."""
from decimal import Decimal
from typing import Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class TransactionSummary(BaseModel):
    """Summary statistics for transactions."""
    
    total_count: int = Field(..., description="Total number of transactions")
    total_amount: Decimal = Field(..., description="Total transaction amount")
    average_amount: Optional[Decimal] = Field(None, description="Average transaction amount")
    currency: str = Field(..., description="Currency code")
    
    class Config:
        json_encoders = {
            Decimal: str,
        }
        json_schema_extra = {
            "example": {
                "total_count": 150,
                "total_amount": "29999.50",
                "average_amount": "199.99",
                "currency": "USD"
            }
        }


class CategorySummary(BaseModel):
    """Summary by product category."""
    
    category: str = Field(..., description="Product category")
    count: int = Field(..., description="Number of transactions in this category")
    total_amount: Decimal = Field(..., description="Total amount for this category")
    average_amount: Decimal = Field(..., description="Average amount for this category")
    
    class Config:
        json_encoders = {
            Decimal: str,
        }
        json_schema_extra = {
            "example": {
                "category": "electronics",
                "count": 50,
                "total_amount": "9999.50",
                "average_amount": "199.99"
            }
        }


class UserSummary(BaseModel):
    """Summary by user."""
    
    user_id: str = Field(..., description="User identifier")
    count: int = Field(..., description="Number of transactions by this user")
    total_amount: Decimal = Field(..., description="Total amount for this user")
    average_amount: Decimal = Field(..., description="Average amount for this user")
    
    class Config:
        json_encoders = {
            Decimal: str,
        }
        json_schema_extra = {
            "example": {
                "user_id": "user123",
                "count": 25,
                "total_amount": "4999.75",
                "average_amount": "199.99"
            }
        }


class MetricsResponse(BaseModel):
    """Response containing various transaction metrics."""
    
    tenant_id: UUID = Field(..., description="Tenant ID")
    overall: TransactionSummary = Field(..., description="Overall transaction summary")
    by_category: List[CategorySummary] = Field(..., description="Summary by product category")
    by_user: List[UserSummary] = Field(..., description="Summary by user")
    
    class Config:
        json_encoders = {
            UUID: str,
            Decimal: str,
        }
        json_schema_extra = {
            "example": {
                "tenant_id": "123e4567-e89b-12d3-a456-426614174001",
                "overall": {
                    "total_count": 150,
                    "total_amount": "29999.50",
                    "average_amount": "199.99",
                    "currency": "USD"
                },
                "by_category": [
                    {
                        "category": "electronics",
                        "count": 50,
                        "total_amount": "9999.50",
                        "average_amount": "199.99"
                    }
                ],
                "by_user": [
                    {
                        "user_id": "user123",
                        "count": 25,
                        "total_amount": "4999.75",
                        "average_amount": "199.99"
                    }
                ]
            }
        }
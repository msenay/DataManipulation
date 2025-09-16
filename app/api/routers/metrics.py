"""Metrics endpoints for transaction analytics."""
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_tenant
from app.db.session import get_db_session
from app.logging import get_logger
from app.schemas.metrics import CategorySummary, MetricsResponse, TransactionSummary, UserSummary
from app.services import metrics as metrics_service

logger = get_logger(__name__)
router = APIRouter()

# Default metrics window: last 30 days
DEFAULT_METRICS_WINDOW_DAYS = 30


def get_default_date_range() -> tuple[datetime, datetime]:
    """
    Get default date range for metrics (last 30 days UTC).
    
    Returns:
        Tuple of (start_ts, end_ts) for the last 30 days
    """
    now = datetime.now(timezone.utc)
    start_ts = now - timedelta(days=DEFAULT_METRICS_WINDOW_DAYS)
    return start_ts, now


def validate_date_range(start_ts: Optional[datetime], end_ts: Optional[datetime]) -> tuple[datetime, datetime]:
    """
    Validate and normalize date range parameters.
    
    Args:
        start_ts: Optional start timestamp
        end_ts: Optional end timestamp
        
    Returns:
        Tuple of validated (start_ts, end_ts)
        
    Raises:
        HTTPException: If date range is invalid
    """
    # Use defaults if not provided
    if start_ts is None and end_ts is None:
        return get_default_date_range()
    elif start_ts is None:
        # If only end_ts provided, use 30 days before it
        start_ts = end_ts - timedelta(days=DEFAULT_METRICS_WINDOW_DAYS)
    elif end_ts is None:
        # If only start_ts provided, use 30 days after it
        end_ts = start_ts + timedelta(days=DEFAULT_METRICS_WINDOW_DAYS)
    
    # Validate that start_ts <= end_ts
    if start_ts > end_ts:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"start_ts ({start_ts.isoformat()}) must be less than or equal to end_ts ({end_ts.isoformat()})"
        )
    
    return start_ts, end_ts


@router.get("/metrics/summary", response_model=TransactionSummary)
async def get_summary_metrics(
    tenant_id: UUID = Depends(require_tenant),
    session: AsyncSession = Depends(get_db_session),
    start_ts: Optional[datetime] = Query(None, description="Start timestamp filter (ISO 8601, defaults to 30 days ago)"),
    end_ts: Optional[datetime] = Query(None, description="End timestamp filter (ISO 8601, defaults to now)")
):
    """
    Get overall transaction summary metrics.
    
    Returns aggregated transaction data including:
    - Total transaction count
    - Total transaction amount
    - Average transaction amount
    - Primary currency
    
    Date range filtering:
    - If both start_ts and end_ts are omitted: defaults to last 30 days
    - If only one is provided: 30-day window around the provided date
    - If both provided: validates start_ts <= end_ts
    """
    try:
        # Validate and normalize date range
        validated_start_ts, validated_end_ts = validate_date_range(start_ts, end_ts)
        
        summary = await metrics_service.get_transaction_summary(
            session=session,
            tenant_id=tenant_id,
            start_ts=validated_start_ts,
            end_ts=validated_end_ts
        )
        
        logger.info(
            "Summary metrics retrieved",
            extra={
                "tenant_id": str(tenant_id),
                "total_count": summary.total_count,
                "date_range": {
                    "start": validated_start_ts.isoformat(),
                    "end": validated_end_ts.isoformat(),
                    "was_defaulted": start_ts is None and end_ts is None
                }
            }
        )
        
        return summary
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to retrieve summary metrics",
            extra={"tenant_id": str(tenant_id), "error": str(e)}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve summary metrics"
        )


@router.get("/metrics/by-category", response_model=List[CategorySummary])
async def get_category_metrics(
    tenant_id: UUID = Depends(require_tenant),
    session: AsyncSession = Depends(get_db_session),
    start_ts: Optional[datetime] = Query(None, description="Start timestamp filter (ISO 8601, defaults to 30 days ago)"),
    end_ts: Optional[datetime] = Query(None, description="End timestamp filter (ISO 8601, defaults to now)")
):
    """
    Get transaction metrics grouped by product category.
    
    Returns a list of category summaries ordered by total amount (descending):
    - Category name
    - Transaction count
    - Total amount
    - Average amount
    
    Date range filtering:
    - If both start_ts and end_ts are omitted: defaults to last 30 days
    - If only one is provided: 30-day window around the provided date
    - If both provided: validates start_ts <= end_ts
    """
    try:
        # Validate and normalize date range
        validated_start_ts, validated_end_ts = validate_date_range(start_ts, end_ts)
        
        categories = await metrics_service.get_metrics_by_category(
            session=session,
            tenant_id=tenant_id,
            start_ts=validated_start_ts,
            end_ts=validated_end_ts
        )
        
        logger.info(
            "Category metrics retrieved",
            extra={
                "tenant_id": str(tenant_id),
                "category_count": len(categories),
                "date_range": {
                    "start": validated_start_ts.isoformat(),
                    "end": validated_end_ts.isoformat(),
                    "was_defaulted": start_ts is None and end_ts is None
                }
            }
        )
        
        return categories
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to retrieve category metrics",
            extra={"tenant_id": str(tenant_id), "error": str(e)}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve category metrics"
        )


@router.get("/metrics/user/{user_id}", response_model=UserSummary)
async def get_user_metrics(
    user_id: str,
    tenant_id: UUID = Depends(require_tenant),
    session: AsyncSession = Depends(get_db_session)
):
    """
    Get transaction summary for a specific user.
    
    Returns user-specific metrics including:
    - User ID
    - Transaction count
    - Total amount spent
    - Average transaction amount
    
    Returns 404 if user has no transactions in the current tenant.
    """
    try:
        user_summary = await metrics_service.get_user_summary(
            session=session,
            tenant_id=tenant_id,
            user_id=user_id
        )
        
        if not user_summary:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No transactions found for user {user_id}"
            )
        
        logger.info(
            "User metrics retrieved",
            extra={
                "tenant_id": str(tenant_id),
                "user_id": user_id,
                "transaction_count": user_summary.count
            }
        )
        
        return user_summary
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to retrieve user metrics",
            extra={"tenant_id": str(tenant_id), "user_id": user_id, "error": str(e)}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user metrics"
        )


@router.get("/metrics", response_model=MetricsResponse)
async def get_comprehensive_metrics(
    tenant_id: UUID = Depends(require_tenant),
    session: AsyncSession = Depends(get_db_session),
    start_ts: Optional[datetime] = Query(None, description="Start timestamp filter (ISO 8601, defaults to 30 days ago)"),
    end_ts: Optional[datetime] = Query(None, description="End timestamp filter (ISO 8601, defaults to now)")
):
    """
    Get comprehensive metrics including overall summary, category breakdown, and top users.
    
    Returns a complete metrics overview with:
    - Overall transaction summary
    - Breakdown by product category (ordered by total amount)
    - Top users by total spending (limited to top 10)
    
    Date range filtering:
    - If both start_ts and end_ts are omitted: defaults to last 30 days
    - If only one is provided: 30-day window around the provided date
    - If both provided: validates start_ts <= end_ts
    """
    try:
        # Validate and normalize date range
        validated_start_ts, validated_end_ts = validate_date_range(start_ts, end_ts)
        
        metrics = await metrics_service.get_comprehensive_metrics(
            session=session,
            tenant_id=tenant_id,
            start_ts=validated_start_ts,
            end_ts=validated_end_ts
        )
        
        logger.info(
            "Comprehensive metrics retrieved",
            extra={
                "tenant_id": str(tenant_id),
                "category_count": len(metrics.by_category),
                "user_count": len(metrics.by_user),
                "date_range": {
                    "start": validated_start_ts.isoformat(),
                    "end": validated_end_ts.isoformat(),
                    "was_defaulted": start_ts is None and end_ts is None
                }
            }
        )
        
        return metrics
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to retrieve comprehensive metrics",
            extra={"tenant_id": str(tenant_id), "error": str(e)}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve comprehensive metrics"
        )
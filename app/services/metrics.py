"""Metrics service for transaction analytics."""
from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Transaction
from app.logging import get_logger
from app.schemas.metrics import CategorySummary, MetricsResponse, TransactionSummary, UserSummary

logger = get_logger(__name__)


async def get_transaction_summary(
    session: AsyncSession,
    tenant_id: UUID,
    start_ts: Optional[datetime] = None,
    end_ts: Optional[datetime] = None
) -> TransactionSummary:
    """
    Get overall transaction summary for a tenant.
    
    Args:
        session: Database session
        tenant_id: Tenant ID
        start_ts: Optional start timestamp filter
        end_ts: Optional end timestamp filter
        
    Returns:
        TransactionSummary with aggregated data
    """
    # Build query with tenant filter and optional date range
    query = select(
        func.count(Transaction.id).label('total_count'),
        func.sum(Transaction.amount).label('total_amount'),
        func.avg(Transaction.amount).label('average_amount'),
        func.count(func.distinct(Transaction.user_id)).label('distinct_users'),
        Transaction.currency
    ).where(Transaction.tenant_id == tenant_id)
    
    # Add date filters if provided
    if start_ts:
        query = query.where(Transaction.ts >= start_ts)
    if end_ts:
        query = query.where(Transaction.ts <= end_ts)
    
    # Group by currency to handle multi-currency scenarios
    query = query.group_by(Transaction.currency)
    
    result = await session.execute(query)
    rows = result.fetchall()
    
    if not rows:
        # No transactions found
        return TransactionSummary(
            total_count=0,
            total_amount=Decimal('0.00'),
            average_amount=None,
            currency="USD"  # Default currency
        )
    
    # For now, we'll aggregate across all currencies (in production, you might want separate summaries)
    total_count = sum(row.total_count for row in rows)
    total_amount = sum(row.total_amount or Decimal('0.00') for row in rows)
    
    # Calculate average
    average_amount = total_amount / total_count if total_count > 0 else None
    
    # Use the most common currency
    primary_currency = rows[0].currency if rows else "USD"
    
    logger.info(
        "Transaction summary calculated",
        extra={
            "tenant_id": str(tenant_id),
            "total_count": total_count,
            "total_amount": str(total_amount),
            "date_range": {
                "start": start_ts.isoformat() if start_ts else None,
                "end": end_ts.isoformat() if end_ts else None
            }
        }
    )
    
    return TransactionSummary(
        total_count=total_count,
        total_amount=total_amount,
        average_amount=average_amount,
        currency=primary_currency
    )


async def get_metrics_by_category(
    session: AsyncSession,
    tenant_id: UUID,
    start_ts: Optional[datetime] = None,
    end_ts: Optional[datetime] = None
) -> List[CategorySummary]:
    """
    Get transaction metrics grouped by product category.
    
    Args:
        session: Database session
        tenant_id: Tenant ID
        start_ts: Optional start timestamp filter
        end_ts: Optional end timestamp filter
        
    Returns:
        List of CategorySummary ordered by total_amount desc
    """
    # Build query with tenant filter
    query = select(
        Transaction.product_category,
        func.count(Transaction.id).label('count'),
        func.sum(Transaction.amount).label('total_amount'),
        func.avg(Transaction.amount).label('average_amount')
    ).where(Transaction.tenant_id == tenant_id)
    
    # Add date filters if provided
    if start_ts:
        query = query.where(Transaction.ts >= start_ts)
    if end_ts:
        query = query.where(Transaction.ts <= end_ts)
    
    # Group by category and order by total amount descending
    query = query.group_by(Transaction.product_category).order_by(desc('total_amount'))
    
    result = await session.execute(query)
    rows = result.fetchall()
    
    category_summaries = []
    for row in rows:
        category_summaries.append(CategorySummary(
            category=row.product_category,
            count=row.count,
            total_amount=row.total_amount or Decimal('0.00'),
            average_amount=row.average_amount or Decimal('0.00')
        ))
    
    logger.info(
        "Category metrics calculated",
        extra={
            "tenant_id": str(tenant_id),
            "category_count": len(category_summaries),
            "date_range": {
                "start": start_ts.isoformat() if start_ts else None,
                "end": end_ts.isoformat() if end_ts else None
            }
        }
    )
    
    return category_summaries


async def get_user_summary(
    session: AsyncSession,
    tenant_id: UUID,
    user_id: str
) -> Optional[UserSummary]:
    """
    Get transaction summary for a specific user.
    
    Args:
        session: Database session
        tenant_id: Tenant ID
        user_id: User ID to get summary for
        
    Returns:
        UserSummary if user has transactions, None otherwise
    """
    # Query for user-specific metrics
    query = select(
        func.count(Transaction.id).label('count'),
        func.sum(Transaction.amount).label('total_amount'),
        func.avg(Transaction.amount).label('average_amount'),
        func.min(Transaction.ts).label('first_purchase_ts'),
        func.max(Transaction.ts).label('last_purchase_ts')
    ).where(
        and_(
            Transaction.tenant_id == tenant_id,
            Transaction.user_id == user_id
        )
    )
    
    result = await session.execute(query)
    row = result.fetchone()
    
    if not row or row.count == 0:
        logger.info(
            "No transactions found for user",
            extra={"tenant_id": str(tenant_id), "user_id": user_id}
        )
        return None
    
    user_summary = UserSummary(
        user_id=user_id,
        count=row.count,
        total_amount=row.total_amount or Decimal('0.00'),
        average_amount=row.average_amount or Decimal('0.00')
    )
    
    logger.info(
        "User summary calculated",
        extra={
            "tenant_id": str(tenant_id),
            "user_id": user_id,
            "transaction_count": row.count,
            "total_amount": str(row.total_amount or Decimal('0.00'))
        }
    )
    
    return user_summary


async def get_comprehensive_metrics(
    session: AsyncSession,
    tenant_id: UUID,
    start_ts: Optional[datetime] = None,
    end_ts: Optional[datetime] = None
) -> MetricsResponse:
    """
    Get comprehensive metrics including overall summary, by category, and top users.
    
    Args:
        session: Database session
        tenant_id: Tenant ID
        start_ts: Optional start timestamp filter
        end_ts: Optional end timestamp filter
        
    Returns:
        MetricsResponse with all metrics
    """
    # Get overall summary
    overall_summary = await get_transaction_summary(session, tenant_id, start_ts, end_ts)
    
    # Get category breakdown
    category_summaries = await get_metrics_by_category(session, tenant_id, start_ts, end_ts)
    
    # Get top users (limited to top 10)
    user_query = select(
        Transaction.user_id,
        func.count(Transaction.id).label('count'),
        func.sum(Transaction.amount).label('total_amount'),
        func.avg(Transaction.amount).label('average_amount')
    ).where(Transaction.tenant_id == tenant_id)
    
    if start_ts:
        user_query = user_query.where(Transaction.ts >= start_ts)
    if end_ts:
        user_query = user_query.where(Transaction.ts <= end_ts)
    
    user_query = user_query.group_by(Transaction.user_id).order_by(desc('total_amount')).limit(10)
    
    user_result = await session.execute(user_query)
    user_rows = user_result.fetchall()
    
    user_summaries = []
    for row in user_rows:
        user_summaries.append(UserSummary(
            user_id=row.user_id,
            count=row.count,
            total_amount=row.total_amount or Decimal('0.00'),
            average_amount=row.average_amount or Decimal('0.00')
        ))
    
    return MetricsResponse(
        tenant_id=tenant_id,
        overall=overall_summary,
        by_category=category_summaries,
        by_user=user_summaries
    )
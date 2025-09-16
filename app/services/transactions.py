"""Transaction service layer for business logic."""
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import NoResultFound

from app.db.models import Transaction
from app.db.tenancy import get_current_tenant
from app.logging import get_logger
from app.schemas.transactions import TransactionCreate, TransactionOut, TransactionUpdate

logger = get_logger(__name__)


async def create_transaction(
    data: TransactionCreate,
    session: AsyncSession,
    tenant_id: UUID
) -> TransactionOut:
    """
    Create a new transaction.
    
    Args:
        data: Transaction creation data
        session: Database session
        
    Returns:
        Created transaction
        
    Raises:
        ValueError: If tenant_id mismatch
    """
    # Use the passed tenant_id instead of context
    current_tenant = tenant_id
    logger.debug("Service create_transaction - using passed tenant", extra={"tenant_id": str(current_tenant)})
    
    # Validate tenant_id if provided in data
    if data.tenant_id and data.tenant_id != current_tenant:
        logger.error(
            "Tenant ID mismatch in transaction creation",
            extra={
                "provided_tenant": str(data.tenant_id),
                "current_tenant": str(current_tenant)
            }
        )
        raise ValueError(f"Tenant ID mismatch: expected {current_tenant}, got {data.tenant_id}")
    
    # Create transaction object
    transaction = Transaction(
        tenant_id=current_tenant,  # Always use current tenant
        user_id=data.user_id,
        product_category=data.product_category,
        amount=data.amount,
        currency=data.currency,
        ts=data.ts or datetime.utcnow()
    )
    
    session.add(transaction)
    await session.commit()
    await session.refresh(transaction)
    
    logger.info(
        "Transaction created",
        extra={
            "transaction_id": str(transaction.id),
            "tenant_id": str(current_tenant),
            "amount": str(data.amount),
            "currency": data.currency
        }
    )
    
    return TransactionOut.model_validate(transaction)


async def get_transactions(
    session: AsyncSession,
    tenant_id: UUID,
    limit: int = 50,
    offset: int = 0,
    start_ts: Optional[datetime] = None,
    end_ts: Optional[datetime] = None,
    user_id: Optional[str] = None
) -> List[TransactionOut]:
    """
    Get transactions with filtering and pagination.
    
    Args:
        session: Database session
        tenant_id: Tenant ID
        limit: Maximum number of results (capped at 100)
        offset: Number of results to skip
        start_ts: Start timestamp filter
        end_ts: End timestamp filter
        user_id: User ID filter
        
    Returns:
        List of transactions
    """
    current_tenant = tenant_id
    
    # Cap limit to 100
    limit = min(limit, 100)
    
    # Build query with explicit tenant filter
    query = select(Transaction).where(Transaction.tenant_id == current_tenant)
    
    # Add filters
    filters = []
    
    if start_ts:
        filters.append(Transaction.ts >= start_ts)
    
    if end_ts:
        filters.append(Transaction.ts <= end_ts)
    
    if user_id:
        filters.append(Transaction.user_id == user_id)
    
    if filters:
        query = query.where(and_(*filters))
    
    # Order by timestamp descending
    query = query.order_by(desc(Transaction.ts))
    
    # Apply pagination
    query = query.offset(offset).limit(limit)
    
    result = await session.execute(query)
    transactions = result.scalars().all()
    
    logger.info(
        "Transactions retrieved",
        extra={
            "tenant_id": str(current_tenant),
            "count": len(transactions),
            "limit": limit,
            "offset": offset,
            "filters": {
                "start_ts": start_ts.isoformat() if start_ts else None,
                "end_ts": end_ts.isoformat() if end_ts else None,
                "user_id": user_id
            }
        }
    )
    
    return [TransactionOut.model_validate(t) for t in transactions]


async def get_transaction_by_id(
    transaction_id: UUID,
    session: AsyncSession,
    tenant_id: UUID
) -> Optional[TransactionOut]:
    """
    Get a transaction by ID.
    
    Args:
        transaction_id: Transaction ID
        session: Database session
        tenant_id: Tenant ID
        
    Returns:
        Transaction if found, None otherwise
    """
    current_tenant = tenant_id
    
    # Query with explicit tenant filter
    query = select(Transaction).where(
        and_(Transaction.id == transaction_id, Transaction.tenant_id == current_tenant)
    )
    
    result = await session.execute(query)
    transaction = result.scalar_one_or_none()
    
    if transaction:
        logger.info(
            "Transaction retrieved by ID",
            extra={
                "transaction_id": str(transaction_id),
                "tenant_id": str(current_tenant)
            }
        )
        return TransactionOut.model_validate(transaction)
    else:
        logger.info(
            "Transaction not found",
            extra={
                "transaction_id": str(transaction_id),
                "tenant_id": str(current_tenant)
            }
        )
        return None


async def update_transaction(
    transaction_id: UUID,
    data: TransactionUpdate,
    session: AsyncSession,
    tenant_id: UUID
) -> Optional[TransactionOut]:
    """
    Update a transaction.
    
    Args:
        transaction_id: Transaction ID
        data: Update data
        session: Database session
        tenant_id: Tenant ID
        
    Returns:
        Updated transaction if found, None otherwise
    """
    current_tenant = tenant_id
    
    # Get existing transaction (with explicit tenant filter)
    query = select(Transaction).where(
        and_(Transaction.id == transaction_id, Transaction.tenant_id == current_tenant)
    )
    result = await session.execute(query)
    transaction = result.scalar_one_or_none()
    
    if not transaction:
        return None
    
    # Update fields
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(transaction, field, value)
    
    await session.commit()
    await session.refresh(transaction)
    
    logger.info(
        "Transaction updated",
        extra={
            "transaction_id": str(transaction_id),
            "tenant_id": str(current_tenant),
            "updated_fields": list(update_data.keys())
        }
    )
    
    return TransactionOut.model_validate(transaction)


async def delete_transaction(
    transaction_id: UUID,
    session: AsyncSession,
    tenant_id: UUID
) -> bool:
    """
    Delete a transaction.
    
    Args:
        transaction_id: Transaction ID
        session: Database session
        tenant_id: Tenant ID
        
    Returns:
        True if deleted, False if not found
    """
    current_tenant = tenant_id
    
    # Get existing transaction (with explicit tenant filter)
    query = select(Transaction).where(
        and_(Transaction.id == transaction_id, Transaction.tenant_id == current_tenant)
    )
    result = await session.execute(query)
    transaction = result.scalar_one_or_none()
    
    if not transaction:
        return False
    
    await session.delete(transaction)
    await session.commit()
    
    logger.info(
        "Transaction deleted",
        extra={
            "transaction_id": str(transaction_id),
            "tenant_id": str(current_tenant)
        }
    )
    
    return True
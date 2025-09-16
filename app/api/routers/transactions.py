"""Transaction endpoints."""
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_tenant
from app.db.session import get_db_session
from app.logging import get_logger
from app.schemas.transactions import TransactionCreate, TransactionOut, TransactionUpdate
from app.services import transactions as transaction_service

logger = get_logger(__name__)
router = APIRouter()


@router.post("/transactions", response_model=TransactionOut, status_code=status.HTTP_201_CREATED)
async def create_transaction(
    data: TransactionCreate,
    tenant_id: UUID = Depends(require_tenant),
    session: AsyncSession = Depends(get_db_session)
):
    """
    Create a new transaction.
    
    Creates a transaction for the current tenant. The tenant_id in the request
    body is optional and will be validated against the header if provided.
    """
    try:
        return await transaction_service.create_transaction(data, session, tenant_id)
    except ValueError as e:
        logger.error("Transaction creation failed", extra={"error": str(e)})
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )


@router.get("/transactions", response_model=List[TransactionOut])
async def list_transactions(
    tenant_id: UUID = Depends(require_tenant),
    session: AsyncSession = Depends(get_db_session),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    start_ts: Optional[datetime] = Query(None, description="Start timestamp filter (ISO 8601)"),
    end_ts: Optional[datetime] = Query(None, description="End timestamp filter (ISO 8601)"),
    user_id: Optional[str] = Query(None, description="User ID filter")
):
    """
    List transactions with filtering and pagination.
    
    Returns transactions for the current tenant with optional filtering by:
    - Time range (start_ts, end_ts)
    - User ID
    
    Results are ordered by timestamp (newest first) and paginated.
    """
    try:
        return await transaction_service.get_transactions(
            session=session,
            tenant_id=tenant_id,
            limit=limit,
            offset=offset,
            start_ts=start_ts,
            end_ts=end_ts,
            user_id=user_id
        )
    except ValueError as e:
        logger.error("Transaction listing failed", extra={"error": str(e)})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.get("/transactions/{transaction_id}", response_model=TransactionOut)
async def get_transaction(
    transaction_id: UUID,
    tenant_id: UUID = Depends(require_tenant),
    session: AsyncSession = Depends(get_db_session)
):
    """
    Get a transaction by ID.
    
    Returns the transaction if it exists and belongs to the current tenant.
    Returns 404 if not found or doesn't belong to the tenant.
    """
    try:
        transaction = await transaction_service.get_transaction_by_id(transaction_id, session, tenant_id)
        if not transaction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Transaction not found"
            )
        return transaction
    except ValueError as e:
        logger.error("Transaction retrieval failed", extra={"error": str(e)})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.put("/transactions/{transaction_id}", response_model=TransactionOut)
async def update_transaction(
    transaction_id: UUID,
    data: TransactionUpdate,
    tenant_id: UUID = Depends(require_tenant),
    session: AsyncSession = Depends(get_db_session)
):
    """
    Update a transaction.
    
    Updates the transaction if it exists and belongs to the current tenant.
    Returns 404 if not found or doesn't belong to the tenant.
    """
    try:
        transaction = await transaction_service.update_transaction(transaction_id, data, session)
        if not transaction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Transaction not found"
            )
        return transaction
    except ValueError as e:
        logger.error("Transaction update failed", extra={"error": str(e)})
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )


@router.delete("/transactions/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_transaction(
    transaction_id: UUID,
    tenant_id: UUID = Depends(require_tenant),
    session: AsyncSession = Depends(get_db_session)
):
    """
    Delete a transaction.
    
    Deletes the transaction if it exists and belongs to the current tenant.
    Returns 404 if not found or doesn't belong to the tenant.
    """
    try:
        deleted = await transaction_service.delete_transaction(transaction_id, session)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Transaction not found"
            )
    except ValueError as e:
        logger.error("Transaction deletion failed", extra={"error": str(e)})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )
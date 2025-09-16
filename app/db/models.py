"""Database models."""
from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, Index, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.types import TypeDecorator, CHAR

from app.db.base import Base


class GUID(TypeDecorator):
    """Platform-independent GUID type.
    
    Uses PostgreSQL's UUID type on PostgreSQL, otherwise uses
    CHAR(36), storing as stringified hex values.
    """
    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(PostgresUUID())
        else:
            return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == 'postgresql':
            return str(value)
        else:
            if not isinstance(value, UUID):
                return str(UUID(value))
            else:
                return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        else:
            if not isinstance(value, UUID):
                return UUID(value)
            return value


class Transaction(Base):
    """Transaction model for storing financial transactions."""
    __tablename__ = "transactions"
    
    # Primary key
    id = Column(GUID(), primary_key=True, default=uuid4, index=True)
    
    # Tenant information
    tenant_id = Column(GUID(), nullable=False)
    
    # Transaction details
    user_id = Column(String(255), nullable=False)
    product_category = Column(String(255), nullable=False)
    amount = Column(Numeric(precision=10, scale=2), nullable=False)
    currency = Column(String(3), nullable=False)
    ts = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    
    # Indexes for efficient querying
    __table_args__ = (
        # Primary tenant + timestamp index (most common query pattern)
        Index('ix_transactions_tenant_ts', 'tenant_id', 'ts'),
        
        # Tenant + user_id index (for user-specific queries)
        Index('ix_transactions_tenant_user', 'tenant_id', 'user_id'),
        
        # Tenant + product_category index (for category-specific queries)
        Index('ix_transactions_tenant_category', 'tenant_id', 'product_category'),
    )

    def __repr__(self):
        return f"<Transaction(id={self.id}, tenant_id={self.tenant_id}, amount={self.amount})>"
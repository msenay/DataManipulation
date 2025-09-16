"""CSV and JSON ingestion utilities."""
import csv
from datetime import datetime
from decimal import Decimal, InvalidOperation
from io import StringIO
from typing import Dict, List, Optional, Tuple, Union
from uuid import UUID

from app.db.models import Transaction
from app.logging import get_logger
from app.schemas.transactions import TransactionCreate

logger = get_logger(__name__)

# Maximum number of errors to report
MAX_ERRORS = 50
# Batch size for database inserts
BATCH_SIZE = 500


class ImportError:
    """Represents an error during import."""
    def __init__(self, line: int, reason: str, data: Optional[Dict] = None):
        self.line = line
        self.reason = reason
        self.data = data or {}

    def to_dict(self) -> Dict:
        return {
            "line": self.line,
            "reason": self.reason
        }


class ImportResult:
    """Result of an import operation."""
    def __init__(self):
        self.ingested = 0
        self.skipped = 0
        self.errors: List[ImportError] = []

    def add_error(self, line: int, reason: str, data: Optional[Dict] = None):
        """Add an error, respecting the maximum error limit."""
        if len(self.errors) < MAX_ERRORS:
            self.errors.append(ImportError(line, reason, data))

    def to_dict(self) -> Dict:
        return {
            "ingested": self.ingested,
            "skipped": self.skipped,
            "errors": [error.to_dict() for error in self.errors]
        }


def validate_and_parse_row(
    row_data: Dict[str, str], 
    line_number: int, 
    current_tenant_id: UUID
) -> Tuple[Optional[TransactionCreate], Optional[str]]:
    """
    Validate and parse a single row of transaction data.
    
    Args:
        row_data: Raw row data as strings
        line_number: Line number for error reporting
        current_tenant_id: Current tenant ID from header
        
    Returns:
        Tuple of (parsed_transaction, error_reason)
        If error_reason is not None, parsed_transaction will be None
    """
    try:
        # Clean up the data - trim whitespace
        cleaned_data = {k: v.strip() if isinstance(v, str) else v for k, v in row_data.items()}
        
        # Check tenant_id if present
        if 'tenant_id' in cleaned_data and cleaned_data['tenant_id']:
            try:
                row_tenant_id = UUID(cleaned_data['tenant_id'])
                if row_tenant_id != current_tenant_id:
                    return None, f"Tenant ID mismatch: expected {current_tenant_id}, got {row_tenant_id}"
            except ValueError:
                return None, f"Invalid tenant_id format: {cleaned_data['tenant_id']}"
        
        # Validate required fields
        required_fields = ['user_id', 'product_category', 'amount', 'currency']
        for field in required_fields:
            if field not in cleaned_data or not cleaned_data[field]:
                return None, f"Missing required field: {field}"
        
        # Validate and parse amount
        try:
            amount = Decimal(cleaned_data['amount'])
            if amount <= 0:
                return None, f"Amount must be positive: {amount}"
        except (InvalidOperation, ValueError):
            return None, f"Invalid amount format: {cleaned_data['amount']}"
        
        # Validate currency
        currency = cleaned_data['currency'].upper()
        if len(currency) != 3 or not currency.isalpha():
            return None, f"Invalid currency format: {currency} (must be 3 letters)"
        
        # Parse timestamp if provided
        ts = None
        if 'ts' in cleaned_data and cleaned_data['ts']:
            try:
                # Try multiple timestamp formats
                ts_str = cleaned_data['ts']
                for fmt in [
                    '%Y-%m-%dT%H:%M:%S.%fZ',  # ISO with microseconds
                    '%Y-%m-%dT%H:%M:%SZ',     # ISO without microseconds
                    '%Y-%m-%dT%H:%M:%S',      # ISO without timezone
                    '%Y-%m-%d %H:%M:%S',      # Space separated
                    '%Y-%m-%d',               # Date only
                ]:
                    try:
                        ts = datetime.strptime(ts_str, fmt)
                        break
                    except ValueError:
                        continue
                
                if ts is None:
                    return None, f"Invalid timestamp format: {ts_str}"
                    
            except ValueError as e:
                return None, f"Invalid timestamp: {str(e)}"
        
        # Validate string lengths
        if len(cleaned_data['user_id']) > 255:
            return None, "user_id too long (max 255 characters)"
        if len(cleaned_data['product_category']) > 255:
            return None, "product_category too long (max 255 characters)"
        
        # Create the transaction object
        transaction_data = TransactionCreate(
            user_id=cleaned_data['user_id'],
            product_category=cleaned_data['product_category'],
            amount=amount,
            currency=currency,
            ts=ts
        )
        
        return transaction_data, None
        
    except Exception as e:
        logger.error(f"Unexpected error parsing row {line_number}", extra={"error": str(e), "row_data": row_data})
        return None, f"Unexpected error: {str(e)}"


async def process_csv_stream(
    csv_content: str,
    current_tenant_id: UUID,
    session
) -> ImportResult:
    """
    Process CSV content stream and import transactions.
    
    Args:
        csv_content: CSV content as string
        current_tenant_id: Current tenant ID
        session: Database session
        
    Returns:
        ImportResult with counts and errors
    """
    result = ImportResult()
    
    try:
        # Parse CSV
        csv_file = StringIO(csv_content)
        reader = csv.DictReader(csv_file)
        
        if not reader.fieldnames:
            result.add_error(1, "CSV file appears to be empty or has no headers")
            return result
        
        batch = []
        line_number = 1  # Header is line 0
        
        for row in reader:
            line_number += 1
            
            # Validate and parse the row
            transaction_data, error_reason = validate_and_parse_row(
                row, line_number, current_tenant_id
            )
            
            if error_reason:
                result.skipped += 1
                result.add_error(line_number, error_reason, row)
                continue
            
            # Add to batch
            batch.append(transaction_data)
            
            # Process batch if it reaches the batch size
            if len(batch) >= BATCH_SIZE:
                ingested_count = await _process_batch(batch, current_tenant_id, session)
                result.ingested += ingested_count
                batch = []
        
        # Process remaining batch
        if batch:
            ingested_count = await _process_batch(batch, current_tenant_id, session)
            result.ingested += ingested_count
        
        logger.info(
            "CSV import completed",
            extra={
                "tenant_id": str(current_tenant_id),
                "ingested": result.ingested,
                "skipped": result.skipped,
                "errors": len(result.errors)
            }
        )
        
    except Exception as e:
        logger.error(f"Error processing CSV stream", extra={"error": str(e)})
        result.add_error(0, f"CSV processing error: {str(e)}")
    
    return result


async def process_json_array(
    json_data: List[Dict],
    current_tenant_id: UUID,
    session
) -> ImportResult:
    """
    Process JSON array of transactions.
    
    Args:
        json_data: List of transaction dictionaries
        current_tenant_id: Current tenant ID
        session: Database session
        
    Returns:
        ImportResult with counts and errors
    """
    result = ImportResult()
    
    try:
        batch = []
        
        for index, row in enumerate(json_data):
            line_number = index + 1
            
            # Validate and parse the row
            transaction_data, error_reason = validate_and_parse_row(
                row, line_number, current_tenant_id
            )
            
            if error_reason:
                result.skipped += 1
                result.add_error(line_number, error_reason, row)
                continue
            
            # Add to batch
            batch.append(transaction_data)
            
            # Process batch if it reaches the batch size
            if len(batch) >= BATCH_SIZE:
                ingested_count = await _process_batch(batch, current_tenant_id, session)
                result.ingested += ingested_count
                batch = []
        
        # Process remaining batch
        if batch:
            ingested_count = await _process_batch(batch, current_tenant_id, session)
            result.ingested += ingested_count
        
        logger.info(
            "JSON import completed",
            extra={
                "tenant_id": str(current_tenant_id),
                "ingested": result.ingested,
                "skipped": result.skipped,
                "errors": len(result.errors)
            }
        )
        
    except Exception as e:
        logger.error(f"Error processing JSON array", extra={"error": str(e)})
        result.add_error(0, f"JSON processing error: {str(e)}")
    
    return result


async def _process_batch(
    batch: List[TransactionCreate],
    current_tenant_id: UUID,
    session
) -> int:
    """
    Process a batch of transactions and insert into database.
    
    Args:
        batch: List of TransactionCreate objects
        current_tenant_id: Current tenant ID
        session: Database session
        
    Returns:
        Number of successfully inserted transactions
    """
    try:
        # Convert to Transaction objects
        transactions = []
        for transaction_data in batch:
            transaction = Transaction(
                tenant_id=current_tenant_id,
                user_id=transaction_data.user_id,
                product_category=transaction_data.product_category,
                amount=transaction_data.amount,
                currency=transaction_data.currency,
                ts=transaction_data.ts or datetime.utcnow()
            )
            transactions.append(transaction)
        
        # Bulk insert
        session.add_all(transactions)
        await session.commit()
        
        logger.debug(f"Batch inserted successfully", extra={"count": len(transactions)})
        return len(transactions)
        
    except Exception as e:
        logger.error(f"Error inserting batch", extra={"error": str(e), "batch_size": len(batch)})
        await session.rollback()
        return 0
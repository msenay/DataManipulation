"""Transaction import endpoints."""
from typing import List, Optional, Union
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_tenant
from app.db.session import get_db_session
from app.logging import get_logger
from app.utils.csv_ingest import process_csv_stream, process_json_array

logger = get_logger(__name__)
router = APIRouter()


@router.post("/transactions/import")
async def import_transactions(
    request: Request,
    tenant_id: UUID = Depends(require_tenant),
    session: AsyncSession = Depends(get_db_session),
    file: Optional[UploadFile] = File(None)
):
    """
    Import transactions from CSV file or JSON array.
    
    Accepts either:
    - CSV file via multipart/form-data (file field)
    - JSON array in request body
    
    Returns import results with counts and error details.
    
    CSV Format:
    - Headers: user_id, product_category, amount, currency, ts (optional), tenant_id (optional)
    - tenant_id if present must match header or row will be skipped
    - ts format: ISO 8601 (YYYY-MM-DDTHH:MM:SS.fZ) or various other formats
    
    JSON Format:
    - Array of objects with same fields as CSV
    
    Response:
    - ingested: Number of successfully imported transactions
    - skipped: Number of skipped rows (validation errors, tenant mismatch)
    - errors: Array of error details (capped at 50 entries)
    """
    try:
        # Check content type to determine processing method
        content_type = request.headers.get("content-type", "")
        
        if file is not None:
            # Process CSV file via multipart/form-data
            if not file.filename.lower().endswith('.csv'):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="File must be a CSV file (.csv extension required)"
                )
            
            # Read file content
            try:
                content = await file.read()
                csv_content = content.decode('utf-8')
            except UnicodeDecodeError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="File must be UTF-8 encoded"
                )
            
            # Process CSV
            result = await process_csv_stream(csv_content, tenant_id, session)
            
            logger.info(
                "CSV import processed",
                extra={
                    "tenant_id": str(tenant_id),
                    "file_name": file.filename,
                    "ingested": result.ingested,
                    "skipped": result.skipped,
                    "error_count": len(result.errors)
                }
            )
            
        elif "application/json" in content_type:
            # Process JSON array
            try:
                json_data = await request.json()
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid JSON: {str(e)}"
                )
            
            if not isinstance(json_data, list):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="JSON data must be an array of transaction objects"
                )
            
            result = await process_json_array(json_data, tenant_id, session)
            
            logger.info(
                "JSON import processed",
                extra={
                    "tenant_id": str(tenant_id),
                    "record_count": len(json_data),
                    "ingested": result.ingested,
                    "skipped": result.skipped,
                    "error_count": len(result.errors)
                }
            )
            
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either CSV file (multipart/form-data) or JSON array (application/json) must be provided"
            )
        
        return result.to_dict()
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Import failed with unexpected error",
            extra={"tenant_id": str(tenant_id), "error": str(e)}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Import failed due to internal error"
        )
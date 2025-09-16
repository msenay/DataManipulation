# FastAPI Multi-Tenant Transaction System

A production-ready FastAPI application with comprehensive multi-tenancy support for managing financial transactions.

## Features

- 🏢 **Multi-tenancy**: Complete tenant isolation at the database level
- 💳 **Transaction Management**: Full CRUD operations with validation
- 📊 **Analytics**: Real-time metrics and reporting
- 📥 **Data Import**: CSV and JSON bulk import with validation
- 🔒 **Security**: Tenant-scoped access control
- 📝 **Logging**: Structured JSON logging with request tracing
- ⚡ **Performance**: Async operations with database connection pooling
- 🧪 **Testing**: Comprehensive test suite
- 🐳 **Docker**: Containerized deployment ready

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd fastapi-tenant-app

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment configuration
cp .env.example .env

# Run the application
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Using Make (Optional)

```bash
make install  # Install dependencies
make run      # Run the server
make test     # Run tests
```

## Environment Configuration

Create a `.env` file with the following variables:

```env
# Database Configuration
DATABASE_URL=postgresql+psycopg://app_user:app_password@localhost:5432/tenant_app
# For PostgreSQL: DATABASE_URL=postgresql+psycopg://user:password@localhost/dbname

# Application Settings
DEBUG=true
LOG_LEVEL=INFO
```

### Database URL Notes

- **PostgreSQL**: `postgresql+psycopg://user:password@localhost:5432/dbname`

## Multi-Tenancy Strategy

This application implements a comprehensive multi-tenancy strategy:

### 1. Header-based Tenant Identification
- All API calls (except `/health`) require an `x-tenant-id` header
- Tenant ID must be a valid UUID (automatically normalized to lowercase)
- Missing header → 400 Bad Request
- Invalid UUID → 422 Unprocessable Entity

### 2. Context Variables
- Tenant ID is stored in Python `contextvars` for the request duration
- Available throughout the request lifecycle via `get_current_tenant()`

### 3. UUID Normalization Policy
- **Canonical Format**: All UUIDs are normalized to **lowercase RFC-4122 format**
- **Input Processing**: Mixed case UUIDs in headers are automatically converted to lowercase
- **Storage**: Database stores UUIDs in normalized lowercase format
  - PostgreSQL: Uses native UUID type (automatically normalized)
- **Output**: All API responses return UUIDs in lowercase format
- **Example**: `123E4567-E89B-12D3-A456-426614174000` → `123e4567-e89b-12d3-a456-426614174000`

### 4. Database Isolation
- **Read Operations**: Automatic tenant filtering on all queries
- **Write Operations**: Automatic tenant_id assignment and validation
- **Cross-tenant Access**: Returns 404 (doesn't leak data existence)

### 5. Event-driven Enforcement
- SQLAlchemy event listeners ensure tenant isolation
- Before flush: validates and sets tenant_id on new records
- Query execution: applies tenant filters automatically

## API Endpoints

### Authentication
All endpoints (except `/health`) require the `x-tenant-id` header:
```bash
curl -H "x-tenant-id: 123e4567-e89b-12d3-a456-426614174000" <endpoint>
```

### Health Check
```bash
# No authentication required
GET /v1/health
```

### Tenant Information
```bash
# Get current tenant info
GET /v1/me
```

### Transactions

#### Create Transaction
```bash
POST /v1/transactions
Content-Type: application/json

{
  "user_id": "user123",
  "product_category": "electronics",
  "amount": "199.99",
  "currency": "USD",
  "ts": "2025-01-01T12:00:00Z"  # Optional, defaults to now
}
```

#### List Transactions
```bash
# Basic listing
GET /v1/transactions

# With filters and pagination
GET /v1/transactions?limit=50&offset=0&start_ts=2025-01-01T00:00:00Z&end_ts=2025-01-31T23:59:59Z&user_id=user123
```

#### Get Transaction by ID
```bash
GET /v1/transactions/{transaction_id}
```

#### Update Transaction
```bash
PUT /v1/transactions/{transaction_id}
Content-Type: application/json

{
  "amount": "299.99",
  "product_category": "premium_electronics"
}
```

#### Delete Transaction
```bash
DELETE /v1/transactions/{transaction_id}
```

### Data Import

#### CSV Import
```bash
POST /v1/transactions/import
Content-Type: multipart/form-data

# Upload CSV file with columns: user_id, product_category, amount, currency, ts, tenant_id
curl -X POST "http://localhost:8000/v1/transactions/import" \
  -H "x-tenant-id: 123e4567-e89b-12d3-a456-426614174000" \
  -F "file=@transactions.csv"
```

#### JSON Array Import
```bash
POST /v1/transactions/import
Content-Type: application/json

[
  {
    "user_id": "user123",
    "product_category": "electronics",
    "amount": "199.99",
    "currency": "USD"
  },
  {
    "user_id": "user456",
    "product_category": "books",
    "amount": "29.99",
    "currency": "EUR"
  }
]
```

Import responses include:
```json
{
  "ingested": 150,
  "skipped": 5,
  "errors": [
    {
      "line": 23,
      "reason": "Invalid amount format: not_a_number"
    }
  ]
}
```

### Import Idempotency Behavior

**⚠️ Important**: The `/v1/transactions/import` endpoint is **NOT idempotent**.

- **Duplicate Handling**: No automatic duplicate detection - each import creates new transactions
- **Recommendation**: Implement client-side deduplication before import
- **Best Practice**: Use unique external IDs in your data and check for existence before import
- **Future Enhancement**: Consider adding an `Idempotency-Key` header for safe retries

**Example of non-idempotent behavior:**
```bash
# First import
curl -X POST "/v1/transactions/import" -F "file=@data.csv"
# Returns: {"ingested": 100, "skipped": 0, "errors": []}

# Second import of same file
curl -X POST "/v1/transactions/import" -F "file=@data.csv"  
# Returns: {"ingested": 100, "skipped": 0, "errors": []} (creates duplicates!)
```

### Analytics & Metrics

#### Overall Summary
```bash
# Default: last 30 days
GET /v1/metrics/summary

# Custom date range
GET /v1/metrics/summary?start_ts=2025-01-01T00:00:00Z&end_ts=2025-01-31T23:59:59Z

# Partial date range (30-day window)
GET /v1/metrics/summary?start_ts=2025-01-01T00:00:00Z
```

#### Category Breakdown
```bash
# Default: last 30 days
GET /v1/metrics/by-category

# Custom date range
GET /v1/metrics/by-category?start_ts=2025-01-01T00:00:00Z&end_ts=2025-01-31T23:59:59Z
```

#### User Summary
```bash
# No date filtering (all-time)
GET /v1/metrics/user/{user_id}
```

#### Comprehensive Metrics
```bash
# Default: last 30 days
GET /v1/metrics

# Custom date range
GET /v1/metrics?start_ts=2025-01-01T00:00:00Z&end_ts=2025-01-31T23:59:59Z
```

### Metrics Date Range Defaults

- **Default Window**: Last 30 days (UTC) when no dates provided
- **Partial Ranges**: If only start_ts or end_ts provided, creates 30-day window
- **Validation**: start_ts must be ≤ end_ts (returns 422 if violated)
- **Timezone**: All timestamps are UTC (ISO 8601 format)

## Sample Data

Load sample data using the provided CSV file:

```bash
curl -X POST "http://localhost:8000/v1/transactions/import" \
  -H "x-tenant-id: 123e4567-e89b-12d3-a456-426614174000" \
  -F "file=@tests/data/transactions.csv"
```

This file contains 22 transactions across 3 tenants with various categories and currencies.

### Sample Tenant UUIDs

- **Tenant 1**: `123e4567-e89b-12d3-a456-426614174000`
- **Tenant 2**: `456e7890-e89b-12d3-a456-426614174001` 
- **Tenant 3**: `789e0123-e89b-12d3-a456-426614174002`

## Limits and Pagination

### Transaction Listing
- **Default limit**: 50 transactions
- **Maximum limit**: 100 transactions
- **Offset-based pagination**: Use `offset` parameter
- **Ordering**: Newest transactions first (by timestamp)

### Import Operations
- **Batch size**: 500 records per database transaction
- **Error reporting**: Maximum 50 errors reported
- **Supported formats**: CSV (UTF-8) and JSON arrays

### Metrics
- **User rankings**: Top 10 users by spending
- **Date filtering**: ISO 8601 timestamps
- **Multi-currency**: Aggregated across all currencies

## Error Codes Policy

### Standard HTTP Status Codes

| Code | Description | Specific Cases | Example |
|------|-------------|----------------|---------|
| 200 | Success | Successful operations | Transaction retrieved |
| 201 | Created | Resource created | Transaction created |
| 204 | No Content | Successful deletion | Transaction deleted |
| 400 | Bad Request | **Missing x-tenant-id header** | `{"detail": "x-tenant-id header is required"}` |
| 404 | Not Found | **Cross-tenant detail access**, nonexistent resources | `{"detail": "Transaction not found"}` |
| 422 | Unprocessable Entity | **Invalid GUID format**, tenant mismatches, validation errors, invalid date ranges | `{"detail": "Invalid tenant ID format: badly formed hexadecimal UUID string"}` |
| 500 | Internal Server Error | Database errors, unexpected failures | `{"detail": "Internal server error"}` |

### Detailed Status Code Rules

#### 400 Bad Request
- **Missing x-tenant-id header**: All endpoints except `/v1/health` require this header
- **Invalid request format**: Malformed JSON, missing required request body

#### 404 Not Found  
- **Cross-tenant detail access**: Accessing transactions/users from different tenants
- **Nonexistent resources**: Requesting transactions or users that don't exist
- **Security note**: Returns 404 instead of 403 to avoid leaking resource existence

#### 422 Unprocessable Entity
- **Invalid GUID format**: Malformed UUID in x-tenant-id header
- **Tenant ID mismatches**: tenant_id in request body doesn't match header
- **Validation errors**: Invalid amounts, currencies, date formats
- **Date range errors**: start_ts > end_ts in metrics endpoints
- **Business rule violations**: Write-guard tenant validation failures

### Error Response Format

```json
{
  "detail": "Error description"
}
```

For validation errors:
```json
{
  "detail": "Validation failed",
  "errors": [
    {
      "type": "string_too_short",
      "loc": ["body", "user_id"],
      "msg": "String should have at least 1 character"
    }
  ]
}
```

## Data Validation

### Transaction Fields

- **user_id**: String, 1-255 characters, required
- **product_category**: String, 1-255 characters, required  
- **amount**: Decimal, positive, max 999999999.99, required
- **currency**: String, exactly 3 letters (ISO 4217), auto-uppercased, required
- **ts**: DateTime, ISO 8601 format, timezone-aware, optional (defaults to now)
- **tenant_id**: UUID, optional in request (auto-set from header)

### Import Validation

- **Row-level validation**: Each row validated independently
- **Tenant matching**: If tenant_id in data, must match header
- **Error aggregation**: Up to 50 errors reported with line numbers
- **Partial success**: Successfully validated rows are imported even if others fail

## Development

### Project Structure

```
app/
├── api/
│   ├── deps.py              # Dependencies (tenant validation)
│   └── routers/             # API route handlers
├── db/
│   ├── models.py            # SQLAlchemy models
│   ├── session.py           # Database session management
│   └── tenancy.py           # Tenant context management
├── middleware/
│   ├── exceptions.py        # Global exception handlers
│   └── logging.py           # Request logging middleware
├── schemas/
│   ├── transactions.py      # Pydantic schemas
│   └── metrics.py           # Analytics schemas
├── services/
│   ├── transactions.py      # Business logic
│   └── metrics.py           # Analytics logic
├── utils/
│   └── csv_ingest.py        # Import utilities
├── config.py                # Configuration management
├── logging.py               # Structured logging setup
└── main.py                  # FastAPI application
```

### Running Tests

```bash
# Install test dependencies
pip install -r requirements.txt

# Run all tests
pytest

# Run with coverage
pytest --cov=app

# Run specific test file
pytest tests/test_transactions.py -v
```

### Code Quality

```bash
# Format code
black app tests
isort app tests

# Lint code
flake8 app tests
```

## Docker Deployment

### Quick Start with Docker Compose

```bash
# Clone the repository
git clone <repository-url>
cd fastapi-tenant-app

# Start all services (PostgreSQL + FastAPI + Redis)
docker-compose up -d

# View logs
docker-compose logs -f app

# Load sample data
make sample

# Stop services
docker-compose down
```

### Production Deployment

```bash
# Copy environment template
cp .env.docker .env

# Edit .env with your production values
nano .env

# Start production services
docker-compose -f docker-compose.prod.yml up -d

# View logs
docker-compose -f docker-compose.prod.yml logs -f

# Stop services
docker-compose -f docker-compose.prod.yml down
```

### Using Docker Only

```bash
# Build image
docker build -t fastapi-tenant-app .

# Run with PostgreSQL (development)
docker run -p 8000:8000 fastapi-tenant-app

# Run with PostgreSQL (production)
docker run -p 8000:8000 \
  -e DATABASE_URL="postgresql+psycopg://user:password@host:5432/dbname" \
  fastapi-tenant-app

# Run with custom configuration
docker run -p 8000:8000 \
  -e DATABASE_URL="postgresql+psycopg://user:password@host:5432/dbname" \
  -e DEBUG="false" \
  -e LOG_LEVEL="INFO" \
  -v $(pwd)/logs:/app/logs \
  fastapi-tenant-app
```

### Docker Services

The Docker Compose setup includes:

- **app**: FastAPI application server
- **db**: PostgreSQL 15 database with health checks
- **redis**: Redis cache (for future features like session storage)
- **nginx**: Reverse proxy with rate limiting (production only)

### Docker Configuration

Environment variables for Docker deployment:

```env
# Database
POSTGRES_DB=tenant_app
POSTGRES_USER=app_user  
POSTGRES_PASSWORD=your_secure_password

# Application
DATABASE_URL=postgresql+psycopg://user:password@db:5432/dbname
DEBUG=false
LOG_LEVEL=INFO

# Optional
REDIS_PASSWORD=your_redis_password
```

### Health Checks

All services include health checks:
- **Database**: `pg_isready` check
- **Application**: HTTP health endpoint check
- **Redis**: Redis ping check

### Volumes

- **postgres_data**: Database persistence
- **redis_data**: Redis persistence  
- **./logs**: Application logs (mounted from host)

## Production Considerations

### Database
- Use PostgreSQL for production
- Enable connection pooling
- Set up read replicas for analytics queries
- Regular backups with point-in-time recovery

### Security
- Use HTTPS in production
- Implement proper authentication (JWT tokens)
- Rate limiting per tenant
- Input sanitization and SQL injection prevention

### Monitoring
- Structured logging to centralized system (ELK stack)
- Application metrics (Prometheus + Grafana)
- Health checks and alerting
- Database performance monitoring

### Scaling
- Horizontal scaling with load balancer
- Database sharding by tenant for very large datasets
- Caching layer (Redis) for frequently accessed data
- Async task processing for imports (Celery)

## API Documentation

Once the server is running, visit:
- **Interactive API docs**: http://localhost:8000/docs
- **ReDoc documentation**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes with tests
4. Run the test suite
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.
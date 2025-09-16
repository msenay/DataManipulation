-- Database initialization script
-- This script runs when the PostgreSQL container starts for the first time

-- Create extensions if needed
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create test database for running tests
CREATE DATABASE test_tenant_app;

-- Grant permissions to test database
GRANT ALL PRIVILEGES ON DATABASE test_tenant_app TO app_user;

-- The application will create its own tables via SQLAlchemy
-- This file can be used for any initial setup, indexes, or seed data
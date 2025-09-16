-- Database initialization script
-- This script runs when the PostgreSQL container starts for the first time

-- Create extensions if needed
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- The application will create its own tables via SQLAlchemy
-- This file can be used for any initial setup, indexes, or seed data

-- Example: Create a function to generate UUIDs (already available via uuid-ossp)
-- This is just a placeholder for any custom database setup
-- ==================== Database Initialization Script ====================
-- This script runs automatically when PostgreSQL container starts
-- It creates indexes and any initial data needed

-- ==================== Create Indexes ====================
-- Index on users table
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_created_at ON users(created_at);

-- Indexes on conversations table
CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON conversations(user_id);
CREATE INDEX IF NOT EXISTS idx_conversations_created_at ON conversations(created_at);
CREATE INDEX IF NOT EXISTS idx_conversations_updated_at ON conversations(updated_at);

-- Indexes on conversation_messages table
CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON conversation_messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_messages_role ON conversation_messages(role);
CREATE INDEX IF NOT EXISTS idx_messages_created_at ON conversation_messages(created_at);

-- ==================== Optional: Sample Data ====================
-- Uncomment below if you want to add sample data on first run
-- Note: Only runs if tables are empty

-- INSERT INTO users (id, email, name, created_at, updated_at)
-- VALUES (
--     '550e8400-e29b-41d4-a716-446655440000',
--     'demo@example.com',
--     'Demo User',
--     NOW(),
--     NOW()
-- ) ON CONFLICT (id) DO NOTHING;

-- ==================== Comments ====================
-- These indexes improve query performance for:
-- - Finding users by email
-- - Filtering conversations by user
-- - Sorting by timestamps
-- - Filtering messages by conversation

COMMIT;
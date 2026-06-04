# 🗄️ Database Management Guide

This guide contains all the commands and queries to inspect, manage, and query your database for the Financial Therapist Chatbot project.

The project connects to:
* **PostgreSQL:** Instance configured via connection parameters in `.env` (`DB_HOST`, `DB_PORT`, `DB_USERNAME`, `DB_PASSWORD`, `DB_DATABASE`) or via `DATABASE_URL`.

---

## 🚀 Easy Query Runner (Python Helper)

We have created a helper script [run_query.py](file:///d:/Finheal-friend/f2-therapist-chatbot-backend/run_query.py) in the root of your backend project. It automatically uses your active database configuration from your `.env`.

### How to use it:
You can run it directly using the virtual environment's Python executable:

```powershell
# 1. View all tables
.\.venv\Scripts\python.exe run_query.py "SELECT table_name FROM information_schema.tables WHERE table_schema='public';"

# 2. View the users table structure
.\.venv\Scripts\python.exe run_query.py "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'users';"

# 3. Query users
.\.venv\Scripts\python.exe run_query.py "SELECT id, email, name, wellness_score FROM users LIMIT 5;"
```

---

## 🐘 PostgreSQL CLI Management (`psql`)

To manage your PostgreSQL instance directly:

### 1. Connect to the Database
Run the following command (replace with your actual database details):
```bash
psql postgresql://username:password@localhost:5432/f2_therapist
# OR if using the .env variables directly:
psql -h localhost -U f2_user -d f2_therapist
```

### 2. General PostgreSQL Commands
* **Show all tables:** `\dt`
* **Show table structure/columns:** `\d table_name`
* **List databases:** `\l`
* **Toggle expanded table formatting (useful for long columns):** `\x`
* **Exit PostgreSQL shell:** `\q`

---

## 📝 SQL Commands Reference

Here are the SQL statements you can execute in your database shell or run using the `run_query.py` script.

### 1. Checking Tables & Schema
```sql
-- Get list of tables in public schema
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'public';

-- Get column details of a table
SELECT column_name, data_type, is_nullable 
FROM information_schema.columns 
WHERE table_name = 'users';
```

### 2. Creating Tables
```sql
-- Example: Creating a new custom table for therapist notes
CREATE TABLE therapist_notes (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL,
    note_content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
```

### 3. Deleting (Dropping) Tables
> [!WARNING]
> Dropping a table will permanently delete all records inside it. Proceed with caution.
```sql
-- Delete the table if it exists
DROP TABLE IF EXISTS therapist_notes;
```

### 4. Running Queries (CRUD Operations)

#### A. Insert / Add Data
```sql
-- Insert a new user manually (for testing)
INSERT INTO users (id, email, name, wellness_score, wellness_tier, momentum_score, hearts, is_guest, created_at, updated_at) 
VALUES (
    'manual-user-uuid-12345', 
    'john.doe@example.com', 
    'John Doe', 
    75, 
    'Growing', 
    80, 
    50, 
    'false', 
    CURRENT_TIMESTAMP, 
    CURRENT_TIMESTAMP
);

-- Insert a conversation for this user
INSERT INTO conversations (id, user_id, title, created_at, updated_at, message_count)
VALUES (
    'manual-conv-uuid-54321', 
    'manual-user-uuid-12345', 
    'Financial Stress Session', 
    CURRENT_TIMESTAMP, 
    CURRENT_TIMESTAMP, 
    0
);
```

#### B. Select / Retrieve Data
```sql
-- View all users
SELECT id, email, name, wellness_score, wellness_tier FROM users;

-- View conversations for a specific user
SELECT * FROM conversations WHERE user_id = 'manual-user-uuid-12345';

-- View conversation messages sorted by time
SELECT role, content, created_at FROM conversation_messages 
WHERE conversation_id = 'manual-conv-uuid-54321' 
ORDER BY created_at ASC;

-- Check wellness breakdown details
SELECT user_id, money_iq, debt_health, overall_score FROM wellness_breakdown;
```

#### C. Update Data
```sql
-- Update user's wellness score and tier
UPDATE users 
SET wellness_score = 85, wellness_tier = 'Thriving', updated_at = CURRENT_TIMESTAMP 
WHERE id = 'manual-user-uuid-12345';

-- Increment heart count for a user
UPDATE users 
SET hearts = hearts + 10 
WHERE id = 'manual-user-uuid-12345';
```

#### D. Delete Data
```sql
-- Delete a specific message
DELETE FROM conversation_messages WHERE id = 'message-uuid-here';

-- Delete a user (will cascade delete their conversations & messages if foreign keys are setup)
DELETE FROM users WHERE id = 'manual-user-uuid-12345';
```

---

## 📊 Project Database Schema Quick Reference

Here are the main tables defined in [src/models.py](file:///d:/Finheal-friend/f2-therapist-chatbot-backend/src/models.py):

| Table Name | Description | Key Columns |
| :--- | :--- | :--- |
| **`users`** | Holds user details, wellness status, and chatbot settings | `id` (PK), `email`, `name`, `hearts`, `wellness_score`, `wellness_tier`, `momentum_score`, `therapy_style`, `created_at` |
| **`conversations`** | Groups messages into sessions | `id` (PK), `user_id` (FK), `title`, `summary`, `created_at`, `message_count` |
| **`conversation_messages`** | Individual chat history rows | `id` (PK), `conversation_id` (FK), `role` (`user`/`assistant`/`system`), `content`, `mood` (JSON), `created_at` |
| **`test_results`** | Stored financial tests taken by users | `id` (PK), `user_id` (FK), `test_type`, `raw_score`, `normalized_score`, `insights` (JSON) |
| **`wellness_breakdown`** | Breakdown scores for user financial aspects | `user_id` (PK, FK), `money_iq`, `debt_health`, `financial_safety`, `overall_score`, `wellness_tier` |
| **`mood_live_state`** | Current state of user mood indices | `user_id` (PK, FK), `stress`, `urgency`, `openness`, `willingness`, `emotion` |
| **`mood_trend_state`** | Smooth trend state of user mood over time | `user_id` (PK, FK), `stress_trend`, `urgency_trend`, `openness_trend`, `emotion_trend` |
| **`user_consolidated_profiles`** | Cached JSON document of all user telemetry | `user_id` (PK, FK), `data` (JSON), `updated_at` |

---

## 🐍 Built-in Diagnostic Tools

You also have a couple of script resources already present in your project:

1. **`python inspect_db.py`**: Runs a quick terminal dump of the first 10 rows of all tables in the configured database (PostgreSQL).
2. **`python test_db_conn.py`**: Validates whether your backend can successfully connect to the PostgreSQL instance using your configured `.env` parameters.

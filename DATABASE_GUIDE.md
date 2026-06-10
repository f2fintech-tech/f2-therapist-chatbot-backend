# 🗄️ Database Management Guide

This guide contains easy-to-run terminal commands and SQL queries to inspect, manage, and query your chatbot database.

---

## 🚀 1. Connecting to the Database

### Step A: Run the connection command in your terminal
```bash
psql "postgresql://postgres:F2fintech_26@therapist-chatbot-db.c5k4w0icgzcw.ap-south-1.rds.amazonaws.com:5432/therapist_chatbot"
```

### Step B: Set client encoding to UTF-8 (Crucial for Windows & Emojis)
As soon as you connect and see the `therapist_chatbot=>` prompt, run this command to prevent emoji display errors:
```sql
\encoding UTF8
```

### Handy general PostgreSQL commands:
* **Show all tables:** `\dt`
* **Show table columns/schema:** `\d table_name` (e.g., `\d users`)
* **Toggle expanded table formatting (useful for reading long messages/JSON):** `\x`
* **Exit psql console:** `\q`

---

## 🛠️ 2. Core Database Schema & Content Management

Use these commands to inspect tables, view columns, check content, or create, delete, and modify tables.

### Check how many tables you have:
* **Option A (Shortcut):** Run `\dt` inside your `psql` session.
* **Option B (SQL Query):**
  ```sql
  SELECT table_name 
  FROM information_schema.tables 
  WHERE table_schema = 'public';
  ```

### Check table columns (schema):
* **Option A (Shortcut):** Run `\d table_name` (e.g., `\d users`).
* **Option B (SQL Query):**
  ```sql
  SELECT column_name, data_type, is_nullable 
  FROM information_schema.columns 
  WHERE table_name = 'users';
  ```

### Check table content (rows):
* **View all columns (first 10 rows):**
  ```sql
  SELECT * FROM users LIMIT 10;
  ```
* **View specific columns only:**
  ```sql
  SELECT id, email, name FROM users;
  ```

### Create a new table:
```sql
CREATE TABLE new_table_name (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Delete (Drop) a table:
```sql
DROP TABLE IF EXISTS new_table_name;
```

### Modify (Alter) an existing table:
* **Add a new column:**
  ```sql
  ALTER TABLE users ADD COLUMN new_column_name VARCHAR(255);
  ```
* **Drop (Remove) a column:**
  ```sql
  ALTER TABLE users DROP COLUMN new_column_name;
  ```
* **Modify a column type:**
  ```sql 
  ALTER TABLE users ALTER COLUMN phone TYPE VARCHAR(64);
  ```

---

## 👥 3. Users Table (`users`)

This table stores all user profiles, credentials, guest status, and overall scores.

### Check all user profiles (ID, Email, Name, and Hearts):
```sql
SELECT id, email, name, hearts, is_guest, created_at FROM users;
```

### Check a specific user's details:
```sql
SELECT id, email, name, phone, location, occupation, bio, risk_tolerance 
FROM users 
WHERE email = 'gnd.dhiman@gmail.com';
```

### Check total number of users (registered vs guests):
```sql
SELECT is_guest, COUNT(*) as total_count 
FROM users 
GROUP BY is_guest;
```

### Reset / Truncate all users (WARNING: Deletes all database records):
```sql
TRUNCATE TABLE users, conversations, conversation_messages, mood_live_state, mood_trend_state, test_results, wellness_breakdown, user_consolidated_profiles CASCADE;
```

---

## 💬 4. Conversations & Messages (`conversations`, `conversation_messages`)

These tables store chat session summaries and individual messages between users and the AI.

### View the latest conversation sessions:
```sql
SELECT id, user_id, title, message_count, updated_at 
FROM conversations 
ORDER BY updated_at DESC 
LIMIT 5;
```

### View messages for a specific conversation session (by ID):
```sql
SELECT role, content, created_at 
FROM conversation_messages 
WHERE conversation_id = 'YOUR_CONVERSATION_ID_HERE' 
ORDER BY created_at ASC;
```

### View all conversations and messages for a specific user:
```sql
SELECT c.title, m.role, m.content, m.created_at
FROM conversations c
JOIN conversation_messages m ON c.id = m.conversation_id
WHERE c.user_id = 'YOUR_USER_ID_HERE'
ORDER BY m.created_at ASC;
```

---

## 📊 5. Test Results & Breakdown (`test_results`, `wellness_breakdown`)

These tables record completed financial health tests and calculated category scores.

### View all test results for a specific user:
```sql
SELECT test_type, raw_score, normalized_score, completed_at, insights 
FROM test_results 
WHERE user_id = 'YOUR_USER_ID_HERE';
```

### View the calculated wellness score breakdown for a specific user:
```sql
SELECT money_iq, debt_health, credit_health, overall_score, wellness_tier 
FROM wellness_breakdown 
WHERE user_id = 'YOUR_USER_ID_HERE';
```

---

## 🧠 6. User Mood State (`mood_live_state`, `mood_trend_state`)

These tables store live mood metrics captured during conversation.

### View the live emotional metrics of a user:
```sql
SELECT stress, urgency, openness, willingness, emotion, updated_at 
FROM mood_live_state 
WHERE user_id = 'YOUR_USER_ID_HERE';
```

### View the smoothed emotional trend of a user over time:
```sql
SELECT stress_trend, urgency_trend, openness_trend, willingness_trend, emotion_trend, updated_at 
FROM mood_trend_state 
WHERE user_id = 'YOUR_USER_ID_HERE';
```

---

## 📂 7. Telemetry Profile (`user_consolidated_profiles`)

This table stores cached JSON telemetry (page activity, calculator history, etc.).

### View cached JSON telemetry data:
```sql
SELECT data, updated_at 
FROM user_consolidated_profiles 
WHERE user_id = 'YOUR_USER_ID_HERE';
```

---

## 🐍 8. Python Helper Scripts

If you want to run these diagnostics or migrations using Python from the command line:

### Test Database Connection:
```powershell
.\.venv\Scripts\python.exe test_db_conn.py
```

### Quick Table Contents Dump (First 10 rows of all tables):
```powershell
.\.venv\Scripts\python.exe inspect_db.py
```

### Run a Custom SQL Query:
```powershell
.\.venv\Scripts\python.exe run_query.py "SELECT COUNT(*) FROM users;"
```

### Migrate SQLite data (`test.db`) to PostgreSQL RDS:
```powershell
.\.venv\Scripts\python.exe migrate_sqlite_to_postgres.py
```

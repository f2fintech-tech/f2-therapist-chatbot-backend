# 🗄️ Database Management Guide

This guide contains easy-to-run terminal commands and SQL queries to inspect, manage, and query your chatbot database.

---

## 🚀 1. Connecting to the Database

### Step A: Run the connection command in your terminal
```bash
psql "postgresql://postgres:F2fintech_26@therapist-chatbot-db.c5k4w0icgzcw.ap-south-1.rds.amazonaws.com:5432/therapist_chatbot"
```

### Step B: Set client encoding to UTF-8 (Crucial for Emojis)
As soon as you connect and see the `therapist_chatbot=>` prompt, run this to prevent display errors:
```sql
\encoding UTF8
```

### 💡 Handy General Shortcuts:
* **Show all tables:** `\dt`
* **Show table columns/schema:** `\d table_name` (e.g., `\d users`)
* **Toggle expanded table formatting (very useful for reading long text/JSON):** `\x`
* **Exit psql console:** `\q`

---

## 👥 2. User Accounts & Consolidated Profiles

### View all registered and guest users:
```sql
SELECT id, email, name, phone, hearts, is_guest, created_at FROM users;
```

### Find a specific user by email:
```sql
    SELECT id, email, name, phone, location, occupation, wellness_score, wellness_tier 
    FROM users 
    WHERE email = 'gnd.dhiman@gmail.com';
```

### Check consolidated JSON telemetry profiles:
```sql
SELECT user_id, updated_at, data FROM user_consolidated_profiles LIMIT 5;
```

---

## 📅 3. Advisors & Appointments (New Tables)

### View all advisors and their availability status:
```sql
SELECT f2_fintech_id, name, designation, availability, rating, reviews_count FROM advisors;
```

### View all upcoming / booked consultations:
```sql
SELECT id, user_id, advisor_name, date, time, completed, cancelled, notes 
FROM advisor_appointments 
ORDER BY booked_at DESC;
```

### Inspect appointment cancel reasons (check user vs manager cancel logs):
```sql
SELECT id, advisor_name, date, time, cancelled, notes, feedback 
FROM advisor_appointments 
WHERE cancelled = true;
```

---

## 💳 4. Credit Scores & Calculator Activity (New Tables)

### View all fetched CIBIL & Experian credit reports:
```sql
SELECT id, user_id, bureau, score, pdf_url, fetched_at FROM user_credit_reports ORDER BY fetched_at DESC;
```

### View recent user calculations (EMI, Compares, Eligibility):
```sql
SELECT id, user_id, calculator_type, loan_type, inputs, created_at 
FROM user_loan_calculator_activities 
ORDER BY created_at DESC 
LIMIT 10;
```

---

## 📈 5. User Activity Analytics & Insights (New)

### Count calculator runs by type and user:
```sql
SELECT user_id, calculator_type, COUNT(*) AS run_count
FROM user_loan_calculator_activities
GROUP BY user_id, calculator_type
ORDER BY run_count DESC;
```

### Retrieve most active users (combining calculator and test/quiz activities):
```sql
SELECT u.id, u.name, u.email,
       COALESCE(c.calc_count, 0) AS calculator_runs,
       COALESCE(t.test_count, 0) AS tests_completed
FROM users u
LEFT JOIN (
    SELECT user_id, COUNT(*) AS calc_count 
    FROM user_loan_calculator_activities 
    GROUP BY user_id
) c ON u.id = c.user_id
LEFT JOIN (
    SELECT user_id, COUNT(*) AS test_count 
    FROM test_results 
    GROUP BY user_id
) t ON u.id = t.user_id
WHERE c.calc_count > 0 OR t.test_count > 0
ORDER BY (COALESCE(c.calc_count, 0) + COALESCE(t.test_count, 0)) DESC;
```

### Extract educational video/article consumption counts from profile JSON:
```sql
SELECT 
    u.id, 
    u.name,
    COALESCE(jsonb_array_length(ucp.data->'financial_education'->'videos_seen'), 0) AS videos_watched,
    COALESCE(jsonb_array_length(ucp.data->'financial_education'->'articles_seen'), 0) AS articles_read
FROM users u
JOIN user_consolidated_profiles ucp ON u.id = ucp.user_id
ORDER BY videos_watched DESC, articles_read DESC;
```

### Get average score and total attempts by test type:
```sql
SELECT test_type, 
       COUNT(*) AS total_attempts, 
       ROUND(AVG(raw_score), 2) AS avg_raw_score, 
       ROUND(AVG(normalized_score), 2) AS avg_normalized_score
FROM test_results
GROUP BY test_type
ORDER BY total_attempts DESC;
```

### Calculate monthly calculator activity trends:
```sql
SELECT 
    TO_CHAR(created_at, 'YYYY-MM') AS month,
    COUNT(DISTINCT user_id) AS active_users,
    COUNT(*) AS total_calculator_runs
FROM user_loan_calculator_activities
GROUP BY TO_CHAR(created_at, 'YYYY-MM')
ORDER BY month DESC;
```

---

## 💬 6. Chat History & Mood Telemetry

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

### View the live emotional metrics of a user:
```sql
SELECT stress, urgency, openness, willingness, emotion, updated_at 
FROM mood_live_state 
WHERE user_id = 'YOUR_USER_ID_HERE';
```

---

## 📊 7. Assessments & Scores

### View all financial health test results for a user:
```sql
SELECT test_type, raw_score, normalized_score, completed_at, insights 
FROM test_results 
WHERE user_id = 'YOUR_USER_ID_HERE';
```

### View overall wellness scores:
```sql
SELECT money_iq, debt_health, credit_health, overall_score, wellness_tier 
FROM wellness_breakdown 
WHERE user_id = 'YOUR_USER_ID_HERE';
```

---

## 🐍 8. Python Helper Scripts

Run these diagnostic commands directly from the backend project folder:

### Test database connection:
```powershell
python test_db_conn.py
```

### Print first 10 rows of all tables:
```powershell
python inspect_db.py
```

### Run a custom query directly from terminal:
```powershell
python run_query.py "SELECT COUNT(*) FROM users;"
```

### Migrate local SQLite data (`test.db`) to AWS RDS:
```powershell
python migrate_sqlite_to_postgres.py
```

---

## ⚠️ 9. Reset Database Tables

### Clear user data only (keeps schema):
```sql
TRUNCATE TABLE users, conversations, conversation_messages, mood_live_state, mood_trend_state, test_results, wellness_breakdown, user_consolidated_profiles, user_credit_reports, user_loan_calculator_activities, advisor_appointments CASCADE;
```

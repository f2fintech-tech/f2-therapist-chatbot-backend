# 🔧 CODESPACES BACKEND URL FIX

## Problem Identified

Your frontend is running in GitHub Codespaces and trying to reach `http://localhost:8000/api/v1`, which doesn't exist in the Codespaces environment. The backend is running on a Codespaces port-forwarded URL.

## Solution

Update your frontend's `.env` file to use the correct Codespaces backend URL.

### Step 1: Find Your Backend Codespaces URL

In VS Code Codespaces:
1. Click the **"Ports"** tab at the bottom
2. Look for port `8000` 
3. You should see a forwarded URL like: `https://redesigned-chainsaw-pj6x7w7vv99w29r4p-8000.app.github.dev`

### Step 2: Update Frontend .env

In your **frontend repository** (not this backend repo), find or create `.env.local`:

**Currently you have:**
```env
VITE_API_BASE_URL=http://localhost:8000/api/v1
VITE_API_KEY=dev-key
```

**Change to:**
```env
VITE_API_BASE_URL=https://redesigned-chainsaw-pj6x7w7vv99w29r4p-8000.app.github.dev/api/v1
VITE_API_KEY=dev-key
```

> **Note:** Replace `redesigned-chainsaw-pj6x7w7vv99w29r4p` with YOUR actual Codespaces subdomain from the Ports panel.

### Step 3: Verify Backend is Running

1. In your backend terminal, make sure it's running:
   ```bash
   python -m uvicorn src.main:app --reload
   ```

2. Test the backend is accessible:
   - Open the backend Codespaces URL in your browser
   - You should see: `{"message": "Financial Therapist Chatbot API", "version": "1.0.0", ...}`

### Step 4: Restart Frontend

1. Stop the frontend development server (Ctrl+C)
2. Restart it:
   ```bash
   pnpm dev
   ```

3. Visit your frontend URL and test the chat

## Why This Works

- **In Codespaces:** `localhost` doesn't exist. All services are accessed via their Codespaces forwarded URLs.
- **Codespaces URL format:** `https://{random-name}-{port}.app.github.dev`
- **CORS is configured:** Your backend already has Codespaces CORS support with: `allow_origin_regex=r"https://.*\.app\.github\.dev"`

## If This Doesn't Work

Run these diagnostic commands:

```bash
# Check if backend is running
curl -v https://redesigned-chainsaw-pj6x7w7vv99w29r4p-8000.app.github.dev/

# Check CORS headers
curl -i -X OPTIONS \
  -H "Origin: https://redesigned-chainsaw-pj6x7w7vv99w29r4p-5173.app.github.dev" \
  https://redesigned-chainsaw-pj6x7w7vv99w29r4p-8000.app.github.dev/api/v1/chat

# Test chat endpoint
curl -X POST https://redesigned-chainsaw-pj6x7w7vv99w29r4p-8000.app.github.dev/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "test", "user_id": "550e8400-e29b-41d4-a716-446655440000"}'
```

## Why Your Collaborator's Setup Works

Your collaborator likely has their frontend `.env` configured with the correct Codespaces backend URL. That's the only difference!

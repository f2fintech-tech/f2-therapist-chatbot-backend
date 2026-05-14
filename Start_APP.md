# 🚀 Starting the F2Finheal Application

## For Local Development (Outside Codespaces)

### Backend
```bash
cd /workspaces/f2-therapist-chatbot-backend
source .venv/bin/activate
python -m uvicorn src.main:app --reload
```

### Frontend
```bash
cd /workspaces/f2-therapist-chatbot-frontend
pnpm install  # one time only
PORT=5173 BASE_PATH=/ pnpm --filter @workspace/f2-finheal dev
```

The frontend should then be available at: `http://localhost:5173`

---

## For GitHub Codespaces ⚠️ IMPORTANT

### CRITICAL SETUP STEP - Configure Backend URL
Before starting the frontend, you MUST update the backend URL in your frontend repository's `.env.local`:

```bash
# Option 1: Automatic Setup (Recommended)
bash /workspaces/f2-therapist-chatbot-backend/setup_codespaces_urls.sh

# Option 2: Manual Setup
# Check the Ports panel and find your Codespaces subdomain (e.g., redesigned-chainsaw-pj6x7w7vv99w29r4p)
# In your frontend repository, create/update .env.local:
# VITE_API_BASE_URL=https://<your-codespace-name>-8000.app.github.dev/api/v1
# VITE_API_KEY=dev-key
```

### Backend (Codespaces)
```bash
cd /workspaces/f2-therapist-chatbot-backend
source .venv/bin/activate
python -m uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend (Codespaces)
```bash
cd /workspaces/f2-therapist-chatbot-frontend
pnpm install  # one time only
pnpm dev
```

**Frontend URL:** Check the Ports panel for `port 5173`

---

## ⚠️ If Backend Requests Are Failing

**Most Common Issue in Codespaces:** Frontend is configured with `http://localhost:8000/api/v1` but should use the Codespaces URL.

See [CODESPACES_FIX.md](CODESPACES_FIX.md) for detailed troubleshooting.
<!-- Local startup on Windows

Backend:
cd D:\FinHeal-Friend\f2-therapist-chatbot-backend
python -m uvicorn src.main:app --reload

Frontend:
cd D:\FinHeal-Friend\f2-therapist-chatbot-frontend
corepack pnpm install
$env:PORT="5173"; $env:BASE_PATH="/"; corepack pnpm --filter @workspace/f2-finheal dev
-->


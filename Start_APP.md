<!-- Local startup on Windows

Backend:
cd D:\FinHeal-Friend\f2-therapist-chatbot-backend
python -m pip install -r requirements.txt
python -m uvicorn src.main:app --reload

Frontend:
cd D:\FinHeal-Friend\f2-therapist-chatbot-frontend
corepack pnpm install
$env:PORT="5173"; $env:BASE_PATH="/"; corepack pnpm --filter @workspace/f2-finheal dev
-->

<!-- Local startup on macOS

Backend:
cd ~/FinHeal-Friend/f2-therapist-chatbot-backend
python3 -m pip install -r requirements.txt
python3 -m uvicorn src.main:app --reload

Frontend:
cd ~/FinHeal-Friend/f2-therapist-chatbot-frontend
corepack pnpm install
export PORT=5173 BASE_PATH=/
corepack pnpm --filter @workspace/f2-finheal dev
-->


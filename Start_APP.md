<!-- Local startup on Windows
Backend:
cd D:\FinHeal-Friend\f2-therapist-chatbot-backend
Start venv : " .\.venv\Scripts\Activate.ps1"
python -m pip install -r requirements.txt
python -m uvicorn src.main:app --reload

Frontend:
cd D:\FinHeal-Friend\f2-therapist-chatbot-frontend
corepack pnpm install
corepack pnpm dev

<!-- Local startup on macOS

Backend:
cd ~/FinHeal-Friend/f2-therapist-chatbot-backend
python3 -m pip install -r requirements.txt
python3 -m uvicorn src.main:app --reload

Frontend:
cd f2-therapist-chatbot-frontend
corepack pnpm install
corepack pnpm dev
-->


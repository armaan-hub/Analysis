# How to Run the Project (Windows)

Project folder:
`Project_AccountingLegalChatbot`

## 1) One-time setup

From this folder (`35. 11-Apr-2026`), run:

```powershell
.\setup_python_env.bat
```

This creates/updates:
- `Project_AccountingLegalChatbot\backend\venv`
- Backend Python packages from `backend\requirements.txt`

Then install frontend packages:

```powershell
Set-Location .\Project_AccountingLegalChatbot\frontend
npm ci
Set-Location ..\..
```

## 2) Configure environment

```powershell
Copy-Item .\Project_AccountingLegalChatbot\.env.example .\Project_AccountingLegalChatbot\.env -Force
```

Edit `.env` and add your API keys.

## 3) Run backend API

```powershell
Set-Location .\Project_AccountingLegalChatbot\backend
.\venv\Scripts\activate
python main.py
```

- API docs: `http://localhost:8000/docs`
- If your `.env` sets `PORT=8080`, use `http://localhost:8080/docs` instead.

## 4) Run frontend UI (new terminal)

```powershell
Set-Location .\Project_AccountingLegalChatbot\frontend
npm run dev
```

Frontend URL is shown by Vite (usually `http://localhost:5173`).

## 5) Useful checks

Backend tests:

```powershell
Set-Location .\Project_AccountingLegalChatbot\backend
.\venv\Scripts\python.exe -m pytest tests -q
```

Frontend checks:

```powershell
Set-Location .\Project_AccountingLegalChatbot\frontend
npm run lint
npm run build
```

# Demet — Instagram İçerik Planlama ve Mesaj Yönetim Sistemi

## Monorepo

```
backend/   — FastAPI Python backend
frontend/  — Next.js frontend
```

## Railway Deployment

### Backend Service
- Root: `backend/`
- Builder: Nixpacks (Python)
- Volume: `/data` → SQLite DB, sessions, uploads

### Frontend Service  
- Root: `frontend/`
- Builder: Nixpacks (Node.js)
- Env: `NEXT_PUBLIC_API_URL=https://<backend-url>/api`

### Environment Variables (Backend)
```env
DATABASE_URL=sqlite:////data/demet.db
DATA_DIR=/data
SECRET_KEY=<generate>
JWT_SECRET_KEY=<generate>
ENCRYPTION_KEY=<generate>
FRONTEND_URL=https://<frontend-url>
DEBUG=false
```

## Local Development
```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000

# Frontend
cd frontend
npm install
npm run dev
```

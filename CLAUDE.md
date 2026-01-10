# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CoinMrkt is a fullstack web application for selling precious metal coins (gold, silver, etc.). It uses a Python/FastAPI backend with MongoDB for data storage. The backend serves the static frontend files directly.

## Commands

### Run the application
```bash
docker compose up --build
```
Access the app at http://localhost:8000

### Run backend only (development)
```bash
cd backend
pip install -r requirements.txt
MONGO_URL=mongodb://localhost:27017 uvicorn main:app --reload
```
Note: For local development, copy frontend files to `backend/static/`

### Stop and clean up
```bash
docker compose down -v  # -v removes volumes including database data
```

## Architecture

```
├── backend/
│   ├── main.py       # FastAPI app, serves static files from /static
│   ├── models.py     # Pydantic models (Coin, Order)
│   ├── database.py   # MongoDB connection via Motor (async)
│   └── Dockerfile    # Copies frontend into /app/static
├── frontend/         # Static files (HTML, CSS, JS)
│   ├── index.html
│   ├── styles.css
│   └── app.js        # Client-side state and API calls
└── docker-compose.yml
```

### API Endpoints
- `GET /` - Serves index.html
- `GET /api/coins` - List all coins
- `GET /api/coins/{id}` - Get single coin
- `POST /api/coins` - Create coin
- `DELETE /api/coins/{id}` - Delete coin
- `POST /api/orders` - Create order (decrements stock)
- `GET /api/orders` - List all orders

### Data Flow
1. FastAPI serves index.html on root route and static files (CSS, JS)
2. Frontend fetches data from `/api/*` endpoints
3. Backend uses Motor (async MongoDB driver) for database operations
4. On first startup, backend seeds sample coin data if collection is empty

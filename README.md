# Harvest - FastAPI Monolith

A FastAPI-based monolithic application with PostgreSQL and Redis.

## Setup

### 1. Create and activate virtual environment

```bash
# Create virtual environment
python -m venv .venv

# Activate on Windows
.venv\Scripts\activate

# Activate on Linux/Mac
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Set up environment variables

```bash
copy .env.example .env
```

### 4. Start Docker services

```bash
docker-compose up -d
```

### 5. Run the application

```bash
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`
API documentation at `http://localhost:8000/docs`

## Docker Commands

- Start services: `docker-compose up -d`
- Stop services: `docker-compose down`
- View logs: `docker-compose logs -f`
- Restart services: `docker-compose restart`

# openai-travel-service

FastAPI backend for travel data integrations.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` and set your TransportAPI credentials:

```bash
TRANSPORTAPI_APP_ID=your_app_id
TRANSPORTAPI_APP_KEY=your_app_key
```

## Run

```bash
source .venv/bin/activate
uvicorn app.main:app --reload --env-file .env --host 127.0.0.1 --port 8000
```

## API

```bash
curl "http://127.0.0.1:8000/health"
curl "http://127.0.0.1:8000/api/bus-stops?query=51.5074,-0.1278"
curl "http://127.0.0.1:8000/api/bus-stops?query=SW1A%201AA"
curl "http://127.0.0.1:8000/api/bus-stops/490013767X/departures?limit=5"
```

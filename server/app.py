from fastapi import FastAPI, HTTPException
from typing import List
from schemas import ImpressionEvent, ClickEvent
from store import InMemoryStore
from model import OnlineModel
from fastapi.middleware.cors import CORSMiddleware
from google_suggest_seeder import load_cache, save_cache, fetch_google_suggestions,seed_google_suggestions
from datetime import datetime, timezone
import trainer

app = FastAPI()

origins = [
    "http://localhost:4200",  # Angular dev
    # add prod domain later
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global in-memory components
store = InMemoryStore()
model = OnlineModel()

@app.on_event("startup")
def on_startup():
    # Start background trainer with references to store and model
    trainer.start_trainer(store, model)

    # ---- SEED STATIC KNOWN QUERIES ----
    initial_queries = [
        "leave policy",
        "leave application form",
        "holiday calendar",
        "salary slip",
        "attendance regularization",
        "work from home policy",
        "travel reimbursement",
        "expense claim",
        "performance review",
        "health insurance",
        "id card request",
        "vpn setup",
        "email signature",
        "timesheet submission",
        "it support",
        "training enrollment",
        "shift change request",
        "benefits portal",
        "project guidelines",
        "company handbook",
    ]
    for q in initial_queries:
        store.add_query(q, increment=5)

    # ---- SEED GOOGLE SUGGESTIONS ----
    seed_google_suggestions(
        store,
        prefixes=["leave", "salary", "policy", "how to", "request", "id card"],
        increment=2,
        ttl_days=7,
        max_size=1000
    )

@app.get('/suggest')
def suggest(prefix: str = '', k: int = 10):
    candidates = store.get_prefix_candidates(prefix, limit=50) if prefix else store.get_top_n(limit=50)
    if not candidates:
        google_suggestions = fetch_google_suggestions(prefix)
        for s in google_suggestions:
            store.add_query(s, increment=1)
        candidates = google_suggestions
    pairs = model.score_candidates(prefix, candidates, store)
    top = pairs[:k]
    return {"suggestions": [{"text": p, "score": float(s)} for p, s in top]}

@app.post('/log_event')
def log_event(ev: dict):
    ev_type = ev.get('type')
    if ev_type not in ('impression', 'click'):
        raise HTTPException(status_code=400, detail='type must be impression or click')
    # Update in-memory popularity and ensure candidates exist
    if ev_type == 'impression':
        q = ev.get('query')
        if q:
            store.add_query(q, increment=1)
        for cand in ev.get('candidates', [])[:20]:
            store.add_query(cand, increment=0)
        if ev.get('clicked'):
            store.add_query(ev.get('clicked'), increment=5)
    else:
        cand = ev.get('candidate')
        if cand:
            store.add_query(cand, increment=5)
    # Enqueue for trainer
    trainer.enqueue_event(ev)
    return {"status": "ok"}

@app.get('/health')
def health():
    return {"status": "ok"}
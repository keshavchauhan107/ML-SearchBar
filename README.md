# ML-SearchBar
Usage (development):
1. Create a virtualenv and install requirements: pip install -r requirements.txt
2. Run the app: uvicorn app:app --reload --port 8000
3. Endpoints:
   - GET  /suggest?prefix=...&k=10
   - POST /log_event  {"type":"impression","query":"...","candidates":["a","b"],"clicked":null}
   - POST /log_event  {"type":"click","query":"...","candidate":"..."}

Notes:
- This in-memory version is ephemeral: restarting the process clears popularity counters and the model state.
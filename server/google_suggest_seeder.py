# google_suggest_seeder.py
"""
Google Suggest Seeder with robust file cache
-------------------------------------------
Features implemented:
  - cache stored in ./cache/google_suggest_cache.json
  - per-prefix fetched_at timestamp and TTL-based expiration (default 7 days)
  - max-size limit for cache (default 1000 prefixes) with eviction of oldest entries
  - atomic writes to avoid corruption
  - optional force refresh flag
  - safe fallbacks when network calls fail

Usage:
    from google_suggest_seeder import seed_google_suggestions
    seed_google_suggestions(store)

You can customize TTL, max_size, cache_dir, prefixes, increment, and force_refresh.
"""

import json
import os
import time
from pathlib import Path
from datetime import datetime, timezone, timedelta
import requests


DEFAULT_CACHE_DIR = Path("./cache")
DEFAULT_CACHE_FILE = "google_suggest_cache.json"
GOOGLE_URL = "https://suggestqueries.google.com/complete/search"


def _now_utc_iso():
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def _parse_iso(ts: str):
    # Accept ISO with Z or offset
    if not ts:
        return None
    try:
        if ts.endswith('Z'):
            ts2 = ts[:-1] + '+00:00'
            return datetime.fromisoformat(ts2)
        return datetime.fromisoformat(ts)
    except Exception:
        return None


def _ensure_cache_dir(cache_dir: Path):
    cache_dir.mkdir(parents=True, exist_ok=True)


def get_cache_path(cache_dir: Path = DEFAULT_CACHE_DIR, cache_file: str = DEFAULT_CACHE_FILE) -> Path:
    _ensure_cache_dir(cache_dir)
    return cache_dir / cache_file


def load_cache(cache_dir: Path = DEFAULT_CACHE_DIR, cache_file: str = DEFAULT_CACHE_FILE):
    path = get_cache_path(cache_dir, cache_file)
    if not path.exists():
        return {}
    try:
        with path.open('r', encoding='utf-8') as f:
            data = json.load(f)
            # Validate shape: prefix -> {"suggestions": [...], "fetched_at": "..."}
            if not isinstance(data, dict):
                return {}
            return data
    except Exception:
        # fallback to empty cache on parse/read errors
        return {}


def save_cache(cache: dict, cache_dir: Path = DEFAULT_CACHE_DIR, cache_file: str = DEFAULT_CACHE_FILE):
    path = get_cache_path(cache_dir, cache_file)
    tmp = path.with_suffix('.tmp')
    try:
        with tmp.open('w', encoding='utf-8') as f:
            json.dump(cache, f, indent=2, ensure_ascii=False)
        # atomic replace
        os.replace(tmp, path)
    except Exception:
        # best-effort: try direct write
        try:
            with path.open('w', encoding='utf-8') as f:
                json.dump(cache, f, indent=2, ensure_ascii=False)
        except Exception:
            # silently ignore write failures to avoid breaking startup
            pass


def fetch_google_suggestions(query: str, max_retries: int = 2, timeout: float = 5.0):
    """Fetch suggestions from Google Suggest (unofficial API). Returns list of strings."""
    params = {"client": "firefox", "q": query}
    last_exc = None
    for attempt in range(max_retries + 1):
        try:
            resp = requests.get(GOOGLE_URL, params=params, timeout=timeout)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list) and len(data) > 1 and isinstance(data[1], list):
                    return [s for s in data[1] if isinstance(s, str)]
            # non-200 or unexpected shape -> return empty to avoid seeding bad data
            return []
        except Exception as e:
            last_exc = e
            # simple backoff
            time.sleep(0.3 * (attempt + 1))
    # all retries failed -> return empty
    return []


def _is_expired(fetched_at_iso: str, ttl_days: int) -> bool:
    if not fetched_at_iso:
        return True
    dt = _parse_iso(fetched_at_iso)
    if not dt:
        return True
    return datetime.now(timezone.utc) - dt > timedelta(days=ttl_days)


def _evict_if_needed(cache: dict, max_size: int):
    """Evict oldest entries until cache size <= max_size."""
    if max_size is None or max_size <= 0:
        return cache
    if len(cache) <= max_size:
        return cache
    # build list of (prefix, fetched_at_datetime)
    items = []
    for k, v in cache.items():
        fa = v.get('fetched_at') if isinstance(v, dict) else None
        dt = _parse_iso(fa) or datetime.fromtimestamp(0, timezone.utc)
        items.append((k, dt))
    # sort by oldest first
    items.sort(key=lambda x: x[1])
    to_remove = len(cache) - max_size
    for i in range(to_remove):
        key = items[i][0]
        cache.pop(key, None)
    return cache


def seed_google_suggestions(store,
                             prefixes=None,
                             increment: int = 2,
                             cache_dir: Path = DEFAULT_CACHE_DIR,
                             cache_file: str = DEFAULT_CACHE_FILE,
                             ttl_days: int = 7,
                             max_size: int = 1000,
                             force_refresh: bool = False):
    """
    Seeds the InMemoryStore using Google Suggest with robust caching.

    Args:
        store: your InMemoryStore instance (must implement add_query)
        prefixes: list of prefixes to query. If None a reasonable set is used.
        increment: popularity increment to apply when seeding
        cache_dir: directory where cache file will be stored (Path or str)
        cache_file: cache filename
        ttl_days: time-to-live in days for cached entries (default 7)
        max_size: maximum number of prefix entries to retain in cache
        force_refresh: if True, ignore TTL and re-fetch all prefixes
    """
    if prefixes is None:
        prefixes = [
            "leave", "salary", "id card", "how to", "work from home",
            "holiday", "hr policy", "it support", "expense", "travel reimbursement",
        ]

    cache_dir = Path(cache_dir)
    cache = load_cache(cache_dir, cache_file)
    updated = False
    seeded_count = 0

    for p in prefixes:
        key = p.lower().strip()
        use_cached = (not force_refresh) and (key in cache) and (not _is_expired(cache.get(key, {}).get('fetched_at'), ttl_days))
        suggestions = []
        if use_cached:
            # Use cached suggestions
            entry = cache.get(key, {})
            suggestions = entry.get('suggestions', []) if isinstance(entry, dict) else []
        else:
            # Fetch from Google and update cache entry
            suggestions = fetch_google_suggestions(key)
            cache[key] = {
                'suggestions': suggestions,
                'fetched_at': _now_utc_iso()
            }
            updated = True

        # Seed into store (do not crash if store fails)
        for s in suggestions:
            try:
                store.add_query(s, increment=increment)
                seeded_count += 1
            except Exception:
                # ignore failures from store
                pass

    # Evict if cache too big
    cache = _evict_if_needed(cache, max_size)

    if updated:
        save_cache(cache, cache_dir, cache_file)

    print(f"[GoogleSeeder] Seeded {seeded_count} suggestions for {len(prefixes)} prefixes. cache_size={len(cache)}")


# __all__ exports
__all__ = [
    'seed_google_suggestions',
    'fetch_google_suggestions',
    'load_cache',
    'save_cache'
]

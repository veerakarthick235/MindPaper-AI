"""
session_store.py
----------------
Thread-safe in-memory session store for multi-user isolation.

Each session is keyed by UUID and auto-evicted after SESSION_TTL seconds
of inactivity. Calling touch() on a session resets its idle timer, so
long-running analyses don't expire mid-stream.
"""

import logging
import threading
import time
import uuid

logger = logging.getLogger(__name__)

# 4-hour session lifetime; refreshed on every meaningful API interaction
SESSION_TTL = 14_400  # seconds


class SessionStore:
    """
    Manages per-session state for the PaperMind RAG pipeline.

    Each session record stores:
        faiss_index  — FaissIndex instance for RAG Q&A (set after analysis)
        result       — full dict from PaperSummarizer.process_document()
        metadata     — extracted paper metadata (title, authors, doi, year)
        filename     — sanitised upload filename
        page_count   — estimated page count
        created_at   — UNIX timestamp of session creation
        last_active  — UNIX timestamp of last activity (used for TTL)
    """

    def __init__(self, ttl: int = SESSION_TTL):
        self._ttl   = ttl
        self._store: dict[str, dict] = {}
        self._lock  = threading.Lock()

        # Background eviction thread runs every 10 minutes
        t = threading.Thread(target=self._evict_loop, daemon=True)
        t.start()
        logger.info("SessionStore started (TTL=%ds)", self._ttl)

    # ── Public API ────────────────────────────────────────────────────────

    def create_session(self) -> str:
        """Create and register a new session; return its UUID."""
        sid = str(uuid.uuid4())
        now = time.time()
        with self._lock:
            self._store[sid] = {
                "faiss_index":  None,
                "result":       None,
                "metadata":     {},
                "filename":     None,
                "page_count":   0,
                "created_at":   now,
                "last_active":  now,
            }
        logger.debug("Session created: %s", sid)
        return sid

    def get(self, sid: str) -> dict | None:
        """
        Return the session dict if it exists and has not expired.
        Returns None if the session is unknown or stale.
        """
        with self._lock:
            session = self._store.get(sid)
            if session and self._is_alive(session):
                return session
        return None

    def update(self, sid: str, **kwargs) -> None:
        """Update fields on an existing session and refresh its TTL."""
        with self._lock:
            if sid in self._store:
                self._store[sid].update(kwargs)
                self._store[sid]["last_active"] = time.time()

    def touch(self, sid: str) -> None:
        """
        Refresh the session's idle timer without changing any data.
        Call this inside long-running SSE streams to prevent mid-analysis expiry.
        """
        with self._lock:
            if sid in self._store:
                self._store[sid]["last_active"] = time.time()

    def delete(self, sid: str) -> None:
        """Manually evict a session (e.g. on explicit logout)."""
        with self._lock:
            self._store.pop(sid, None)

    def stats(self) -> dict:
        """Return aggregate statistics for the /api/usage monitoring endpoint."""
        with self._lock:
            active  = sum(1 for s in self._store.values() if self._is_alive(s))
            total   = len(self._store)
        return {
            "active_sessions": active,
            "total_sessions":  total,
        }

    # ── Internal helpers ──────────────────────────────────────────────────

    def _is_alive(self, session: dict) -> bool:
        """True if the session has been active within the TTL window."""
        return (time.time() - session["last_active"]) < self._ttl

    def _evict_loop(self) -> None:
        """Background thread: sweep and evict stale sessions every 10 minutes."""
        while True:
            time.sleep(600)
            with self._lock:
                expired = [
                    sid
                    for sid, s in self._store.items()
                    if not self._is_alive(s)
                ]
                for sid in expired:
                    del self._store[sid]
            if expired:
                logger.info("Evicted %d stale session(s)", len(expired))


# ── Singleton ─────────────────────────────────────────────────────────────
# Shared across the entire Flask application process
store = SessionStore()

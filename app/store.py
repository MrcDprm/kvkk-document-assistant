"""In-memory session store.

Documents and the pseudonym table are kept only in memory, never on disk or in a database.
A session expires after `ttl_seconds` without use; when the store is full the session that
was used least recently is dropped. A server restart therefore deletes everything, by design.
"""

import secrets
import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass, field

from kvkk_mask import Entity
from kvkk_mask.pseudonymizer import Pseudonymizer


@dataclass
class AuditEntry:
    """One request to the LLM: exactly what left the server, and what it cost."""
    kind: str
    sent_text: str
    input_tokens: int
    output_tokens: int
    latency_ms: int


@dataclass
class Session:
    id: str
    last_used: float
    filename: str = ""
    text: str = ""
    entities: list[Entity] = field(default_factory=list)
    excluded: set[str] = field(default_factory=set)  # tokens the user marked as wrong (all mentions)
    pseudonymizer: Pseudonymizer = field(default_factory=Pseudonymizer)
    audit: list[AuditEntry] = field(default_factory=list)


class SessionStore:
    def __init__(self, ttl_seconds: int, max_sessions: int, clock: Callable[[], float] = time.monotonic):
        self._ttl = ttl_seconds
        self._max = max_sessions
        self._clock = clock
        self._sessions: OrderedDict[str, Session] = OrderedDict()  # least recently used first
        self._lock = threading.Lock()

    def create(self) -> Session:
        with self._lock:
            self._purge_expired()
            while len(self._sessions) >= self._max:
                self._sessions.popitem(last=False)
            # 32 random bytes: the session id is the only key to the document, so it must be unguessable.
            session = Session(id=secrets.token_urlsafe(32), last_used=self._clock())
            self._sessions[session.id] = session
            return session

    def get(self, session_id: str | None) -> Session | None:
        if not session_id:
            return None
        with self._lock:
            self._purge_expired()
            session = self._sessions.get(session_id)
            if session is not None:
                session.last_used = self._clock()
                self._sessions.move_to_end(session_id)
            return session

    def delete(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)

    def __len__(self) -> int:
        with self._lock:
            self._purge_expired()
            return len(self._sessions)

    def _purge_expired(self) -> None:
        deadline = self._clock() - self._ttl
        # Ordered by last use, so expired sessions are all at the front.
        while self._sessions:
            oldest = next(iter(self._sessions.values()))
            if oldest.last_used > deadline:
                break
            self._sessions.popitem(last=False)

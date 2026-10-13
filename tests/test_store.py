from app.store import SessionStore


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_create_and_get():
    store = SessionStore(ttl_seconds=60, max_sessions=10)
    session = store.create()
    assert store.get(session.id) is session
    assert store.get("unknown") is None
    assert store.get(None) is None


def test_session_ids_are_long_and_unique():
    store = SessionStore(ttl_seconds=60, max_sessions=100)
    ids = {store.create().id for _ in range(50)}
    assert len(ids) == 50
    assert all(len(i) >= 40 for i in ids)


def test_session_expires_after_ttl_without_use():
    clock = FakeClock()
    store = SessionStore(ttl_seconds=60, max_sessions=10, clock=clock)
    session = store.create()
    clock.now += 59
    assert store.get(session.id) is session  # using it resets the timer
    clock.now += 59
    assert store.get(session.id) is session
    clock.now += 61
    assert store.get(session.id) is None
    assert len(store) == 0


def test_least_recently_used_session_is_dropped_when_full():
    clock = FakeClock()
    store = SessionStore(ttl_seconds=600, max_sessions=2, clock=clock)
    a = store.create()
    clock.now += 1
    b = store.create()
    clock.now += 1
    store.get(a.id)  # a is now newer than b
    clock.now += 1
    c = store.create()
    assert store.get(b.id) is None
    assert store.get(a.id) is a
    assert store.get(c.id) is c


def test_delete():
    store = SessionStore(ttl_seconds=60, max_sessions=10)
    session = store.create()
    store.delete(session.id)
    store.delete(session.id)  # deleting twice is fine
    assert store.get(session.id) is None

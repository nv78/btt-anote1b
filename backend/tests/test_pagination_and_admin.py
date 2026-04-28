"""Cursor pagination, admin submissions, and CSV export shape."""

from __future__ import annotations

from datetime import timedelta

try:
    import app as app_module
except ImportError:
    import backend.app as app_module  # type: ignore

app = app_module.app
_STORE = app_module._STORE


def _clear_store():
    _STORE["submissions"].clear()
    _STORE["evaluations"].clear()
    _STORE["datasets"].clear()


def _seed_leaderboard_rows():
    """Order after sort (dataset ASC, score DESC, id DESC): (a,0.8,3), (a,0.5,2), (b,0.9,1)."""
    _clear_store()
    base = app_module.utc_now()
    rows = [
        ("b", 0.9, 1),
        ("a", 0.5, 2),
        ("a", 0.8, 3),
    ]
    for ds, sc, sid in rows:
        _STORE["submissions"].append({
            "id": sid,
            "benchmark_dataset_name": ds,
            "model_name": f"m{sid}",
            "submitter_id": "user-a",
            "submitted_by": "user-a",
            "created": base - timedelta(seconds=sid),
        })
        _STORE["evaluations"].append({
            "submission_id": sid,
            "score": sc,
            "metric": "bleu",
            "evaluation_details": {"metric": "bleu", "detailed_scores": {"n": sid}},
        })


def test_get_leaderboard_keyset_matches_offset(monkeypatch):
    monkeypatch.setattr(app_module, "get_db_connection", lambda: (None, None))
    _seed_leaderboard_rows()
    with app.test_client() as c:
        off = c.get("/public/get_leaderboard?page_size=2&page=2")
        cur = c.get("/public/get_leaderboard?page_size=2")
        assert cur.status_code == 200
        j0 = cur.get_json()
        nc = j0.get("next_cursor")
        assert nc
        c2 = c.get("/public/get_leaderboard?page_size=2&cursor=" + nc)
        assert c2.status_code == 200
        j_off = off.get_json()
        j_cur = c2.get_json()
        assert [x["submission_id"] for x in j_off["leaderboard"]] == [
            x["submission_id"] for x in j_cur["leaderboard"]
        ]


def test_my_submissions_cursor(monkeypatch):
    monkeypatch.setattr(app_module, "get_db_connection", lambda: (None, None))
    _seed_leaderboard_rows()
    with app.test_client() as c:
        r1 = c.get("/public/my_submissions?submitter_id=user-a&page_size=2")
        assert r1.status_code == 200
        j1 = r1.get_json()
        assert len(j1["submissions"]) == 2
        nc = j1.get("next_cursor")
        assert nc
        r2 = c.get("/public/my_submissions?submitter_id=user-a&page_size=2&cursor=" + nc)
        j2 = r2.get_json()
        assert len(j2["submissions"]) == 1


def test_admin_submissions_requires_config(monkeypatch):
    monkeypatch.setattr(app_module, "get_db_connection", lambda: (None, None))
    monkeypatch.delenv("LEADERBOARD_ADMIN_API_KEYS", raising=False)
    with app.test_client() as c:
        r = c.get("/api/admin/submissions", headers={"X-Admin-Key": "x"})
        assert r.status_code == 503


def test_admin_submissions_lists_rows(monkeypatch):
    monkeypatch.setenv("LEADERBOARD_ADMIN_API_KEYS", "secret-admin")
    monkeypatch.setattr(app_module, "get_db_connection", lambda: (None, None))
    _seed_leaderboard_rows()
    with app.test_client() as c:
        r = c.get("/api/admin/submissions", headers={"X-Admin-Key": "secret-admin"})
        assert r.status_code == 200
        data = r.get_json()
        assert data["success"] is True
        assert len(data["submissions"]) == 3


def test_export_csv_headers(monkeypatch):
    monkeypatch.setattr(app_module, "get_db_connection", lambda: (None, None))
    _seed_leaderboard_rows()
    with app.test_client() as c:
        r = c.get("/public/export/leaderboard?format=csv")
        assert r.status_code == 200
        text = r.get_data(as_text=True)
        first = text.splitlines()[0]
        assert "primary_metric" in first
        assert "detailed_scores_json" in first
        assert "submission_id" in first


def test_pagination_cursor_roundtrip():
    try:
        from pagination import (
            decode_cursor,
            leaderboard_cursor_decode,
            leaderboard_cursor_encode,
            my_submissions_cursor_decode,
            my_submissions_cursor_encode,
        )
    except ImportError:
        from backend.pagination import (  # type: ignore
            decode_cursor,
            leaderboard_cursor_decode,
            leaderboard_cursor_encode,
            my_submissions_cursor_decode,
            my_submissions_cursor_encode,
        )

    t = leaderboard_cursor_encode(
        dataset_name="ds",
        score=1.5,
        submission_id=99,
        next_rank_start=3,
        single_dataset=False,
    )
    d = decode_cursor(t)
    dec = leaderboard_cursor_decode(d)
    assert dec == (False, "ds", 1.5, 99, 3)

    t2 = my_submissions_cursor_encode("2024-01-01T00:00:00+00:00", 42)
    d2 = decode_cursor(t2)
    assert my_submissions_cursor_decode(d2) == ("2024-01-01T00:00:00+00:00", 42)

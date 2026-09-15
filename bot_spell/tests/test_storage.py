import storage


def make(tmp_path):
    return storage.Storage(tmp_path / "t.sqlite3")


def test_topic_roundtrip(tmp_path):
    s = make(tmp_path)
    assert s.topic(1) is None
    s.set_topic(1, 10)
    assert s.topic(1) == 10
    s.set_topic(1, None)
    assert s.topic(1) is None


def test_stats_counts_and_streak(tmp_path):
    s = make(tmp_path)
    s.record_attempt(1, "sd1", 9, True)
    s.record_attempt(1, "sd2", 9, False)
    s.record_attempt(1, "sd3", 10, True)
    s.record_attempt(1, "sd4", 10, True)
    st = s.stats(1)
    assert st["total_attempts"] == 4
    assert st["correct"] == 3
    assert st["unique_tasks"] == 4
    assert st["streak"] == 2
    assert st["per_topic"] == [
        {"task_no": 9, "total": 2, "correct": 1},
        {"task_no": 10, "total": 2, "correct": 2},
    ]


def test_pick_next_prefers_unseen_and_avoids_repeat(tmp_path):
    s = make(tmp_path)
    ids = ["a", "b", "c"]
    s.record_attempt(1, "a", 9, True)
    for _ in range(30):
        assert s.pick_next(1, ids) != "a"  # "a" is both seen and last


def test_pick_next_single_task(tmp_path):
    s = make(tmp_path)
    assert s.pick_next(1, ["only"]) == "only"
    assert s.pick_next(1, []) is None

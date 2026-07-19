from scripts.check_verified import check_verified

BASE = {"reproduced_overall": 95.0, "committed_overall": 95.2, "tolerance": 0.5}


def test_within_tolerance_passes():
    ok, msg = check_verified({**BASE, "delta": 0.2})
    assert ok and "within" in msg


def test_outside_tolerance_fails():
    ok, msg = check_verified({**BASE, "reproduced_overall": 94.0})
    assert not ok and "tolerance" in msg.lower()


def test_missing_overall_fails():
    ok, msg = check_verified({"reproduced_overall": 95.0})
    assert not ok

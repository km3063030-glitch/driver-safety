from services.ingest.rules import HarshBurstRule


def make():
    return HarshBurstRule(window_s=60, threshold=3, cooldown_s=300)


def test_fires_at_threshold():
    rule = make()
    assert rule.observe("V", 0) is None
    assert rule.observe("V", 10) is None
    assert rule.observe("V", 20) == 3


def test_cooldown_suppresses_repeat_then_refires():
    rule = make()
    for t in (0, 10, 20):
        rule.observe("V", t)
    assert rule.observe("V", 30) is None
    rule.observe("V", 400)
    rule.observe("V", 410)
    assert rule.observe("V", 420) == 3


def test_old_events_expire():
    rule = make()
    rule.observe("V", 0)
    rule.observe("V", 10)
    assert rule.observe("V", 100) is None


def test_out_of_order_events_still_count():
    rule = make()
    rule.observe("V", 20)
    rule.observe("V", 0)
    assert rule.observe("V", 10) == 3


def test_vehicles_are_independent():
    rule = make()
    for t in (0, 10):
        rule.observe("A", t)
    assert rule.observe("B", 20) is None
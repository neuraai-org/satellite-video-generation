from geovideo.schemas import TimelineConfig
from geovideo.timeline import build_poi_cues, timeline_state_at


def test_build_poi_cues():
    cfg = TimelineConfig(duration=5.0, intro_delay=1.0, poi_stagger=0.5)
    cues = build_poi_cues(3, cfg)
    assert cues[0].start == 1.0
    assert cues[1].start == 1.5
    assert cues[2].start == 2.0


def test_timeline_state():
    cfg = TimelineConfig(duration=5.0, intro_delay=0.0, poi_stagger=1.0)
    state = timeline_state_at(1.2, 2, cfg, default_zoom=12)
    assert state.active_index == 1
    assert 0.0 <= state.reveal_progress <= 1.0

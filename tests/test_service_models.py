from service_models import BookmarkRecordModel, ProgressEntryModel


def test_bookmark_record_model_clamps_and_rounds_values():
    record = BookmarkRecordModel(time=15.9876, duration=10.0, track=-3)

    assert record.time == 10.0
    assert record.duration == 10.0
    assert record.track == 0


def test_progress_entry_model_clamps_percent_and_counts():
    entry = ProgressEntryModel(percent=145.2, current_frag=-2, total_frags=-5)

    assert entry.percent == 100.0
    assert entry.current_frag == 0
    assert entry.total_frags == 0

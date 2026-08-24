"""Unit tests for publish-time coverage metadata (no database required)."""

from datetime import date

from etl.publish import _coverage


def _days(*specs: tuple[int, int, int]) -> list[date]:
    return [date(*s) for s in specs]


def test_empty_series_reports_nothing():
    assert _coverage([]) == {
        "first_snapshot_date": None,
        "latest_snapshot_date": None,
        "consecutive_since": None,
        "coverage_gaps": [],
    }


def test_unbroken_series_has_no_gaps():
    got = _coverage(_days((2026, 8, 22), (2026, 8, 23), (2026, 8, 24)))
    assert got["coverage_gaps"] == []
    assert got["first_snapshot_date"] == "2026-08-22"
    assert got["consecutive_since"] == "2026-08-22"
    assert got["latest_snapshot_date"] == "2026-08-24"


def test_gap_is_reported_with_inclusive_bounds():
    got = _coverage(_days((2026, 8, 9), (2026, 8, 24)))
    assert got["coverage_gaps"] == [{"start": "2026-08-10", "end": "2026-08-23", "days": 14}]


def test_first_snapshot_date_survives_a_gap():
    """The bug this guards: a gap must not erase the start of history.

    `first_snapshot_date` is what the site prints as "history begins"; if it
    tracked the consecutive run instead, the 2026-08 source migration would
    have claimed no data existed before the migration date.
    """
    got = _coverage(_days((2026, 4, 24), (2026, 8, 9), (2026, 8, 24)))
    assert got["first_snapshot_date"] == "2026-04-24"
    assert got["consecutive_since"] == "2026-08-24"


def test_consecutive_since_tracks_only_the_latest_run():
    got = _coverage(_days((2026, 8, 1), (2026, 8, 5), (2026, 8, 6), (2026, 8, 7)))
    assert got["consecutive_since"] == "2026-08-05"
    assert len(got["coverage_gaps"]) == 1


def test_multiple_gaps_are_all_reported():
    got = _coverage(_days((2026, 1, 1), (2026, 1, 5), (2026, 1, 6), (2026, 2, 1)))
    assert [g["days"] for g in got["coverage_gaps"]] == [3, 25]


def test_single_snapshot_is_its_own_start_and_end():
    got = _coverage(_days((2026, 8, 24)))
    assert got["first_snapshot_date"] == got["latest_snapshot_date"] == "2026-08-24"
    assert got["consecutive_since"] == "2026-08-24"
    assert got["coverage_gaps"] == []

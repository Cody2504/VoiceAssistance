"""Tests for build_consistency_map (cross-view consistency, Part 1)."""
from consistency_map import build_consistency_map


def test_identity_for_unmixed_row():
    # rows without org_clip_ids_order have no map (loss skipped)
    assert build_consistency_map(None, "v1") == []
    assert build_consistency_map([], "v1") == []


def test_maps_own_vid_entries_to_source_ranges():
    order = [["v1", [5, 7]], ["v2", [0, 3]], ["v1", [0, 2]]]
    # mixed positions: 0-1 -> v1[5:7], 2-4 -> donor v2, 5-6 -> v1[0:2]
    assert build_consistency_map(order, "v1") == [(0, 2, 5, 7), (5, 7, 0, 2)]


def test_skips_donor_entries():
    order = [["v2", [0, 4]]]
    assert build_consistency_map(order, "v1") == []


def test_accepts_tuple_entries():
    order = [("v1", (3, 6))]
    assert build_consistency_map(order, "v1") == [(0, 3, 3, 6)]

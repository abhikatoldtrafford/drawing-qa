from drawing_qa.geometry import GridMap, cluster, join_tokens, num


def test_cluster_groups_close_values():
    assert cluster([10, 1, 2, 11, 30], tol=2) == [[1, 2], [10, 11], [30]]


def test_num_parses_and_rejects():
    assert num("1,234.5") == 1234.5
    assert num("E350A") is None
    assert num(None) is None


def test_join_tokens_concatenates_touching_fragments_without_inventing_characters():
    words = [(20.5, 0, 50, 10, "508*6"), (0, 0, 20, 10, "PIPE"), (140, 0, 150, 10, "kg")]
    assert [t[4] for t in join_tokens(words)] == ["PIPE508*6", "kg"]


def test_join_tokens_drops_duplicate_overlapping_word():
    words = [(100, 0, 110, 10, "75"), (100.3, 0, 110.3, 10, "75"), (130, 0, 140, 10, "75")]
    assert [t[4] for t in join_tokens(words)] == ["75", "75"]


def _grid():
    cols = [(100 + 50 * i, i + 1) for i in range(10)]          # x=100..550 -> 1..10
    rows = [(100 + 40 * i, ch) for i, ch in enumerate("ABCDEFGHJK")]
    return GridMap(cols, rows)


def test_grid_cell_of_and_rect_roundtrip():
    g = _grid()
    assert g.cell_of(151, 141) == "B2"
    x0, y0, x1, y1 = g.cell_rect("B2")
    assert (x0, y0, x1, y1) == (125, 120, 175, 160)
    assert g.cell_of((x0 + x1) / 2, (y0 + y1) / 2) == "B2"


def test_grid_rejects_unknown_cell():
    import pytest
    with pytest.raises(ValueError, match="unknown grid cell 'Z99'"):
        _grid().cell_rect("Z99")

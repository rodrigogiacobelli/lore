"""``cli._origin_table`` — the one home for the conditional ORIGIN column.

Spec: ``nested-projects-spec`` — Part 4 "Unit", unit S4, and D-15.

The column is conditional so that a project in no tree prints exactly what it
printed before this feature existed (SC-7). One renderer owns that condition;
``standards-dry`` names seven copies of it as the failure mode.
"""

from __future__ import annotations

import pytest

from lore.cli import _format_table, _origin_table


HEADERS = ["ID", "GROUP", "TITLE"]
ROWS = [
    ["tech-db-schema", "technical", "DB Schema"],
    ["standards-naming", "standards", "Naming"],
]


def test_all_self_origins_render_exactly_like_format_table():
    # nested-projects-spec — D-15 / SC-7: no column, byte for byte
    assert _origin_table(HEADERS, ROWS, ["self", "self"]) == _format_table(HEADERS, ROWS)


def test_an_empty_result_renders_like_format_table():
    # nested-projects-spec — D-15: nothing to name an origin for
    assert _origin_table(HEADERS, [], []) == _format_table(HEADERS, [])


def test_one_foreign_row_adds_the_column_to_every_row():
    # nested-projects-spec — FR-16 / D-15: the column appears when the result
    # set holds at least one non-`self` row, and then as the FIRST column
    assert _origin_table(HEADERS, ROWS, ["self", "camelot"]) == _format_table(
        ["ORIGIN", *HEADERS],
        [
            ["self", "tech-db-schema", "technical", "DB Schema"],
            ["camelot", "standards-naming", "standards", "Naming"],
        ],
    )


def test_the_column_uses_format_tables_own_padding():
    # nested-projects-spec — D-29: `_origin_table` wraps `_format_table`, so
    # the 2-space indent, the 2-space gaps and the unpadded last column are
    # unchanged and there is one padding rule in the CLI, not two
    rendered = _origin_table(HEADERS, ROWS, ["camelot", "self"])

    assert rendered[0] == "  ORIGIN   ID                GROUP      TITLE"
    assert rendered[1] == "  camelot  tech-db-schema    technical  DB Schema"
    assert rendered[2] == "  self     standards-naming  standards  Naming"


@pytest.mark.parametrize("origins", [["self", "self"], ["self", "realm"]])
def test_the_row_count_never_changes(origins):
    # nested-projects-spec — FR-16: the column is presentation; it adds and
    # removes no row
    assert len(_origin_table(HEADERS, ROWS, origins)) == len(ROWS) + 1

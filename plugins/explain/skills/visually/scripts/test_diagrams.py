#!/usr/bin/env python3
"""Unit tests for diagrams.py. Run: python3 test_diagrams.py"""
import contextlib
import io
import unittest

from diagrams import (
    _pad,
    display_width,
    main,
    render_box,
    render_columns,
    render_diamond,
    validate,
    wrapped_cells,
)


def run_cli(*argv):
    """Invoke main() with a fake argv[0] and capture (exit_code, stdout)."""
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = main(["diagrams.py", *argv])
    return code, out.getvalue()


def run_cli_err(*argv):
    """Same, but also capture stderr — notes and error text go there."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(["diagrams.py", *argv])
    return code, out.getvalue(), err.getvalue()

MISALIGNED_NESTED_BOX = (
    "┌──────────────────────────────┐\n"
    "│        DiagramSample          │\n"
    "│    (generic user interface)   │\n"
    "│                                │\n"
    "│  ┌──────────────┐             │\n"
    "│  │ WorkerClient │             │\n"
    "│  └──────┬───────┘             │\n"
    "└─────────┼──────────────────────┘\n"
)


class TestValidateNestedBoxAlignment(unittest.TestCase):
    def test_flags_misaligned_nested_box_body_lines(self):
        issues = validate(MISALIGNED_NESTED_BOX)
        self.assertTrue(issues, "expected the known-bad diagram to be flagged")
        # every body line (2-7) of the outer box should be flagged, since all
        # of them are one column short of the widened bottom border
        flagged_lines = {ln for ln, _ in issues}
        self.assertTrue({2, 3, 4, 5, 6, 7}.issubset(flagged_lines))

    def test_clean_rect_has_no_issues(self):
        clean = (
            "┌──────┐\n"
            "│ text │\n"
            "└──────┘\n"
        )
        self.assertEqual(validate(clean), [])

    def test_missing_bottom_border_is_flagged(self):
        broken = (
            "┌──────┐\n"
            "│ text │\n"
        )
        issues = validate(broken)
        self.assertEqual(len(issues), 1)
        self.assertIn("no matching", issues[0][1])

    def test_unclosed_top_border_is_flagged(self):
        broken = "┌──────\n"
        issues = validate(broken)
        self.assertEqual(len(issues), 1)
        self.assertIn("no matching", issues[0][1])


class TestRenderBoxIsAlwaysValid(unittest.TestCase):
    def test_single_line_rect(self):
        rows = render_box("Ready", style="rect")
        self.assertEqual(validate("\n".join(rows)), [])
        widths = {display_width(r) for r in rows}
        self.assertEqual(len(widths), 1, "all rows of a box must share one width")

    def test_multiline_content_rect(self):
        rows = render_box(["DiagramSample", "(generic user interface)"], style="rect")
        self.assertEqual(validate("\n".join(rows)), [])

    def test_round_style(self):
        rows = render_box("Ready", style="round")
        self.assertEqual(validate("\n".join(rows)), [])
        self.assertTrue(rows[0].startswith("╭") and rows[0].endswith("╮"))
        self.assertTrue(rows[-1].startswith("╰") and rows[-1].endswith("╯"))

    def test_min_width_widens_short_content(self):
        rows = render_box("Hi", style="rect", min_width=20)
        self.assertEqual(validate("\n".join(rows)), [])
        self.assertEqual(display_width(rows[0]), display_width(rows[1]))
        self.assertGreater(display_width(rows[0]), len("Hi") + 4)

    def test_nested_box_is_valid(self):
        inner = render_box("WorkerClient", style="rect")
        outer_content = ["DiagramSample", "(generic user interface)", ""] + [
            "  " + line for line in inner
        ]
        outer = render_box(outer_content, style="rect", align="left")
        text = "\n".join(outer)
        self.assertEqual(validate(text), [], text)


class TestRenderDiamond(unittest.TestCase):
    def test_middle_row_is_widest(self):
        top, middle, bottom = render_diamond("Valid?")
        self.assertEqual(display_width(top), display_width(bottom))
        self.assertEqual(display_width(middle), display_width(top) + 1)
        self.assertTrue(middle.startswith("<") and middle.endswith(">"))
        self.assertTrue(top.strip().startswith(".") and top.strip().endswith("."))
        self.assertTrue(bottom.strip().startswith("'") and bottom.strip().endswith("'"))

    def test_short_text_does_not_crash(self):
        top, middle, bottom = render_diamond("OK")
        self.assertTrue(top and middle and bottom)


class TestRenderColumns(unittest.TestCase):
    WIDTH, GAP, INDENT = 20, 4, 2

    def _render(self, rows, headers=None):
        return render_columns(
            rows, headers=headers, width=self.WIDTH, gap=self.GAP, indent=self.INDENT
        )

    def test_right_column_never_drifts(self):
        start = self.INDENT + self.WIDTH + self.GAP
        out = self._render(
            [
                ("one", "alpha"),
                ("a considerably longer left cell that wraps over lines", "beta"),
                ("x", "a considerably longer right cell that wraps too"),
            ],
            headers=("Before", "After"),
        )
        checked = 0
        for line in out:
            if len(line) <= self.INDENT + self.WIDTH:
                continue  # left-only line; rstrip already removed the padding
            self.assertEqual(
                line[self.INDENT + self.WIDTH:start].strip(), "",
                f"gutter should be blank: {line!r}",
            )
            self.assertNotEqual(line[start], " ", f"right cell not flush: {line!r}")
            checked += 1
        self.assertGreater(checked, 4, "expected several two-column lines to check")

    def test_headers_get_a_rule_matching_their_width(self):
        out = self._render([("l", "r")], headers=("Before", "After"))
        self.assertTrue(out[1].strip().startswith("─"))
        self.assertEqual(out[1].count("─"), len("Before") + len("After"))

    def test_blank_side_does_not_crash_or_shift(self):
        out = self._render([("left only", ""), ("", "right only")])
        self.assertTrue(any(line.strip() == "left only" for line in out))
        right = next(line for line in out if "right only" in line)
        self.assertEqual(right.index("right only"), self.INDENT + self.WIDTH + self.GAP)

    def test_two_column_output_survived_the_n_column_generalisation(self):
        """Regression guard: the 2-column geometry is what Shape 2C ships, and
        it must be byte-identical to the pre-generalisation formula."""
        field = 12 + 3
        out = render_columns(
            [("alpha", "beta"), ("gamma", "delta")],
            headers=("Left", "Right"), width=12, gap=3, indent=1,
        )
        expected = [
            " " + _pad("Left", field, "left") + "Right",
            " " + _pad("────", field, "left") + "─────",
            "",
            " " + _pad("alpha", field, "left") + "beta",
            "",
            " " + _pad("gamma", field, "left") + "delta",
        ]
        self.assertEqual(out, [line.rstrip() for line in expected])


class TestRenderColumnsThreeColumn(unittest.TestCase):
    """Shape 1E is a row-label column plus one column per option, which two
    columns cannot express — the rule to generate it is only followable if
    three columns work."""

    ROWS = [("setup cost", "low", "high"), ("main unknown", "when it starts", "who runs it")]
    HEADERS = ("", "Keep the current DB", "Add a cache")
    WIDTHS = [14, 24, 12]
    GAP, INDENT = 2, 0

    def _render(self):
        return render_columns(self.ROWS, headers=self.HEADERS, width=self.WIDTHS,
                              gap=self.GAP, indent=self.INDENT)

    def test_every_column_starts_at_a_fixed_screen_column(self):
        out = self._render()
        c2 = self.INDENT + self.WIDTHS[0] + self.GAP
        c3 = c2 + self.WIDTHS[1] + self.GAP
        data = [line for line in out[2:] if line.strip()]
        self.assertEqual(len(data), len(self.ROWS))
        for line, (label, mid, right) in zip(data, self.ROWS):
            self.assertTrue(line.startswith(label), line)
            self.assertEqual(line[c2:c2 + len(mid)], mid, line)
            self.assertEqual(line[c3:c3 + len(right)], right, line)

    def test_unlabelled_first_column_gets_no_rule(self):
        out = self._render()
        header, rule = out[0], out[1]
        self.assertTrue(header.startswith(" "), "blank label header leaves the column empty")
        c2 = self.INDENT + self.WIDTHS[0] + self.GAP
        self.assertEqual(rule[:c2].strip(), "", "no rule under an empty header")
        self.assertEqual(rule.count("─"),
                         len("Keep the current DB") + len("Add a cache"))

    def test_tight_drops_the_blank_line_between_rows(self):
        loose = self._render()
        tight = render_columns(self.ROWS, headers=self.HEADERS, width=self.WIDTHS,
                               gap=self.GAP, indent=self.INDENT, blank_between=False)
        self.assertIn("", loose)
        self.assertNotIn("", tight)
        self.assertEqual([l for l in loose if l], tight,
                         "tight must drop only the blank lines, nothing else")

    def test_scalar_width_applies_to_all_three_columns(self):
        out = render_columns(self.ROWS, width=10, gap=2, indent=0)
        c3 = (10 + 2) * 2
        line = out[0]
        self.assertEqual(line[c3:c3 + 4], "high")


class TestRenderSubcommands(unittest.TestCase):
    """The CLI is what `allowed-tools` pre-approves, so every render path the
    skill instructs must be reachable from it and agree with the library."""

    def test_box_matches_library(self):
        code, out = run_cli("box", "--align", "left", "StockRegistry", "V3")
        self.assertEqual(code, 0)
        expected = render_box(["StockRegistry", "V3"], align="left")
        self.assertEqual(out.splitlines(), expected)

    def test_box_honours_style_and_min_width(self):
        code, out = run_cli("box", "--style", "round", "--min-width", "20", "Ready")
        self.assertEqual(code, 0)
        rows = out.splitlines()
        self.assertEqual(rows, render_box("Ready", style="round", min_width=20))
        self.assertTrue(rows[0].startswith("╭"))

    def test_diamond_matches_library(self):
        code, out = run_cli("diamond", "In stock?")
        self.assertEqual(code, 0)
        self.assertEqual(out.splitlines(), render_diamond("In stock?"))

    def test_columns_pairs_cells_in_order(self):
        code, out = run_cli(
            "columns", "--header-row",
            "Today", "If we automate it",
            "left one", "right one", "left two", "right two",
        )
        self.assertEqual(code, 0)
        expected = render_columns(
            [("left one", "right one"), ("left two", "right two")],
            headers=("Today", "If we automate it"),
        )
        self.assertEqual(out.splitlines(), expected)

    def test_columns_rejects_odd_cell_count(self):
        code, out = run_cli("columns", "left", "right", "orphan")
        self.assertEqual(code, 2)
        self.assertEqual(out, "", "error text belongs on stderr, not stdout")

    def test_columns_accepts_geometry_flags(self):
        code, out = run_cli("columns", "--width", "20", "--indent", "0", "l", "r")
        self.assertEqual(code, 0)
        self.assertEqual(
            out.splitlines(),
            render_columns([("l", "r")], width=20, indent=0),
        )

    def test_columns_builds_shape_1e_from_the_cli(self):
        """The command Shape 1E's Avoid line points at has to reproduce
        Shape 1E's own table, or the rule it states is unfollowable."""
        code, out = run_cli(
            "columns", "--cols", "3", "--header-row", "--width", "14,24,12",
            "--gap", "2", "--indent", "0",
            "", "Keep the current DB", "Add a cache",
            "setup cost", "low", "high",
        )
        self.assertEqual(code, 0)
        self.assertEqual(out.splitlines(), render_columns(
            [("setup cost", "low", "high")],
            headers=("", "Keep the current DB", "Add a cache"),
            width=[14, 24, 12], gap=2, indent=0,
        ))

    def test_columns_rejects_cells_not_a_multiple_of_cols(self):
        code, out = run_cli("columns", "--cols", "3", "a", "b", "c", "d")
        self.assertEqual(code, 2)
        self.assertEqual(out, "", "error text belongs on stderr, not stdout")

    def test_columns_rejects_a_malformed_width(self):
        code, out = run_cli("columns", "--width", "wide", "l", "r")
        self.assertEqual(code, 2)
        self.assertEqual(out, "")

    def test_tight_columns_report_a_label_that_had_to_wrap(self):
        """The failure this exists for: a row label split in half reads as two
        labels, and the rendered block gives no sign it happened."""
        code, out, err = run_cli_err(
            "columns", "--cols", "3", "--header-row", "--tight",
            "--width", "22,26,26", "--gap", "2", "--indent", "0",
            "", "io_uring", "epoll",
            "streaming, 1 conn, 16KB", "183K qps", "224K qps",
        )
        self.assertEqual(code, 0, "a wrapped cell is a note, not an error")
        self.assertIn("streaming, 1 conn, 16KB", err)
        self.assertIn("column 1", err)
        self.assertEqual(
            out.splitlines(),
            render_columns(
                [("streaming, 1 conn, 16KB", "183K qps", "224K qps")],
                headers=("", "io_uring", "epoll"),
                width=[22, 26, 26], gap=2, indent=0, blank_between=False,
            ),
            "the note must not change a single byte of the rendered block",
        )

    def test_tight_columns_stay_quiet_when_every_cell_fits(self):
        code, out, err = run_cli_err(
            "columns", "--cols", "3", "--header-row", "--tight",
            "--width", "14,24,12", "--gap", "2", "--indent", "0",
            "", "Keep the current DB", "Add a cache",
            "setup cost", "low", "high",
        )
        self.assertEqual(code, 0)
        self.assertEqual(err, "", "nothing wrapped, so there is nothing to say")

    def test_sentence_columns_never_report_their_expected_wrapping(self):
        """Shape 2C's cells are whole sentences and are meant to wrap. If this
        starts failing, someone made the note unconditional and every
        before/after block now warns about working correctly."""
        code, out, err = run_cli_err(
            "columns", "--header-row",
            "Today", "If we automate it",
            "Staff call each visitor the day before.",
            "The system sends a reminder the day before.",
        )
        self.assertEqual(code, 0)
        self.assertGreater(len(out.splitlines()), 4, "these cells did wrap")
        self.assertEqual(err, "")

    def test_wrapped_cells_locates_the_offender_including_in_headers(self):
        found = wrapped_cells(
            [("fits", "also fits"), ("a considerably longer cell", "fits")],
            headers=("a header far too wide for its column", "ok"),
            width=12,
        )
        self.assertEqual(
            [(label, col) for label, col, _cell, _w in found],
            [("header", 1), ("row 2", 1)],
        )
        self.assertEqual(found[1][2], "a considerably longer cell")
        self.assertEqual(found[1][3], 12, "reports the width it was measured against")

    def test_no_subcommand_prints_help_and_exits_2(self):
        code, out = run_cli()
        self.assertEqual(code, 2)
        self.assertIn("columns", out)

    def test_validate_still_works_via_cli(self):
        code, out = run_cli("validate", __file__)
        self.assertIn(code, (0, 1), "validate returns 0 for clean, 1 for issues")
        self.assertTrue(out)


if __name__ == "__main__":
    unittest.main()

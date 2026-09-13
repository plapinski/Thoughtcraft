#!/usr/bin/env python3
"""Render boxes, diamonds, and columns, and validate closed-box alignment.

Use a subcommand's --help for CLI options and demo for examples.
The validator does not check trees, diamonds, or column layouts.
"""
import argparse
import sys
import textwrap
import unicodedata

STYLES = {
    # style: (top-left, top-right, bottom-left, bottom-right, horizontal, vertical)
    "rect": ("┌", "┐", "└", "┘", "─", "│"),
    "round": ("╭", "╮", "╰", "╯", "─", "│"),
}

_OPEN_TO_STYLE = {"┌": "rect", "╭": "round"}
_BOTTOM_OPEN = {"┌": "└", "╭": "╰"}
_BOTTOM_CLOSE = {"┌": "┘", "╭": "╯"}


def _char_width(ch):
    return 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1


def display_width(s):
    return sum(_char_width(c) for c in s)


def _pad(text, width, align="center"):
    gap = width - display_width(text)
    if gap <= 0:
        return text
    if align == "left":
        return text + " " * gap
    if align == "right":
        return " " * gap + text
    left = gap // 2
    return " " * left + text + " " * (gap - left)


def render_box(lines, style="rect", min_width=0, align="center", pad_x=1):
    """Render `lines` (a string, or list of strings for multi-line content)
    inside a box. Returns a list of strings, one per row, all the same
    display width — safe to print directly or to nest inside another box."""
    if isinstance(lines, str):
        lines = [lines]
    tl, tr, bl, br, h, v = STYLES[style]
    inner_width = max([display_width(l) for l in lines] + [min_width])
    top = tl + h * (inner_width + pad_x * 2) + tr
    bottom = bl + h * (inner_width + pad_x * 2) + br
    pad = " " * pad_x
    body = [v + pad + _pad(l, inner_width, align) + pad + v for l in lines]
    return [top] + body + [bottom]


def render_diamond(text, pad_x=1):
    """Render a decision diamond around a single line of text. Tapered:
    the <text> row is the widest point, the '.'/''' rows are inset by one
    column on each side, matching how a real decision diamond narrows."""
    inner = display_width(text) + pad_x * 2
    dash_count = max(inner - 2, 0)
    top = " " + "." + "-" * dash_count + "."
    middle = "<" + " " * pad_x + text + " " * pad_x + ">"
    bottom = " " + "'" + "-" * dash_count + "'"
    return [top, middle, bottom]


def _parse_widths(spec):
    """Parse the CLI --width value: one number for every column, or one per
    column separated by commas. The comma form exists because a multi-value
    flag would be ambiguous against the positional cells that follow it."""
    vals = [int(p.strip()) for p in str(spec).split(",") if p.strip()]
    if not vals:
        raise ValueError(spec)
    return vals[0] if len(vals) == 1 else vals


def _column_widths(rows, headers, width):
    """Normalise the width spec to one number per column.

    Shared with wrapped_cells so the warning cannot disagree with the renderer
    about how wide a column actually is."""
    ncols = max([len(r) for r in rows] + [len(headers) if headers else 0])
    widths = list(width) if isinstance(width, (list, tuple)) else [width] * ncols
    while len(widths) < ncols:
        widths.append(widths[-1])
    return widths


def wrapped_cells(rows, headers=None, width=34):
    """Report cells that will be split across lines, as (label, col, cell, width).

    Sentence-length cells are *supposed* to wrap — that is what a before/after
    block is — so this is only worth asking about for a dense fragment table,
    where a label broken in half reads as two labels and nothing in the output
    says it happened. main() therefore only calls this under --tight.

    Same convention as validate(): return findings, let the caller print them."""
    widths = _column_widths(rows, headers, width)
    found = []
    all_rows = ([(("header"), headers)] if headers else []) + [
        (f"row {i + 1}", row) for i, row in enumerate(rows)
    ]
    for label, row in all_rows:
        for j, cell in enumerate(row):
            if len(textwrap.wrap(cell, widths[j])) > 1:
                found.append((label, j + 1, cell, widths[j]))
    return found


def render_columns(rows, headers=None, width=34, gap=4, indent=2, blank_between=True):
    """Render rows as aligned columns — the shape used for before/after
    explanations and for side-by-side comparisons. `rows` is a list of text
    sequences, two cells for a before/after block or three when the first
    column holds row labels. Every cell is wrapped to its column's width and
    each column starts at the same screen column on every line, computed from
    actual text width, so it cannot drift the way a hand-typed block does.

    `width` is one number for every column, or a list of numbers per column
    (a label column usually wants to be narrower than the ones it labels).
    `headers` is an optional sequence matching the row length, underlined with
    a ─ rule; pass "" for a column that has no header, such as row labels.
    Pass "" for any cell to leave it blank.

    `blank_between` puts an empty line between rows, which sentence-length
    cells need to stay readable. Set it False for a dense table of fragments,
    where a gap after every row buries the pattern you are comparing.
    """
    widths = _column_widths(rows, headers, width)
    ncols = len(widths)
    pre = " " * indent

    def row_line(cells):
        # every column but the last is padded to its own width plus the gutter;
        # the last needs no padding, and trailing space is stripped
        out = pre
        for i, cell in enumerate(cells):
            out += cell if i == ncols - 1 else _pad(cell, widths[i] + gap, "left")
        return out.rstrip()

    lines = []
    if headers:
        hs = list(headers) + [""] * (ncols - len(headers))
        lines.append(row_line(hs))
        lines.append(row_line(["─" * display_width(h) for h in hs]))
    for i, row in enumerate(rows):
        cells = list(row) + [""] * (ncols - len(row))
        if blank_between and (i or headers):
            lines.append("")
        wrapped = [textwrap.wrap(c, widths[j]) or [""] for j, c in enumerate(cells)]
        for n in range(max(len(w) for w in wrapped)):
            lines.append(row_line([w[n] if n < len(w) else "" for w in wrapped]))
    return lines


def validate(text):
    """Return a list of (line_number, message) for every box whose top
    border, bottom border, or body lines don't agree on width. Detects
    nesting by scanning column-by-column rather than only at line start,
    so a box embedded mid-line (inside another box's body) is checked too.
    """
    lines = text.splitlines()
    issues = []
    n = len(lines)
    for i, line in enumerate(lines):
        for c, ch in enumerate(line):
            if ch not in _OPEN_TO_STYLE:
                continue
            style = _OPEN_TO_STYLE[ch]
            _, close, _, _, _, _ = STYLES[style]
            close_col = line.find(close, c + 1)
            if close_col == -1:
                issues.append((i + 1, f"'{ch}' at column {c} has no matching '{close}' on the same line"))
                continue
            width = close_col - c + 1
            bottom_open = _BOTTOM_OPEN[ch]
            bottom_close = _BOTTOM_CLOSE[ch]
            bottom_row = None
            for j in range(i + 1, n):
                cand = lines[j]
                if len(cand) > c and cand[c] == bottom_open:
                    bottom_row = j
                    break
            if bottom_row is None:
                issues.append((i + 1, f"'{ch}' at column {c} has no matching '{bottom_open}' below in column {c}"))
                continue
            expected_close_col = c + width - 1
            bottom_line = lines[bottom_row]
            if len(bottom_line) <= expected_close_col or bottom_line[expected_close_col] != bottom_close:
                found = bottom_line[expected_close_col] if expected_close_col < len(bottom_line) else "<end of line>"
                issues.append((
                    bottom_row + 1,
                    f"bottom border for box opened at line {i + 1} col {c} (width {width}) "
                    f"should have '{bottom_close}' at column {expected_close_col}, found '{found}'",
                ))
            for k in range(i + 1, bottom_row):
                body = lines[k]
                if len(body) <= c or body[c] != "│":
                    continue  # not a body line of this box (blank/connector line) — skip
                if len(body) <= expected_close_col or body[expected_close_col] != "│":
                    found = body[expected_close_col] if expected_close_col < len(body) else "<end of line>"
                    issues.append((
                        k + 1,
                        f"box body line (opened line {i + 1} col {c}, width {width}) "
                        f"should have '│' at column {expected_close_col}, found '{found}'",
                    ))
    return issues


def _demo():
    for row in render_box(["DiagramSample", "(generic user interface)"], style="rect", align="center"):
        print(row)
    print()
    for row in render_box("Ready", style="round"):
        print(row)
    print()
    for row in render_diamond("Valid?"):
        print(row)
    print()
    for row in render_columns(
        [("Staff call each visitor the day before.",
          "The system sends a reminder the day before.")],
        headers=("Today", "If we send reminders"),
    ):
        print(row)
    print()
    for row in render_columns(
        [("When", "On request", "Every night"),
         ("Main unknown", "Time per check", "Missed changes")],
        headers=("", "Manual checks", "Scheduled checks"),
        width=[14, 24, 18], gap=2, indent=0,
    ):
        print(row)


def _build_parser():
    parser = argparse.ArgumentParser(
        prog="diagrams.py",
        description="Render and validate box-drawing ASCII diagrams with "
                    "computed padding and alignment.",
    )
    sub = parser.add_subparsers(dest="cmd")

    p_box = sub.add_parser("box", help="render a box around one or more lines of text")
    p_box.add_argument("lines", nargs="+", metavar="LINE")
    p_box.add_argument("--style", choices=sorted(STYLES), default="rect")
    p_box.add_argument("--align", choices=("left", "center", "right"), default="center")
    p_box.add_argument("--min-width", dest="min_width", type=int, default=0)

    p_diamond = sub.add_parser("diamond", help="render a decision diamond around one line")
    p_diamond.add_argument("text", metavar="TEXT")

    p_columns = sub.add_parser(
        "columns", help="render rows as aligned columns (before/after, comparison)"
    )
    p_columns.add_argument(
        "cells", nargs="+", metavar="CELL",
        help="cells in reading order, grouped into rows of --cols. Pass '' for a blank cell.",
    )
    p_columns.add_argument("--cols", type=int, default=2,
                           help="cells per row (default 2; use 3 when the first column holds row labels)")
    p_columns.add_argument("--header-row", dest="header_row", action="store_true",
                           help="treat the first row of cells as column headers")
    p_columns.add_argument("--width", default="34",
                           help="column width, or one per column: 14,24,12")
    p_columns.add_argument("--gap", type=int, default=4)
    p_columns.add_argument("--indent", type=int, default=2)
    p_columns.add_argument("--tight", action="store_true",
                           help="no blank line between rows — for a dense table of fragments")

    p_validate = sub.add_parser(
        "validate", help="report boxes whose borders don't line up (closed boxes only)"
    )
    p_validate.add_argument("path", metavar="file|-", help="'-' reads from stdin")

    sub.add_parser("demo", help="print example shapes")
    return parser


def main(argv):
    parser = _build_parser()
    args = parser.parse_args(argv[1:])

    if args.cmd is None:
        parser.print_help()
        return 2
    if args.cmd == "demo":
        _demo()
        return 0
    if args.cmd == "box":
        for row in render_box(args.lines, style=args.style,
                              min_width=args.min_width, align=args.align):
            print(row)
        return 0
    if args.cmd == "diamond":
        for row in render_diamond(args.text):
            print(row)
        return 0
    if args.cmd == "columns":
        n = args.cols
        if n < 1:
            print("columns needs --cols of at least 1", file=sys.stderr)
            return 2
        if len(args.cells) % n:
            print(f"columns needs a multiple of {n} cells (--cols {n}), "
                  f"got {len(args.cells)}", file=sys.stderr)
            return 2
        rows = [tuple(args.cells[i:i + n]) for i in range(0, len(args.cells), n)]
        headers = None
        if args.header_row:
            headers, rows = rows[0], rows[1:]
        try:
            width = _parse_widths(args.width)
        except ValueError:
            print("columns --width takes a number, or one per column "
                  "separated by commas", file=sys.stderr)
            return 2
        for row in render_columns(rows, headers=headers, width=width,
                                  gap=args.gap, indent=args.indent,
                                  blank_between=not args.tight):
            print(row)
        # A fragment table is the one place a wrapped cell is almost certainly a
        # mistake. Notes, not errors: the output is correct, just probably not
        # what was wanted, so exit stays 0.
        if args.tight:
            for label, col, cell, w in wrapped_cells(rows, headers, width):
                print(f"note: {label} column {col} wrapped at {w} chars: {cell!r} "
                      f"— shorten it or widen the column", file=sys.stderr)
        return 0
    if args.cmd == "validate":
        if args.path == "-":
            text = sys.stdin.read()
        else:
            with open(args.path, encoding="utf-8") as fh:
                text = fh.read()
        issues = validate(text)
        for line_no, msg in issues:
            print(f"line {line_no}: {msg}")
        if issues:
            print(f"\n{len(issues)} issue(s) found", file=sys.stderr)
            return 1
        print("no issues found")
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))

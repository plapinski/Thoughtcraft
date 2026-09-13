# Diagram tooling

Use [diagrams.py](../scripts/diagrams.py) for diagrams with two or more boxes,
nesting, or columns. It computes padding and alignment. Simple arrows and trees
can be written directly. These commands complement the
[shared content rules](../SKILL.md#shared-rules).

## Paths

Replace `<skill-dir>` with the absolute directory containing the loaded
`SKILL.md`, including when installed in a cache. Keep the resulting helper path
quoted. Resolve reference links from the file containing the link; never infer
resource paths from the user's working directory. Use the host's execution and
approval mechanism.

## Boxes

```sh
python3 "<skill-dir>/scripts/diagrams.py" box --align left "Stock records" "Locations"
python3 "<skill-dir>/scripts/diagrams.py" box --style round "Ready"
python3 "<skill-dir>/scripts/diagrams.py" diamond "In stock?"
```

`diamond` takes one line. Render it before arranging a flowchart's surrounding
boxes. Compose generated shapes with connectors without changing their borders.

## Nesting

Render the inner box first:

```sh
python3 "<skill-dir>/scripts/diagrams.py" box --align left --min-width 17 \
    "Stock records" "Locations"
```

Pass the generated rows as separately quoted arguments to the outer box:

```sh
python3 "<skill-dir>/scripts/diagrams.py" box --align left "Inventory service" "" \
    '  ┌───────────────────┐' \
    '  │ Stock records     │' \
    '  │ Locations         │' \
    '  └───────────────────┘'
```

Use matching `--min-width` values for sibling boxes. This is the content width:
the default padding and borders add four columns. An empty argument adds a blank
row. See the [complete hierarchy](../../../EXAMPLES.md#1d-nested-hierarchy).

## Columns

Cells are passed in row order. `--header-row` uses the first row as headers.
Two columns suit full sentences:

```sh
python3 "<skill-dir>/scripts/diagrams.py" columns --header-row \
    "Today" "If we send reminders" \
    "Staff call each visitor." "The system sends a reminder."
```

For a compact comparison, use three columns, an empty row-label header, and
`--tight` to omit blank lines between rows:

```sh
python3 "<skill-dir>/scripts/diagrams.py" columns --cols 3 --header-row --tight \
    --width 14,19,19 --gap 3 --indent 0 \
    "" "Manual checks" "Scheduled checks" \
    "When" "On request" "Every night" \
    "Main unknown" "Time per check" "Missed changes"
```

Read stderr: with `--tight`, wrapping produces a note while the exit code stays
zero. Shorten the cell or widen its column. Sentence wrapping is expected without
`--tight`. Stack a long before-and-after under two headings if columns would be
hard to read.

## Validation and fallback

Validate a closed-box diagram by sending its text through stdin:

```sh
python3 "<skill-dir>/scripts/diagrams.py" validate -
```

A file path also works for an existing diagram. Exit 1 means alignment issues
were found. The validator checks closed boxes, not columns, diamonds, or
connectors. Do not pass branching trees to it: their `┌─` connectors look like
unclosed boxes. Inspect those shapes directly.

If Python is unavailable, draw manually, count columns, and check alignment
before sending. Font rendering can affect appearance, so avoid relying on
emoji or combining characters for alignment.

Use `demo` for sample renderer output and each subcommand's `--help` for flags.

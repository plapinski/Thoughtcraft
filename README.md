# Thoughtcraft

Explain is a plugin for Claude Code and Codex that turns explanations into
plain language and diagrams. Use it to follow a process, compare options, or
understand how the pieces fit together.

## Install

You need Python 3 for the bundled diagram renderer.

**Claude Code** — run these commands inside Claude:

```text
/plugin marketplace add plapinski/Thoughtcraft
/plugin install explain@thoughtcraft
```

**Codex** — run these commands in your terminal:

```sh
codex plugin marketplace add plapinski/Thoughtcraft
codex plugin add explain@thoughtcraft
```

Start a new session or task after installation.

## Use

In Claude Code:

```text
/explain:visually Explain how an article goes from draft to publication.
```

In Codex, select the installed skill with `$` or the app's composer:

```text
$explain:visually Explain how an article goes from draft to publication.
```

Leave off the request to redraw the previous answer. Explain can also activate
when an explanation would benefit from a diagram. Ask for technical detail,
plain language, or both.

See [worked examples](plugins/explain/EXAMPLES.md) for every mode and shape.
For updates, development, and compatibility notes, see [Contributing](CONTRIBUTING.md).

[MIT license](LICENSE).

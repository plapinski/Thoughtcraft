# Contributing

Use any editor or agent; no personal skills, plugins, or MCP configuration are
required. See [AGENTS.md](AGENTS.md) for packaging and coding conventions.
Discuss substantial proposals in an issue, work in your fork, and submit a
pull request to `main`.

## Local development

Claude Code can load your working plugin directly:

```sh
claude --plugin-dir plugins/explain
```

To test a native installation, use a disposable checkout and an isolated
profile. Register the checkout's absolute path as a marketplace, then install
`explain@thoughtcraft` using the [installation commands](README.md#install).
This keeps experiments separate from your usual installed plugins.

Installed plugins are cached copies. Start a new session after reinstalling.
For a local Codex marketplace, reinstall with `codex plugin add explain@thoughtcraft`;
marketplace upgrade only refreshes Git sources. If same-version edits stay
cached, use a fresh profile or bump both manifests in a disposable copy.
Keep the working plugin's version unchanged until release.

## Updates

For an installation from GitHub, refresh the marketplace and reinstall or update:

**Claude Code**, inside a session:

```text
/plugin marketplace update thoughtcraft
/plugin update explain@thoughtcraft
```

**Codex**, in a terminal:

```sh
codex plugin marketplace upgrade thoughtcraft
codex plugin add explain@thoughtcraft
```

Start a new session or task afterward.

## Checks

Run from the repository root; Python checks need no third-party packages:

```sh
python3 scripts/validate_marketplace.py
python3 scripts/test_validate_marketplace.py
python3 plugins/explain/skills/visually/scripts/test_diagrams.py
```

For packaging changes, also run:

```sh
claude plugin validate . --strict
claude plugin validate plugins/explain --strict
```

The shared validator checks catalogs, paired manifests, skill metadata,
invocation policies, and bundled resource paths. It accepts an optional
repository path and exits with 0 for success, 1 for validation failures, or 2
when it cannot run. CI runs these checks in `.github/workflows/validate.yml`.

For installation changes, verify native discovery and bundled files in isolated
profiles. Run helpers from an installed path containing spaces and an unrelated
working directory. Record versions, commands, results, and any unavailable
checks. Installation checks do not establish model behavior.

## Pull requests

Describe what changes for users and how you checked it. Include rendered output
for presentation changes. Use Conventional Commits, such as `docs(explain): ...`
or `fix(explain): ...`, and `!` for breaking changes. Maintainers squash completed
contributions into one commit after review and passing CI.

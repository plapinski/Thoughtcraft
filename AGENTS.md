# Contributor guidance

Thoughtcraft ships the same skills for Claude Code and Codex. Read
[CONTRIBUTING.md](CONTRIBUTING.md) for development and submission instructions.
Keep `CLAUDE.md` exactly `@AGENTS.md` followed by a newline.

## Packaging

Each `plugins/<name>/` is a complete plugin with two manifests:

- Claude Code: `.claude-plugin/plugin.json`, listed in the root
  `.claude-plugin/marketplace.json`. Skills are discovered under `skills/`;
  do not add a `skills` field to the Claude manifest.
- Codex: `.codex-plugin/plugin.json`, listed in the root
  `.agents/plugins/marketplace.json`. Set `"skills": "./skills/"`; catalog sources
  use `{"source": "local", "path": "./plugins/<name>"}` relative to the repo root.

Edit manifests directly; there is no build step. Keep catalog membership and
paired manifest names, versions, descriptions, authors, URLs, licenses, and
keywords synchronized. Claude's `displayName` maps to Codex's
`interface.displayName`.

Keep skill-specific references and helpers beside `SKILL.md` in `references/`
and `scripts/`. Shared plugin code belongs in `plugins/<name>/shared/`.
Ship every resource a skill uses inside its plugin.

## Skill conventions

Use kebab-case names: plugins name a topic, skills name an action
(`explain` / `visually`). Frontmatter `name` matches the skill directory and is
at most 64 characters. `description` is a nonempty string of at most 1,024
characters. Put extra routing guidance in the body, not `when_to_use`.

The validator supports scalar YAML frontmatter, including block strings,
lowercase booleans, and the two-level Codex `policy.allow_implicit_invocation`
mapping. Extend validation and tests before introducing other YAML forms.

Resolve helper paths from the loaded skill's location, including installed
caches, and quote absolute paths when executing them. Resolve Markdown links
relative to their containing file. `<skill-dir>` and `<plugin-root>` are
placeholders for absolute paths, not environment variables.

Keep Claude invocation metadata and Codex `agents/openai.yaml` policies
consistent. Claude's `allowed-tools` does not grant permissions in other hosts.
Write shared instructions independently of host syntax, and allow required
host progress messages before the final explanation.

Explain uses DOT graphs to route modes and shapes. Keep shared rules in the
meta-skill, shape rules in the mode references, and commands in the tooling
reference. Link to worked examples instead of repeating them. Preserve the
skill's documented behavior when simplifying instructions.

## Code and checks

Python tooling uses only the standard library. Use four-space indentation,
descriptive snake_case names, and explicit validation errors. Document public
functions and non-obvious behavior. Colocate `unittest` renderer tests with
their code; repository validation and its tests belong in `scripts/`.

Run the [checks](CONTRIBUTING.md#checks) for affected code and packaging. Test
boundaries and malformed inputs when changing renderers or validators; add a
CI step for new executable components. Include sample output for changes to
diagram presentation.

Keep plugin versions unchanged during implementation. At release, bump each
changed plugin's version in both manifests together.

## Contributor tools

Use any editor or agent. Keep personal tool installations, credentials, MCP
configuration, and machine settings out of commits. Marketplace catalogs,
plugin manifests, and skill sidecars are product files and remain tracked.

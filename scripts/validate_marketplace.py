#!/usr/bin/env python3
"""Validate shared skills/resources and native Claude Code and Codex packaging.

This is the repository's contract, not a general vendor-schema or YAML parser.
Claude's schema check remains separate: claude plugin validate . --strict.
Uses only the standard library.

Run: python3 scripts/validate_marketplace.py [marketplace-root]
Exit: 0 clean, 1 problems found, 2 could not run (no catalogs or bad arguments).
"""
import json
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

FRONTMATTER_BUDGET = 1024
KEBAB = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
SEMVER = re.compile(
    r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*))*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
)
CATALOGS = {
    "claude": ".claude-plugin/marketplace.json",
    "codex": ".agents/plugins/marketplace.json",
}
COMMON_FIELDS = {
    "name", "version", "description", "author", "homepage", "repository",
    "license", "keywords",
}
SKILL_FIELDS = {
    "name", "description", "argument-hint", "user-invocable",
    "disable-model-invocation", "allowed-tools",
}
LINK = re.compile(r"\[[^\]\n]*\]\(([^)\n]+)\)")
RESOURCE = re.compile(
    r"(?P<base><skill-dir>|<plugin-root>|\$\{CLAUDE_SKILL_DIR\}|"
    r"\$\{CLAUDE_PLUGIN_ROOT\})/(?P<path>[^\s\"'`<>),]+)"
)


class Report:
    """Collect all actionable failures in one run."""

    def __init__(self):
        self.errors = []

    def error(self, where, message):
        self.errors.append((str(where), message))

    def check(self, condition, where, message):
        if not condition:
            self.error(where, message)
        return bool(condition)


def read_text(path, report):
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        report.error(path, f"cannot read file: {exc}")
        return None


def load_json(path, report):
    text = read_text(path, report)
    if text is None:
        return None
    try:
        value = json.loads(text)
    except ValueError as exc:
        report.error(path, f"invalid JSON: {exc}")
        return None
    if report.check(isinstance(value, dict), path, "must be a JSON object"):
        return value
    return None


def scalar(value):
    """Parse only the scalar YAML forms deliberately used in this repository."""
    if value.startswith('"'):
        result = json.loads(value)  # JSON-compatible double-quoted YAML strings.
        if not isinstance(result, str):
            raise ValueError("expected a quoted string")
        return result
    if value.startswith("'"):
        if not re.fullmatch(r"'(?:[^']|'')*'", value):
            raise ValueError("invalid single-quoted string")
        return value[1:-1].replace("''", "'")
    if value in ("true", "false"):
        return value == "true"
    if (not value or value[0] in "[{&*!>|%@`" or ": " in value
            or " #" in value or value.startswith("#")):
        raise ValueError("unsupported YAML scalar; quote strings or use a block")
    if value.lower() in ("null", "~", "yes", "no", "on", "off", "true", "false"):
        raise ValueError("ambiguous YAML scalar; quote strings, use true/false for booleans")
    if re.fullmatch(r"[-+]?\d+(?:\.\d+)?", value):
        raise ValueError("numeric YAML scalar; quote strings")
    return value


def parse_frontmatter(text):
    """Parse a flat scalar mapping; reject unsupported forms rather than guess.

    Block scalars use two-space indentation, with no blank or more-indented
    content lines. This subset is sufficient for our descriptions. The YAML
    clip/strip ending is retained so the description budget is accurate.
    """
    lines = text.splitlines()
    if not lines or lines[0] != "---" or "---" not in lines[1:]:
        raise ValueError("missing YAML frontmatter fences (---)")
    lines = lines[1:lines.index("---", 1)]
    fields = {}
    i = 0
    while i < len(lines):
        line = lines[i]
        i += 1
        if not line or line.startswith("#"):
            continue
        match = re.fullmatch(r"([a-z][a-z0-9-]*):\s*(.*)", line)
        if not match:
            raise ValueError(f"unsupported YAML at frontmatter line {i}: {line!r}")
        key, value = match.groups()
        if key in fields:
            raise ValueError(f"duplicate frontmatter field `{key}`")
        if value in (">", ">-", "|", "|-"):
            chunks = []
            while i < len(lines) and lines[i].startswith(" "):
                content = lines[i]
                if not content.startswith("  ") or not content[2:] or content[2].isspace():
                    raise ValueError(f"`{key}` block needs two-space indentation and text")
                chunks.append(content[2:])
                i += 1
            if not chunks:
                raise ValueError(f"`{key}` block is empty")
            if i < len(lines) and not lines[i]:
                raise ValueError("blank block lines are unsupported; use contiguous text")
            value = (" " if value.startswith(">") else "\n").join(chunks)
            if not match.group(2).endswith("-"):
                value += "\n"
            fields[key] = value
        else:
            fields[key] = scalar(value)
    return fields


def string(value, where, label, report):
    return report.check(isinstance(value, str) and bool(value.strip()), where,
                        f"`{label}` must be a non-empty string")


def string_list(value, where, label, report):
    return report.check(isinstance(value, list) and bool(value)
                        and all(isinstance(item, str) and item.strip() for item in value),
                        where, f"`{label}` must be a non-empty array of strings")


def fields_only(value, allowed, where, report):
    for field in sorted(set(value) - allowed):
        report.error(where, f"unsupported field `{field}` for this repository's format")


def bundled_path(base, relative, boundary, where, report, directory=False):
    """Resolve a resource inside its package, including symlink containment."""
    path = (base / relative).resolve()
    if not report.check(path.is_relative_to(boundary.resolve()), where,
                        f"path escapes bundled root: {relative!r}"):
        return None
    exists = path.is_dir() if directory else path.is_file()
    kind = "directory" if directory else "file"
    if not report.check(exists, where, f"unresolved bundled {kind}: {relative!r}"):
        return None
    return path


def check_resources(plugin_dir, report):
    """Check local Markdown links and all documented helper-path placeholders."""
    for path in sorted(plugin_dir.rglob("*.md")):
        if not path.resolve().is_relative_to(plugin_dir.resolve()):
            report.error(path, "Markdown file escapes bundled plugin root")
            continue
        text = read_text(path, report)
        if text is None:
            continue
        for target in LINK.findall(text):
            target = target.removeprefix("<").removesuffix(">")
            url = urlsplit(target)
            if url.scheme or target.startswith("#"):
                continue
            bundled_path(path.parent, unquote(url.path), plugin_dir, path, report)
        for match in RESOURCE.finditer(text):
            base = plugin_dir
            if match["base"] in ("<skill-dir>", "${CLAUDE_SKILL_DIR}"):
                base = next((parent for parent in (path.parent, *path.parents)
                             if (parent / "SKILL.md").is_file()
                             and parent.is_relative_to(plugin_dir)), None)
                if base is None:
                    report.error(path, "skill-relative resource has no containing SKILL.md")
                    continue
            bundled_path(base, match["path"], plugin_dir, path, report)


def check_skill(skill_dir, report):
    """Check common scalar metadata and the two native invocation policies."""
    where = skill_dir / "SKILL.md"
    text = read_text(where, report)
    if text is None:
        return
    try:
        fields = parse_frontmatter(text)
    except ValueError as exc:
        report.error(where, str(exc))
        return
    fields_only(fields, SKILL_FIELDS, where, report)
    name = fields.get("name")
    if string(name, where, "name", report):
        report.check(name == skill_dir.name, where, "frontmatter name must match skill directory")
        report.check(len(name) <= 64 and KEBAB.fullmatch(name), where,
                     "skill name must be kebab-case, at most 64 characters")
    description = fields.get("description")
    if string(description, where, "description", report):
        report.check(len(description) <= FRONTMATTER_BUDGET, where,
                     f"description is {len(description)} characters; limit is {FRONTMATTER_BUDGET}")
    for flag in ("user-invocable", "disable-model-invocation"):
        report.check(type(fields.get(flag)) is bool, where, f"`{flag}` must be a YAML boolean")
    for field in ("argument-hint", "allowed-tools"):
        if field in fields:
            string(fields[field], where, field, report)
    if "allowed-tools" in fields and isinstance(fields["allowed-tools"], str):
        report.check(bool(re.fullmatch(
            r'Bash\(python3 "(?P<helper>\$\{CLAUDE_(?:SKILL_DIR|PLUGIN_ROOT)\}'
            r'/[a-zA-Z0-9_./-]+\.py)" \*\)'
            r'(?:, Bash\(python3 (?P=helper) \*\))?',
            fields["allowed-tools"])), where,
            "allowed-tools must be scoped to one bundled Python helper; "
            "an equivalent unquoted Claude matching rule is optional")
    policy_path = skill_dir / "agents/openai.yaml"
    policy = read_text(policy_path, report)
    if policy is not None:
        match = re.fullmatch(r"policy:\n  allow_implicit_invocation: (true|false)\n?", policy)
        if report.check(match is not None, policy_path,
                        "expected policy.allow_implicit_invocation as a YAML boolean (true/false)"):
            report.check((match[1] == "true") == (fields.get("disable-model-invocation") is False),
                         policy_path, "invocation policy disagrees with Claude disable-model-invocation")


def check_manifest(plugin_dir, harness, report):
    """Validate the fields used by one native manifest format."""
    where = plugin_dir / f".{harness}-plugin/plugin.json"
    manifest = load_json(where, report)
    if manifest is None:
        return None
    extra = {"displayName"} if harness == "claude" else {"skills", "interface"}
    fields_only(manifest, COMMON_FIELDS | extra, where, report)
    for field in sorted(COMMON_FIELDS - {"author", "keywords"}):
        string(manifest.get(field), where, field, report)
    report.check(manifest.get("name") == plugin_dir.name, where,
                 "plugin name must match directory and marketplace entry")
    version = manifest.get("version")
    if isinstance(version, str):
        report.check(SEMVER.fullmatch(version), where, f"version {version!r} must be strict semver")
    author = manifest.get("author")
    if report.check(isinstance(author, dict), where, "`author` must be an object"):
        fields_only(author, {"name", "email", "url"}, where, report)
        for field in ("name", "email", "url"):
            string(author.get(field), where, f"author.{field}", report)
    string_list(manifest.get("keywords"), where, "keywords", report)
    if harness == "claude":
        string(manifest.get("displayName"), where, "displayName", report)
        if "skills" in manifest:
            report.error(where, "remove Claude `skills`; Claude auto-discovers skills/")
    else:
        report.check(manifest.get("skills") == "./skills/", where,
                     "Codex `skills` must be './skills/'")
        interface = manifest.get("interface")
        if report.check(isinstance(interface, dict), where, "`interface` must be an object"):
            required = {"displayName", "shortDescription", "longDescription", "developerName",
                        "category", "websiteURL"}
            fields_only(interface, required | {"capabilities", "defaultPrompt"}, where, report)
            for field in sorted(required):
                string(interface.get(field), where, f"interface.{field}", report)
            for field in ("capabilities", "defaultPrompt"):
                string_list(interface.get(field), where, f"interface.{field}", report)
            prompts = interface.get("defaultPrompt")
            if isinstance(prompts, list):
                report.check(len(prompts) <= 3 and all(isinstance(p, str) and len(p) <= 128 for p in prompts),
                             where, "interface.defaultPrompt allows at most 3 strings, 128 characters each")
            report.check(interface.get("category") == "Productivity", where,
                         "interface.category must be 'Productivity'")
            for field, expected in (
                    ("longDescription", manifest.get("description")),
                    ("developerName", author.get("name") if isinstance(author, dict) else None),
                    ("websiteURL", manifest.get("homepage"))):
                report.check(interface.get(field) == expected, where,
                             f"interface.{field} must match shared metadata")
    return manifest


def check_catalog(root, harness, plugin_names, report):
    """Require a native catalog entry for every shared plugin directory."""
    where = root / CATALOGS[harness]
    catalog = load_json(where, report)
    if catalog is None:
        return
    extra = {"$schema", "owner", "description"} if harness == "claude" else {"interface"}
    fields_only(catalog, {"name", "plugins"} | extra, where, report)
    report.check(catalog.get("name") == "thoughtcraft", where, "marketplace name must be 'thoughtcraft'")
    if harness == "claude":
        owner = catalog.get("owner")
        if report.check(isinstance(owner, dict), where, "`owner` must be an object"):
            fields_only(owner, {"name", "email", "url"}, where, report)
            for field in ("name", "email", "url"):
                string(owner.get(field), where, f"owner.{field}", report)
        for field in ("description", "$schema"):
            if field in catalog:
                string(catalog[field], where, field, report)
    else:
        interface = catalog.get("interface")
        if report.check(isinstance(interface, dict), where, "`interface` must be an object"):
            fields_only(interface, {"displayName"}, where, report)
            string(interface.get("displayName"), where, "interface.displayName", report)
    entries = catalog.get("plugins")
    if not report.check(isinstance(entries, list) and entries, where, "`plugins` must be a non-empty array"):
        return
    seen = set()
    for i, entry in enumerate(entries):
        entry_where = f"{where}:plugins[{i}]"
        if not report.check(isinstance(entry, dict), entry_where, "entry must be an object"):
            continue
        extras = {"description", "keywords", "license"} if harness == "claude" else {"policy"}
        fields_only(entry, {"name", "source", "category"} | extras, entry_where, report)
        name = entry.get("name")
        if not string(name, entry_where, "name", report):
            continue
        report.check(bool(KEBAB.fullmatch(name)), entry_where, "plugin name must be kebab-case")
        report.check(name not in seen, entry_where, f"duplicate plugin name {name!r}")
        seen.add(name)
        source = entry.get("source")
        if harness == "codex":
            if report.check(isinstance(source, dict), entry_where, "Codex source must be an object"):
                fields_only(source, {"source", "path"}, entry_where, report)
                report.check(source.get("source") == "local", entry_where, "source.source must be 'local'")
                source = source.get("path")
            policy = entry.get("policy")
            if report.check(isinstance(policy, dict), entry_where, "policy must be an object"):
                fields_only(policy, {"installation", "authentication"}, entry_where, report)
                for field, expected in (("installation", "AVAILABLE"),
                                        ("authentication", "ON_INSTALL")):
                    report.check(policy.get(field) == expected, entry_where, f"policy.{field} must be {expected!r}")
        else:
            for field in ("description", "license"):
                string(entry.get(field), entry_where, field, report)
            string_list(entry.get("keywords"), entry_where, "keywords", report)
        category = "productivity" if harness == "claude" else "Productivity"
        report.check(entry.get("category") == category, entry_where, f"category must be {category!r}")
        if string(source, entry_where, "source path", report):
            report.check(source == f"./plugins/{name}", entry_where,
                         f"source must be repository-relative './plugins/{name}'")
            bundled_path(root, source, root, entry_where, report, directory=True)
    report.check(seen == plugin_names, where,
                 f"catalog membership must match plugins/: missing {sorted(plugin_names - seen)}, "
                 f"unexpected {sorted(seen - plugin_names)}")


def validate(root):
    """Return all shared-source and harness-specific validation findings."""
    root = Path(root).resolve()
    report = Report()
    plugins_root = root / "plugins"
    plugins = sorted(p for p in plugins_root.iterdir() if p.is_dir()) if plugins_root.is_dir() else []
    report.check(plugins, plugins_root, "no plugin directories")
    names = {p.name for p in plugins}
    for harness in CATALOGS:
        check_catalog(root, harness, names, report)
    for plugin in plugins:
        if not report.check(plugin.resolve().is_relative_to(plugins_root), plugin,
                            "plugin directory escapes plugins/"):
            continue
        report.check(KEBAB.fullmatch(plugin.name), plugin, "plugin directory must be kebab-case")
        claude = check_manifest(plugin, "claude", report)
        codex = check_manifest(plugin, "codex", report)
        if claude is not None and codex is not None:
            for field in sorted(COMMON_FIELDS):
                report.check(claude.get(field) == codex.get(field), plugin,
                             f"Claude and Codex manifests disagree on `{field}`")
            interface = codex.get("interface")
            if isinstance(interface, dict):
                report.check(claude.get("displayName") == interface.get("displayName"), plugin,
                             "Claude displayName must match Codex interface.displayName")
        skills = plugin / "skills"
        skill_dirs = sorted(p for p in skills.iterdir() if p.is_dir()) if skills.is_dir() else []
        report.check(skill_dirs, skills, "missing or empty skills/ directory")
        for skill in skill_dirs:
            if report.check(skill.resolve().is_relative_to(plugin.resolve()), skill,
                            "skill directory escapes plugin root"):
                check_skill(skill, report)
        check_resources(plugin, report)
    return report


def print_report(report, root):
    if not report.errors:
        print(f"✔ {root} — Claude/Codex packaging, skills and bundled resources check out")
        return
    print(f"✘ {len(report.errors)} problems in {root}:", file=sys.stderr)
    for where, message in report.errors:
        print(f"  ❯ {where}: {message}", file=sys.stderr)


def main(argv):
    if len(argv) > 2:
        print(__doc__, file=sys.stderr)
        return 2
    root = Path(argv[1] if len(argv) > 1 else ".").resolve()
    if not any((root / path).is_file() for path in CATALOGS.values()):
        print(f"✘ no Claude or Codex marketplace catalog under {root}", file=sys.stderr)
        return 2
    report = validate(root)
    print_report(report, root)
    return 1 if report.errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

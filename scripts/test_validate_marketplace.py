#!/usr/bin/env python3
"""Regression tests for the shared marketplace contract; standard library only."""
import contextlib
import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import validate_marketplace as validator

REPO = Path(__file__).resolve().parents[1]
SKILL = 'plugins/fixture/skills/check/SKILL.md'
CLAUDE = 'plugins/fixture/.claude-plugin/plugin.json'
CODEX = 'plugins/fixture/.codex-plugin/plugin.json'


def add_fixture(root):
    """Add an independent plugin fixture with shared and skill resources."""
    plugin = root / 'plugins/fixture'
    description = 'A synthetic fixture for marketplace validation.'
    for harness in ('claude', 'codex'):
        original = root / 'plugins/explain' / f'.{harness}-plugin/plugin.json'
        manifest = json.loads(original.read_text())
        manifest.update(name='fixture', version='0.0.0', description=description,
                        keywords=['test-fixture'])
        if harness == 'claude':
            manifest['displayName'] = 'Fixture'
        else:
            manifest['interface'].update(
                displayName='Fixture', shortDescription='Validation fixture.',
                longDescription=description, defaultPrompt=['Check the fixture.'])
        target = plugin / f'.{harness}-plugin/plugin.json'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(manifest))
        catalog_path = root / validator.CATALOGS[harness]
        catalog = json.loads(catalog_path.read_text())
        entry = json.loads(json.dumps(catalog['plugins'][0]))
        entry.update(name='fixture')
        entry['source'] = ('./plugins/fixture' if harness == 'claude' else
                           {'source': 'local', 'path': './plugins/fixture'})
        if harness == 'claude':
            entry.update(description=description, keywords=['test-fixture'])
        catalog['plugins'].append(entry)
        catalog_path.write_text(json.dumps(catalog))
    contents = {
        'skills/check/SKILL.md': (
            '---\nname: check\ndescription: Validate a synthetic example.\n'
            'user-invocable: true\ndisable-model-invocation: true\n'
            'allowed-tools: Bash(python3 "${CLAUDE_PLUGIN_ROOT}/shared/helper.py" *)\n'
            '---\n[Guide](references/guide.md)\n'
            '[Helper](../../shared/helper.py)\n[State](../../shared/state.md)\n'),
        'skills/check/agents/openai.yaml':
            'policy:\n  allow_implicit_invocation: false\n',
        'skills/check/references/guide.md': '# Fixture guide\n',
        'shared/helper.py': 'print("fixture helper")\n',
        'shared/state.md': '# Synthetic state\n',
    }
    for relative, text in contents.items():
        target = plugin / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)


class TestRepository(unittest.TestCase):
    def test_actual_checkout_has_matching_catalogs_and_valid_plugins(self):
        report = validator.validate(REPO)
        self.assertEqual(report.errors, [])
        plugins = {p.name for p in (REPO / 'plugins').iterdir() if p.is_dir()}
        self.assertIn('explain', plugins)
        for path in validator.CATALOGS.values():
            catalog = json.loads((REPO / path).read_text())
            self.assertEqual({p['name'] for p in catalog['plugins']}, plugins)
        explain = REPO / 'plugins/explain/skills'
        self.assertEqual({p.parent.name for p in explain.glob('*/SKILL.md')}, {'visually'})


class TestFrontmatter(unittest.TestCase):
    def parse(self, source):
        return validator.parse_frontmatter(f"---\n{source}\n---\nBody\n")

    def test_supported_scalars_and_block_chomping(self):
        fields = self.parse('name: "start"\nargument-hint: \'it\'\'s a choice\'\n'
                            'description: >\n  First line.\n  Second line.\n'
                            'user-invocable: true\ndisable-model-invocation: false')
        self.assertEqual(fields['name'], 'start')
        self.assertEqual(fields['argument-hint'], "it's a choice")
        self.assertEqual(fields['description'], 'First line. Second line.\n')
        self.assertIs(fields['user-invocable'], True)
        self.assertIs(fields['disable-model-invocation'], False)
        for style, expected in ((">-", "a b"), ("|-", "a\nb"), ("|", "a\nb\n")):
            self.assertEqual(self.parse(f"description: {style}\n  a\n  b")['description'], expected)

    def test_unsupported_or_ambiguous_yaml_is_reported(self):
        for source in ('name: a\nname: b', 'name: [start]', 'name: {a: b}',
                       'name: 42', 'name: null', 'name: &alias start',
                       'name: *alias', 'description: >\n   too indented',
                       'description: >', 'name: "unterminated', 'name: \'broken',
                       'metadata:\n  key: value', 'name: start # comment',
                       'description: >\n  a\n\n  b'):
            with self.subTest(source=source), self.assertRaises(ValueError):
                self.parse(source)

    def test_missing_frontmatter_fences_are_reported(self):
        for text in ('name: start', '---\nname: start', '\n---\nname: start\n---'):
            with self.subTest(text=text), self.assertRaisesRegex(ValueError, 'fences'):
                validator.parse_frontmatter(text)


class TestMarketplace(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='thoughtcraft tests ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'marketplace with spaces'
        self.root.mkdir()
        shutil.copytree(REPO / 'plugins/explain', self.root / 'plugins/explain',
                        ignore=shutil.ignore_patterns('__pycache__', '.DS_Store'))
        for relative in validator.CATALOGS.values():
            catalog = json.loads((REPO / relative).read_text())
            catalog['plugins'] = [p for p in catalog['plugins'] if p['name'] == 'explain']
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(catalog))
        add_fixture(self.root)

    def errors(self):
        return '\n'.join(f'{where}: {message}' for where, message in validator.validate(self.root).errors)

    def mutate_json(self, relative, mutate):
        path = self.root / relative
        original = json.loads(path.read_text())
        mutate(original)
        path.write_text(json.dumps(original))

    def assert_problem(self, fragment):
        self.assertIn(fragment, self.errors())

    def test_fixture_catalogs_expose_two_plugins_and_two_skills(self):
        self.assertEqual(self.errors(), '')
        expected = {'explain': {'visually'}, 'fixture': {'check'}}
        for catalog_path in validator.CATALOGS.values():
            catalog = json.loads((self.root / catalog_path).read_text())
            self.assertEqual({e['name'] for e in catalog['plugins']}, set(expected))
        for name, skills in expected.items():
            skill_files = (self.root / 'plugins' / name / 'skills').glob('*/SKILL.md')
            self.assertEqual({p.parent.name for p in skill_files}, skills)

    def test_missing_manifests_are_actionable_for_both_harnesses(self):
        for path in (CLAUDE, CODEX):
            (self.root / path).unlink()
        errors = self.errors()
        for path in (CLAUDE, CODEX):
            self.assertIn(path, errors)
        self.assertIn('cannot read file', errors)

    def test_missing_one_catalog_is_a_validation_failure(self):
        (self.root / validator.CATALOGS['codex']).unlink()
        self.assert_problem('.agents/plugins/marketplace.json')

    def test_catalog_membership_catches_missing_and_unlisted_plugins(self):
        self.mutate_json(validator.CATALOGS['codex'], lambda obj: obj['plugins'].pop())
        self.assert_problem('catalog membership')

    def test_duplicate_entries_are_rejected(self):
        self.mutate_json(validator.CATALOGS['codex'],
                         lambda obj: obj['plugins'].append(obj['plugins'][0]))
        self.assert_problem('duplicate plugin name')

    def test_unresolved_and_escaping_sources_are_rejected(self):
        for harness in validator.CATALOGS:
            path = self.root / validator.CATALOGS[harness]
            original = path.read_text()
            for bad in ('./missing', '../outside', '/tmp'):
                catalog = json.loads(original)
                catalog['plugins'][0]['source'] = (
                    bad if harness == 'claude' else {'source': 'local', 'path': bad})
                path.write_text(json.dumps(catalog))
                self.assert_problem('source must be repository-relative')
            path.write_text(original)

    def test_matching_identity_version_and_display_metadata_are_required(self):
        for field, value in (('name', 'wrong'), ('version', '99.0.0'),
                             ('description', 'different'), ('author', {'name': 'Other'}),
                             ('repository', 'https://example.com'), ('license', 'Other'),
                             ('keywords', ['other'])):
            path = self.root / CODEX
            original = path.read_text()
            self.mutate_json(CODEX, lambda obj: obj.update({field: value}))
            self.assert_problem(f'manifests disagree on `{field}`')
            path.write_text(original)
        self.mutate_json(CODEX, lambda obj: obj['interface'].update(displayName='Wrong'))
        self.assert_problem('Claude displayName must match')

    def test_semver_boundaries(self):
        for version in ('0.1.0', '1.0.0-rc.1+local.5', '2.3.4+codex.test'):
            self.assertIsNotNone(validator.SEMVER.fullmatch(version))
        for version in ('v1.0.0', '01.2.3', '1.0', '1.0.0-01', '1.0.0+', '1.0.0-a..b'):
            self.assertIsNone(validator.SEMVER.fullmatch(version))
        self.mutate_json(CODEX, lambda obj: obj.update(version='1.0'))
        self.assert_problem('must be strict semver')

    def test_manifest_field_types_never_crash_validation(self):
        for relative in (CLAUDE, CODEX):
            path = self.root / relative
            original = path.read_text()
            for field in json.loads(original):
                for value in ([], 3, False, None):
                    with self.subTest(path=relative, field=field, value=value):
                        payload = json.loads(original)
                        payload[field] = value
                        path.write_text(json.dumps(payload))
                        self.assertNotEqual(self.errors(), '')
            path.write_text(original)

    def test_catalog_field_types_never_crash_validation(self):
        for relative in validator.CATALOGS.values():
            path = self.root / relative
            original = path.read_text()
            for payload in ([], {'name': [], 'plugins': []}, {'name': 'thoughtcraft', 'plugins': [None]},
                            {'name': 'thoughtcraft', 'plugins': [{'name': ['bad']}]},
                            {'name': 'thoughtcraft', 'plugins': [{'name': 'explain', 'source': []}]}):
                path.write_text(json.dumps(payload))
                self.assertNotEqual(self.errors(), '')
            path.write_text(original)

    def test_json_parse_failures_and_wrong_root_type(self):
        for payload in ('{', '[]', 'null'):
            (self.root / CODEX).write_text(payload)
            self.assert_problem('.codex-plugin/plugin.json')

    def test_harness_specific_fields_and_policies(self):
        self.mutate_json(CLAUDE, lambda obj: obj.update(skills='./skills/'))
        self.mutate_json(CODEX, lambda obj: obj.update(skills='./', displayName='Wrong place'))
        self.mutate_json(validator.CATALOGS['codex'],
                         lambda obj: obj['plugins'][0]['policy'].update(
                             installation='INSTALLED_BY_DEFAULT', authentication='ON_USE'))
        for message in ('remove Claude `skills`', "Codex `skills` must be './skills/'",
                        'unsupported field `displayName`', 'policy.installation', 'policy.authentication'):
            self.assert_problem(message)

    def test_skill_description_budget_counts_decoded_string(self):
        path = self.root / SKILL
        original = path.read_text()
        for size in (1024, 1025):
            frontmatter = ('---\nname: check\ndescription: ' + json.dumps('é' * size) + '\n'
                           'user-invocable: true\ndisable-model-invocation: true\n---\nBody\n')
            path.write_text(frontmatter)
            if size == 1024:
                self.assertEqual(self.errors(), '')
            else:
                self.assert_problem('limit is 1024')
        path.write_text(original)

    def test_invalid_skill_fields_names_and_descriptions(self):
        path = self.root / SKILL
        original = path.read_text()
        for source in ('name: different\ndescription: valid', 'name: check\ndescription: false',
                       'name: check\ndescription: ""', 'name: check\ndescription: [a]',
                       'name: check\ndescription: valid\nwhen_to_use: old'):
            path.write_text('---\n' + source + '\nuser-invocable: true\n'
                            'disable-model-invocation: true\n---\nBody\n')
            self.assertNotEqual(self.errors(), '')
        path.write_text(original)

    def test_missing_empty_skills_and_missing_skill_file(self):
        shutil.rmtree(self.root / 'plugins/explain/skills')
        (self.root / SKILL).unlink()
        self.assert_problem('missing or empty skills/')
        self.assert_problem('check/SKILL.md')

    def test_unresolved_resources_in_shared_and_skill_directories(self):
        for relative in ('plugins/fixture/shared/helper.py',
                         'plugins/fixture/shared/state.md',
                         'plugins/explain/skills/visually/references/mode-1-structural.md',
                         'plugins/explain/skills/visually/scripts/diagrams.py'):
            (self.root / relative).unlink()
        for message in ('helper.py', 'state.md', 'mode-1-structural.md', 'diagrams.py'):
            self.assert_problem(message)
        self.assert_problem('unresolved bundled file: ')

    def test_nested_reference_links_are_resolved_from_containing_file(self):
        path = self.root / 'plugins/fixture/skills/check/references/guide.md'
        with path.open('a') as output:
            output.write('\n[Missing](nested/missing.md#anchor)\n')
        self.assert_problem('nested/missing.md')

    def test_symlinks_cannot_escape_the_plugin(self):
        outside = Path(self.temp.name) / 'outside.py'
        outside.write_text('print("outside")')
        helper = self.root / 'plugins/fixture/shared/helper.py'
        helper.unlink()
        helper.symlink_to(outside)
        self.assert_problem('path escapes bundled root')

    def test_invocation_policy_is_explicit_and_matches_claude(self):
        for skill in (self.root / 'plugins').glob('*/skills/*'):
            expected = skill.parents[1].name == 'explain'
            policy_path = skill / 'agents/openai.yaml'
            self.assertEqual(policy_path.read_text(),
                             f'policy:\n  allow_implicit_invocation: {str(expected).lower()}\n')
        policy = self.root / 'plugins/fixture/skills/check/agents/openai.yaml'
        for text, message in (('policy:\n  allow_implicit_invocation: true\n', 'disagrees'),
                              ('policy:\n  allow_implicit_invocation: "false"\n', 'YAML boolean')):
            policy.write_text(text)
            self.assert_problem(message)
        policy.unlink()
        self.assert_problem('agents/openai.yaml')

    def test_allowed_tools_cannot_expand_beyond_the_bundled_helper(self):
        path = self.root / SKILL
        original = path.read_text()
        for grant in ('Bash(*)', 'Bash(python3 *)',
                      'Bash(python3 "${CLAUDE_PLUGIN_ROOT}/shared/helper.py" *), Bash(rm *)'):
            lines = [f'allowed-tools: {grant}' if line.startswith('allowed-tools:') else line
                     for line in original.splitlines()]
            path.write_text('\n'.join(lines) + '\n')
            self.assert_problem('allowed-tools must be scoped')

    def test_helpers_execute_from_copied_plugins_and_unrelated_working_directory(self):
        cwd = Path(self.temp.name) / 'unrelated cwd'
        cwd.mkdir()
        commands = (
            (self.root / 'plugins/explain/skills/visually/scripts/diagrams.py',
             ['box', 'Shared source'], '│ Shared source │'),
            (self.root / 'plugins/fixture/shared/helper.py', [], 'fixture helper'),
        )
        for helper, args, expected in commands:
            result = subprocess.run([sys.executable, '-S', str(helper), *args],
                                    cwd=cwd, text=True, capture_output=True, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(expected, result.stdout)

    def test_cli_exit_codes_are_preserved(self):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(validator.main(['validate', str(self.root)]), 0)
            (self.root / CODEX).write_text('{}')
            self.assertEqual(validator.main(['validate', str(self.root)]), 1)
            self.assertEqual(validator.main(['validate', self.temp.name]), 2)
            self.assertEqual(validator.main(['validate', 'a', 'b']), 2)


if __name__ == '__main__':
    unittest.main()

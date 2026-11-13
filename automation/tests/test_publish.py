import argparse
import base64
from contextlib import redirect_stdout
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from automation import pipeline as p
from automation import publish as q

FIXTURES = Path(__file__).parent / 'fixtures'


class PublisherConfigurationTests(unittest.TestCase):
    def test_production_configuration_targets_main_and_both_keyword_files(self):
        root = Path(__file__).parents[1]
        config = json.loads((root / 'publishing.json').read_text())
        self.assertEqual(config['repository'], 'ohlongshawnson/nopartisan')
        self.assertEqual(config['branch'], 'main')
        self.assertEqual(q.PATHS, ('keywords/politics.json', 'extension/keywords.json'))


class FakeGitHub(q.GitHub):
    """Exercise the real API orchestration with an in-memory GitHub transport."""
    def __init__(self, raw, race=False, fail=None):
        super().__init__('ohlongshawnson/nopartisan', 'main')
        self.head_sha = 'a' * 40
        self.tree_sha = 'c' * 40
        self.new_sha = 'b' * 40
        self.raw = raw
        self.files = {name: raw for name in q.PATHS}
        self.calls = []
        self.race = race
        self.fail = fail
        self.payload = None

    def request(self, method, path, payload=None):
        self.calls.append((method, path, copy.deepcopy(payload)))
        if method == self.fail:
            raise ValueError('simulated HTTP failure')
        if path == '/git/ref/heads/main':
            return {'object': {'sha': self.head_sha}}
        if method == 'GET' and path.startswith('/git/commits/'):
            return {'tree': {'sha': self.tree_sha}}
        if method == 'GET' and path.startswith('/contents/'):
            name = path.removeprefix('/contents/').split('?')[0]
            raw = self.files[name]
            return {'encoding': 'base64', 'content': base64.b64encode(raw).decode(), 'size': len(raw)}
        if path == '/git/trees':
            if payload['base_tree'] != self.tree_sha:
                raise AssertionError('base tree lost')
            self.payload = payload
            return {'sha': 'd' * 40}
        if path == '/git/commits':
            if payload['parents'] != ['a' * 40]:
                raise AssertionError('unexpected parent')
            return {'sha': self.new_sha}
        if method == 'PATCH':
            if payload['force'] is not False:
                raise AssertionError('force push attempted')
            if self.race:
                raise ValueError('simulated non-fast-forward conflict')
            self.files = {entry['path']: entry['content'].encode() for entry in self.payload['tree']}
            self.head_sha = self.new_sha
            return {'object': {'sha': self.head_sha}}
        raise AssertionError((method, path))


class PublisherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.cfg = json.loads((FIXTURES / 'publishing-v1.json').read_bytes())
        self.cfg.update(minimum_records=6, maximum_records=6)
        self.config = self.root / 'publishing.json'
        p.save(self.config, self.cfg)
        self.token = self.root / 'credential'
        self.token.write_text('fixture-token-not-a-real-credential')
        self.token.chmod(0o600)
        self.args = argparse.Namespace(config=str(self.config), data=str(self.root / 'data'),
                                       dry_run=False, token_file=str(self.token))
        self.base = p.encode({'schemaVersion': 1, 'version': 'original', 'keywords': ['political campaign']})
        names = {'senate_xml': 'publishing-senate.xml', 'legislators_csv': 'legislators.csv', 'feed': 'news.xml'}
        self.responses = {s['url']: (FIXTURES / names[s['kind']]).read_bytes() for s in self.cfg['sources']}

    def run_pipeline(self, api):
        with patch.object(p.Fetcher, 'get', side_effect=lambda url: self.responses[url]), redirect_stdout(io.StringIO()):
            return q.run(self.args, api=api)

    def writes(self, api):
        return [c for c in api.calls if c[0] != 'GET']

    def test_complete_run_atomic_files_and_noop(self):
        api = FakeGitHub(self.base)
        result = self.run_pipeline(api)
        self.assertEqual(result['status'], 'published')
        self.assertEqual(result['keywords'], 7)
        self.assertEqual(result['added'], 6)
        self.assertEqual(len(self.writes(api)), 3)  # tree, commit, single ref update
        self.assertEqual(api.files[q.PATHS[0]], api.files[q.PATHS[1]])
        complete = json.loads(api.files[q.PATHS[0]])
        self.assertEqual(complete['schemaVersion'], 1)
        self.assertIn('political campaign', complete['keywords'])
        self.assertIn('angus s. king, jr.', complete['keywords'])
        p.validate_list(complete)
        self.assertEqual(set(e['path'] for e in api.payload['tree']), set(q.PATHS))
        self.assertEqual(p.load(Path(self.args.data) / 'last-success.json')['commit'], api.new_sha)
        api.calls.clear()
        result = self.run_pipeline(api)
        self.assertEqual(result['status'], 'unchanged')
        self.assertEqual(result['version'], complete['version'])
        self.assertFalse(self.writes(api))

    def test_dry_run_never_writes_or_advances_success(self):
        self.args.dry_run = True
        self.args.token_file = '/missing-token-not-needed'
        api = FakeGitHub(self.base)
        self.assertEqual(self.run_pipeline(api)['status'], 'dry-run')
        self.assertFalse(self.writes(api))
        self.assertFalse((Path(self.args.data) / 'last-success.json').exists())

    def test_network_failure_preserves_remote_and_success(self):
        for source in self.cfg['sources']:
            with self.subTest(source=source['id']):
                api = FakeGitHub(self.base)
                def fetched(url):
                    if url == source['url']:
                        raise OSError('simulated source failure')
                    return self.responses[url]
                with patch.object(p.Fetcher, 'get', side_effect=fetched):
                    with self.assertRaises(OSError):
                        q.run(self.args, api=api)
                self.assertFalse(self.writes(api))
                self.assertEqual(api.raw, self.base)

    def test_empty_invalid_and_small_collection_never_writes(self):
        url = self.cfg['sources'][0]['url']
        for body in [b'<contact_information/>', b'<html>denied</html>', b'<broken',
                     (FIXTURES / 'senate.xml').read_bytes(), b'']:
            api = FakeGitHub(self.base)
            self.responses[url] = body
            with self.assertRaises((ValueError, p.ET.ParseError)):
                self.run_pipeline(api)
            self.assertFalse(self.writes(api))
            self.assertEqual(api.files[q.PATHS[0]], self.base)

    def test_disagreeing_identity_state_affiliation_or_name_stops(self):
        url = self.cfg['sources'][0]['url']
        original = self.responses[url]
        for before, after in [(b'C000127', b'C999999'), (b'<state>WA</state>', b'<state>CA</state>'),
                              (b'<party>D</party>', b'<party>R</party>'),
                              (b'<first_name>Maria</first_name>', b'<first_name>Wrong</first_name>')]:
            self.responses[url] = original.replace(before, after)
            api = FakeGitHub(self.base)
            with self.assertRaises(ValueError):
                self.run_pipeline(api)
            self.assertFalse(self.writes(api))

    def test_normalized_dedup_and_complete_list(self):
        base = p.encode({'schemaVersion': 1, 'version': 'v', 'keywords': [' ＭＡＲＩＡ  Cantwell ', 'political campaign']})
        output, added = q.merge(base, [{'phrase': 'Maria Cantwell'}, {'phrase': 'Amy Klobuchar'}, {'phrase': 'amy  klobuchar'}])
        self.assertEqual(added, ['amy klobuchar'])
        self.assertEqual(len(json.loads(output)['keywords']), 3)
        output2, added = q.merge(output, [{'phrase': 'Amy Klobuchar'}])
        self.assertEqual(output2, output)
        self.assertEqual(added, [])

    def test_foundational_vocabulary_survives_collected_name_updates(self):
        foundation = json.loads((Path(__file__).parents[2] / 'keywords/foundational.json').read_text())['keywords']
        base = p.encode({'schemaVersion': 1, 'version': 'foundation', 'keywords': foundation})
        output, added = q.merge(base, [{'phrase': 'Amy Klobuchar'}])
        result = json.loads(output)
        self.assertEqual(result['schemaVersion'], 1)
        self.assertTrue(set(foundation).issubset(result['keywords']))
        self.assertIn('amy klobuchar', added)
        output, _ = q.merge(output, [{'phrase': 'Maria Cantwell'}])
        self.assertTrue(set(foundation).issubset(json.loads(output)['keywords']))

    def test_malformed_or_empty_merge(self):
        for candidates in [[], [{'phrase': 'Trump'}], [{'phrase': 'A\x00 B'}]]:
            with self.assertRaises(ValueError):
                q.merge(self.base, candidates)

    def test_invalid_remote_schema_or_unsynced_bundle(self):
        for raw in [b'{}', p.encode({'schemaVersion': 2, 'version': 'v', 'keywords': ['name']})]:
            api = FakeGitHub(raw)
            with self.assertRaises(ValueError):
                self.run_pipeline(api)
            self.assertFalse(self.writes(api))
        api = FakeGitHub(self.base)
        api.files[q.PATHS[1]] = self.base + b' '
        with self.assertRaises(ValueError):
            self.run_pipeline(api)
        self.assertFalse(self.writes(api))

    def test_remote_race_no_force_or_replacement(self):
        api = FakeGitHub(self.base, race=True)
        with self.assertRaisesRegex(ValueError, 'non-fast-forward'):
            self.run_pipeline(api)
        self.assertEqual(api.files[q.PATHS[0]], self.base)
        self.assertEqual(api.head_sha, 'a' * 40)
        run = sorted((Path(self.args.data) / 'publishing').iterdir())[-1]
        result = p.load(run / 'result.json')
        self.assertEqual(result['intended_commit'], api.new_sha)
        self.assertEqual(result['status'], 'failed')
        self.assertFalse((Path(self.args.data) / 'last-success.json').exists())

    def test_github_write_failure_does_not_replace_list(self):
        api = FakeGitHub(self.base, fail='POST')
        with self.assertRaises(ValueError):
            self.run_pipeline(api)
        self.assertFalse(any(c[0] == 'PATCH' for c in api.calls))
        self.assertEqual(api.files[q.PATHS[0]], self.base)

    def test_existing_success_marker_survives_failure(self):
        marker = Path(self.args.data) / 'last-success.json'
        p.save(marker, {'commit': 'prior-good-commit'})
        self.responses[self.cfg['sources'][0]['url']] = b'bad-source'
        with self.assertRaises(p.ET.ParseError):
            self.run_pipeline(FakeGitHub(self.base))
        self.assertEqual(p.load(marker), {'commit': 'prior-good-commit'})

    def test_config_and_credential_validation(self):
        self.assertEqual(q.token_from_file(self.token), 'fixture-token-not-a-real-credential')
        self.token.chmod(0o644)
        with self.assertRaises(ValueError):
            q.token_from_file(self.token)
        self.cfg['sources'][0]['required'] = False
        p.save(self.config, self.cfg)
        with self.assertRaises(ValueError):
            q.publishing_config(self.config)

    def test_concurrent_run_lock(self):
        import fcntl
        data = Path(self.args.data)
        data.mkdir()
        with (data / 'publish.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaisesRegex(ValueError, 'another publishing run'):
                self.run_pipeline(FakeGitHub(self.base))

    def test_isolated_systemd_credentials(self):
        import stat
        from types import SimpleNamespace
        managed = Path('/run/credentials/fixture.service/github-token')
        info = SimpleNamespace(st_mode=stat.S_IFREG | 0o440, st_uid=0)
        with patch.object(Path, 'stat', return_value=info), patch.object(p, 'read_bytes', return_value=b'fixture-token'), \
                patch.dict(q.os.environ, {'CREDENTIALS_DIRECTORY': str(managed.parent)}):
            self.assertEqual(q.token_from_file(managed), 'fixture-token')
            with self.assertRaises(ValueError):
                q.token_from_file(self.root / 'ordinary-group-readable-file')

    def test_empty_feed_cannot_publish(self):
        self.responses[self.cfg['sources'][2]['url']] = b'<rss><channel/></rss>'
        api = FakeGitHub(self.base)
        with self.assertRaisesRegex(ValueError, 'empty source'):
            self.run_pipeline(api)
        self.assertFalse(self.writes(api))


if __name__ == '__main__':
    unittest.main()

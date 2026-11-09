import argparse
from contextlib import redirect_stdout, redirect_stderr
import csv
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from automation import pipeline as p

FIXTURES = Path(__file__).parent / 'fixtures'


class LogicTests(unittest.TestCase):
    def test_extension_normalization(self):
        for source, expected in [(' ＭＡＧＡ\u00a0  Party ', 'maga party'),
                                 ('\ufeffJoe\tBiden\n', 'joe biden'),
                                 ('Straße', 'straße'), ('İ', 'i\u0307'),
                                 ('A\u0085B', 'a\u0085b'), ('e\u0301lection', 'élection')]:
            self.assertEqual(p.normalize(source), expected)

    def test_literal_unicode_boundaries(self):
        self.assertTrue(p.contains('C++ discussion', 'C++'))
        self.assertTrue(p.contains('#MAGA!', 'maga'))
        for text in ['magazine', 'MAGA2026', 'éMAGA', '_MAGA', 'MAGA_']:
            self.assertFalse(p.contains(text, 'maga'))

    def test_ambiguous_single_terms_excluded(self):
        for name in ['Trump', 'Joe', 'Washington', 'election', '#MAGA', '123 456', 'John\u200b Smith']:
            self.assertIsNotNone(p.blocked_reason(name))
        self.assertIsNone(p.blocked_reason('Maria Cantwell'))
        self.assertIsNotNone(p.blocked_reason('ordinary everyday', 'organization'))

    def test_schema(self):
        valid = {'schemaVersion': 1, 'version': 'v', 'keywords': ['Full Name']}
        self.assertEqual(p.validate_list(valid), valid)
        invalid = [None, {}, {**valid, 'schemaVersion': True}, {**valid, 'version': 1},
                   {**valid, 'version': 'v' * 101}, {**valid, 'keywords': []},
                   {**valid, 'keywords': ['x'] * 10001}]
        for word in ['', '   ', 7, 'x' * 121, 'a\nname', 'a\x85name', '😀' * 61]:
            invalid.append({**valid, 'keywords': [word]})
        for value in invalid:
            with self.subTest(value=str(value)[:60]), self.assertRaises((ValueError, UnicodeError)):
                p.validate_list(value)
        with self.assertRaises(ValueError):
            p.validate_list({**valid, 'keywords': ['政治' * 60] * 3000})

    def test_saved_sources(self):
        for kind, name in [('legislators_csv', 'legislators.csv'), ('feed', 'news.xml'), ('feed', 'atom.xml'), ('senate_xml', 'senate.xml')]:
            self.assertTrue(p.parse_source({'kind': kind}, (FIXTURES / name).read_bytes()))

    def test_malformed_sources(self):
        bad = [('feed', b'<html>access denied</html>'), ('feed', b'<rss>'),
               ('feed', (FIXTURES / 'malformed.xml').read_bytes()),
               ('feed', '<!DOCTYPE rss><rss/>'.encode('utf-16')),
               ('legislators_csv', b'first_name,last_name\nJoe,Test\n'),
               ('senate_xml', b'<contact_information/>'),
               ('feed', b'<rss><channel><item><title>x</title></item></channel></rss>')]
        for kind, raw in bad:
            with self.subTest(kind=kind, raw=raw[:40]), self.assertRaises((ValueError, p.ET.ParseError, UnicodeError)):
                p.parse_source({'kind': kind}, raw)

    def test_bad_csv_rows(self):
        raw = (FIXTURES / 'legislators.csv').read_bytes()
        for changed in [raw.replace(b'https://www.cantwell.senate.gov', b'https://example.org'),
                        raw.replace(b'C000127', b'bad-id'), raw + b'extra,column\n']:
            with self.assertRaises(ValueError):
                p.parse_source({'kind': 'legislators_csv'}, changed)

    def test_urls(self):
        for url in ['http://example.org', 'https://user:pass@example.org', 'https://127.0.0.1',
                    'https://localhost', 'https://example.org/#secret', 'https://example.org:123/x']:
            with self.assertRaises(ValueError):
                p.safe_url(url)
        self.assertEqual(p.safe_url('https://example.org/path'), 'https://example.org/path')

    def test_redirect_rejected(self):
        with self.assertRaises(ValueError):
            p.NoRedirect().redirect_request(None, None, 302, '', {}, 'https://example.org')

    def test_fetch_size_and_timeout(self):
        class Response:
            status = 200
            headers = {'Content-Length': str(p.MAX_SOURCE + 1)}
            def __enter__(self): return self
            def __exit__(self, *args): pass
        fetcher = p.Fetcher()
        with patch.object(fetcher.opener, 'open', return_value=Response()) as opened:
            with self.assertRaisesRegex(ValueError, 'exceeds'):
                fetcher.get('https://example.org')
            self.assertEqual(opened.call_args.kwargs['timeout'], 15)
        class Streaming(Response):
            headers = {}
            def read1(self, size): return b'x' * size
        with patch.object(fetcher.opener, 'open', return_value=Streaming()), patch.object(p.time, 'sleep'):
            with self.assertRaisesRegex(ValueError, 'exceeds'):
                fetcher.get('https://example.org')
        class Compressed(Response):
            headers = {'Content-Encoding': 'gzip'}
        with patch.object(fetcher.opener, 'open', return_value=Compressed()), patch.object(p.time, 'sleep'):
            with self.assertRaisesRegex(ValueError, 'compressed'):
                fetcher.get('https://example.org')
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'large'
            path.write_bytes(b'x' * 101)
            with self.assertRaises(ValueError):
                p.read_bytes(path, 100)


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.root_patch = patch.object(p, 'ROOT', self.root)
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)
        self.data = self.root / 'data'
        base = {'schemaVersion': 1, 'version': 'original', 'keywords': [' ＭＡＲＩＡ  Cantwell ']}
        for name in ['keywords/politics.json', 'extension/keywords.json']:
            p.save(self.root / name, base)
        self.original = (self.root / 'keywords/politics.json').read_bytes()
        self.sources = [
            {'id': 'people', 'name': 'Fixture directory', 'kind': 'legislators_csv', 'required': True,
             'url': 'https://example.org/people.csv', 'snapshot_date': '2020-01-01'},
            {'id': 'other', 'name': 'Duplicate fixture directory', 'kind': 'legislators_csv', 'url': 'https://example.org/duplicate.csv'},
            {'id': 'news', 'name': 'Synthetic news', 'kind': 'feed', 'url': 'https://example.org/feed.xml'}]
        self.cfg = self.root / 'sources.json'
        p.save(self.cfg, {'scope': 'US Senate test fixtures', 'sources': self.sources})
        for source in self.sources:
            filename = 'news.xml' if source['kind'] == 'feed' else 'legislators.csv'
            self.cli('import-source', '--source', source['id'], '--file', str(FIXTURES / filename),
                     '--fetched-at', '2026-01-01T00:00:00Z', '--transport', 'fixture')

    def cli(self, *args, expected=0):
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            result = p.main(['--config', str(self.cfg), '--data', str(self.data), *args])
        self.assertEqual(result, expected, args)

    def collect(self, limit='12', expected=0):
        self.cli('collect', '--imports-only', '--limit', limit, expected=expected)
        return sorted((self.data / 'runs').iterdir())[-1]

    def approval(self, run):
        report = p.load(run / 'candidates.json')
        target = self.root / 'approval.json'
        self.cli('approve', '--run', str(run), '--ids', report['candidates'][0]['id'],
                 '--reviewer', 'Fixture reviewer', '--reason', 'Synthetic test approval only',
                 '--acknowledge-concerns', '--out', str(target))
        return target

    def test_dedup_coverage_and_concerns(self):
        run = self.collect()
        report = p.load(run / 'candidates.json')
        words = [c['normalized_phrase'] for c in report['candidates']]
        self.assertNotIn('maria cantwell', words)
        self.assertEqual(len(words), len(set(words)))
        self.assertGreater(report['summary']['duplicate_records'], 0)
        self.assertEqual({c['affiliation'] for c in report['candidates']}, {'Democrat', 'Republican', 'Independent'})
        self.assertTrue(all(c['review_status'] == 'pending' and c['ambiguity_concerns'] for c in report['candidates']))
        self.assertGreater(report['summary']['unmatched_feed_entries'], 0)
        self.assertNotIn('business celebrity', words)
        self.assertEqual((self.root / 'keywords/politics.json').read_bytes(), self.original)
        self.assertTrue((run / 'report.md').exists())
        self.assertTrue((run / 'proposed-additions.json').exists())

    def test_batch_limit(self):
        report = p.load(self.collect(limit='3') / 'candidates.json')
        self.assertEqual(len(report['candidates']), 3)
        self.assertGreater(report['summary']['deferred'], 0)

    def test_approval_gate_and_patch(self):
        run = self.collect()
        report = p.load(run / 'candidates.json')
        self.cli('approve', '--run', str(run), '--ids', report['candidates'][0]['id'], '--reviewer', 'Human',
                 '--reason', 'Review', '--out', str(self.root / 'no.json'), expected=2)
        approval = self.approval(run)
        output = self.root / 'changes.patch'
        self.cli('patch', '--run', str(run), '--approval', str(approval), '--out', str(output), expected=2)
        self.cli('patch', '--run', str(run), '--approval', str(approval), '--version', 'reviewed', '--out', str(output))
        text = output.read_text()
        self.assertIn('a/keywords/politics.json', text)
        self.assertIn('a/extension/keywords.json', text)
        self.assertEqual(text.count('+  "version": "reviewed"'), 2)
        self.assertEqual((self.root / 'keywords/politics.json').read_bytes(), self.original)
        self.cli('patch', '--run', str(run), '--approval', str(approval), '--version', 'reviewed',
                 '--out', str(self.root / 'keywords/politics.json'), expected=2)
        self.assertEqual((self.root / 'keywords/politics.json').read_bytes(), self.original)
        # Actually apply the generated unified diff in a temporary fixture repository.
        import subprocess
        subprocess.run(['git', 'apply', '--check', str(output)], cwd=self.root, check=True)
        subprocess.run(['git', 'apply', str(output)], cwd=self.root, check=True)
        self.assertEqual((self.root / 'keywords/politics.json').read_bytes(), (self.root / 'extension/keywords.json').read_bytes())
        p.validate_list(p.load(self.root / 'keywords/politics.json'))

    def test_tampered_report_and_stale_baseline(self):
        run = self.collect()
        approval = self.approval(run)
        arguments = ['patch', '--run', str(run), '--approval', str(approval), '--version', 'reviewed', '--out', str(self.root / 'p.patch')]
        raw = (run / 'candidates.json').read_bytes()
        (run / 'candidates.json').write_bytes(raw + b' ')
        self.cli(*arguments, expected=2)
        (run / 'candidates.json').write_bytes(raw)
        (self.root / 'keywords/politics.json').write_bytes(self.original + b' ')
        self.cli(*arguments, expected=2)

    def test_source_integrity_and_required_failure(self):
        (self.data / 'imports/people.body').write_bytes(b'corrupt')
        report = p.load(self.collect(expected=2) / 'candidates.json')
        self.assertTrue(report['summary']['required_source_failed'])

    def test_duplicate_config_ids(self):
        p.save(self.cfg, {'sources': [self.sources[0], self.sources[0]]})
        with self.assertRaises(ValueError):
            p.config(self.cfg)

    def test_empty_approval_does_not_change_version(self):
        run = self.collect()
        approval_path = self.approval(run)
        approval = p.load(approval_path)
        approval['approved_ids'] = []
        p.save(approval_path, approval)
        output = self.root / 'noop.patch'
        self.cli('patch', '--run', str(run), '--approval', str(approval_path), '--version', 'ignored', '--out', str(output))
        self.assertEqual(output.read_bytes(), b'')


if __name__ == '__main__':
    unittest.main()

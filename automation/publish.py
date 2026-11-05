"""Collect fresh source evidence and atomically publish a complete schema-1 list."""
from __future__ import annotations

import argparse
import base64
from collections import Counter
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import re
import stat
import sys
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, build_opener

from . import pipeline as p

PATHS = ('keywords/politics.json', 'extension/keywords.json')


class GitHub:
    """No credential helper, subprocess, redirects, or automatic write retries."""
    def __init__(self, repository, branch, token=None):
        if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository):
            raise ValueError('invalid repository')
        if not re.fullmatch(r'[A-Za-z0-9_./-]+', branch) or '..' in branch:
            raise ValueError('invalid branch')
        self.prefix = 'https://api.github.com/repos/' + repository
        self.branch = branch
        self.token = token
        self.opener = build_opener(p.NoRedirect())

    def request(self, method, path, payload=None):
        headers = {'Accept': 'application/vnd.github+json', 'User-Agent': 'NOpartisan-publisher/1.0',
                   'X-GitHub-Api-Version': '2026-03-10', 'Accept-Encoding': 'identity'}
        if self.token:
            headers['Authorization'] = 'Bearer ' + self.token
        elif method != 'GET':
            raise ValueError('GitHub write token required')
        if payload is not None:
            headers['Content-Type'] = 'application/json'
        request = Request(self.prefix + path, method=method, headers=headers,
                          data=None if payload is None else p.encode(payload))
        try:
            with self.opener.open(request, timeout=20) as response:
                raw = response.read(p.MAX_SOURCE + 1)
                if len(raw) > p.MAX_SOURCE:
                    raise ValueError('GitHub response exceeds 2 MB')
                return json.loads(raw)
        except HTTPError as exc:
            # Never log headers, request payloads, tokens, or raw server bodies.
            raise ValueError(f'GitHub {method} {path.split("?")[0]} returned HTTP {exc.code}; '
                             'check authentication, permissions, branch rules, rate limits, or concurrent updates') from None

    def head(self):
        return self.request('GET', '/git/ref/heads/' + quote(self.branch, safe=''))['object']['sha']

    def file(self, path, commit):
        data = self.request('GET', '/contents/' + path + '?ref=' + commit)
        if data.get('encoding') != 'base64' or data.get('size', p.MAX_LIST + 1) > p.MAX_LIST:
            raise ValueError('invalid or oversized GitHub keyword file')
        raw = base64.b64decode(''.join(data['content'].split()), validate=True)
        if len(raw) > p.MAX_LIST:
            raise ValueError('GitHub keyword file exceeds 1 MB')
        return raw

    def baseline(self):
        head = self.head()
        commit = self.request('GET', '/git/commits/' + head)
        canonical, bundled = (self.file(path, head) for path in PATHS)
        if canonical != bundled:
            raise ValueError('remote canonical and bundled keyword files differ')
        p.validate_list(json.loads(canonical))
        return head, commit['tree']['sha'], canonical

    def publish(self, head, tree, raw, message, checkpoint):
        p.validate_list(json.loads(raw))
        if self.head() != head:
            raise ValueError('GitHub branch advanced; rerun from fresh baseline')
        # Use one tree and one commit, preserving ALL other repository files.
        created_tree = self.request('POST', '/git/trees', {
            'base_tree': tree,
            'tree': [{'path': path, 'mode': '100644', 'type': 'blob', 'content': raw.decode('utf-8')}
                     for path in PATHS],
        })['sha']
        commit = self.request('POST', '/git/commits', {
            'message': message, 'tree': created_tree, 'parents': [head],
        })['sha']
        checkpoint(commit)  # Durable intent before the single publication operation.
        # A racing main update is non-fast-forward from this single-parent commit.
        result = self.request('PATCH', '/git/refs/heads/' + quote(self.branch, safe=''),
                              {'sha': commit, 'force': False})
        if result['object']['sha'] != commit:
            raise ValueError('unexpected GitHub branch update response')
        # Read back both committed files before reporting success.
        for path in PATHS:
            if self.file(path, commit) != raw:
                raise ValueError('GitHub committed keyword verification failed')
        return commit


def token_from_file(path):
    path = Path(path)
    if path.resolve().is_relative_to(p.ROOT.resolve()):
        raise ValueError('credential must be outside the repository/image code')
    metadata = path.stat()
    # systemd may expose its isolated, read-only credentials as root-owned 0440.
    # Ordinary operator files must still be private; never relax their permissions.
    managed_directory = os.environ.get('CREDENTIALS_DIRECTORY')
    managed = (managed_directory and path.parent == Path(managed_directory)
               and str(path).startswith('/run/credentials/') and metadata.st_uid == 0
               and stat.S_IMODE(metadata.st_mode) == 0o440)
    if not stat.S_ISREG(metadata.st_mode) or (metadata.st_mode & 0o077 and not managed):
        raise ValueError('credential must be a regular private file (0600/0400) or isolated systemd credential')
    if metadata.st_uid not in (0, os.getuid()):
        raise ValueError('credential file has unexpected owner')
    token = p.read_bytes(path, 4096).decode('ascii').strip()
    if not token or any(c.isspace() or ord(c) < 33 for c in token):
        raise ValueError('invalid credential file')
    return token


def collect(cfg, folder):
    """All configured sources must succeed. Never reuse an import/cache on failure."""
    if cfg.get('policy_version') == 2:
        from . import expanded
        return expanded.collect(cfg, folder)
    fetcher, directories, feeds, sources = p.Fetcher(), {}, [], []
    for source in cfg['sources']:
        record = {**source, 'fetched_at': p.now()}
        try:
            raw = fetcher.get(source['url'])
            parsed = p.parse_source(source, raw)
            if not parsed:
                raise ValueError('empty source')
            if source['kind'] != 'feed':
                if not cfg['minimum_records'] <= len(parsed) <= cfg['maximum_records']:
                    raise ValueError('directory size outside configured safety bounds')
                directories[source['kind']] = parsed
            else:
                feeds.extend((item, source['name']) for item in parsed)
            (folder / (source['id'] + '.body')).write_bytes(raw)
            record.update(status='ok', sha256=p.digest(raw), bytes=len(raw), records=len(parsed))
        except Exception:
            record['status'] = 'failed'
            raise
        finally:
            sources.append(record)
            p.save(folder / 'sources.json', sources)
    official = directories['senate_xml']
    corroborating = directories['legislators_csv']
    def index(records):
        result = {}
        for person in records:
            if not re.fullmatch('[A-Z][0-9]{6}', person['identifier']):
                raise ValueError('invalid bioguide identifier')
            if person['identifier'] in result:
                raise ValueError('duplicate political identity in directory')
            result[person['identifier']] = person
        return result
    official_by_id, other_by_id = index(official), index(corroborating)
    # Matching complete identity sets protects against partial well-formed responses.
    if official_by_id.keys() != other_by_id.keys():
        raise ValueError('directory membership sets disagree; retaining published list')
    candidates, names = [], set()
    for identifier, person in sorted(official_by_id.items()):
        other = other_by_id[identifier]
        if any(person[k] != other[k] for k in ('affiliation', 'state')):
            raise ValueError('directory affiliation/state disagreement for ' + identifier)
        # Official first_name sometimes includes a suffix (e.g. "Angus S., Jr.").
        # Use the CSV's literal full_name field; require the same complete name
        # tokens as the official first/last fields, allowing suffix placement.
        # Do not manufacture aliases by dropping initials or guessing nicknames.
        def name_tokens(value):
            return Counter(re.findall(r'[^\W_]+', p.normalize(value)))
        if name_tokens(person['phrase']) != name_tokens(other['phrase']):
            raise ValueError('directory full name disagreement for ' + identifier)
        phrase = p.normalize(other['phrase'])
        reason = p.blocked_reason(phrase)
        if reason:
            raise ValueError('invalid directory phrase: ' + reason)
        if phrase in names:
            raise ValueError('ambiguous duplicate full name across political identities')
        names.add(phrase)
        candidates.append({
            'phrase': phrase, 'identifier': identifier, 'affiliation': person['affiliation'],
            'state': person['state'], 'official_url': person['official_url'],
            'evidence': 'Official Senate membership corroborated by identity, full name tokens, state and affiliation.',
            'phrase_source': 'legislators_csv full_name; normalized literally',
            'source_ids': [s['id'] for s in cfg['sources'] if s['kind'] != 'feed'],
            'news_mentions': [{'source_name': name, 'article_url': item['url'],
                               'context': 'Directory full name occurs in feed title.'}
                              for item, name in feeds if p.contains(item['title'], phrase)][:3],
            'ambiguity_concerns': ['Namesakes and nonpolitical mentions remain possible.'],
        })
    if not candidates:
        raise ValueError('empty validated collection')
    p.save(folder / 'collected.json', candidates)
    return candidates


def merge(base_raw, candidates):
    base = p.validate_list(json.loads(base_raw))
    if not candidates:
        raise ValueError('empty collection cannot publish')
    existing = {p.normalize(word): word for word in reversed(base['keywords'])}
    merged = dict(existing)
    for candidate in candidates:
        phrase = p.normalize(candidate['phrase'])
        if candidate.get('category'):
            from .expanded import candidate_valid
            candidate_valid(candidate)
        elif p.blocked_reason(phrase):
            raise ValueError('invalid collection phrase')
        merged.setdefault(phrase, phrase)
    added = sorted(set(merged) - set(existing))
    if not added:
        return base_raw, []
    # Stable deterministic version: a date plus complete normalized-set digest.
    version = datetime.now(timezone.utc).strftime('%Y-%m-%d') + '.' + p.digest(p.encode(sorted(merged)))[:12]
    if version == base['version']:
        version += '.1'
    output = {'schemaVersion': 1, 'version': version, 'keywords': [merged[k] for k in sorted(merged)]}
    return p.encode(p.validate_list(output)), added


def publishing_config(path):
    if p.load(path).get('policy_version') == 2:
        from . import expanded
        return expanded.config(path)
    cfg = p.config(path)
    if not (type(cfg.get('minimum_records')) is int and type(cfg.get('maximum_records')) is int
            and 1 <= cfg['minimum_records'] <= cfg['maximum_records'] <= 110):
        raise ValueError('invalid publishing collection bounds')
    kinds = [s['kind'] for s in cfg['sources']]
    if kinds.count('senate_xml') != 1 or kinds.count('legislators_csv') != 1:
        raise ValueError('publishing requires exactly one official Senate directory and one corroborating CSV')
    for source in cfg['sources']:
        if source.get('required') is not True:
            raise ValueError('all publishing sources must be required')
    # Constrain automatic inclusion to the reviewed source families.
    official = next(s for s in cfg['sources'] if s['kind'] == 'senate_xml')
    other = next(s for s in cfg['sources'] if s['kind'] == 'legislators_csv')
    if official['url'] != 'https://www.senate.gov/general/contact_information/senators_cfm.xml':
        raise ValueError('unapproved official publishing source')
    if other['url'] != 'https://raw.githubusercontent.com/unitedstates/congress-legislators/gh-pages/legislators-current.csv':
        raise ValueError('unapproved corroborating publishing source')
    return cfg


def run(args, api=None):
    cfg = publishing_config(args.config)
    data = Path(args.data)
    data.mkdir(parents=True, exist_ok=True)
    with (data / 'publish.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError('another publishing run holds the data-directory lock') from None
        folder = data / 'publishing' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        folder.mkdir(parents=True)
        result = {'started_at': p.now(), 'status': 'started', 'dry_run': args.dry_run,
                  'repository': cfg['repository'], 'branch': cfg['branch'], 'run': str(folder)}
        try:
            token = None if args.dry_run else token_from_file(args.token_file)
            api = api or GitHub(cfg['repository'], cfg['branch'], token)
            candidates = collect(cfg, folder)
            head, tree, base = api.baseline()
            (folder / 'previous.json').write_bytes(base)
            output, added = merge(base, candidates)
            (folder / 'complete-keywords.json').write_bytes(output)
            if cfg.get('policy_version') == 2:
                from .expanded import write_review
                result['review'] = write_review(base, candidates, folder)
            result.update(base_commit=head, added=len(added), collected=len(candidates),
                          affiliations=dict(Counter({c['identifier']:c['affiliation'] for c in candidates if c.get('affiliation')}.values())),
                          keywords=len(json.loads(output)['keywords']), version=json.loads(output)['version'],
                          sha256=p.digest(output))
            if getattr(args,'reviewed_sha256',None) and args.reviewed_sha256 != p.digest(output):
                raise ValueError('output differs from inspected categorized diff; review a fresh dry run')
            if not added:
                result['status'] = 'unchanged'
            elif args.dry_run:
                result['status'] = 'dry-run'
            else:
                def checkpoint(commit):
                    result.update(status='publishing', intended_commit=commit)
                    p.save(folder / 'result.json', result)
                commit = api.publish(head, tree, output,
                    f'Update political keywords ({len(added)} additions; schema 1)\n\n'
                    f'Automatic policy: {cfg["scope"]}.\nComplete list SHA-256: {p.digest(output)}', checkpoint)
                result.update(status='published', commit=commit)
        except Exception as exc:
            # Network timeouts after PATCH can have an uncertain result; intent
            # was saved so the next run can safely inspect/deduplicate remote state.
            result.update(status='failed', error=str(exc), finished_at=p.now())
            p.save(folder / 'result.json', result)
            raise
        result['finished_at'] = p.now()
        p.save(folder / 'result.json', result)
        # Only advance the local success pointer after verified success/no-op.
        if result['status'] in ('published', 'unchanged') and not args.dry_run:
            temporary = data / 'last-success.json.tmp'
            p.save(temporary, result)
            temporary.replace(data / 'last-success.json')
        print(json.dumps(result, indent=2))
        return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', default=str(p.ROOT / 'automation/publishing.json'))
    parser.add_argument('--data', default='/var/lib/nopartisan')
    parser.add_argument('--token-file', default='/etc/nopartisan/github-token')
    parser.add_argument('--dry-run', action='store_true', help='fresh collection and remote comparison, no GitHub writes')
    parser.add_argument('--reviewed-sha256', help='require the exact complete-list digest inspected in a dry run')
    args = parser.parse_args(argv)
    try:
        run(args)
        return 0
    except Exception as exc:
        print(f'Publishing failed: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())

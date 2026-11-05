"""Standard-library-only, manually invoked collection and reviewed patch CLI."""
from __future__ import annotations

import argparse
import csv
from datetime import date, datetime, timezone
import difflib
import hashlib
import io
import json
from pathlib import Path
import re
import sys
import time
import unicodedata
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
MAX_SOURCE = 2_000_000
MAX_LIST = 1_000_000
# ECMAScript \s (not Python's broader \s). NFKC precedes lowercase and folding.
SPACE = re.compile('[\u0009-\u000d\u0020\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000\ufeff]+')


def now():
    return datetime.now(timezone.utc).isoformat()


def normalize(value):
    return SPACE.sub(' ', unicodedata.normalize('NFKC', value).lower()).strip(' ')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def encode(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8')


def read_bytes(path, limit=MAX_SOURCE):
    with Path(path).open('rb') as stream:
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise ValueError(f'{path}: exceeds {limit} bytes')
    return raw


def load(path, limit=MAX_SOURCE):
    return json.loads(read_bytes(path, limit))


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(encode(value))


def new_artifact(path, raw):
    """Never overwrite a published list, approval, or report through --out."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(raw)


def phrase_valid(value):
    if not isinstance(value, str) or not normalize(value):
        raise ValueError('empty or non-string phrase')
    # JavaScript length counts UTF-16 code units.
    if len(value.encode('utf-16-le')) // 2 > 120:
        raise ValueError('phrase exceeds 120 UTF-16 units')
    if any(unicodedata.category(c) in ('Cc', 'Cs') for c in value):
        raise ValueError('control character or surrogate in phrase')


def validate_list(data):
    if (not isinstance(data, dict) or type(data.get('schemaVersion')) is not int
            or data['schemaVersion'] != 1 or not isinstance(data.get('version'), str)
            or len(data['version'].encode('utf-16-le')) // 2 > 100):
        raise ValueError('invalid schemaVersion/version')
    words = data.get('keywords')
    if not isinstance(words, list) or not 1 <= len(words) <= 10000:
        raise ValueError('expected 1–10,000 keywords')
    for word in words:
        phrase_valid(word)
        phrase_valid(normalize(word))
    if len(encode(data)) > MAX_LIST:
        raise ValueError('keyword download exceeds 1 MB')
    return data


def safe_url(value):
    if not isinstance(value, str) or any(ord(c) < 33 for c in value):
        raise ValueError('invalid URL')
    parsed = urlsplit(value)
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.username
            or parsed.password or parsed.fragment or parsed.port not in (None, 443)):
        raise ValueError('expected public HTTPS URL without credentials/fragment')
    # Config is trusted local input; never use feed links as download targets.
    import ipaddress
    try:
        address = ipaddress.ip_address(parsed.hostname)
    except ValueError:
        if parsed.hostname == 'localhost' or '.' not in parsed.hostname:
            raise ValueError('local hosts are not sources')
    else:
        if not address.is_global:
            raise ValueError('private IP is not a source')
    return value


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError(f'HTTP redirect refused ({code}); review configured URL')


class Fetcher:
    def __init__(self):
        self.last_request = 0.0
        self.opener = build_opener(NoRedirect())

    def get(self, url):
        safe_url(url)
        time.sleep(max(0, self.last_request + 1.0 - time.monotonic()))
        self.last_request = time.monotonic()
        request = Request(url, headers={
            'User-Agent': 'NOpartisan-review/0.1 (+https://github.com/ohlongshawnson/nopartisan)',
            'Accept-Encoding': 'identity',
        })
        started = time.monotonic()
        with self.opener.open(request, timeout=15) as response:
            if response.status != 200:
                raise ValueError(f'HTTP {response.status}')
            if response.headers.get('Content-Encoding', 'identity') != 'identity':
                raise ValueError('compressed responses refused')
            declared = response.headers.get('Content-Length')
            if declared and int(declared) > MAX_SOURCE:
                raise ValueError('source exceeds 2 MB')
            chunks, size = [], 0
            while True:
                chunk = response.read1(min(65536, MAX_SOURCE + 1 - size))
                size += len(chunk)
                if size > MAX_SOURCE:
                    raise ValueError('source exceeds 2 MB')
                if time.monotonic() - started > 30:
                    raise ValueError('source exceeded 30-second total read budget')
                if not chunk:
                    break
                chunks.append(chunk)
        return b''.join(chunks)


def config(path):
    cfg = load(path)
    if not isinstance(cfg, dict) or not isinstance(cfg.get('sources'), list) or not 1 <= len(cfg['sources']) <= 8:
        raise ValueError('config must contain 1–8 sources')
    ids = set()
    for source in cfg['sources']:
        if (not isinstance(source, dict) or not re.fullmatch('[a-z][a-z0-9_-]{0,39}', source.get('id', ''))
                or source['id'] in ids or source.get('kind') not in ('legislators_csv', 'senate_xml', 'feed')
                or not isinstance(source.get('name'), str) or not source['name']
                or type(source.get('required', False)) is not bool):
            raise ValueError('invalid/duplicate source configuration')
        safe_url(source['url'])
        if source.get('snapshot_date'):
            date.fromisoformat(source['snapshot_date'])
        ids.add(source['id'])
    return cfg


def xml(raw):
    # Decode UTF-8 strictly before checking declarations (reject UTF-16 tricks).
    text = raw.decode('utf-8-sig')
    if re.search(r'<!\s*(DOCTYPE|ENTITY)', text, re.I):
        raise ValueError('DTD/entities refused')
    return ET.fromstring(text)


def field(value, name, max_length=200):
    if not isinstance(value, str) or not value.strip() or len(value) > max_length:
        raise ValueError(f'invalid source field: {name}')
    if any(unicodedata.category(c) == 'Cc' for c in value):
        raise ValueError(f'control in source field: {name}')
    return value.strip()


def person(first, last, party, state, identifier, website, full=None):
    first, last = field(first, 'first'), field(last, 'last')
    phrase = field(full or f'{first} {last}', 'full name')
    phrase_valid(phrase)
    if not re.fullmatch('[A-Z]{2}', state or ''):
        raise ValueError('invalid state')
    party = field(party, 'party')
    website = safe_url(website)
    if not urlsplit(website).hostname.endswith('.senate.gov'):
        raise ValueError('Senate member URL is not official')
    return {'phrase': phrase, 'first': first, 'last': last,
            'affiliation': {'D': 'Democrat', 'R': 'Republican', 'I': 'Independent'}.get(party, party), 'state': state,
            'identifier': field(identifier, 'identifier'), 'official_url': website}


def parse_source(source, raw):
    if len(raw) > MAX_SOURCE:
        raise ValueError('source exceeds 2 MB')
    kind = source['kind']
    if kind == 'legislators_csv':
        reader = csv.DictReader(io.StringIO(raw.decode('utf-8-sig'), newline=''), strict=True)
        required = {'first_name', 'last_name', 'full_name', 'type', 'party', 'state', 'bioguide_id', 'url'}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError('missing legislator CSV columns')
        people = []
        for index, row in enumerate(reader):
            if index >= 1000 or None in row or any(v is None for v in row.values()):
                raise ValueError('malformed/oversized CSV')
            if row['type'] not in ('sen', 'rep'):
                raise ValueError('unknown legislator type')
            # Initial scope is the Senate. House rows are deliberately deferred.
            if row['type'] == 'sen':
                p = person(row['first_name'], row['last_name'], row['party'], row['state'],
                           row['bioguide_id'], row['url'], row['full_name'])
                if not re.fullmatch('[A-Z][0-9]{6}', p['identifier']):
                    raise ValueError('invalid bioguide ID')
                people.append(p)
        if not people:
            raise ValueError('empty Senate directory')
        return people
    root = xml(raw)
    if kind == 'senate_xml':
        if root.tag != 'contact_information':
            raise ValueError('unexpected Senate XML root')
        members = root.findall('member')
        if not 1 <= len(members) <= 110:
            raise ValueError('invalid Senate member count')
        return [person(m.findtext('first_name'), m.findtext('last_name'), m.findtext('party'),
                       m.findtext('state'), m.findtext('bioguide_id'), m.findtext('website')) for m in members]
    if root.tag == 'rss' and root.find('channel') is not None:
        entries = root.findall('channel/item')
        extract = lambda e: (e.findtext('title'), e.findtext('link'))
    elif root.tag == '{http://www.w3.org/2005/Atom}feed':
        ns = '{http://www.w3.org/2005/Atom}'
        entries = root.findall(ns + 'entry')
        def extract(e):
            links = [l.get('href') for l in e.findall(ns + 'link') if l.get('rel', 'alternate') == 'alternate']
            return e.findtext(ns + 'title'), links[0] if links else None
    else:
        raise ValueError('unexpected RSS/Atom root')
    if len(entries) > 500:
        raise ValueError('feed has more than 500 entries')
    result = []
    for entry in entries:
        title, link = extract(entry)
        result.append({'title': field(title, 'headline', 1000), 'url': safe_url(link)})
    return result


def blocked_reason(phrase, category='person'):
    try:
        phrase_valid(phrase)
        phrase_valid(normalize(phrase))
    except (ValueError, UnicodeError) as exc:
        return str(exc)
    tokens = normalize(phrase).split(' ')
    if category != 'person':
        return 'milestone 1 only accepts directory-backed full person names'
    if len(tokens) < 2 or not all(any(c.isalpha() for c in t) for t in tokens):
        return 'single names, generic terms, and non-name tokens are excluded'
    if any(unicodedata.category(c) == 'Cf' for c in phrase):
        return 'invisible formatting characters require source correction'
    return None


def contains(text, phrase):
    text, phrase = normalize(text), normalize(phrase)
    def boundary(c):
        return c == '_' or unicodedata.category(c)[0] in ('L', 'N')
    start = 0
    while (index := text.find(phrase, start)) >= 0:
        end = index + len(phrase)
        if (index == 0 or not boundary(text[index - 1])) and (end == len(text) or not boundary(text[end])):
            return True
        start = index + 1
    return False


def import_source(args):
    cfg = config(args.config)
    source = next((s for s in cfg['sources'] if s['id'] == args.source), None)
    if source is None:
        raise ValueError('unknown source ID')
    raw = read_bytes(args.file)
    parse_source(source, raw)
    stamp = datetime.fromisoformat(args.fetched_at.replace('Z', '+00:00'))
    if stamp.tzinfo is None or stamp > datetime.now(timezone.utc):
        raise ValueError('fetched-at must be timezone-aware and not in the future')
    folder = Path(args.data) / 'imports'
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f'{source["id"]}.body').write_bytes(raw)
    save(folder / f'{source["id"]}.json', {
        'source_url': source['url'], 'source_name': source['name'], 'sha256': digest(raw),
        'fetched_at': stamp.isoformat(), 'transport': args.transport,
        'note': 'Operator-supplied snapshot; hash verifies local integrity, not source authenticity.',
    })
    print(f'Imported {source["id"]}: {len(raw)} bytes, sha256={digest(raw)}')


def collect(args):
    cfg = config(args.config)
    base_raw = read_bytes(ROOT / 'keywords/politics.json', MAX_LIST)
    if base_raw != read_bytes(ROOT / 'extension/keywords.json', MAX_LIST):
        raise ValueError('canonical and bundled lists differ')
    base = validate_list(json.loads(base_raw))
    existing = {normalize(p) for p in base['keywords']}
    folder = Path(args.data) / 'runs' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    folder.mkdir(parents=True)
    sources, directories, feeds, exclusions = [], [], [], []
    fetcher, fatal = Fetcher(), False
    for source in cfg['sources']:
        record = dict(source)
        try:
            if args.imports_only:
                metadata = load(Path(args.data) / 'imports' / f'{source["id"]}.json')
                raw = read_bytes(Path(args.data) / 'imports' / f'{source["id"]}.body')
                if metadata['source_url'] != source['url'] or metadata['sha256'] != digest(raw):
                    raise ValueError('snapshot URL/hash mismatch')
                record.update(metadata)
            else:
                raw = fetcher.get(source['url'])
                record.update(fetched_at=now(), transport='direct HTTPS', sha256=digest(raw))
            parsed = parse_source(source, raw)
            (folder / f'{source["id"]}.body').write_bytes(raw)
            record.update(status='ok', records=len(parsed), bytes=len(raw))
            target = feeds if source['kind'] == 'feed' else directories
            target.extend((item, record) for item in parsed)
        except (ValueError, KeyError, TypeError, OSError, URLError, ET.ParseError, csv.Error) as exc:
            record.update(status='error', error=str(exc))
            fatal |= source.get('required', False)
            print(f'{source["id"]}: {exc}', file=sys.stderr)
        sources.append(record)
    people, duplicate_count = {}, 0
    for p, source in directories:
        phrase = normalize(p['phrase'])
        reason = blocked_reason(p['phrase'])
        if reason or phrase in existing:
            exclusions.append({'phrase': p['phrase'], 'reason': reason or 'already published'})
            continue
        if phrase in people:
            duplicate_count += 1
            people[phrase]['provenance'].append({'source_url': source['url'], 'source_name': source['name'],
                                                  'fetched_at': source['fetched_at'], 'sha256': source['sha256']})
            if people[phrase]['affiliation'] != p['affiliation']:
                people[phrase]['ambiguity_concerns'].append('Sources disagree on affiliation; resolve before approval.')
            if people[phrase]['identifier'] != p['identifier']:
                people[phrase]['ambiguity_concerns'].append('Sources identify different people with the same name; resolve before approval.')
            continue
        concerns = ['Full names can identify other people; inspect representative matches before approval.',
                    'Directory membership does not make every mention political; personal/nonpolitical posts may be hidden.']
        if not contains(p['phrase'], p['first']) or not contains(p['phrase'], p['last']):
            concerns.append('Directory display name differs from first/last fields; verify preferred name.')
        if source['kind'] == 'legislators_csv':
            concerns.append('Community-maintained snapshot; confirm current office/name using official directory or member website.')
        if source.get('snapshot_date') and (date.today() - date.fromisoformat(source['snapshot_date'])).days > 30:
            concerns.append('Snapshot is over 30 days old; verify membership and affiliation as of review.')
        people[phrase] = {
            'id': digest(phrase.encode())[:16], 'proposed_phrase': p['phrase'], 'normalized_phrase': phrase,
            'category': 'person', 'source_url': source['url'], 'source_name': source['name'],
            'discovered_at': now(), 'affiliation': p['affiliation'], 'identifier': p['identifier'], 'official_url': p['official_url'],
            'evidence': f'Senate directory record {p["identifier"]}: {p["phrase"]}; {p["affiliation"]}; {p["state"]}.',
            'provenance': [{'source_url': source['url'], 'source_name': source['name'],
                            'fetched_at': source['fetched_at'], 'sha256': source['sha256']}],
            'ambiguity_concerns': concerns, 'review_status': 'pending',
            'proposal_reason': 'Full name in an in-scope federal political office directory; same rule for every affiliation.',
            'news_mentions': [],
        }
    # Feeds only corroborate already directory-backed names. No headline-only extraction.
    unmatched = 0
    for item, source in feeds:
        matched = False
        for phrase, candidate in people.items():
            if contains(item['title'], phrase):
                # No article text or full headline retained; linked evidence is enough.
                if len(candidate['news_mentions']) < 3:
                    candidate['news_mentions'].append({'source_name': source['name'], 'source_url': source['url'],
                                                       'article_url': item['url'], 'context': 'Full directory name occurs in feed title.'})
                matched = True
        unmatched += not matched
    # Alphabetic round-robin across ALL source affiliations; not a completeness/balance claim.
    groups = {}
    for phrase, candidate in sorted(people.items()):
        groups.setdefault(candidate['affiliation'], []).append(candidate)
    candidates = []
    while len(candidates) < args.limit and any(groups.values()):
        for affiliation in sorted(groups):
            if groups[affiliation] and len(candidates) < args.limit:
                candidates.append(groups[affiliation].pop(0))
    deferred = [c for group in groups.values() for c in group]
    result = {
        'scope': cfg.get('scope'), 'created_at': now(), 'base_sha256': digest(base_raw),
        'base_version': base['version'], 'sources': sources, 'candidates': candidates,
        'exclusions': exclusions, 'deferred': [{'phrase': c['proposed_phrase'], 'reason': 'batch limit'} for c in deferred],
        'summary': {'candidates': len(candidates), 'directory_records': len(directories),
                    'duplicate_records': duplicate_count, 'excluded': len(exclusions), 'deferred': len(deferred),
                    'feed_entries': len(feeds), 'unmatched_feed_entries': unmatched,
                    'source_errors': sum(s['status'] == 'error' for s in sources), 'required_source_failed': fatal},
    }
    save(folder / 'candidates.json', result)
    report_hash = digest(read_bytes(folder / 'candidates.json'))
    save(folder / 'proposed-additions.json', {'status': 'UNAPPROVED — not an extension keyword list',
         'report_sha256': report_hash, 'additions': [{'id': c['id'], 'phrase': c['proposed_phrase']} for c in candidates]})
    lines = ['# NOpartisan candidate review', '', f'Scope: {result["scope"]}', '',
             'UNAPPROVED. Published lists are unchanged. Every candidate requires human review.', '',
             '## Collection', '', '```json', json.dumps(result['summary'], indent=2), '```', '']
    for source in sources:
        lines.extend([f'- {source["name"]}: {source["status"]}; {source["url"]}',
                      f'  {source.get("error", source.get("transport", ""))}'])
    lines.extend(['', '## Candidates', ''])
    for c in candidates:
        lines.extend([f'### {c["proposed_phrase"]} ({c["id"]})', '', c['evidence'], '',
                      f'Source: {c["source_url"]}', f'Official verification link (not fetched automatically): {c["official_url"]}',
                      f'Discovered: {c["discovered_at"]}; status: pending', '', c['proposal_reason'], '',
                      *('- ' + concern for concern in c['ambiguity_concerns']), ''])
    lines.extend(['## Exclusions and deferrals', '',
                  'House members are outside this initial Senate batch. Single names, surnames, generic words,',
                  'places, business/celebrity/journalist names without directory evidence, slogans and hashtags',
                  'are not extracted. Unmatched headlines never justify a block. No affiliation is excluded.', '',
                  'The alphabetic sample is a small review workload, not a measure of viewpoint coverage.',
                  'See candidates.json for every duplicate count, exclusion, deferred phrase and source hash.', ''])
    (folder / 'report.md').write_text('\n'.join(lines), encoding='utf-8')
    print(json.dumps({'run': str(folder), **result['summary']}, indent=2))
    return 2 if fatal or not candidates else 0


def approve(args):
    run = Path(args.run)
    raw = read_bytes(run / 'candidates.json')
    report = json.loads(raw)
    ids = args.ids.split(',')
    by_id = {c['id']: c for c in report['candidates']}
    if len(ids) != len(set(ids)) or not set(ids).issubset(by_id):
        raise ValueError('unknown/duplicate candidate IDs')
    if report['summary']['required_source_failed']:
        raise ValueError('required source failed; recollect before approval')
    if any(by_id[i]['ambiguity_concerns'] for i in ids) and not args.acknowledge_concerns:
        raise ValueError('review concerns, then explicitly pass --acknowledge-concerns')
    new_artifact(args.out, encode({'report_sha256': digest(raw), 'base_sha256': report['base_sha256'],
                    'approved_ids': ids, 'reviewer': field(args.reviewer, 'reviewer'),
                    'reason': field(args.reason, 'review reason', 1000), 'approved_at': now(),
                    'concerns_acknowledged': args.acknowledge_concerns}))
    print(f'Wrote local approval {args.out}; no keyword file modified.')


def generate_patch(args):
    raw = read_bytes(Path(args.run) / 'candidates.json')
    report, approval = json.loads(raw), load(args.approval)
    if approval['report_sha256'] != digest(raw) or approval['base_sha256'] != report['base_sha256']:
        raise ValueError('approval does not match report')
    field(approval['reviewer'], 'reviewer')
    field(approval['reason'], 'review reason', 1000)
    if report['summary']['required_source_failed']:
        raise ValueError('required source failed')
    old = read_bytes(ROOT / 'keywords/politics.json', MAX_LIST)
    if digest(old) != report['base_sha256'] or old != read_bytes(ROOT / 'extension/keywords.json', MAX_LIST):
        raise ValueError('published baseline changed or bundle differs; recollect and review again')
    data = validate_list(json.loads(old))
    by_id = {c['id']: c for c in report['candidates']}
    ids = approval['approved_ids']
    if not isinstance(ids, list) or len(ids) != len(set(ids)) or not set(ids).issubset(by_id):
        raise ValueError('unknown/duplicate approved IDs')
    seen = {normalize(k) for k in data['keywords']}
    for ident in ids:
        c = by_id[ident]
        if c['review_status'] != 'pending' or blocked_reason(c['proposed_phrase'], c['category']):
            raise ValueError('invalid candidate in approval')
        if c['ambiguity_concerns'] and approval.get('concerns_acknowledged') is not True:
            raise ValueError('candidate concerns not acknowledged')
        phrase = normalize(c['proposed_phrase'])
        if phrase not in seen:
            data['keywords'].append(c['proposed_phrase'])
            seen.add(phrase)
    if len(seen) == len({normalize(k) for k in json.loads(old)['keywords']}):
        patch = ''  # No keyword set change: do not change the version or formatting.
    else:
        if not args.version or args.version == data['version']:
            raise ValueError('changed keyword set requires a distinct --version')
        data['version'] = args.version
        new = encode(validate_list(data)).decode()
        patch = ''.join(''.join(difflib.unified_diff(old.decode().splitlines(True), new.splitlines(True),
                   fromfile='a/' + name, tofile='b/' + name)) for name in ('keywords/politics.json', 'extension/keywords.json'))
    new_artifact(args.out, patch.encode('utf-8'))
    print(f'Wrote {args.out}; {len(patch.encode())} bytes. Review and apply separately; no published file modified.')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', default=str(ROOT / 'automation/sources.json'))
    parser.add_argument('--data', default=str(Path.home() / 'nopartisan-data'))
    commands = parser.add_subparsers(dest='command', required=True)
    importer = commands.add_parser('import-source', help='validate a source fetched through another authorized transport')
    importer.add_argument('--source', required=True)
    importer.add_argument('--file', required=True)
    importer.add_argument('--fetched-at', required=True)
    importer.add_argument('--transport', required=True)
    importer.set_defaults(action=import_source)
    collector = commands.add_parser('collect')
    collector.add_argument('--imports-only', action='store_true')
    collector.add_argument('--limit', type=int, default=12, choices=range(1, 51), metavar='1..50')
    collector.set_defaults(action=collect)
    reviewer = commands.add_parser('approve')
    reviewer.add_argument('--run', required=True)
    reviewer.add_argument('--ids', required=True, help='comma-separated candidate IDs reviewed by a human')
    reviewer.add_argument('--reviewer', required=True)
    reviewer.add_argument('--reason', required=True)
    reviewer.add_argument('--acknowledge-concerns', action='store_true')
    reviewer.add_argument('--out', required=True)
    reviewer.set_defaults(action=approve)
    patcher = commands.add_parser('patch')
    patcher.add_argument('--run', required=True)
    patcher.add_argument('--approval', required=True)
    patcher.add_argument('--version')
    patcher.add_argument('--out', required=True)
    patcher.set_defaults(action=generate_patch)
    args = parser.parse_args(argv)
    try:
        return args.action(args) or 0
    except (ValueError, KeyError, TypeError, OSError, UnicodeError, ET.ParseError, csv.Error) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())

"""Check the local unsigned signing candidate without contacting Mozilla or reading credentials."""
from pathlib import Path
from zipfile import ZipFile
from html.parser import HTMLParser
from urllib.parse import unquote, urlsplit
import hashlib
import json
import re
import unicodedata

ROOT = Path(__file__).resolve().parents[1]
EXTENSION_ID = 'nopartisan@ohlongshawnson.github.io'
# Deliberately reviewed runtime files only. New assets must be reviewed before shipping.
RELEASE_FILES = {
    'Blue NOP Tech Logo.png', 'background.js', 'content.css', 'content.js', 'core.js',
    'foundational.json', 'inspection.css', 'inspection.html', 'inspection.js', 'keywords.json', 'manifest.json',
    'options.css', 'options.html', 'options.js', 'popup.css', 'popup.html', 'popup.js', 'x-adapter.js',
}

def require(condition, message):
    if not condition:
        raise SystemExit(f'Release check failed: {message}')

class References(HTMLParser):
    def handle_starttag(self, tag, attributes):
        attributes = dict(attributes)
        key = 'href' if tag == 'link' else 'src'
        if tag not in {'script', 'img', 'link'} or key not in attributes:
            return
        value = attributes[key]
        parsed = urlsplit(value)
        require(not parsed.scheme and not parsed.netloc, f'external runtime asset: {value}')
        require(unquote(parsed.path) in RELEASE_FILES, f'unknown HTML asset: {value}')

def main():
    manifest = json.loads((ROOT/'extension/manifest.json').read_text())
    package = json.loads((ROOT/'package.json').read_text())
    lock = json.loads((ROOT/'package-lock.json').read_text())
    version = manifest['version']
    require(re.fullmatch(r'\d+\.\d+\.\d+', version), 'expected a three-part numeric release version')
    require(package['version'] == lock['version'] == lock['packages']['']['version'] == version, 'version metadata differs')
    require(manifest['browser_specific_settings']['gecko']['id'] == EXTENSION_ID, 'permanent Firefox ID changed')
    require(manifest['browser_specific_settings']['gecko']['data_collection_permissions']['required'] == ['none'], 'review changed data collection')
    require(package['license'] == lock['packages']['']['license'] == 'MIT', 'MIT metadata differs')
    foundation = (ROOT/'keywords/foundational.json').read_bytes()
    require(foundation == (ROOT/'extension/foundational.json').read_bytes(), 'foundational copies differ')
    foundation_data = json.loads(foundation)
    require(foundation_data.get('schemaVersion') == 1 and isinstance(foundation_data.get('version'), str)
            and 0 < len(foundation_data['version']) <= 100 and isinstance(foundation_data.get('keywords'), list)
            and 0 < len(foundation_data['keywords']) <= 10000, 'foundational schema invalid')
    canonical = (ROOT/'keywords/politics.json').read_bytes()
    require(canonical == (ROOT/'extension/keywords.json').read_bytes(), 'published and bundled keyword files differ')
    data = json.loads(canonical)
    require(type(data['schemaVersion']) is int and data['schemaVersion'] == 1 and isinstance(data['version'], str) and len(data['version']) <= 100, 'keyword schema/version invalid')
    require(isinstance(data['keywords'], list) and 1 <= len(data['keywords']) <= 10000 and len(canonical) <= 1000000, 'keyword count/size invalid')
    for word in data['keywords']:
        require(isinstance(word, str) and word.strip() and len(word.encode('utf-16-le')) // 2 <= 120, 'invalid keyword phrase')
        require(not any(unicodedata.category(char) == 'Cc' for char in word), 'control character in keyword')
    require(set(foundation_data['keywords']).issubset(data['keywords']), 'feed omits foundational vocabulary')
    source_files = {path.relative_to(ROOT/'extension').as_posix() for path in (ROOT/'extension').rglob('*') if path.is_file()}
    require(source_files == RELEASE_FILES, f'unreviewed or missing runtime files: {source_files ^ RELEASE_FILES}')
    archive_path = ROOT/f'dist/nopartisan-{version}.zip'
    secret_patterns = [
        rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
        rb'\b(?:gh[pousr]_|github_pat_)[A-Za-z0-9_]{20,}',
        rb'\bAKIA[0-9A-Z]{16}\b',
    ]
    with ZipFile(archive_path) as archive:
        require(archive.testzip() is None, 'ZIP integrity error')
        expected = RELEASE_FILES | {'LICENSE'}
        require(set(archive.namelist()) == expected and len(archive.namelist()) == len(expected), 'ZIP includes extra/missing/duplicate entries')
        for name in sorted(expected):
            path = ROOT/'LICENSE' if name == 'LICENSE' else ROOT/'extension'/name
            require(not path.is_symlink(), f'symlink is not a reviewed runtime file: {name}')
            blob = archive.read(name)
            require(blob == path.read_bytes(), f'archive does not match source: {name}')
            require(not any(re.search(pattern, blob) for pattern in secret_patterns), f'credential pattern in {name}')
            if name.endswith('.html'):
                References().feed(blob.decode('utf-8'))
    digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    archive_path.with_suffix('.zip.sha256').write_text(f'{digest}  {archive_path.name}\n')
    print(f'PASS {version}: permanent ID, metadata, schema 1, {len(data["keywords"])} synchronized keywords, exact runtime files, HTML assets, ZIP integrity, and credential-pattern checks')
    print(f'Package: {archive_path}')
    print(f'SHA-256: {digest}')

if __name__ == '__main__':
    main()

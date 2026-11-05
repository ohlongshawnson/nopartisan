"""Create a reproducible unsigned archive. Firefox release installation needs signing."""
from pathlib import Path
import json
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED
root = Path(__file__).resolve().parents[1]
assert (root/'keywords/politics.json').read_bytes() == (root/'extension/keywords.json').read_bytes(), 'Bundled keyword list differs from canonical list'
version = json.loads((root/'extension/manifest.json').read_text())['version']
out = root/f'dist/nopartisan-{version}.zip'
out.parent.mkdir(exist_ok=True)
with ZipFile(out, 'w') as archive:
    for path in sorted((root/'extension').rglob('*')):
        if path.is_file():
            info = ZipInfo(path.relative_to(root/'extension').as_posix(), date_time=(2026,1,1,0,0,0))
            info.compress_type = ZIP_DEFLATED
            archive.writestr(info, path.read_bytes())
print(out)

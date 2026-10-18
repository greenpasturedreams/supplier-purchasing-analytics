"""Create an upload-ready ZIP, excluding the generated local database/runtime files."""
from pathlib import Path
import json
import re
import zipfile

ROOT=Path(__file__).resolve().parents[1]


def main():
    audit=json.loads((ROOT/'reports'/'validation.json').read_text())
    assert audit['all_checks_passed']
    for doc in [ROOT/'README.md',*(ROOT/'docs').glob('*.md')]:
        for link in re.findall(r'\]\(([^)]+)\)',doc.read_text(encoding='utf-8')):
            if link.startswith(('https:','http:','#')):
                continue
            target=doc.parent/link.split('#')[0]
            assert target.exists(),f'Broken local link: {doc.name}: {link}'
    files=[ROOT/name for name in ['.gitignore','README.md','requirements.txt','run_project.py']]
    for name in ['data/raw','data/processed','docs','sql','src','tests','reports']:
        files.extend(p for p in (ROOT/name).rglob('*') if p.is_file()
                     and '__pycache__' not in p.parts and p.suffix!='.pyc' and p.name!='qa_montage.png')
    assert len(files)==len(set(files))
    assert max(p.stat().st_size for p in files)<25*1024*1024, 'A file exceeds the browser-upload size target'
    archive=ROOT.parent/'supplier_purchasing_analytics.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as handle:
        for path in sorted(files):
            handle.write(path,path.relative_to(ROOT))
    with zipfile.ZipFile(archive) as handle:
        assert handle.testzip() is None
        assert 'README.md' in handle.namelist()
        assert not any(name.endswith('.db') for name in handle.namelist())
    print(f'Packaged {len(files)} files; {archive.stat().st_size/1024/1024:.1f} MiB. Local links and ZIP integrity verified.')


if __name__=='__main__':
    main()

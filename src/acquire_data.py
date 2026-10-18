"""Acquire publisher-hosted BPI 2019 XES and verify the original XML checksum."""
from pathlib import Path
import argparse
import gzip
import hashlib
import json
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
META_URL = 'https://data.4tu.nl/v2/articles/35ed7122-966a-484e-a0e1-749b64e3366d'
GZIP_URL = 'https://icpmconference.org/2019/wp-content/uploads/sites/6/2019/01/log_IEEE.xes_.gz'
EXPECTED_MD5 = '4eb909242351193a61e1c15b9c3cc814'


def digest(path, compressed=False):
    h = hashlib.md5()
    opener = gzip.open if compressed else open
    total = 0
    with opener(path, 'rb') as handle:
        for block in iter(lambda: handle.read(1024*1024), b''):
            h.update(block)
            total += len(block)
    return h.hexdigest(), total


def download(url, path):
    request = urllib.request.Request(url, headers={'User-Agent':'BPI2019-Portfolio/1.0'})
    with urllib.request.urlopen(request, timeout=90) as src, path.open('wb') as dst:
        for block in iter(lambda: src.read(1024*1024), b''):
            dst.write(block)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--download', action='store_true', help='Explicitly allow network acquisition if source is absent')
    args = parser.parse_args()
    raw = ROOT/'data'/'raw'
    raw.mkdir(parents=True, exist_ok=True)
    path = raw/'BPI_Challenge_2019.xes.gz'
    if not path.exists():
        if not args.download:
            raise SystemExit('Source absent. Run: python src/acquire_data.py --download')
        download(META_URL, raw/'publisher_metadata.json')
        download(GZIP_URL, path)
    checksum, size = digest(path, compressed=True)
    if checksum != EXPECTED_MD5:
        raise ValueError(f'XML MD5 mismatch: {checksum}. Do not analyze an unverified source.')
    metadata = json.loads((raw/'publisher_metadata.json').read_text(encoding='utf-8'))
    assert metadata['files'][0]['computed_md5'] == checksum
    manifest = {
        'dataset':'BPI Challenge 2019', 'doi':metadata['doi'],
        'publisher_metadata_url':META_URL, 'download_url':GZIP_URL,
        'compressed_bytes':path.stat().st_size, 'xml_bytes':size, 'xml_md5':checksum,
        'compressed_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
        'license':metadata['license'], 'source_verified':True,
    }
    (raw/'source_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(manifest,indent=2))


if __name__=='__main__':
    main()

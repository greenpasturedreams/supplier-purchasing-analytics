"""Rebuild the complete project locally; network is opt-in with --download."""
from pathlib import Path
import argparse
import subprocess
import sys

ROOT=Path(__file__).resolve().parent


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--download',action='store_true',help='Download publisher source if absent')
    parser.add_argument('--skip-import',action='store_true',help='Reuse existing raw SQLite tables for SQL/report iteration')
    args=parser.parse_args()
    acquisition=[sys.executable,str(ROOT/'src'/'acquire_data.py')]
    if args.download:
        acquisition.append('--download')
    subprocess.run(acquisition,check=True,cwd=ROOT)
    scripts=[] if args.skip_import else ['import_xes.py','profile_source.py']
    for script in scripts+['build_analysis.py','eda.py','write_readme.py']:
        subprocess.run([sys.executable,str(ROOT/'src'/script)],check=True,cwd=ROOT)
    subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-v'],check=True,cwd=ROOT)


if __name__=='__main__':
    main()

#!/usr/bin/env python3
"""Assemble une bibliothèque d'essai à partir de content-fr/, puis l'indexe.

  python3 content-fr/build.py [--out /chemin/vers/lastbook-fr]

Lit content-fr/manifests/*.json (chemins relatifs à content-fr/) et
content-fr/topics/*.json, copie les documents dans <out>/library-data/, écrit les
manifestes avec des chemins relatifs à library-data/, puis appelle
engine/library.py build pour produire catalog.json et search.sqlite.

Vérifie ensuite content-fr/topics/*.json avec tools/validate_topics.py.
"""
import argparse, json, shutil, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', default='/Volumes/EXTRADATA/RELIQUE/library-fr')
    a = ap.parse_args()
    out = Path(a.out)
    lib = out / 'library-data'
    shutil.rmtree(out, ignore_errors=True)
    (lib / 'manifests').mkdir(parents=True)
    (lib / 'documents').mkdir(parents=True, exist_ok=True)

    docs = HERE / 'documents'
    for f in sorted(docs.iterdir()):
        if f.is_file() and not f.name.startswith('._'):
            shutil.copy2(f, lib / 'documents' / f.name)

    records = []
    for m in sorted((HERE / 'manifests').glob('*.json')):
        if m.name.startswith('._'):
            continue
        for r in json.loads(m.read_text(encoding='utf-8')):
            src = HERE / r['path']
            if not src.is_file():
                sys.exit(f'manquant: {src}')
            r = dict(r)
            r['path'] = 'documents/' + src.name
            records.append(r)
    (lib / 'manifests' / 'content-fr.json').write_text(
        json.dumps(records, indent=1, ensure_ascii=False), encoding='utf-8')

    env = dict(**__import__('os').environ, LASTBOOK_LIBRARY=str(lib))
    subprocess.run([sys.executable, str(REPO / 'engine/library.py'), 'build'],
                   env=env, check=True)

    subprocess.run([sys.executable, str(REPO / 'tools/validate_topics.py'),
                    '--data', str(out)] + [str(p) for p in sorted((HERE / 'topics').glob('*.json'))],
                   check=True)
    print(f'\nbibliothèque prête: {lib}  ({len(records)} documents)')


if __name__ == '__main__':
    main()

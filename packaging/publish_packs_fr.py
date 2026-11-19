#!/usr/bin/env python3
"""Écrit le manifeste des packs RELIQUE (départements) et le SHA256SUMS.txt.

  RELIQUE_DOWNLOAD_HOST=downloads.relique.fr python3 packaging/publish_packs_fr.py

Lit chaque `FR-*/manifest-fragment.json`, remplace l'hôte d'origine des fichiers par
`--base` (ou `RELIQUE_DOWNLOAD_BASE`), recalcule taille et SHA-256 depuis le fichier
présent, puis écrit :

  <out>/manifest-v1.json   ce que `packaging/release_manifest.py --packs` consomme
  <out>/SHA256SUMS.txt     une ligne « <sha256>  <nom> » par archive, pour publication

Le manifeste passe `engine/setup/manifest.validate` si l'hôte est autorisé
(`RELIQUE_DOWNLOAD_HOST` pour l'hôte RELIQUE).
"""
import argparse, hashlib, json, os, sys, urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT)]


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def stamp(entry, folder, base):
    """(entry, [lignes de somme]) : URL réécrite, taille et SHA-256 relus depuis le fichier."""
    lines = []
    for f in entry.get('files') or []:
        src = folder / f['name']
        if not src.is_file():
            raise SystemExit(f'manquant: {src}')
        # on garde le dossier d'origine de l'URL (maps/ ou addresses/), on change l'hôte
        dossier = urllib.parse.urlsplit(f.get('url', '')).path.strip('/').split('/')[0] or 'maps'
        f['url'] = f'{base}/{dossier}/{f["name"]}'
        f['size'] = src.stat().st_size
        f['sha256'] = sha256(src)
        lines.append(f'{f["sha256"]}  {f["name"]}')
    return entry, lines


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--packs', default='/Volumes/EXTRADATA/RELIQUE/data/packs')
    ap.add_argument('--out', default='/Volumes/EXTRADATA/RELIQUE/data/release')
    ap.add_argument('--base', default=os.environ.get('RELIQUE_DOWNLOAD_BASE', 'https://downloads.relique.fr'))
    a = ap.parse_args()

    packs_root, out = Path(a.packs), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    packs, indexes, sums = [], [], []

    for folder in sorted(packs_root.glob('FR-*')):
        frag = folder / 'manifest-fragment.json'
        if not frag.is_file():
            print(f'  {folder.name}: pas de fragment, ignoré', flush=True)
            continue
        data = json.loads(frag.read_text(encoding='utf-8'))
        for m in data.get('maps') or []:
            m, lines = stamp(m, folder, a.base)
            packs.append(m); sums += lines
        for ai in data.get('address_indexes') or []:
            ai, lines = stamp(ai, folder, a.base)
            indexes.append(ai); sums += lines
        print(f'  {folder.name}: carte + adresses', flush=True)

    manifest = {'version': 1, 'published': None, 'packs': packs,
                'maps': [], 'address_indexes': indexes}
    (out / 'manifest-v1.json').write_text(json.dumps(manifest, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
    (out / 'SHA256SUMS.txt').write_text('\n'.join(sums) + '\n', encoding='utf-8')

    # l'hôte doit être en place AVANT l'import : ALLOWED_HOSTS se construit au chargement
    os.environ.setdefault('RELIQUE_DOWNLOAD_HOST', a.base.split('//', 1)[-1])
    from engine.setup import manifest as M
    ok = M.validate(json.loads((out / 'manifest-v1.json').read_text(encoding='utf-8'))) is not None
    print(f'\n{out / "manifest-v1.json"}: {len(packs)} cartes, {len(indexes)} index d’adresses, '
          f'{len(sums)} archives | validate: {"OK" if ok else "refusé"}')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())

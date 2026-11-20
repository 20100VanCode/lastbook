#!/usr/bin/env python3
"""Gardien du lot : remonte le disque externe et reprend au premier département non fait.

Le volume exFAT se démonte (câble, veille, pilote) et tue le lot en cours. Ce script
boucle : il vérifie le montage, attend la fin du lot, puis repart du premier département
dont le pack n'est pas complet — jusqu'aux 101.

  python3 tools/lot_watchdog.py --disk disk4s3 --mount /Volumes/EXTRADATA --root /Volumes/EXTRADATA/RELIQUE

Journal dans `<root>/data/lot-watchdog.log`.
"""
import argparse, json, subprocess, sys, time, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT)]
from engine.departements import DEPARTEMENTS                        # noqa: E402


def mounted(mountpoint: Path) -> bool:
    return mountpoint.is_dir() and any(mountpoint.iterdir())


def remount(disk: str, mountpoint: Path) -> bool:
    subprocess.run(['diskutil', 'mount', disk], capture_output=True)
    time.sleep(4)
    return mounted(mountpoint)


def complet(packs: Path, code: str) -> bool:
    """Le pack est-il écrit, complet, et porte-t-il la couche cultures ?"""
    d = packs / f'FR-{code}'
    if not d.is_dir():
        return False
    try:
        zips = [z for z in d.glob('*.zip')
                if not z.name.startswith('._') and z.stat().st_size >= 100_000]
    except OSError:
        return False
    if not zips or not (d / 'manifest-fragment.json').is_file():
        return False
    try:
        for z in zips:
            if any('crops' in n for n in zipfile.ZipFile(z).namelist()):
                return True
    except (OSError, KeyError, zipfile.BadZipFile):
        return False
    return False


def prochain(packs: Path):
    for entry in DEPARTEMENTS:
        code = entry[0]
        if not complet(packs, code):
            return code
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--disk', default='disk4s3')
    ap.add_argument('--mount', default='/Volumes/EXTRADATA')
    ap.add_argument('--root', default='/Volumes/EXTRADATA/RELIQUE')
    ap.add_argument('--repo', default=str(Path(__file__).resolve().parents[1]))
    a = ap.parse_args()
    root, mount = Path(a.root), Path(a.mount)
    packs = root / 'data' / 'packs'
    log = root / 'data' / 'lot-watchdog.log'
    env = dict(**__import__('os').environ)

    while True:
        if not mounted(mount):
            print(f'{time.strftime("%H:%M:%S")} disque démonté → remontage', flush=True)
            remount(a.disk, mount)
        if not mounted(mount):
            print(f'{time.strftime("%H:%M:%S")} remontage impossible, nouvel essai dans 30 s', flush=True)
            time.sleep(30)
            continue

        code = prochain(packs)
        if code is None:
            print(f'{time.strftime("%H:%M:%S")} les 101 packs sont complets', flush=True)
            return 0
        print(f'{time.strftime("%H:%M:%S")} reprise à {code}', flush=True)
        t0 = time.time()
        r = subprocess.run(
            [sys.executable, '-B', 'tools/build_all_fr.py', '--from', code,
             '--cache', str(root / 'data' / 'cache'), '--work', str(root / 'data' / 'work'),
             '--out', str(packs), '--ign', str(root / 'data' / 'ign')],
            cwd=a.repo, env=env,
            stdout=open(log, 'ab'), stderr=subprocess.STDOUT)
        dt = int(time.time() - t0)
        print(f'{time.strftime("%H:%M:%S")} lot arrêté (code {r.returncode}) après {dt} s', flush=True)
        time.sleep(10)


if __name__ == '__main__':
    sys.exit(main())

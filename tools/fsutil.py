#!/usr/bin/env python3
"""Recherche de fichiers insensible à la casse.

Les livraisons IGN mélangent les casses : la BD TOPO 2.2 délivre `.PRJ`/`.SHP`
en majuscules, la 3.5 un `.gpkg` en minuscules. Sur un volume sensible à la casse
(exFAT), `Path.rglob('*.prj')` ne trouve donc pas `.PRJ` — et l'étape échoue
« ni .gpkg ni .prj ». On passe par le nom, pas par le motif de pathlib.
"""
import fnmatch


def rglob_ci(src, pattern):
    """Itérateur des chemins de `src` dont le nom matche `pattern`, à la casse près."""
    pat = pattern.lower()
    for p in src.rglob('*'):
        if fnmatch.fnmatch(p.name.lower(), pat):
            yield p

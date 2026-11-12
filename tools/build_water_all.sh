#!/bin/zsh
# Waits for the NHD downloads to finish, then imports every state into derived/geo/water.sqlite.
self=${0:A}; cd "${self:h}/.." || exit 1
until grep -q "all finished" derived/geo/sources/nhd/fetch.log 2>/dev/null; do sleep 30; done
derived/buildenv/bin/python tools/build_water.py nhd && echo "$(date +%T) NHD import complete"

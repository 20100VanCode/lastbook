#!/bin/zsh
# Runs the elevation-tile build until it completes (it resumes where it stopped).
self=${0:A}; cd "${self:h}/.." || exit 1
for attempt in 1 2 3 4 5 6; do
  PYTHONWARNINGS=ignore derived/buildenv/bin/python tools/build_terrain.py --workers 24 && { echo "$(date +%T) terrain build complete"; exit 0 }
  echo "$(date +%T) build stopped (attempt $attempt), resuming"; sleep 5
done

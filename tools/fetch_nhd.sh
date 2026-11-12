#!/bin/zsh
# Downloads the USGS NHD (final 2023 snapshot) state GeoPackages listed in derived/geo/sources/nhd/files.txt,
# three at a time, California first then smallest first. Resumable: re-run to continue.
self=${0:A}
cd "${self:h}/../derived/geo/sources/nhd" || exit 1
fetch_one() {
  local size=$1 url=$2 f=${2:t}
  [[ -f $f && $(stat -f %z $f) == $size ]] && return 0
  for try in 1 2 3 4 5; do
    curl -s -L -C - --retry 5 --retry-delay 10 -o $f $url
    [[ $(stat -f %z $f 2>/dev/null) == $size ]] && { echo "$(date +%T) done $f"; return 0 }
    head -c 5 $f 2>/dev/null | grep -q '<?xml' && rm -f $f   # an error page, not data
    sleep 15
  done
  echo "$(date +%T) FAILED $f"
}
if [[ $1 == one ]]; then fetch_one $2 $3; exit; fi
xargs -P 3 -L 1 $self one < files.txt
echo "$(date +%T) all finished"

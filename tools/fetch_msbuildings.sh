#!/bin/zsh
# Downloads Microsoft Global ML Building Footprints for the US and territories (resumable).
#   tools/fetch_msbuildings.sh   -> derived/geo/sources/msbuildings/<Region>/<quadkey>.csv.gz
cd "${0:A:h}/../derived/geo/sources/msbuildings" || exit 1
curl -sSfL -o dataset-links.csv https://minedbuildings.z5.web.core.windows.net/global-buildings/dataset-links.csv || exit 1
grep -E '^(UnitedStates|PuertoRico|USVirginIslands|Guam|AmericanSamoa|NorthernMarianaIslands),' dataset-links.csv |
  awk -F, '{print $1 "/" $2 ".csv.gz " $3}' |
  xargs -P 6 -L 1 zsh -c 'f=$0; [[ -s $f ]] && exit 0; mkdir -p ${f:h}; curl -sSfL --retry 5 --retry-delay 3 -o $f.part "$1" && mv $f.part $f || echo "failed $f"'
echo "done: $(ls */*.csv.gz | wc -l) files"

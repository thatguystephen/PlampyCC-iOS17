#!/bin/sh
# Read-only screenshot measurement, not a rendering simulation.
set -eu
image=${1:?usage: sh tests/measure-flashlight-optics.sh IMG_1095.JPG}
sha256sum "$image"
magick identify "$image"
for fuzz in 5 10 15; do
    printf 'background fuzz=%s%%\n' "$fuzz"
    magick "$image" -crop 60x90+390+100 +repage -fuzz "$fuzz%" -trim -format 'flashlight %wx%h offset %X,%Y\n' info:
    magick "$image" -crop 95x90+95+100 +repage -fuzz "$fuzz%" -trim -format 'battery %wx%h offset %X,%Y\n' info:
    magick "$image" -crop 100x105+645+95 +repage -fuzz "$fuzz%" -trim -format 'power %wx%h offset %X,%Y\n' info:
    magick "$image" -crop 100x95+920+100 +repage -fuzz "$fuzz%" -trim -format 'vpn %wx%h offset %X,%Y\n' info:
done

#!/bin/bash
# Gives the Linux test distro a fresh start on the test host: pristine Ubuntu 24.04.5 (official WSL image, sha checked),
# plus a user "tester". Nothing else, so `apt install ./lastbook.deb` has to pull its own dependencies. Never packaged.
# Run from the Mac:  bash app/tests/linux_reset.sh            (only ever touches the distro called LastbookTest)
# Afterwards:        bash app/tests/linux_reset.sh tools      test tools (Xvfb, AT-SPI, tshark...) - after the .deb is in
set -e
HOST="${LASTBOOK_TEST_HOST:?Set LASTBOOK_TEST_HOST to your Windows SSH host}"; D=LastbookTest
IMG='C:\LastbookTest\image\ubuntu-24.04.5-wsl-amd64.wsl'; SHA=bb415d824822c4b878125729af451a5d18fb13d1cf5cbed9a7393ad64ac6039e
HERE="$(cd "$(dirname "$0")" && pwd)"
in_root() { ssh $HOST wsl -d $D -u root -- bash -s | tr -d '\000\r'; }

if [ "${1:-}" = tools ]; then
  in_root <<'EOF'
export DEBIAN_FRONTEND=noninteractive
echo "wireshark-common wireshark-common/install-setuid boolean false" | debconf-set-selections
apt-get install -y -qq xvfb x11-utils xdotool imagemagick at-spi2-core python3-pyatspi gir1.2-atspi-2.0 pulseaudio \
  pulseaudio-utils tcpdump tshark nftables iproute2 curl desktop-file-utils xdg-utils libglib2.0-bin procps psmisc jq >/dev/null 2>&1
apt-get clean; echo "tools in"
EOF
  COPYFILE_DISABLE=1 tar --no-xattrs -C "$HERE" -cf - $(cd "$HERE" && ls linux_*) 2>/dev/null | ssh $HOST 'mkdir -p /c/LastbookTest/bench && tar xf - -C /c/LastbookTest/bench'
  echo 'mkdir -p /opt/bench; cp /mnt/c/LastbookTest/bench/linux_* /opt/bench/; chmod +x /opt/bench/*; /opt/bench/linux_env.sh up' | in_root
  exit 0
fi

wsl_() { ssh $HOST "powershell -NoProfile -Command \"$*\"" | tr -d '\000\r'; }
got=$(wsl_ "(Get-FileHash '$IMG' -Algorithm SHA256).Hash.ToLower()")
[ "$got" = "$SHA" ] || { echo "image sha mismatch: $got"; exit 1; }
wsl_ "wsl -l -q" | grep -qx "$D" && wsl_ "wsl --unregister $D"
wsl_ "wsl --import $D C:\\LastbookTest\\distro '$IMG' --version 2"
in_root <<'EOF'
useradd -m -s /bin/bash -G sudo,audio,video tester
echo 'tester ALL=(ALL) NOPASSWD:ALL' > /etc/sudoers.d/tester
printf '[boot]\nsystemd=true\n[user]\ndefault=tester\n[interop]\nappendWindowsPath=false\n' > /etc/wsl.conf
apt-get update -qq
EOF
wsl_ "wsl --terminate $D"
echo "$D is fresh: $(echo 'lsb_release -ds; dpkg -l | grep -c ^ii' | in_root | tr '\n' ' ') packages"

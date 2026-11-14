#!/bin/bash
# Linux end-to-end steps for Lastbook, run from the Mac against the LastbookTest WSL2 distro on the test host. Never packaged.
#   bash app/tests/linux_e2e.sh STEP [args]     each step prints PASS/FAIL lines and leaves evidence in $EV (on the test host:
#                                               C:\LastbookTest\evidence\<run>, in the distro /mnt/c/LastbookTest/evidence/<run>)
# Order: reset -> install DEB -> tools -> up -> launch -> (drive setup with `at`) -> ... see the run notes.
# Settings to match the .deb (from linux-shell):
APP_CMD="${APP_CMD:-/opt/lastbook/lastbook.py}"          # what the launcher runs
APP_AT="${APP_AT:-lastbook}"            # AT-SPI application name (substring)
PKG="${PKG:-lastbook}"
RUNNER="${RUNNER:-lastbook-llm}"   # local AI runner process names (regex)
RUN_ID="${RUN_ID:-$(date +%Y%m%d-%H%M)}"
HOST="${LASTBOOK_TEST_HOST:?Set LASTBOOK_TEST_HOST to your Windows SSH host}"; D=LastbookTest
EVW="/mnt/c/LastbookTest/evidence/$RUN_ID"
HERE="$(cd "$(dirname "$0")" && pwd)"

root() { ssh $HOST wsl -d $D -u root -- bash -s | tr -d '\000\r' | grep -v 'This could be dangerous'; }
E=/opt/bench/linux_env.sh
AT="$E run python3 /opt/bench/linux_at.py $APP_AT"

step="$1"; shift
case "$step" in
reset) bash "$HERE/linux_reset.sh" ;;
install)   # $1 = .deb path on the Mac
  deb="$1"; name=$(basename "$deb")
  ssh $HOST "mkdir -p /c/LastbookTest/debs"; cat "$deb" | ssh $HOST "cat > /c/LastbookTest/debs/$name"
  root <<EOF
mkdir -p $EVW; cd /tmp; cp /mnt/c/LastbookTest/debs/$name /tmp/
sha256sum /tmp/$name | tee $EVW/deb.sha256
dpkg -l | awk '/^ii/{print \$2}' | sort > $EVW/pkgs-before.txt
DEBIAN_FRONTEND=noninteractive apt-get install -y /tmp/$name > $EVW/apt-install.log 2>&1; echo "apt exit \$?" | tee -a $EVW/apt-install.log
dpkg -l | awk '/^ii/{print \$2}' | sort > $EVW/pkgs-after.txt
echo "pulled in: \$(comm -13 $EVW/pkgs-before.txt $EVW/pkgs-after.txt | wc -l) packages"
dpkg -L $PKG > $EVW/deb-files.txt; grep -E '\.desktop$|/icons/' $EVW/deb-files.txt
for f in \$(grep -E '\.desktop$' $EVW/deb-files.txt); do desktop-file-validate "\$f" && echo "desktop file ok: \$f"; grep -E '^(Exec|Icon|Name|Categories)=' "\$f"; done
EOF
  ;;
tools) bash "$HERE/linux_reset.sh" tools ;;
launcher)   # icon resolves, Exec runs: start through the .desktop file like a launcher does
  root <<EOF
f=\$(dpkg -L $PKG | grep -E 'applications/.*\.desktop$' | head -1); icon=\$(grep -m1 '^Icon=' \$f | cut -d= -f2)
ls /usr/share/icons/hicolor/*/apps/\$icon.* /usr/share/pixmaps/\$icon.* 2>/dev/null | tee $EVW/icon-files.txt | head -3
[ -s $EVW/icon-files.txt ] && echo "PASS icon \$icon found" || echo "FAIL icon \$icon not in hicolor/pixmaps"
EOF
  ;;
start)      # start the app through its .desktop file (gio launch), inside the namespace; watchers on
  root <<EOF
mkdir -p $EVW; $E capture $EVW/net start
nohup /opt/bench/linux_net_watch.sh $EVW/net/ss.log >/dev/null 2>&1 &
f=\$(dpkg -L $PKG | grep -E 'applications/.*\.desktop$' | head -1)
$E run setsid gio launch \$f > $EVW/app-stdout.log 2>&1 &
sleep 8; pgrep -af "$APP_CMD|lastbook" | grep -v pgrep | head -5
EOF
  ;;
stop-watch)
  root <<EOF
touch $EVW/net/ss.log.stop; sleep 3; tail -1 $EVW/net/ss.log; $E capture $EVW/net stop
grep -E ' LISTEN ' $EVW/net/ss.log | head -5
EOF
  ;;
at)        echo "$AT $(printf '%q ' "$@")" | root ;;           # linux_e2e.sh at read | press "Small" | type "..." | wait "re" 60
shot)      echo "$E shot $EVW/${1:-shot}.png" | root ;;
sound)     echo "$E run bash /opt/bench/linux_sound.sh ${1:-8} $EVW/${2:-video}.wav" | root ;;
offline)   echo "$E offline" | root ;;
online)    echo "$E online" | root ;;
procs)     echo "pgrep -af '$APP_CMD|lastbook|$RUNNER' | grep -v pgrep || echo 'no app or runner process'" | root ;;
quit)      echo "pkill -TERM -f '$APP_CMD' ; sleep 5; pgrep -af '$APP_CMD|$RUNNER' | grep -v pgrep || echo 'PASS nothing left'" | root ;;
kill)      echo "pkill -KILL -f '$APP_CMD' ; sleep 5; pgrep -af '$APP_CMD|$RUNNER' | grep -v pgrep || echo 'PASS nothing left'" | root ;;
seed-model)  # the 17 GB Gemma file already on the test host, into the place setup looks for files ($1 = folder in the distro)
  echo "sudo -u tester mkdir -p '$1'; cp /mnt/c/LastbookTest/models/gemma-4-26B-A4B-it-UD-Q4_K_M.gguf '$1/' && chown tester '$1'/*.gguf && ls -la '$1'" | root ;;
uninstall)
  root <<EOF
du -sh /home/tester/.local/share/* /home/tester/LastbookData 2>/dev/null | tee $EVW/data-before-uninstall.txt
DEBIAN_FRONTEND=noninteractive apt-get remove -y $PKG > $EVW/apt-remove.log 2>&1; echo "remove exit \$?"
du -sh /home/tester/.local/share/* /home/tester/LastbookData 2>/dev/null | tee $EVW/data-after-uninstall.txt
diff $EVW/data-before-uninstall.txt $EVW/data-after-uninstall.txt && echo "PASS library untouched by remove"
EOF
  ;;
sh)        echo "$*" | root ;;
*) sed -n 2,12p "$0" ;;
esac

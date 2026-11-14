#!/bin/bash
# Logs every TCP/UDP socket in the app's network namespace every 2 s until OUT.stop appears. Never packaged. Run as root.
#   linux_net_watch.sh OUT_FILE        (touch OUT_FILE.stop to end it; prints a summary)
# Everything in namespace "lb" is the app and its children (linux_env.sh), so any LISTEN line is the app's.
OUT="$1"; : > "$OUT"; rm -f "$OUT.stop"
while [ ! -e "$OUT.stop" ]; do
  ip netns exec lb ss -tunapH 2>/dev/null | grep -v '^$' | sed "s/^/$(date +%T) /" >> "$OUT"
  sleep 2
done
listen=$(grep -cE ' (LISTEN|UNCONN) ' "$OUT")
peers=$(grep -vE ' (LISTEN|UNCONN) ' "$OUT" | awk '{print $7}' | sort -u | tr '\n' ' ')
echo "$(date +%T) watch ended; listening/unconnected sockets seen: $listen; peers: ${peers:-none}" | tee -a "$OUT"

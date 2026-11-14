#!/bin/bash
# Test bench for the Linux app inside the LastbookTest WSL2 distro. Never packaged. Run as root.
#
#   linux_env.sh up          headless X (:77), a null sound card, and network namespace "lb" (veth + NAT) for the app
#   linux_env.sh offline     cut the namespace off the internet (loopback only stays)
#   linux_env.sh online      give it back
#   linux_env.sh capture DIR start/stop  every packet in or out of the namespace -> DIR/egress.pcap, DNS and TLS names -> DIR/names.txt
#   linux_env.sh run CMD...  run CMD as tester inside the namespace on the headless display
#   linux_env.sh shot FILE   screenshot of the headless display
#
# Why a namespace: every WSL2 distro shares one kernel and network stack, so `ss` or tcpdump in the root namespace would
# also see other distros. In "lb" every socket and packet is the app's.
set -u
NS=lb; HOST_IF=lbh0; NS_IF=lbn0; NET=10.77.0
DISP=:77; U=tester; UID_=$(id -u $U)
RUN="/run/user/$UID_"; PULSE=/run/user/$UID_/lbpulse/native

up() {
  ip netns add $NS 2>/dev/null
  if ! ip link show $HOST_IF >/dev/null 2>&1; then
    ip link add $HOST_IF type veth peer name $NS_IF
    ip link set $NS_IF netns $NS
    ip addr add $NET.1/24 dev $HOST_IF; ip link set $HOST_IF up
    ip netns exec $NS ip addr add $NET.2/24 dev $NS_IF
    ip netns exec $NS ip link set $NS_IF up
    ip netns exec $NS ip link set lo up
  fi
  sysctl -qw net.ipv4.ip_forward=1
  nft delete table ip lbtest 2>/dev/null
  nft -f - <<EOF
table ip lbtest {
  chain post {
    type nat hook postrouting priority 100; policy accept;
    ip saddr $NET.0/24 oifname != "$HOST_IF" masquerade
  }
  set newconns { type ipv4_addr . inet_proto . inet_service; flags dynamic; size 65535; }
  chain fromapp {
    type filter hook forward priority -5; policy accept;
    iifname "$HOST_IF" ct state new update @newconns { ip daddr . meta l4proto . th dport }
  }
}
EOF
  # Docker in a sibling distro may set an iptables FORWARD drop policy; let the namespace through it.
  if nft list chain ip filter FORWARD >/dev/null 2>&1 && ! nft list chain ip filter FORWARD | grep -q $HOST_IF; then
    nft insert rule ip filter FORWARD iifname $HOST_IF accept; nft insert rule ip filter FORWARD oifname $HOST_IF accept
  fi
  mkdir -p /etc/netns/$NS; printf 'nameserver 1.1.1.1\nnameserver 8.8.8.8\n' > /etc/netns/$NS/resolv.conf
  online
  loginctl enable-linger $U; for i in $(seq 20); do [ -S $RUN/bus ] && break; sleep 0.5; done
  # WSLg bind-mounts its own read-only /tmp/.X11-unix; this distro gets a private one so Xvfb (and not the owner's screen) is used
  if mount | grep -q ' /tmp/.X11-unix '; then umount /tmp/.X11-unix 2>/dev/null || umount -l /tmp/.X11-unix; fi
  mkdir -p /tmp/.X11-unix; chmod 1777 /tmp/.X11-unix
  [ -S /tmp/.X11-unix/X${DISP#:} ] || pkill -f "Xvfb $DISP"
  pgrep -f "Xvfb $DISP" >/dev/null || { sudo -u $U setsid Xvfb $DISP -screen 0 1440x900x24 -nolisten tcp >/tmp/xvfb.log 2>&1 & sleep 1; }
  # sound: a private pulseaudio with a null sink whose monitor the tests record. Not WSLg's server: that one plays on the
  # owner's Windows speakers.
  if ! sudo -u $U PULSE_SERVER=unix:$PULSE pactl info >/dev/null 2>&1; then
    mkdir -p $(dirname $PULSE); chown $U $(dirname $PULSE)
    printf 'load-module module-native-protocol-unix socket=%s auth-anonymous=1\nload-module module-null-sink sink_name=lbsink\nset-default-sink lbsink\n' $PULSE > /tmp/lbpulse.pa
    sudo -u $U XDG_RUNTIME_DIR=$RUN setsid pulseaudio --daemonize=yes --exit-idle-time=-1 --use-pid-file=no --system=no -n -F /tmp/lbpulse.pa
    sleep 1
  fi
  echo "up: ns=$NS display=$DISP pulse=$PULSE"
}

online()  { ip netns exec $NS ip route replace default via $NET.1; echo online; }
offline() { ip netns exec $NS ip route del default 2>/dev/null; echo "offline (routes: $(ip netns exec $NS ip -br route | tr '\n' ' '))"; }

capture() {
  local dir="$1" what="$2"; mkdir -p "$dir"
  if [ "$what" = start ]; then
    nft flush set ip lbtest newconns
    setsid tcpdump --immediate-mode -s 256 -i $HOST_IF -U -Z root -w "$dir/egress.pcap" >"$dir/tcpdump.log" 2>&1 & echo $! > "$dir/.tcpdump.pid"; sleep 2
  else
    kill -INT "$(cat "$dir/.tcpdump.pid")" 2>/dev/null; sleep 2
    tshark -r "$dir/egress.pcap" -T fields -e frame.time -e ip.dst -e dns.qry.name -e tls.handshake.extensions_server_name \
      -Y 'dns.flags.response==0 || tls.handshake.type==1' 2>/dev/null > "$dir/names.txt"
    nft list set ip lbtest newconns | tr -d '\t' | grep -oE '[0-9.]+ \. (tcp|udp) \. [0-9a-z-]+' > "$dir/newconns.txt"
    echo "new connections (kernel, lossless): $(tr '\n' ',' < "$dir/newconns.txt")"
    tshark -r "$dir/egress.pcap" -q -z conv,ip 2>/dev/null > "$dir/conversations.txt"
    echo "names: $(cut -f3,4 "$dir/names.txt" | tr '\t' '\n' | grep . | sort -u | tr '\n' ' ')"
  fi
}

run() {
  # sudo -u keeps us in the namespace (ip netns exec runs first)
  ip netns exec $NS sudo -u $U env -i HOME=/home/$U USER=$U LOGNAME=$U PATH=/usr/local/bin:/usr/bin:/bin LANG=C.UTF-8 \
    DISPLAY=$DISP GDK_BACKEND=x11 XDG_RUNTIME_DIR=$RUN DBUS_SESSION_BUS_ADDRESS=unix:path=$RUN/bus \
    PULSE_SERVER=unix:$PULSE XDG_SESSION_TYPE=x11 XDG_CURRENT_DESKTOP=GNOME GTK_A11Y=atspi NO_AT_BRIDGE=0 \
    "$@"
}

shot() { DISPLAY=$DISP import -window root "$1" && echo "$1"; }

cmd="$1"; shift
case "$cmd" in up|online|offline|capture|run|shot) "$cmd" "$@";; *) sed -n 2,12p "$0"; exit 2;; esac

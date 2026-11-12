# Logs every process seen, so a process in the network trace that has since gone can still be named. Reads only.
import json, subprocess, sys, time
end = time.time() + float(sys.argv[2]); seen = {}
PS = "Get-CimInstance Win32_Process | Select ProcessId,ParentProcessId,Name,CommandLine | ConvertTo-Json -Compress"
while time.time() < end:
    o = subprocess.run(['powershell', '-NoProfile', '-Command', PS], capture_output=True, text=True, errors='replace').stdout
    try:
        for r in json.loads(o):
            k = r['ProcessId']
            if k not in seen: seen[k] = {'ppid': r['ParentProcessId'], 'name': r['Name'], 'cmd': (r['CommandLine'] or '')[:240], 't': round(time.time(), 1)}
    except Exception: pass
    json.dump(seen, open(sys.argv[1], 'w'), indent=0)
    time.sleep(0.5)

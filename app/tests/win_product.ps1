# The product as a person starts it, with no test code in the process: main.py --data <folder>. No debug port. Watches sockets, takes a window shot, closes the window.
param([string]$Run,[int]$Hold=45,[string]$TestArgs='')
$B='C:\Users\you\app-test\app-build'; $L="$B\logs\$Run"; $S="$B\src\app"; $Task='LastbookAppBuildRun'; $T2='LastbookAppBuildSession'
$pyw='C:\Users\you\app-test\python-pkg\tools\pythonw.exe'
New-Item -ItemType Directory -Force $L | Out-Null
$other=Get-CimInstance Win32_Process | ?{ $_.Name -like 'python*' -and $_.CommandLine -match 'app-build' }; if($other){ "ANOTHER RUN GOING"; exit 2 }
$data="$B\datalink"; if(-not (Test-Path $data)){ New-Item -ItemType Junction -Path $data -Target (Get-Item 'C:\Users\you\app-test\app-only-proof\data\L*').FullName | Out-Null }   # the real name has characters schtasks mangles
"data short path: $data"
$base=@{}; Get-NetTCPConnection -State Listen | %{ $base["$($_.LocalAddress):$($_.LocalPort)/$($_.OwningProcess)"]=1 }
$tr="$pyw -I -B -X utf8 $S\main.py --data $data"
if($TestArgs){ $tr="$pyw -I -B -X utf8 $S\tests\win_app.py --run $Run $TestArgs" }
schtasks /create /tn $Task /tr $tr /sc once /st 23:59 /it /f 2>&1 | Out-Null
$t0=Get-Date; schtasks /run /tn $Task 2>&1 | Out-Null
$p=$null; while(-not $p -and ((Get-Date)-$t0).TotalSeconds -lt 30){ $p=Get-CimInstance Win32_Process | ?{ $_.Name -eq 'pythonw.exe' -and $_.CommandLine -match 'app-build' } | Select -First 1; Start-Sleep -Milliseconds 100 }
schtasks /delete /tn $Task /f 2>&1 | Out-Null
if(-not $p){ "NO PROCESS"; exit 1 }
$apppid=[int]$p.ProcessId; $h=Get-Process -Id $apppid; $null=$h.Handle
"app pid $apppid session $($h.SessionId) cmd: $($p.CommandLine)"
$tot=@{listen=0;udp=0;est=0}; $rows=@{}; $newsys=@{}; $n=0; $peak=0; $peakT=0; $args0=$null
while(((Get-Date)-$t0).TotalSeconds -lt $Hold -and -not $h.HasExited){
  $all=Get-CimInstance Win32_Process | Select ProcessId,ParentProcessId,Name,CommandLine
  $tree=@($apppid); do{$c=$tree.Count;$tree=@($tree+($all|?{$tree -contains $_.ParentProcessId}|%{[int]$_.ProcessId}))|Select -Unique}while($tree.Count -gt $c)
  if(-not $args0){ $br=$all|?{$_.Name -eq 'msedgewebview2.exe' -and $_.CommandLine -notmatch '--type=' -and ($tree -contains [int]$_.ProcessId)}|Select -First 1; if($br){ $args0=$br.CommandLine } }
  netstat -ano | %{ $f=($_ -split '\s+')|?{$_}; if($f.Count -ge 4 -and $f[0] -in 'TCP','UDP' -and ($tree -contains [int]$f[-1])){ $rows[$_.Trim()]=1; if($_ -match 'LISTENING'){$tot.listen++} elseif($f[0] -eq 'UDP'){$tot.udp++} else {$tot.est++} } }
  Get-NetTCPConnection -State Listen | %{ $k="$($_.LocalAddress):$($_.LocalPort)/$($_.OwningProcess)"; if(-not $base[$k]){ $newsys[$k]=1 } }
  $mem=Get-Process -Id $tree -EA SilentlyContinue; $a=[math]::Round((Get-Process -Id $apppid).PrivateMemorySize64/1MB); $t=[math]::Round(($mem|Measure PrivateMemorySize64 -Sum).Sum/1MB); if($a -gt $peak){$peak=$a}; if($t -gt $peakT){$peakT=$t}
  $n++; Start-Sleep -Seconds 1
}
"samples=$n listen=$($tot.listen) udp=$($tot.udp) est=$($tot.est) new_system_listeners=$($newsys.Count) app=$peak tree=$peakT processes=$($tree.Count)"
"rows:"; $rows.Keys|Select -First 20
"new listeners:"; $newsys.Keys|Select -First 20
"webview browser cmd: "; $args0
$ps='C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe'
foreach($do in 'shot','close'){
  "`"$ps`" -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$S\tests\win_session.ps1`" -AppPid $apppid -Do $do -Out `"$L\$do`" > `"$L\$do.err`" 2>&1" | Out-File "$L\$do.cmd" -Encoding ascii
  schtasks /create /tn $T2 /tr "$L\$do.cmd" /sc once /st 23:59 /it /f 2>&1 | Out-Null
  schtasks /run /tn $T2 2>&1 | Out-Null; $t1=Get-Date; while(-not (Test-Path "$L\$do.txt") -and ((Get-Date)-$t1).TotalSeconds -lt 20){ Start-Sleep -Milliseconds 300 }
  schtasks /delete /tn $T2 /f 2>&1 | Out-Null; Get-Content "$L\$do.txt" -EA SilentlyContinue; Get-Content "$L\$do.err" -EA SilentlyContinue | Select -First 6
}
$t1=Get-Date; $null=$h.WaitForExit(20000); "exited=$($h.HasExited) after $([math]::Round(((Get-Date)-$t1).TotalSeconds,1))s exit code $(if($h.HasExited){$h.ExitCode})"
if(-not $h.HasExited){ "stopping my own PID $apppid"; Stop-Process -Id $apppid -Force }
Start-Sleep 3
"left: " + ((Get-CimInstance Win32_Process | ?{ $_.Name -in 'pythonw.exe','python.exe','msedgewebview2.exe' -and $_.CommandLine -match 'app-build|webview' -and $_.CommandLine -match 'app-test|derived.webview|LASTBO~' }) | %{ "$($_.ProcessId) $($_.Name)" }) -join ', '
"tasks: " + ((schtasks /query /fo csv 2>$null) -match 'Lastbook').Count
Get-Content ((Get-Item 'C:\Users\you\app-test\app-only-proof\data\L*').FullName + '\derived\logs\lastbook.log') -Tail 8

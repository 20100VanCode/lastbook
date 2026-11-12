# One run of the packaged Lastbook.exe in the logged-in desktop session, started through a scheduled task. Never packaged.
# The exe gets no test code. For DevTools runs the only addition is the runtime's own environment variable.
# -Cdp: drive it with win_driver.py, then close it. -Env: extra NAME=VALUE pairs. -Data 'none': start with no --data. -AppArgs: anything else.
param([string]$Run,[int]$Hold=45,[switch]$Cdp,[string]$Steps='',[int]$Limit=500,[string]$Data='',[string]$AppArgs='',[string[]]$Env=@(),[string]$Exe='C:\Users\you\app-test\app-build\dist\Lastbook\Lastbook.exe',[switch]$Shot,[switch]$NoClose,[int]$ExpectExit=-1)
$ErrorActionPreference='Continue'
$B='C:\Users\you\app-test\app-build'; $L="$B\logs\$Run"; $S="$B\src\app"; $Task='LastbookAppBuildRun'; $T2='LastbookAppBuildSession'
$py='C:\Users\you\app-test\python-pkg\tools\python.exe'; $ps='C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe'
New-Item -ItemType Directory -Force $L | Out-Null; Remove-Item "$L\*.txt" -EA SilentlyContinue
$other=Get-Process Lastbook -EA SilentlyContinue; if($other){ "ANOTHER RUN GOING: $($other.Id)"; exit 2 }
$real=(Get-Item 'C:\Users\you\app-test\app-only-proof\data\L*').FullName     # the real name has characters schtasks mangles, so a script reads it
if($Data -eq ''){ $dataArg=$real } elseif($Data -eq 'none'){ $dataArg=$null } else { $dataArg=$Data }
$browserArgs='--disable-features=ElasticOverscroll,msOneAuthWAM --disable-background-networking --disable-component-update --disable-domain-reliability --no-pings --host-resolver-rules="MAP * ~NOTFOUND" --webrtc-ip-handling-policy=disable_non_proxied_udp'
$envs=@('SURVIVAL_MODEL_BASE=http://127.0.0.1:1')+$Env   # never the real model's port
if($Cdp){ $envs+="WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS=$browserArgs --remote-debugging-port=8941" }
$la=@(); if($dataArg){ $la+="--data `"$dataArg`"" }; if($AppArgs){ $la+=$AppArgs }
$launch=@('$ErrorActionPreference="Stop"')
foreach($e in $envs){ $k,$v=$e -split '=',2; $launch+="`$env:$k=@'`n$v`n'@" }
$launch+="try { `$p=Start-Process -FilePath '$Exe' -ArgumentList @'`n$($la -join ' ')`n'@ -PassThru; `$p.Id | Out-File -Encoding ascii '$L\pid.txt' } catch { `$_ | Out-String | Out-File -Encoding utf8 '$L\launch-error.txt' }"
if(-not $la){ $launch[-1]="try { `$p=Start-Process -FilePath '$Exe' -PassThru; `$p.Id | Out-File -Encoding ascii '$L\pid.txt' } catch { `$_ | Out-String | Out-File -Encoding utf8 '$L\launch-error.txt' }" }
[IO.File]::WriteAllText("$L\launch.ps1",($launch -join "`r`n"),[Text.UTF8Encoding]::new($true))
"`"$ps`" -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$L\launch.ps1`" > `"$L\launch.err`" 2>&1" | Out-File "$L\launch.cmd" -Encoding ascii
$base=@{}; Get-NetTCPConnection -State Listen | %{ $base["$($_.LocalAddress):$($_.LocalPort)/$($_.OwningProcess)"]=1 }
$t0=Get-Date
schtasks /create /tn $Task /tr "$L\launch.cmd" /sc once /st 23:59 /it /f 2>&1 | Out-Null
schtasks /run /tn $Task 2>&1 | Out-Null
while(-not ((Test-Path "$L\pid.txt") -or (Test-Path "$L\launch-error.txt")) -and ((Get-Date)-$t0).TotalSeconds -lt 30){ Start-Sleep -Milliseconds 100 }
schtasks /delete /tn $Task /f 2>&1 | Out-Null
function CI { "code integrity events since start (3033 blocked, 3077 enforced block, 3076/3034 audit), for this build:"; $ev=Get-WinEvent -FilterHashtable @{LogName='Microsoft-Windows-CodeIntegrity/Operational';StartTime=$t0.AddSeconds(-2);Id=3033,3034,3076,3077} -EA SilentlyContinue; "  all such events on the machine: $(@($ev).Count)"; $ev | Select -First 8 | %{ "  $($_.TimeCreated.ToString('HH:mm:ss')) $($_.Id) " + $_.Message.Substring(0,[math]::Min(260,$_.Message.Length)) } }
if(Test-Path "$L\launch-error.txt"){ "LAUNCH FAILED:"; Get-Content "$L\launch-error.txt" | Select -First 12; CI; exit 1 }
if(-not (Test-Path "$L\pid.txt")){ "NO PID"; Get-Content "$L\launch.err" -EA SilentlyContinue | Select -First 8; CI; exit 1 }
Start-Sleep -Milliseconds 300
$apppid=[int](Get-Content "$L\pid.txt"); $h=Get-Process -Id $apppid -EA SilentlyContinue
if(-not $h){ "process $apppid already gone"; CI; exit 1 }
$null=$h.Handle
"exe pid $apppid session $($h.SessionId) path $($h.Path) started $($t0.ToString('HH:mm:ss')) user $((Get-CimInstance Win32_Process -Filter "ProcessId=$apppid" | Invoke-CimMethod -MethodName GetOwner).User)"
$drv=$null
if($Steps){ $drv=Start-Process -FilePath $py -ArgumentList '-I','-B','-X','utf8',"$S\tests\win_driver.py",$Run,$Steps -RedirectStandardOutput "$L\driver.out" -RedirectStandardError "$L\driver.err" -PassThru -WindowStyle Hidden }
$tot=@{listen=0;udp=0;est=0}; $rows=@{}; $newsys=@{}; $n=0; $peak=0; $peakT=0; $args0=$null; $w="$L\watch.jsonl"; $tree=@($apppid)
while(-not $h.HasExited -and (((Get-Date)-$t0).TotalSeconds -lt $Hold -or ($drv -and -not $drv.HasExited -and ((Get-Date)-$t0).TotalSeconds -lt $Limit))){
  $all=Get-CimInstance Win32_Process | Select ProcessId,ParentProcessId,Name,CommandLine
  $tree=@($apppid); do{$c=$tree.Count;$tree=@($tree+($all|?{$tree -contains $_.ParentProcessId}|%{[int]$_.ProcessId}))|Select -Unique}while($tree.Count -gt $c)
  if(-not $args0){ $br=$all|?{$_.Name -eq 'msedgewebview2.exe' -and $_.CommandLine -notmatch '--type=' -and ($tree -contains [int]$_.ProcessId)}|Select -First 1; if($br){ $args0=$br.CommandLine } }
  netstat -ano | %{ $f=($_ -split '\s+')|?{$_}; if($f.Count -ge 4 -and $f[0] -in 'TCP','UDP' -and ($tree -contains [int]$f[-1]) -and -not ($Cdp -and $_ -match ':8941\b')){ $rows[$_.Trim()]=1; if($_ -match 'LISTENING'){$tot.listen++} elseif($f[0] -eq 'UDP'){$tot.udp++} else {$tot.est++} } }
  Get-NetTCPConnection -State Listen | ?{ -not ($Cdp -and $_.LocalPort -eq 8941) } | %{ $k="$($_.LocalAddress):$($_.LocalPort)/$($_.OwningProcess)"; if(-not $base[$k]){ $newsys[$k]=1 } }
  $mem=Get-Process -Id $tree -EA SilentlyContinue; $me=Get-Process -Id $apppid -EA SilentlyContinue; $a=if($me){[math]::Round($me.PrivateMemorySize64/1MB)}else{0}; $t=[math]::Round(($mem|Measure PrivateMemorySize64 -Sum).Sum/1MB); if($a -gt $peak){$peak=$a}; if($t -gt $peakT){$peakT=$t}
  (@{t=[math]::Round(((Get-Date)-$t0).TotalSeconds,1);app=$a;tree=$t;n=$tree.Count}|ConvertTo-Json -Compress)|Out-File $w -Append -Encoding utf8
  $n++; Start-Sleep -Seconds 1
}
"samples=$n secs=$([math]::Round(((Get-Date)-$t0).TotalSeconds)) listen=$($tot.listen) udp=$($tot.udp) est=$($tot.est) new_system_listeners=$($newsys.Count) peak_app=$peak peak_tree=$peakT processes=$($tree.Count) exited=$($h.HasExited)"
"socket rows of the tree:"; $rows.Keys|Select -First 20
"new listeners on the machine:"; $newsys.Keys|Select -First 20
"webview browser command line: $args0"
if($drv -and -not $drv.HasExited){ "driver still going at limit: stopping my driver PID $($drv.Id)"; Stop-Process -Id $drv.Id -Force }
$dos=@(); if($Shot -and -not $h.HasExited){ $dos+='shot' }; if(-not $NoClose -and -not $h.HasExited){ $dos+='close' }
foreach($do in $dos){
  "`"$ps`" -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$S\tests\win_session.ps1`" -AppPid $apppid -Do $do -Out `"$L\$do`" > `"$L\$do.err`" 2>&1" | Out-File "$L\$do.cmd" -Encoding ascii
  schtasks /create /tn $T2 /tr "$L\$do.cmd" /sc once /st 23:59 /it /f 2>&1 | Out-Null
  schtasks /run /tn $T2 2>&1 | Out-Null; $t1=Get-Date; while(-not (Test-Path "$L\$do.txt") -and ((Get-Date)-$t1).TotalSeconds -lt 20){ Start-Sleep -Milliseconds 300 }
  schtasks /delete /tn $T2 /f 2>&1 | Out-Null; Get-Content "$L\$do.txt" -EA SilentlyContinue; Get-Content "$L\$do.err" -EA SilentlyContinue | Select -First 6
}
$t1=Get-Date; if(-not $NoClose){ $null=$h.WaitForExit(20000) }
"exited=$($h.HasExited) after $([math]::Round(((Get-Date)-$t1).TotalSeconds,1))s exit code $(if($h.HasExited){$h.ExitCode})"
if(-not $h.HasExited){ "stopping my own PID $apppid"; Stop-Process -Id $apppid -Force }
Start-Sleep 3
"left in the tree: " + ((Get-Process -Id $tree -EA SilentlyContinue | %{ "$($_.Id) $($_.Name)" }) -join ', ')
"tasks: " + ((schtasks /query /fo csv 2>$null) -match 'LastbookAppBuild').Count
CI
if($dataArg){ Get-Content ($dataArg + '\derived\logs\lastbook.log') -Tail 6 -Encoding utf8 -EA SilentlyContinue }

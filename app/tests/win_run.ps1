# One real-window run on the Alienware. Starts the app with schtasks /it, runs the driver, samples sockets and memory, stops only its own PID.
param([string]$Run,[string]$AppArgs='--stub --cdp --no-index',[string]$Steps='',[int]$Limit=500,[string]$Entry='tests\win_app.py',[int]$Hold=0,[switch]$Keep)
$ErrorActionPreference='Continue'
$B='C:\Users\you\app-test\app-build'; $L="$B\logs\$Run"; $Task='LastbookAppBuildRun'; $S="$B\src\app"
$pyw='C:\Users\you\app-test\python-pkg\tools\pythonw.exe'; $py='C:\Users\you\app-test\python-pkg\tools\python.exe'
$other=Get-CimInstance Win32_Process | ?{ $_.Name -like 'python*' -and $_.CommandLine -match 'app-build' }
if($other){ "ANOTHER RUN GOING: $($other.ProcessId)"; exit 2 }
New-Item -ItemType Directory -Force $L | Out-Null; Remove-Item "$L\pid.txt" -EA SilentlyContinue
$base=@{}; Get-NetTCPConnection -State Listen | %{ $base["$($_.LocalAddress):$($_.LocalPort)/$($_.OwningProcess)"]=1 }
$preview=@(Get-Process msedgewebview2 -EA SilentlyContinue | %{$_.Id})
$tr= if($Entry -eq 'main.py'){ "$pyw -I -B -X utf8 $S\main.py $AppArgs" } else { "$pyw -I -B -X utf8 $S\$Entry --run $Run $AppArgs" }
schtasks /create /tn $Task /tr $tr /sc once /st 23:59 /it /f 2>&1 | Out-Null
$t0=Get-Date
schtasks /run /tn $Task 2>&1 | Out-Null
$apppid=$null
while(-not $apppid -and ((Get-Date)-$t0).TotalSeconds -lt 30){
  if($Entry -eq 'main.py'){ $p=Get-CimInstance Win32_Process | ?{ $_.Name -eq 'pythonw.exe' -and $_.CommandLine -match 'app-build' } | Select -First 1; if($p){$apppid=[int]$p.ProcessId} }
  elseif(Test-Path "$L\pid.txt"){$apppid=[int](Get-Content "$L\pid.txt")}
  Start-Sleep -Milliseconds 100 }
schtasks /delete /tn $Task /f 2>&1 | Out-Null
if(-not $apppid){ "NO PID - window did not start"; exit 1 }
$pr=Get-Process -Id $apppid -EA SilentlyContinue
"app pid $apppid session $($pr.SessionId) path $($pr.Path) start $($t0.ToString('HH:mm:ss'))"
$drv=$null
if($Steps){ $drv=Start-Process -FilePath $py -ArgumentList '-I','-B','-X','utf8',"$S\tests\win_driver.py",$Run,$Steps -RedirectStandardOutput "$L\driver.out" -RedirectStandardError "$L\driver.err" -PassThru -WindowStyle Hidden }
$w="$L\watch.jsonl"; $n=0; $tot=@{listen=0;udp=0;est=0}; $remotes=@{}; $newsys=@{}; $peak=0; $peakTree=0; $peakWs=0
while((Get-Process -Id $apppid -EA SilentlyContinue) -and ((Get-Date)-$t0).TotalSeconds -lt $Limit){
  $all=Get-CimInstance Win32_Process | Select ProcessId,ParentProcessId,Name
  $tree=@($apppid); do{$c=$tree.Count;$tree=@($tree+($all|?{$tree -contains $_.ParentProcessId}|%{[int]$_.ProcessId}))|Select -Unique}while($tree.Count -gt $c)
  $ns=netstat -ano | %{ $f=($_ -split '\s+')|?{$_}; if($f.Count -ge 4 -and $f[0] -in 'TCP','UDP' -and ($tree -contains [int]$f[-1]) -and $_ -notmatch ':8941\b'){ $_.Trim() } }
  $li=@($ns|?{$_ -match 'LISTENING'}); $ud=@($ns|?{$_ -match '^UDP'}); $est=@($ns|?{$_ -match '^TCP' -and $_ -notmatch 'LISTENING'})
  $tot.listen+=$li.Count; $tot.udp+=$ud.Count; $tot.est+=$est.Count
  foreach($e in $est+$ud+$li){ $remotes[$e]=1 }
  Get-NetTCPConnection -State Listen | ?{$_.LocalPort -ne 8941} | %{ $k="$($_.LocalAddress):$($_.LocalPort)/$($_.OwningProcess)"; if(-not $base[$k]){ $newsys[$k]=1 } }
  $mem=Get-Process -Id $tree -EA SilentlyContinue | Select Id,@{n='p';e={[math]::Round($_.PrivateMemorySize64/1MB)}},@{n='ws';e={[math]::Round($_.WorkingSet64/1MB)}}
  $appm=($mem|?{$_.Id -eq $apppid}).p; $treem=($mem|Measure p -Sum).Sum; $wsm=($mem|Measure ws -Sum).Sum
  if($appm -gt $peak){$peak=$appm}; if($treem -gt $peakTree){$peakTree=$treem}; if($wsm -gt $peakWs){$peakWs=$wsm}
  (@{t=[math]::Round(((Get-Date)-$t0).TotalSeconds,1);ts=[DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()/1000;n=$tree.Count;app=$appm;tree=$treem;ws=$wsm;top=($mem|Sort p -Desc|Select -First 3|%{"$($_.Id):$($_.p)"}) -join ' '}|ConvertTo-Json -Compress) | Out-File $w -Append -Encoding utf8
  $n++
  if($drv -and $drv.HasExited){ if($Hold -le 0){ break }; $Hold-=2 }
  if(-not $drv -and $Hold -gt 0){ $Hold-=2; if($Hold -le 0){break} }
  Start-Sleep -Seconds 1
}
if($drv -and -not $drv.HasExited){ "driver still going at limit: stopping my driver PID $($drv.Id)"; Stop-Process -Id $drv.Id -Force }
$tree2=@()
$still=Get-Process -Id $apppid -EA SilentlyContinue
if($still -and -not $Keep){ "stopping my own app PID $apppid"; Stop-Process -Id $apppid -Force } elseif(-not $still){ "app exited by itself" }
"samples=$n secs=$([math]::Round(((Get-Date)-$t0).TotalSeconds)) listen=$($tot.listen) udp=$($tot.udp) est=$($tot.est) new_system_listeners=$($newsys.Count) peak_app_private=$peak peak_tree_private=$peakTree peak_tree_ws=$peakWs"
"socket rows of the process tree, 8941 left out:"; $remotes.Keys | Select -First 30
"new listeners on the machine, 8941 left out:"; $newsys.Keys | Select -First 20
"task left: " + (schtasks /query /tn $Task 2>&1 | Select -First 1)
Start-Sleep -Seconds 3
"app-build processes left: " + ((Get-CimInstance Win32_Process | ?{ $_.CommandLine -match 'app-build|app-only-proof\\data' }) | %{ "$($_.ProcessId) $($_.Name)" }) -join ', '

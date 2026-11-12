# Runs inside the logged-in session through a scheduled task. Shot of the app's own window, or asks it to close as a person would.
param([int]$AppPid,[string]$Do,[string]$Out)
Add-Type -AssemblyName System.Drawing
Add-Type @"
using System;using System.Runtime.InteropServices;
public static class W { [DllImport("user32.dll")] public static extern bool SetProcessDPIAware(); [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r); [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr dc, uint f);
[DllImport("user32.dll",CharSet=CharSet.Unicode)] public static extern int GetWindowText(IntPtr h, System.Text.StringBuilder s, int n);
[DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc p, IntPtr l); public delegate bool EnumProc(IntPtr h, IntPtr l);
[DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid); [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
public struct RECT { public int L,T,R,B; } }
"@
[W]::SetProcessDPIAware()|Out-Null   # or the rectangle is scaled down and the shot shows only its corner
$found=New-Object System.Collections.ArrayList
$cb=[W+EnumProc]{ param($h,$l); $p=[uint32]0; [W]::GetWindowThreadProcessId($h,[ref]$p)|Out-Null; if($p -eq $AppPid -and [W]::IsWindowVisible($h)){ $found.Add($h)|Out-Null }; $true }
[W]::EnumWindows($cb,[IntPtr]::Zero)|Out-Null
$lines=@("visible windows of ${AppPid}: $($found.Count)")
foreach($h in $found){ $s=New-Object System.Text.StringBuilder 256; [W]::GetWindowText($h,$s,256)|Out-Null; $r=New-Object W+RECT; [W]::GetWindowRect($h,[ref]$r)|Out-Null; $lines+="  title='$($s.ToString())' rect=$($r.L),$($r.T),$($r.R),$($r.B)"
  if($Do -eq 'shot'){ $b=New-Object System.Drawing.Bitmap ($r.R-$r.L),($r.B-$r.T); $g=[System.Drawing.Graphics]::FromImage($b); $d=$g.GetHdc(); [W]::PrintWindow($h,$d,2)|Out-Null; $g.ReleaseHdc($d); $b.Save("$Out.png"); $g.Dispose(); $b.Dispose() } }
if($Do -eq 'close'){ (Get-Process -Id $AppPid).CloseMainWindow() | %{ $lines+="CloseMainWindow: $_" } }
$lines | Out-File "$Out.txt" -Encoding utf8

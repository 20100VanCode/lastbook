param(
    [Parameter(Mandatory = $true)]
    [string] $Path,
    [Parameter(Mandatory = $true)]
    [string] $SignTool,
    [Parameter(Mandatory = $true)]
    [string] $Dlib,
    [Parameter(Mandatory = $true)]
    [string] $Metadata
)

# Sign the unpacked app before build_setup_windows.sh creates its payload.
# Also run this on the generated uninstaller before it enters the payload,
# and on the final installer after packaging. Existing valid vendor signatures
# are preserved. Azure credentials remain in the user's authenticated session.
$ErrorActionPreference = 'Stop'
foreach ($RequiredFile in @($SignTool, $Dlib, $Metadata)) {
    if (-not (Test-Path -LiteralPath $RequiredFile -PathType Leaf)) {
        throw "Required signing file was not found: $RequiredFile"
    }
}
$Target = Get-Item -LiteralPath $Path
if ($Target.PSIsContainer) {
    $Files = @(Get-ChildItem -LiteralPath $Target.FullName -Recurse -File |
        Where-Object { $_.Extension -in @('.exe', '.dll', '.pyd') } |
        Sort-Object FullName)
} else {
    $Files = @($Target)
}
if ($Files.Count -eq 0) {
    throw 'No executable files were found to sign.'
}

foreach ($File in $Files) {
    $Signature = Get-AuthenticodeSignature -LiteralPath $File.FullName
    if ($Signature.Status -eq 'Valid') {
        Write-Output "Already signed: $($File.Name)"
        continue
    }
    if ($Signature.Status -ne 'NotSigned') {
        throw "Existing signature needs investigation: $($File.FullName) ($($Signature.Status))"
    }
    & $SignTool sign /fd SHA256 /tr 'http://timestamp.acs.microsoft.com' /td SHA256 /dlib $Dlib /dmdf $Metadata $File.FullName
    if ($LASTEXITCODE -ne 0) {
        throw "Signing failed: $($File.FullName)"
    }
    & $SignTool verify /pa /all $File.FullName
    if ($LASTEXITCODE -ne 0) {
        throw "Signature verification failed: $($File.FullName)"
    }
    $Signature = Get-AuthenticodeSignature -LiteralPath $File.FullName
    if ($Signature.Status -ne 'Valid' -or $null -eq $Signature.TimeStamperCertificate) {
        throw "A valid timestamped signature was not found: $($File.FullName)"
    }
    Write-Output "Signed and verified: $($File.Name)"
}

# 빌드 결과물에 코드 서명을 한다.
# 인증서가 Windows 인증서 저장소(보안 토큰 포함)에 등록되어 있어야 한다.
#   $env:HWONHI_CERT_THUMBPRINT = "<인증서 지문>"
#   powershell -ExecutionPolicy Bypass -File tools\sign.ps1 dist\훤히
# 지문 확인: Get-ChildItem Cert:\CurrentUser\My -CodeSigningCert
param([Parameter(Mandatory = $true)][string]$Dir)

$thumb = $env:HWONHI_CERT_THUMBPRINT
if (-not $thumb) { Write-Output 'SIGN SKIPPED (HWONHI_CERT_THUMBPRINT 없음)'; exit 0 }
$cert = Get-ChildItem Cert:\CurrentUser\My, Cert:\LocalMachine\My -CodeSigningCert |
        Where-Object { $_.Thumbprint -eq $thumb.Replace(' ', '').ToUpper() } | Select-Object -First 1
if (-not $cert) { Write-Output "SIGN FAILED: 인증서 $thumb 을 찾지 못함"; exit 1 }

# exe 와, 아직 서명되지 않은 동봉 라이브러리(.dll/.pyd)에 서명한다.
# 이미 다른 곳(Python, Microsoft 등)의 서명이 있는 파일은 건드리지 않는다.
$targets = Get-ChildItem $Dir -Recurse -Include *.exe, *.dll, *.pyd |
           Where-Object { (Get-AuthenticodeSignature $_.FullName).Status -eq 'NotSigned' }
$bad = 0
foreach ($f in $targets) {
  $r = Set-AuthenticodeSignature -FilePath $f.FullName -Certificate $cert -HashAlgorithm SHA256 `
         -TimestampServer 'http://timestamp.digicert.com'
  if ($r.Status -ne 'Valid') { $bad++; Write-Output ("  실패: {0} ({1})" -f $f.Name, $r.StatusMessage) }
}
if ($bad) { Write-Output ("SIGN FAILED: {0}/{1}" -f $bad, $targets.Count); exit 1 }
Write-Output ("SIGN OK: {0} files" -f $targets.Count)

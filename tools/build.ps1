param([string]$OutputName = ('hwonhi-' + (Get-Date -Format 'yyyyMMdd-HHmmss')))
$ErrorActionPreference = 'Stop'
if ($OutputName -notmatch '^[a-zA-Z0-9][a-zA-Z0-9._-]{0,80}$') { throw 'OutputName must be a simple folder name.' }
# 스크립트 위치 기준으로 프로젝트 폴더를 잡는다 (PC 경로에 의존하지 않음)
Set-Location (Split-Path -Parent $PSScriptRoot)
# Existing builds and running applications keep their own output folders.
$distRoot = Join-Path (Get-Location).Path ('dist/' + $OutputName)
$workRoot = Join-Path (Get-Location).Path ('build/' + $OutputName)
if ((Test-Path -LiteralPath $distRoot) -or (Test-Path -LiteralPath $workRoot)) { throw 'Build output already exists; choose a new OutputName.' }
New-Item -ItemType Directory -Path $workRoot | Out-Null
$started = Get-Date
$repoPath = (Get-Location).Path
$pyargs = @(
  '-m','PyInstaller','--noconfirm','--distpath',$distRoot,'--workpath',$workRoot,'--specpath',$workRoot,'--onedir','--name','훤히','--windowed','--icon',(Join-Path $repoPath 'assets/훤히.ico'),
  '--add-data',((Join-Path $repoPath 'detector\ui\index.html') + ';ui'),
  '--add-data',((Join-Path $repoPath 'assets\훤히.ico') + ';assets'),
  '--add-data',((Join-Path $repoPath 'assets\fonts') + ';assets\fonts'),
  '--collect-all','fontTools','--collect-all','brotli','--collect-all','playwright','--collect-all','winrt','--collect-all','pypdfium2','--collect-all','pypdfium2_raw',
  '--exclude-module','webview','--exclude-module','clr','--exclude-module','pythonnet',
  '--exclude-module','clr_loader',
  '--paths',(Join-Path $repoPath 'detector'),(Join-Path $repoPath 'detector/main.py')
)
& '.\.venv\Scripts\python.exe' @pyargs 2>&1 | Tee-Object -FilePath (Join-Path $workRoot 'build.log') | Select-String -Pattern 'ERROR|Traceback|completed successfully'
$buildExit = $LASTEXITCODE
$bundle = Join-Path $distRoot '훤히'
$exe = Join-Path $bundle '훤히.exe'
if ($buildExit -ne 0 -or -not (Test-Path -LiteralPath $exe)) { throw ('BUILD FAILED: exit ' + $buildExit) }
if ((Get-Item -LiteralPath $exe).LastWriteTime -lt $started) { throw 'BUILD FAILED: stale executable' }
$size = (Get-ChildItem -LiteralPath $bundle -Recurse -File | Measure-Object -Property Length -Sum).Sum / 1MB
Write-Output ('BUILD OK / {0:N0} MB / {1}' -f $size, $exe)
& (Join-Path $PSScriptRoot 'sign.ps1') $bundle
if ($LASTEXITCODE -ne 0) { throw 'SIGN FAILED' }

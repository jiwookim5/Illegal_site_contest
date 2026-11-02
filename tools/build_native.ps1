# 네이티브 창(WebView2) 버전 빌드.
# 주의: pythonnet 이 포함되면 Windows Smart App Control 이 서명 없는 실행 파일을
# 차단할 수 있다. 코드 서명이 준비되기 전에는 기본 빌드(tools\build.ps1)를 쓸 것.
param([string]$OutputName = ('hwonhi-native-' + (Get-Date -Format 'yyyyMMdd-HHmmss')))
$ErrorActionPreference = 'Stop'
if ($OutputName -notmatch '^[a-zA-Z0-9][a-zA-Z0-9._-]{0,80}$') { throw 'OutputName must be a simple folder name.' }
Set-Location (Split-Path -Parent $PSScriptRoot)
$repoPath = (Get-Location).Path
$distRoot = Join-Path $repoPath ('dist_native/' + $OutputName)
$workRoot = Join-Path $repoPath ('build_native/' + $OutputName)
if ((Test-Path -LiteralPath $distRoot) -or (Test-Path -LiteralPath $workRoot)) { throw 'Build output already exists; choose a new OutputName.' }
& '.\.venv\Scripts\python.exe' -c 'import webview, clr'
if ($LASTEXITCODE -ne 0) { throw 'Native build requires pywebview and pythonnet in .venv.' }
New-Item -ItemType Directory -Path $workRoot | Out-Null
$started = Get-Date
$pyargs = @(
  '-m','PyInstaller','--noconfirm','--onedir','--name','훤히','--windowed','--icon',(Join-Path $repoPath 'assets/훤히.ico'),
  '--distpath',$distRoot,'--workpath',$workRoot,'--specpath',$workRoot,
  '--add-data',((Join-Path $repoPath 'detector/ui/index.html') + ';ui'),
  '--add-data',((Join-Path $repoPath 'assets/훤히.ico') + ';assets'),
  '--add-data',((Join-Path $repoPath 'assets/fonts') + ';assets/fonts'),
  '--collect-all','fontTools','--collect-all','brotli','--collect-all','playwright','--collect-all','winrt','--collect-all','pypdfium2','--collect-all','pypdfium2_raw',
  '--collect-all','webview','--collect-all','clr_loader','--collect-all','pythonnet',
  '--hidden-import','clr','--hidden-import','bottle','--hidden-import','proxy_tools',
  '--paths',(Join-Path $repoPath 'detector'),(Join-Path $repoPath 'detector/main.py')
)
& '.\.venv\Scripts\python.exe' @pyargs 2>&1 | Tee-Object -FilePath (Join-Path $workRoot 'build.log') | Select-String -Pattern 'ERROR|Traceback|completed successfully'
$buildExit = $LASTEXITCODE
$bundle = Join-Path $distRoot '훤히'
$exe = Join-Path $bundle '훤히.exe'
if ($buildExit -ne 0 -or -not (Test-Path -LiteralPath $exe)) { throw ('NATIVE BUILD FAILED: exit ' + $buildExit) }
if ((Get-Item -LiteralPath $exe).LastWriteTime -lt $started) { throw 'NATIVE BUILD FAILED: stale executable' }
$size = (Get-ChildItem -LiteralPath $bundle -Recurse -File | Measure-Object -Property Length -Sum).Sum / 1MB
Write-Output ('NATIVE BUILD OK / {0:N0} MB / {1}' -f $size, $exe)
& (Join-Path $PSScriptRoot 'sign.ps1') $bundle
if ($LASTEXITCODE -ne 0) { throw 'SIGN FAILED' }

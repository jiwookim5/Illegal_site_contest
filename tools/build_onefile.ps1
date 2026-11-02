# 스크립트 위치 기준으로 프로젝트 폴더를 잡는다 (PC 경로에 의존하지 않음)
Set-Location (Split-Path -Parent $PSScriptRoot)
# 실행 중인 훤히가 있으면 결과물이 잠겨 덮어쓰지 못한다. 그런데도 옛 파일이 남아 있어
# 빌드가 성공한 것처럼 보이므로, 시작 전에 막고 끝난 뒤 파일 시각까지 확인한다.
$running = Get-Process -Name '훤히' -ErrorAction SilentlyContinue
if ($running) { Write-Output ('BUILD STOPPED: 훤히가 실행 중입니다 (PID {0}). 모두 종료한 뒤 다시 빌드하세요.' -f ($running.Id -join ', ')); exit 1 }
$started = Get-Date
# 폴더 배포본과 같은 이름을 쓰므로 작업 폴더를 분리해 섞이지 않게 한다.
Remove-Item -Recurse -Force 'build_single' -ErrorAction SilentlyContinue
$pyargs = @(
  '-m','PyInstaller','--noconfirm','--onefile','--name','훤히','--windowed','--icon','assets\훤히.ico',
  '--distpath','.','--workpath','build_single',
  '--add-data','detector\ui\index.html;ui',
  '--add-data','assets\훤히.ico;assets',
  '--add-data','assets\fonts;assets\fonts',
  '--collect-all','fontTools','--collect-all','brotli','--collect-all','playwright','--collect-all','winrt','--collect-all','pypdfium2','--collect-all','pypdfium2_raw',
  '--exclude-module','webview','--exclude-module','clr','--exclude-module','pythonnet',
  '--exclude-module','clr_loader',
  '--paths','detector','detector\main.py'
)
& '.\.venv\Scripts\python.exe' @pyargs 2>&1 | Select-String -Pattern 'ERROR|Traceback|completed successfully' | Select-Object -Last 3
if ((Test-Path '훤히.exe') -and (Get-Item '훤히.exe').LastWriteTime -ge $started) {
  $m = (Get-Item '훤히.exe').Length/1MB
  Write-Output ('SINGLE EXE OK / {0:N0} MB' -f $m)
  # 같은 경로에 덮어쓰면 탐색기가 옛 아이콘을 계속 보여 준다. 이 파일이 바뀌었다고 알려 아이콘을 다시 읽게 한다
  Add-Type -Namespace Hwonhi -Name Shell -MemberDefinition '[DllImport("shell32.dll", CharSet=CharSet.Unicode)] public static extern void SHChangeNotify(int e, uint f, string a, IntPtr b);'
  [Hwonhi.Shell]::SHChangeNotify(0x2000, 0x5, (Resolve-Path '훤히.exe').Path, [IntPtr]::Zero)   # SHCNE_UPDATEITEM, SHCNF_PATHW
  [Hwonhi.Shell]::SHChangeNotify(0x8000000, 0x0, $null, [IntPtr]::Zero)                        # SHCNE_ASSOCCHANGED
} else { Write-Output 'BUILD FAILED (결과물이 새로 만들어지지 않음)' }

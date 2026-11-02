@echo off
chcp 65001 > nul
cd /d "%~dp0"
title 훤히 우회 기법 시험 사이트

if not exist ".venv\Scripts\python.exe" (
  echo [오류] 개발 환경^(.venv^)이 없습니다. docs\빌드_매뉴얼.md 4장을 참고해 준비해 주세요.
  pause
  exit /b 1
)

echo 탐지 우회 기법 시험 사이트^(testsite_evasion^)만 띄웁니다. 작업표시줄에 최소화된 창으로 떠 있습니다.
start "hwonhi-evasion-8788" /min cmd /c "set SITE=testsite_evasion&& .venv\Scripts\python.exe tools\serve.py 8788"
timeout /t 2 /nobreak > nul

echo.
echo ================================================================
echo  훤히 화면의 주소 입력란에 아래 주소를 넣고 [탐지 시작]
echo.
echo   http://127.0.0.1:8788/evasion/
echo.
echo  정답과 비교까지 자동으로 하려면 이 창을 닫은 뒤 다음을 실행하세요.
echo   .venv\Scripts\python tools\evasion_check.py
echo  페이지 목록과 항목 설명: testsite_evasion\README.md
echo ================================================================
echo.

if exist "훤히.exe" (
  echo 훤히를 실행합니다...
  start "" "훤히.exe"
) else if exist "dist\훤히\훤히.exe" (
  echo 훤히를 실행합니다...
  start "" "dist\훤히\훤히.exe"
) else (
  echo [안내] 훤히.exe 가 없습니다. 빌드한 뒤 직접 실행해 주세요.
)

echo.
echo 다 쓰셨으면 이 창에서 아무 키나 누르세요. 시험 사이트를 종료합니다.
pause > nul
taskkill /F /T /FI "WINDOWTITLE eq hwonhi-evasion-8788" > nul 2>&1
echo 시험 사이트를 종료했습니다.
timeout /t 2 /nobreak > nul

@echo off
chcp 65001 > nul
cd /d "%~dp0"
title 훤히 시험 사이트

if not exist ".venv\Scripts\python.exe" (
  echo [오류] 개발 환경^(.venv^)이 없습니다. docs\빌드_매뉴얼.md 4장을 참고해 준비해 주세요.
  pause
  exit /b 1
)

echo 시험 사이트 16개를 띄웁니다. 작업표시줄에 최소화된 창으로 떠 있습니다.
start "hwonhi-testsite-8765" /min cmd /c "set SITE=testsite&& .venv\Scripts\python.exe tools\serve.py 8765"
start "hwonhi-testsite-8766" /min cmd /c "set SITE=testsite2&& .venv\Scripts\python.exe tools\serve.py 8766"
start "hwonhi-testsite-8767" /min cmd /c "set SITE=testsite3&& .venv\Scripts\python.exe tools\serve.py 8767"
start "hwonhi-testsite-8768" /min cmd /c "set SITE=testsite4&& .venv\Scripts\python.exe tools\serve.py 8768"
start "hwonhi-testsite-8769" /min cmd /c "set SITE=testsite5&& .venv\Scripts\python.exe tools\serve.py 8769"
start "hwonhi-testsite-8770" /min cmd /c "set SITE=testsite6&& .venv\Scripts\python.exe tools\serve.py 8770"
start "hwonhi-testsite-8771" /min cmd /c "set SITE=testsite7&& .venv\Scripts\python.exe tools\serve.py 8771"
start "hwonhi-testsite-8772" /min cmd /c "set SITE=testsite8&& .venv\Scripts\python.exe tools\serve.py 8772"
start "hwonhi-testsite-8773" /min cmd /c "set SITE=testsite9&& .venv\Scripts\python.exe tools\serve.py 8773"
start "hwonhi-testsite-8774" /min cmd /c "set SITE=testsite10&& .venv\Scripts\python.exe tools\serve.py 8774"
start "hwonhi-testsite-8775" /min cmd /c "set SITE=testsite11&& .venv\Scripts\python.exe tools\serve.py 8775"
start "hwonhi-testsite-8776" /min cmd /c "set SITE=testsite12&& .venv\Scripts\python.exe tools\serve.py 8776"
start "hwonhi-testsite-8777" /min cmd /c "set SITE=testsite13&& .venv\Scripts\python.exe tools\serve.py 8777"
start "hwonhi-testsite-8778" /min cmd /c "set SITE=testsite14&& .venv\Scripts\python.exe tools\serve.py 8778 8779 8780 8781 8782 8783 8784 8785"
start "hwonhi-testsite-8786" /min cmd /c "set SITE=testsite15&& .venv\Scripts\python.exe tools\serve.py 8786"
start "hwonhi-testsite-8787" /min cmd /c "set SITE=testsite16&& .venv\Scripts\python.exe tools\serve.py 8787"
start "hwonhi-testsite-8788" /min cmd /c "set SITE=testsite_evasion&& .venv\Scripts\python.exe tools\serve.py 8788"
timeout /t 2 /nobreak > nul

echo.
echo ================================================================
echo  훤히 화면의 주소 입력란에 아래 주소 중 하나를 넣고 [탐지 시작]
echo.
echo   기본 ^(주요 4종^)       http://127.0.0.1:8765/board/list
echo   중간 난이도           http://127.0.0.1:8766/notice/index
echo   어려움 ^(iframe 중첩^)  http://127.0.0.1:8767/portal/list
echo   어려움                http://127.0.0.1:8768/www/main
echo   첨부파일 ^(문서·zip^)   http://127.0.0.1:8769/bbs/list
echo   검색결과 반사 점검      http://127.0.0.1:8770/main
echo   은닉 빈틈 ^(주요 4종^)   http://127.0.0.1:8771/gap/list
echo   자바스크립트 게시판      http://127.0.0.1:8772/egov/main.do
echo   마약·대포통장 등 광고    http://127.0.0.1:8773/free/list
echo   게시판 노출 광고        http://127.0.0.1:8774/visit/list
echo   점검 범위^(서브도메인^)   http://www.demo.localhost:8775/main
echo   크롤링 구멍^(POST 등^)   http://127.0.0.1:8776/egov/list.do
echo   견고성^(더보기 등^)      http://127.0.0.1:8777/site/main
echo   연계 링크 확인 ^(설정에서 켜기^) http://127.0.0.1:8778/main
echo   지연 삽입 광고          http://127.0.0.1:8786/late/list
echo   그림 속 글자 ^(설정에서 '그림 속 글자 검사' 켜기^) http://127.0.0.1:8787/ocr/list
echo   탐지 우회 기법 ^(아직 못 잡는 것 포함^) http://127.0.0.1:8788/evasion/list
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
echo 다 쓰셨으면 이 창에서 아무 키나 누르세요. 시험 사이트를 모두 종료합니다.
pause > nul
taskkill /F /T /FI "WINDOWTITLE eq hwonhi-testsite*" > nul 2>&1
echo 시험 사이트를 종료했습니다.
timeout /t 2 /nobreak > nul

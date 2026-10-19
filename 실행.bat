@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ==========================================
echo  화물운송종사자격 모의시험 - 내 PC에서 실행
echo ==========================================
echo  주소: http://localhost:8000
echo  종료: 이 창을 닫으세요.
echo.
set OPEN=start "" cmd /c "timeout /t 2 /nobreak >nul & start http://localhost:8000/"

where py >nul 2>nul
if %errorlevel%==0 (
  %OPEN%
  py -m http.server 8000
  goto :end
)
where python >nul 2>nul
if %errorlevel%==0 (
  %OPEN%
  python -m http.server 8000
  goto :end
)
where npx >nul 2>nul
if %errorlevel%==0 (
  %OPEN%
  npx --yes http-server -p 8000 -c-1
  goto :end
)
echo [안내] Python 또는 Node.js가 필요합니다.
echo  https://www.python.org 에서 Python을 설치한 뒤 다시 실행해 주세요.
:end
pause

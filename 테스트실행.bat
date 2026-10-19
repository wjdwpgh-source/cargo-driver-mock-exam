@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ==========================================
echo  화물운송종사자격 모의시험 - 자동 테스트 전체 실행
echo ==========================================
echo  처음 한 번만 준비:  pip install openpyxl playwright  그리고  python -m playwright install chromium
echo  (단위 테스트는 Node.js가 있으면 함께 실행됩니다)
echo.
where py >nul 2>nul
if %errorlevel%==0 (
  py tests\run_all.py
) else (
  python tests\run_all.py
)
echo.
pause

@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
echo ==========================================
echo  검수 결과 반영: 검수 폴더의 최신 검수표 → data\raw 엑셀 원본 → 문제 변환
echo ==========================================
set PY=
where py >nul 2>nul && set PY=py
if not defined PY ( where python >nul 2>nul && set PY=python )
if not defined PY (
  echo [안내] Python이 필요합니다. https://www.python.org 에서 설치한 뒤 다시 실행하세요.
  pause
  goto :eof
)
%PY% -c "import openpyxl" 2>nul || (
  echo 엑셀 읽기 도구(openpyxl)를 설치합니다...
  %PY% -m pip install --user openpyxl
)
%PY% tools\apply_review.py && %PY% tools\convert.py
echo.
pause

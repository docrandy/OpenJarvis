@echo off
title OpenJarvis Launcher
echo Starting OpenJarvis...

:: Load environment variables
for /f "usebackq tokens=1,* delims==" %%a in ("%~dp0.env") do (
    set "line=%%a"
    if not "!line:~0,1!"=="#" set "%%a=%%b"
)

:: Enable delayed expansion for the # check above
setlocal enabledelayedexpansion
for /f "usebackq tokens=1,* delims==" %%a in ("%~dp0.env") do (
    set "line=%%a"
    if not "!line:~0,1!"=="#" (
        if not "%%a"=="" endlocal & set "%%a=%%b" & setlocal enabledelayedexpansion
    )
)
endlocal

:: Start backend in a new window
start "Jarvis Backend" cmd /k "cd /d %~dp0 && set /p dummy=Loading .env... <nul && for /f "usebackq tokens=1,* delims==" %%a in (".env") do @(set "%%a=%%b") && echo. && echo Backend starting on http://127.0.0.1:8000 && uv run jarvis serve"

:: Wait for backend to initialize
timeout /t 3 /nobreak >nul

:: Start frontend in a new window
start "Jarvis Frontend" cmd /k "cd /d %~dp0frontend && echo Frontend starting... && npm run dev"

:: Wait for frontend
timeout /t 5 /nobreak >nul

:: Open browser
start http://localhost:5173

echo.
echo Jarvis is starting up:
echo   Backend:  http://127.0.0.1:8000
echo   Frontend: http://localhost:5173 (opening in browser...)
echo.
echo Close this window anytime. The backend and frontend run in their own windows.
timeout /t 5 >nul

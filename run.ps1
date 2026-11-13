<#
.SYNOPSIS
    CopyCop Unified Project Runner (PowerShell)
.DESCRIPTION
    Starts both the FastAPI Backend and Vite React Frontend.
#>

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$PythonExe = if (Test-Path ".\.venv\Scripts\python.exe") {
    ".\.venv\Scripts\python.exe"
} else {
    "python"
}

Write-Host "Launching CopyCop via $PythonExe..." -ForegroundColor Cyan
& $PythonExe run.py @args

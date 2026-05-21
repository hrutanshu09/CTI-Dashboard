$ErrorActionPreference = 'Stop'

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackendDir = Join-Path $ScriptDir 'backend'
$BackendBeDir = Join-Path $ScriptDir 'backend_BE'
$FrontendDir = Join-Path $ScriptDir 'frontend'

function Resolve-PythonExe {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ServiceDir
    )

    $commonCandidates = @(
        (Join-Path $ScriptDir '.venv\\Scripts\\python.exe'),
        (Join-Path $BackendBeDir 'myenv\\Scripts\\python.exe')
    )

    $serviceCandidates = @(
        (Join-Path $ServiceDir '.venv\\Scripts\\python.exe'),
        (Join-Path $ServiceDir 'venv\\Scripts\\python.exe'),
        (Join-Path $ServiceDir 'myenv\\Scripts\\python.exe')
    )

    foreach ($candidate in ($serviceCandidates + $commonCandidates)) {
        if (Test-Path $candidate) {
            return $candidate
        }
    }

    $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCmd) { return $pythonCmd.Source }

    $pyCmd = Get-Command py -ErrorAction SilentlyContinue
    if ($pyCmd) { return $pyCmd.Source }

    return $null
}

$backendPython = Resolve-PythonExe -ServiceDir $BackendDir
$backendBePython = Resolve-PythonExe -ServiceDir $BackendBeDir

if (-not $backendPython) {
    throw 'No Python runtime found for backend.'
}
if (-not $backendBePython) {
    throw 'No Python runtime found for backend_BE.'
}

if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    throw 'npm is not installed or not in PATH.'
}

$processes = @()

function Start-ServiceProcess {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,
        [Parameter(Mandatory = $true)]
        [string]$WorkingDirectory,
        [Parameter(Mandatory = $true)]
        [string]$FilePath,
        [Parameter(Mandatory = $false)]
        [string[]]$ArgumentList = @()
    )

    Write-Host "Starting $Name..."
    $proc = Start-Process -FilePath $FilePath -ArgumentList $ArgumentList -WorkingDirectory $WorkingDirectory -PassThru -WindowStyle Hidden
    $script:processes += $proc
    Write-Host "$Name started (PID: $($proc.Id))"
}

function Stop-AllProcesses {
    if (-not $script:processes -or $script:processes.Count -eq 0) {
        return
    }

    Write-Host ''
    Write-Host 'Stopping services...'

    foreach ($proc in $script:processes) {
        try {
            if (-not $proc.HasExited) {
                Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
            }
        } catch {
        }
    }
}

try {
    Start-ServiceProcess -Name 'Backend API (port 8000)' -WorkingDirectory $BackendDir -FilePath $backendPython -ArgumentList @('-m', 'uvicorn', 'main:app', '--host', '127.0.0.1', '--port', '8000')

    Start-ServiceProcess -Name 'Backend BE API (port 8001)' -WorkingDirectory $BackendBeDir -FilePath $backendBePython -ArgumentList @('-m', 'uvicorn', 'main:app', '--host', '127.0.0.1', '--port', '8001')

    Start-ServiceProcess -Name 'Frontend (port 3001)' -WorkingDirectory $FrontendDir -FilePath 'npm.cmd' -ArgumentList @('start')

    Write-Host ''
    Write-Host 'All services launched:'
    Write-Host '- Frontend:      http://127.0.0.1:3001'
    Write-Host '- Backend API:   http://127.0.0.1:8000'
    Write-Host '- Backend BE:    http://127.0.0.1:8001'
    Write-Host ''
    Write-Host 'Press Ctrl+C to stop all services.'

    while ($true) {
        Start-Sleep -Seconds 1
        foreach ($proc in $processes) {
            if ($proc.HasExited) {
                throw "A service exited unexpectedly (PID: $($proc.Id), ExitCode: $($proc.ExitCode))."
            }
        }
    }
}
catch {
    Write-Host "Error: $($_.Exception.Message)"
}
finally {
    Stop-AllProcesses
}

$ErrorActionPreference = 'Stop'

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackendDir = Join-Path $ScriptDir 'backend'
$BackendBeDir = Join-Path $ScriptDir 'backend_BE'
$FrontendDir = Join-Path $ScriptDir 'frontend'
$LogDir = Join-Path $ScriptDir 'logs'

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

function Test-PythonModule {
    param(
        [Parameter(Mandatory = $true)]
        [string]$FilePath,
        [string[]]$ArgumentPrefix = @(),
        [Parameter(Mandatory = $true)]
        [string]$ModuleName
    )

    try {
        $args = @($ArgumentPrefix + @('-c', "import $ModuleName"))
        & $FilePath @args *> $null
        return $LASTEXITCODE -eq 0
    } catch {
        return $false
    }
}

function New-PythonCandidate {
    param(
        [Parameter(Mandatory = $true)]
        [string]$FilePath,
        [string[]]$ArgumentPrefix = @(),
        [string]$Label = ''
    )

    return [PSCustomObject]@{
        FilePath = $FilePath
        ArgumentPrefix = $ArgumentPrefix
        Label = if ($Label) { $Label } else { $FilePath }
    }
}

function Resolve-PythonCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ServiceDir,
        [switch]$PreferPy311
    )

    $candidates = @()

    foreach ($relative in @('.venv311\Scripts\python.exe', '.venv\Scripts\python.exe', 'venv\Scripts\python.exe', 'myenv\Scripts\python.exe')) {
        $candidate = Join-Path $ServiceDir $relative
        if (Test-Path $candidate) {
            $candidates += New-PythonCandidate -FilePath $candidate -Label $candidate
        }
    }

    if ($PreferPy311) {
        $pyCmd = Get-Command py -ErrorAction SilentlyContinue
        if ($pyCmd) {
            $candidates += New-PythonCandidate -FilePath $pyCmd.Source -ArgumentPrefix @('-3.11') -Label 'py -3.11'
        }
    }

    foreach ($relative in @('.venv\Scripts\python.exe', '.venv311\Scripts\python.exe')) {
        $candidate = Join-Path $ScriptDir $relative
        if (Test-Path $candidate) {
            $candidates += New-PythonCandidate -FilePath $candidate -Label $candidate
        }
    }

    $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCmd) {
        $candidates += New-PythonCandidate -FilePath $pythonCmd.Source -Label 'python'
    }

    $pyFallback = Get-Command py -ErrorAction SilentlyContinue
    if ($pyFallback) {
        $candidates += New-PythonCandidate -FilePath $pyFallback.Source -Label 'py'
    }

    foreach ($candidate in $candidates) {
        if (Test-PythonModule -FilePath $candidate.FilePath -ArgumentPrefix $candidate.ArgumentPrefix -ModuleName 'uvicorn') {
            return $candidate
        }
    }

    return $null
}

function Get-FrontendPort {
    $envPath = Join-Path $FrontendDir '.env'
    if (-not (Test-Path $envPath)) {
        return '3000'
    }

    $portLine = Get-Content -LiteralPath $envPath | Where-Object { $_ -match '^\s*PORT\s*=' } | Select-Object -First 1
    if ($portLine -and $portLine -match '^\s*PORT\s*=\s*(\d+)') {
        return $Matches[1]
    }

    return '3000'
}

function Stop-ProcessOnPort {
    param(
        [Parameter(Mandatory = $true)]
        [int]$Port
    )

    $connections = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue
    $pids = @($connections | Select-Object -ExpandProperty OwningProcess -Unique | Where-Object { $_ -gt 0 })
    foreach ($owningPid in $pids) {
        try {
            $proc = Get-Process -Id $owningPid -ErrorAction SilentlyContinue
            if ($proc) {
                Write-Host "Stopping existing process on port $Port (PID: $owningPid, $($proc.ProcessName))..."
                Stop-Process -Id $owningPid -Force -ErrorAction SilentlyContinue
            }
        } catch {
        }
    }
}

function Start-ServiceProcess {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,
        [Parameter(Mandatory = $true)]
        [string]$WorkingDirectory,
        [Parameter(Mandatory = $true)]
        [string]$FilePath,
        [Parameter(Mandatory = $false)]
        [string[]]$ArgumentList = @(),
        [Parameter(Mandatory = $true)]
        [string]$LogName
    )

    $stdout = Join-Path $LogDir "$LogName.out.log"
    $stderr = Join-Path $LogDir "$LogName.err.log"
    Remove-Item -LiteralPath $stdout, $stderr -Force -ErrorAction SilentlyContinue

    Write-Host "Starting $Name..."
    $proc = Start-Process -FilePath $FilePath -ArgumentList $ArgumentList -WorkingDirectory $WorkingDirectory -PassThru -WindowStyle Hidden -RedirectStandardOutput $stdout -RedirectStandardError $stderr
    $script:processes += [PSCustomObject]@{
        Name = $Name
        Process = $proc
        Stdout = $stdout
        Stderr = $stderr
    }
    Write-Host "$Name started (PID: $($proc.Id))"
}

function Show-ServiceLogs {
    param(
        [Parameter(Mandatory = $true)]
        $Service
    )

    Write-Host ''
    Write-Host "Last logs for $($Service.Name):"
    foreach ($path in @($Service.Stdout, $Service.Stderr)) {
        if (Test-Path $path) {
            Write-Host "--- $path ---"
            Get-Content -LiteralPath $path -Tail 40 -ErrorAction SilentlyContinue
        }
    }
}

function Stop-AllProcesses {
    if (-not $script:processes -or $script:processes.Count -eq 0) {
        return
    }

    Write-Host ''
    Write-Host 'Stopping services...'

    foreach ($service in $script:processes) {
        try {
            if (-not $service.Process.HasExited) {
                Stop-Process -Id $service.Process.Id -Force -ErrorAction SilentlyContinue
            }
        } catch {
        }
    }
}

$frontendPort = Get-FrontendPort
$backendPython = Resolve-PythonCommand -ServiceDir $BackendDir
$backendBePython = Resolve-PythonCommand -ServiceDir $BackendBeDir -PreferPy311

if (-not $backendPython) {
    throw 'No Python runtime with uvicorn found for backend. Install backend dependencies first.'
}
if (-not $backendBePython) {
    throw 'No Python 3.11/runtime with uvicorn found for backend_BE. Install backend_BE dependencies first.'
}

$npmCmd = Get-Command npm.cmd -ErrorAction SilentlyContinue
if (-not $npmCmd) {
    throw 'npm.cmd is not installed or not in PATH.'
}

$processes = @()

try {
    Stop-ProcessOnPort -Port 8000
    Stop-ProcessOnPort -Port 8001
    Stop-ProcessOnPort -Port ([int]$frontendPort)

    Start-ServiceProcess `
        -Name 'Backend API (port 8000)' `
        -WorkingDirectory $BackendDir `
        -FilePath $backendPython.FilePath `
        -ArgumentList @($backendPython.ArgumentPrefix + @('-m', 'uvicorn', 'main:app', '--host', '127.0.0.1', '--port', '8000', '--reload')) `
        -LogName 'backend-8000'

    Start-ServiceProcess `
        -Name 'Backend BE API (port 8001)' `
        -WorkingDirectory $BackendBeDir `
        -FilePath $backendBePython.FilePath `
        -ArgumentList @($backendBePython.ArgumentPrefix + @('-m', 'uvicorn', 'main:app', '--host', '127.0.0.1', '--port', '8001', '--reload')) `
        -LogName 'backend-be-8001'

    Start-ServiceProcess `
        -Name "Frontend (port $frontendPort)" `
        -WorkingDirectory $FrontendDir `
        -FilePath $npmCmd.Source `
        -ArgumentList @('start') `
        -LogName 'frontend'

    Write-Host ''
    Write-Host 'All services launched:'
    Write-Host "- Frontend:      http://127.0.0.1:$frontendPort"
    Write-Host '- Backend API:   http://127.0.0.1:8000'
    Write-Host '- Backend BE:    http://127.0.0.1:8001'
    Write-Host ''
    Write-Host "Logs: $LogDir"
    Write-Host 'Press Ctrl+C to stop all services.'

    while ($true) {
        Start-Sleep -Seconds 2
        foreach ($service in $processes) {
            if ($service.Process.HasExited) {
                Show-ServiceLogs -Service $service
                throw "$($service.Name) exited unexpectedly (PID: $($service.Process.Id), ExitCode: $($service.Process.ExitCode))."
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

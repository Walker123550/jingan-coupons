param([string]$PythonPath = '', [switch]$WithCapture)
$ErrorActionPreference = 'Stop'
$env:PYTHONUTF8 = '1'
$pythonArgs = @()
if ($PythonPath) {
    if (-not (Test-Path -LiteralPath $PythonPath)) { throw 'PythonPath does not exist.' }
    $pythonCommand = $PythonPath
} elseif (Get-Command py.exe -ErrorAction SilentlyContinue) {
    $pythonCommand = (Get-Command py.exe).Source
    $pythonArgs = @('-3.12')
} else {
    $command = Get-Command python.exe -ErrorAction SilentlyContinue
    if (-not $command -or $command.Source -match '\\WindowsApps\\') { throw 'Install real 64-bit Python 3.12 first, or provide -PythonPath.' }
    $pythonCommand = $command.Source
}
& $pythonCommand @pythonArgs -c "import sys;sys.exit(0 if sys.version_info[:2]==(3,12) and sys.maxsize>2**32 else 1)"
if ($LASTEXITCODE -ne 0) { throw 'Use 64-bit Python 3.12 for this tested setup.' }
& $pythonCommand @pythonArgs -m venv (Join-Path $PSScriptRoot '.venv-win')
if ($LASTEXITCODE -ne 0) { throw 'Windows virtual environment creation failed.' }
$nativePython = Join-Path $PSScriptRoot '.venv-win\Scripts\python.exe'
$requirements = if ($WithCapture) { 'requirements.txt' } else { 'requirements-core.txt' }
& $nativePython -m pip install -r (Join-Path $PSScriptRoot $requirements)
if ($LASTEXITCODE -ne 0) { throw 'Dependency install failed; check network/proxy.' }
Push-Location $PSScriptRoot
try { & $nativePython -m pytest -q } finally { Pop-Location }
if ($LASTEXITCODE -ne 0) { throw 'Tests failed.' }
Write-Output 'Native Windows setup complete. Configure own session/location before sending.'

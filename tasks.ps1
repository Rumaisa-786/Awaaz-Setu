param(
  [Parameter(Position=0)][ValidateSet('setup','install','test','smoke','api','frontend','eval')][string]$Task = 'setup',
  [Parameter(ValueFromRemainingArguments=$true)][string[]]$TaskArgs
)
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Backend = Join-Path $Root 'backend'
$VenvPython = Join-Path $Backend '.venv\Scripts\python.exe'

switch ($Task) {
  { $_ -in 'setup','install' } {
    if (-not (Test-Path $VenvPython)) {
      $PythonLauncher = Get-Command py -ErrorAction SilentlyContinue
      $Created = $false
      if ($PythonLauncher) {
        py -3.11 -m venv (Join-Path $Backend '.venv') 2>$null
        $Created = ($LASTEXITCODE -eq 0)
      }
      if (-not $Created) {
        python -c "import sys; assert sys.version_info >= (3,11), 'Python 3.11+ required'; print(sys.version)"
        python -m venv (Join-Path $Backend '.venv')
      }
    }
    & $VenvPython -m pip --version *> $null
    if ($LASTEXITCODE -ne 0) {
      & $VenvPython -m ensurepip --upgrade
      if ($LASTEXITCODE -ne 0) {
        python -m pip --python $VenvPython install --upgrade pip
        if ($LASTEXITCODE -ne 0) { throw 'Could not bootstrap pip in backend/.venv; repair the Python installation and rerun .\tasks.ps1 setup.' }
      }
    }
    & $VenvPython -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) { throw 'Python pip upgrade failed.' }
    & $VenvPython -m pip install -e "$Backend[dev]"
    if ($LASTEXITCODE -ne 0) { throw 'Backend dependency installation failed.' }
    npm --prefix (Join-Path $Root 'frontend') install
    if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' }
  }
  'test' { & $VenvPython -m pytest (Join-Path $Backend 'tests'); if ($LASTEXITCODE -ne 0) { throw 'Backend tests failed.' } }
  'smoke' { & $VenvPython (Join-Path $Backend 'scripts\smoke_tests.py'); if ($LASTEXITCODE -ne 0) { throw 'Smoke suite failed.' } }
  'eval' { & $VenvPython (Join-Path $Backend 'scripts\evaluate.py') @TaskArgs; if ($LASTEXITCODE -ne 0) { throw 'Evaluation failed.' } }
  'api' { & $VenvPython -m uvicorn app.main:app --app-dir $Backend --reload }
  'frontend' { npm --prefix (Join-Path $Root 'frontend') run dev }
}

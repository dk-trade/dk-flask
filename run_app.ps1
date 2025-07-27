# run_app.ps1

$pythonVersion = "3.12.1"
$pythonInstallerUrl = "https://www.python.org/ftp/python/$pythonVersion/python-$pythonVersion-amd64.exe"
$venvDir = "py_env"

Write-Host "🔧 Starting Options Strategy App setup..." -ForegroundColor Cyan

# Step 1: Check Python
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    Write-Host "🐍 Python not found. Downloading Python $pythonVersion..." -ForegroundColor Yellow
    $installerPath = "$env:TEMP\python-$pythonVersion.exe"
    Invoke-WebRequest $pythonInstallerUrl -OutFile $installerPath

    Write-Host "📦 Installing Python silently..."
    Start-Process -FilePath $installerPath -ArgumentList "/quiet InstallAllUsers=1 PrependPath=1" -Wait

    # Reload shell to reflect new PATH
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine")
    $python = Get-Command python -ErrorAction SilentlyContinue
    if (-not $python) {
        Write-Host "❌ Python install failed. Please install manually from https://www.python.org/" -ForegroundColor Red
        exit 1
    }
}

# Step 2: Create or reuse virtual environment
if (-not (Test-Path "$venvDir/Scripts/Activate.ps1")) {
    Write-Host "📁 Creating virtual environment in '$venvDir'..."
    python -m venv $venvDir
} else {
    Write-Host "✅ Reusing existing virtual environment '$venvDir'..."
}

# Step 3: Activate virtual environment
Write-Host "⚙️ Activating environment..."
. "$venvDir/Scripts/Activate.ps1"

# Step 4: Upgrade pip + install requirements
Write-Host "⬆️ Upgrading pip..."
python -m pip install --upgrade pip

Write-Host "📦 Installing required packages from requirements.txt..."
pip install -r requirements.txt

# Step 5: Ensure .env file exists
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "`n⚠️ A '.env' file has been created for you." -ForegroundColor Yellow
    Write-Host "✏️  Please edit '.env' and enter your Schwab credentials before continuing."
    Pause
}

# Step 6: Run the app
Write-Host "`n🚀 Starting server at http://127.0.0.1:5000 ..."
python app.py

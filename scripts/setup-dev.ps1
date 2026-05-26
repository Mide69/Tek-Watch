# Tek Watch - Development Environment Setup Script (PowerShell)
# This script sets up the local development environment on Windows

Write-Host "🚀 Tek Watch - Development Setup" -ForegroundColor Cyan
Write-Host "====================================" -ForegroundColor Cyan
Write-Host ""

# Check prerequisites
Write-Host "📋 Checking prerequisites..." -ForegroundColor Yellow

$prerequisites = @{
    "Docker" = { docker --version }
    "Python" = { python --version }
    "Node.js" = { node --version }
}

$allPrerequisitesMet = $true

foreach ($prereq in $prerequisites.Keys) {
    try {
        $null = & $prerequisites[$prereq] 2>&1
        Write-Host "✅ $prereq found" -ForegroundColor Green
    }
    catch {
        Write-Host "❌ $prereq is not installed" -ForegroundColor Red
        $allPrerequisitesMet = $false
    }
}

if (-not $allPrerequisitesMet) {
    Write-Host ""
    Write-Host "Please install missing prerequisites:" -ForegroundColor Red
    Write-Host "  - Docker Desktop: https://www.docker.com/products/docker-desktop"
    Write-Host "  - Python 3.12+: https://www.python.org/downloads/"
    Write-Host "  - Node.js 18+: https://nodejs.org/"
    exit 1
}

Write-Host ""

# Create .env.local if it doesn't exist
if (-not (Test-Path ".env.local")) {
    Write-Host "📝 Creating .env.local from template..." -ForegroundColor Yellow
    Copy-Item ".env.example" ".env.local"
    Write-Host "✅ Created .env.local - please edit with your configuration" -ForegroundColor Green
    Write-Host ""
}
else {
    Write-Host "✅ .env.local already exists" -ForegroundColor Green
    Write-Host ""
}

# Setup Python virtual environments
Write-Host "🐍 Setting up Python virtual environments..." -ForegroundColor Yellow

# Agent
if (-not (Test-Path "agent\venv")) {
    Write-Host "  Creating agent venv..." -ForegroundColor Gray
    Push-Location agent
    python -m venv venv
    .\venv\Scripts\Activate.ps1
    python -m pip install --upgrade pip
    pip install -r requirements.txt
    deactivate
    Pop-Location
    Write-Host "  ✅ Agent venv created" -ForegroundColor Green
}
else {
    Write-Host "  ✅ Agent venv already exists" -ForegroundColor Green
}

# Ingest Consumer
if (-not (Test-Path "ingest-consumer\venv")) {
    Write-Host "  Creating ingest-consumer venv..." -ForegroundColor Gray
    Push-Location ingest-consumer
    python -m venv venv
    .\venv\Scripts\Activate.ps1
    python -m pip install --upgrade pip
    pip install -r requirements.txt
    deactivate
    Pop-Location
    Write-Host "  ✅ Ingest consumer venv created" -ForegroundColor Green
}
else {
    Write-Host "  ✅ Ingest consumer venv already exists" -ForegroundColor Green
}

# API
if (-not (Test-Path "api\venv")) {
    Write-Host "  Creating API venv..." -ForegroundColor Gray
    Push-Location api
    python -m venv venv
    .\venv\Scripts\Activate.ps1
    python -m pip install --upgrade pip
    pip install -r requirements.txt
    deactivate
    Pop-Location
    Write-Host "  ✅ API venv created" -ForegroundColor Green
}
else {
    Write-Host "  ✅ API venv already exists" -ForegroundColor Green
}

Write-Host ""

# Setup Dashboard
if (Test-Path "dashboard\package.json") {
    Write-Host "📦 Installing Dashboard dependencies..." -ForegroundColor Yellow
    Push-Location dashboard
    if (-not (Test-Path "node_modules")) {
        npm install
        Write-Host "✅ Dashboard dependencies installed" -ForegroundColor Green
    }
    else {
        Write-Host "✅ Dashboard dependencies already installed" -ForegroundColor Green
    }
    Pop-Location
    Write-Host ""
}

# Setup Admin Portal (if it exists)
if (Test-Path "admin-portal\package.json") {
    Write-Host "📦 Installing Admin Portal dependencies..." -ForegroundColor Yellow
    Push-Location admin-portal
    if (-not (Test-Path "node_modules")) {
        npm install
        Write-Host "✅ Admin Portal dependencies installed" -ForegroundColor Green
    }
    else {
        Write-Host "✅ Admin Portal dependencies already installed" -ForegroundColor Green
    }
    Pop-Location
    Write-Host ""
}

# Pull Docker images
Write-Host "🐳 Pulling Docker images..." -ForegroundColor Yellow
docker-compose pull localstack
Write-Host "✅ Docker images pulled" -ForegroundColor Green
Write-Host ""

# Create necessary directories
Write-Host "📁 Creating directories..." -ForegroundColor Yellow
New-Item -ItemType Directory -Force -Path "logs" | Out-Null
New-Item -ItemType Directory -Force -Path "data" | Out-Null
Write-Host "✅ Directories created" -ForegroundColor Green
Write-Host ""

Write-Host "✨ Setup complete!" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  1. Edit .env.local with your AWS credentials and configuration"
Write-Host "  2. Start services: docker-compose up"
Write-Host "  3. Access API docs: http://localhost:8000/docs"
Write-Host "  4. Access Dashboard: http://localhost:3000"
Write-Host ""
Write-Host "For more information, see:" -ForegroundColor Cyan
Write-Host "  - README.md - Project overview"
Write-Host "  - DEVELOPMENT.md - Development guide"
Write-Host "  - PROJECT_STATUS.md - Current status"
Write-Host ""
Write-Host "Happy coding! 🎉" -ForegroundColor Magenta

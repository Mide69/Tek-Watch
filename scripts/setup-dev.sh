#!/bin/bash

# Tribe Watch - Development Environment Setup Script
# This script sets up the local development environment

set -e

echo "🚀 Tribe Watch - Development Setup"
echo "===================================="
echo ""

# Check prerequisites
echo "📋 Checking prerequisites..."

if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker Desktop."
    exit 1
fi

if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.12+."
    exit 1
fi

if ! command -v node &> /dev/null; then
    echo "❌ Node.js is not installed. Please install Node.js 18+."
    exit 1
fi

echo "✅ All prerequisites found"
echo ""

# Create .env.local if it doesn't exist
if [ ! -f .env.local ]; then
    echo "📝 Creating .env.local from template..."
    cp .env.example .env.local
    echo "✅ Created .env.local - please edit with your configuration"
    echo ""
else
    echo "✅ .env.local already exists"
    echo ""
fi

# Setup Python virtual environments
echo "🐍 Setting up Python virtual environments..."

# Agent
if [ ! -d "agent/venv" ]; then
    echo "  Creating agent venv..."
    cd agent
    python3 -m venv venv
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
    deactivate
    cd ..
    echo "  ✅ Agent venv created"
else
    echo "  ✅ Agent venv already exists"
fi

# Ingest Consumer
if [ ! -d "ingest-consumer/venv" ]; then
    echo "  Creating ingest-consumer venv..."
    cd ingest-consumer
    python3 -m venv venv
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
    deactivate
    cd ..
    echo "  ✅ Ingest consumer venv created"
else
    echo "  ✅ Ingest consumer venv already exists"
fi

# API
if [ ! -d "api/venv" ]; then
    echo "  Creating API venv..."
    cd api
    python3 -m venv venv
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
    deactivate
    cd ..
    echo "  ✅ API venv created"
else
    echo "  ✅ API venv already exists"
fi

echo ""

# Setup Dashboard
if [ -f "dashboard/package.json" ]; then
    echo "📦 Installing Dashboard dependencies..."
    cd dashboard
    if [ ! -d "node_modules" ]; then
        npm install
        echo "✅ Dashboard dependencies installed"
    else
        echo "✅ Dashboard dependencies already installed"
    fi
    cd ..
    echo ""
fi

# Setup Admin Portal (if it exists)
if [ -f "admin-portal/package.json" ]; then
    echo "📦 Installing Admin Portal dependencies..."
    cd admin-portal
    if [ ! -d "node_modules" ]; then
        npm install
        echo "✅ Admin Portal dependencies installed"
    else
        echo "✅ Admin Portal dependencies already installed"
    fi
    cd ..
    echo ""
fi

# Pull Docker images
echo "🐳 Pulling Docker images..."
docker-compose pull localstack
echo "✅ Docker images pulled"
echo ""

# Create necessary directories
echo "📁 Creating directories..."
mkdir -p logs
mkdir -p data
echo "✅ Directories created"
echo ""

echo "✨ Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Edit .env.local with your AWS credentials and configuration"
echo "  2. Start services: docker-compose up"
echo "  3. Access API docs: http://localhost:8000/docs"
echo "  4. Access Dashboard: http://localhost:3000"
echo ""
echo "For more information, see:"
echo "  - README.md - Project overview"
echo "  - DEVELOPMENT.md - Development guide"
echo "  - PROJECT_STATUS.md - Current status"
echo ""
echo "Happy coding! 🎉"

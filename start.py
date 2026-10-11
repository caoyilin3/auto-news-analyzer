#!/usr/bin/env python3
"""
AutoNewsAnalyzer - Main Startup Script
Simplified version supporting multiple startup modes
"""

import os
import sys
import argparse
import subprocess
from pathlib import Path

def print_banner():
    """Print startup banner"""
    print("╔══════════════════════════════════════════════════════════╗")
    print("║                AutoNewsAnalyzer v2.0                    ║")
    print("║        Self-Evolving AI-Powered News Analysis System     ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print()

def check_environment():
    """Check runtime environment"""
    print("🔍 Checking runtime environment...")
    
    # Check Python version
    if sys.version_info < (3, 8):
        print(f"❌ Python 3.8+ required, current version: {sys.version}")
        return False
    
    # Check project files
    required_files = ["main.py", "requirements.txt"]
    for file in required_files:
        if not Path(file).exists():
            print(f"❌ Missing file: {file}")
            return False
    
    print("✅ Environment check passed")
    return True

def run_setup():
    """Run project setup"""
    print("🛠️  Running project setup...")
    
    # Create necessary directories
    directories = [
        "data/raw", "data/processed", "data/knowledge_base", "data/logs",
        "config", "tests", "docs"
    ]
    
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
        print(f"  ✅ Created directory: {directory}")
    
    # Create configuration file
    config_template = """
# Development environment configuration
mode: development
debug: true
log_level: DEBUG

data_sources:
  - name: mock
    type: mock
    enabled: true
    
credibility:
  min_score: 0.5
  
knowledge:
  extractors: [financial, technical, market]
  
evolution:
  enabled: true
"""
    
    config_file = Path("config/development.yaml")
    if not config_file.exists():
        config_file.parent.mkdir(exist_ok=True)
        config_file.write_text(config_template.strip())
        print("  ✅ Created configuration file: config/development.yaml")
    
    print("✅ Project setup completed")

def install_dependencies():
    """Install dependencies"""
    print("📦 Installing dependencies...")
    
    try:
        # Install basic dependencies
        subprocess.run([sys.executable, "-m", "pip", "install", 
                       "-r", "requirements.txt"], check=True)
        
        # Install spacy model
        print("  📥 Downloading language model...")
        subprocess.run([sys.executable, "-m", "spacy", 
                       "download", "en_core_web_sm"], 
                      capture_output=True)
        
        print("✅ Dependencies installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Dependency installation failed: {e}")
        return False

def run_development():
    """Run in development mode"""
    print("🚀 Starting development mode...")
    subprocess.run([sys.executable, "main.py", "--mode", "development"])

def run_production():
    """Run in production mode"""
    print("🏭 Starting production mode...")
    subprocess.run([sys.executable, "main.py", "--mode", "production"])

def run_test():
    """Run tests"""
    print("🧪 Running tests...")
    subprocess.run([sys.executable, "-m", "pytest", "tests/", "-v"])

def run_api():
    """Start API server"""
    print("🌐 Starting API server...")
    subprocess.run([sys.executable, "main.py", "api", "--port", "8080"])

def run_cli():
    """Start command line interface"""
    print("💻 Starting command line interface...")
    subprocess.run([sys.executable, "main.py", "cli"])

def show_help():
    """Display help information"""
    print("""
Usage:
    python start.py [command] [arguments]

Commands:
    setup      - Set up project environment
    dev        - Run in development mode
    prod       - Run in production mode
    test       - Run tests
    api        - Start API server
    cli        - Start command line interface
    check      - Check environment
    help       - Display this help

Examples:
    python start.py setup    # Initial setup
    python start.py dev      # Development mode
    python start.py test     # Run tests
    python start.py api      # Start API server
    """)

def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description="AutoNewsAnalyzer Startup Script",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        "command",
        nargs="?",
        default="help",
        choices=["setup", "dev", "prod", "test", "api", "cli", "check", "help"],
        help="Command to execute"
    )
    
    args = parser.parse_args()
    
    print_banner()
    
    if args.command == "setup":
        if check_environment():
            run_setup()
            install_dependencies()
    elif args.command == "dev":
        if check_environment():
            run_development()
    elif args.command == "prod":
        if check_environment():
            run_production()
    elif args.command == "test":
        if check_environment():
            run_test()
    elif args.command == "api":
        if check_environment():
            run_api()
    elif args.command == "cli":
        if check_environment():
            run_cli()
    elif args.command == "check":
        check_environment()
    elif args.command == "help":
        show_help()
    else:
        show_help()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Program interrupted")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
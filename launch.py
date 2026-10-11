#!/usr/bin/env python3
"""
AutoNewsAnalyzer - 快速启动脚本
一键启动所有必要服务
"""

import os
import sys
import subprocess
import threading
import time
from pathlib import Path

class ServiceManager:
    """服务管理器"""
    
    def __init__(self):
        self.services = {}
        self.running = False
        
    def start_service(self, name, command, env=None):
        """启动服务"""
        print(f"🚀 启动 {name}...")
        
        env_vars = os.environ.copy()
        if env:
            env_vars.update(env)
        
        try:
            process = subprocess.Popen(
                command,
                shell=True,
                env=env_vars,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            self.services[name] = process
            
            # 启动监控线程
            thread = threading.Thread(
                target=self._monitor_service,
                args=(name, process)
            )
            thread.daemon = True
            thread.start()
            
            print(f"✅ {name} 已启动 (PID: {process.pid})")
            return True
            
        except Exception as e:
            print(f"❌ 启动 {name} 失败: {e}")
            return False
    
    def _monitor_service(self, name, process):
        """监控服务"""
        stdout, stderr = process.communicate()
        
        if process.returncode != 0:
            print(f"⚠️  {name} 异常退出，返回码: {process.returncode}")
            if stderr:
                print(f"   错误信息: {stderr[:200]}")
    
    def stop_all(self):
        """停止所有服务"""
        print("\n🛑 正在停止所有服务...")
        
        for name, process in self.services.items():
            if process.poll() is None:  # 进程还在运行
                print(f"  停止 {name}...")
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
        
        print("✅ 所有服务已停止")

def check_dependencies():
    """检查依赖"""
    print("🔍 检查依赖...")
    
    try:
        import yaml
        import flask
        import requests
        import pandas
        import numpy
        import spacy
        
        print("✅ 所有Python依赖已安装")
        return True
        
    except ImportError as e:
        print(f"❌ 缺少依赖: {e}")
        print("   请运行: pip install -r requirements.txt")
        return False

def setup_environment():
    """设置环境"""
    print("🛠️  设置环境...")
    
    # 创建目录
    directories = [
        "data/raw", "data/processed", "data/knowledge_base",
        "data/logs", "config", "deployments"
    ]
    
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
        print(f"  ✅ 创建: {directory}")
    
    # 创建默认配置文件
    config_content = """
# AutoNewsAnalyzer 配置文件
system:
  name: "AutoNewsAnalyzer"
  version: "2.0.0"
  mode: "development"
  debug: true

database:
  postgres:
    host: "localhost"
    port: 5432
    database: "autonews"
  
  redis:
    host: "localhost"
    port: 6379

api:
  host: "0.0.0.0"
  port: 8080

logging:
  level: "INFO"
  file: "data/logs/system.log"
"""
    
    config_file = Path("config/development.yaml")
    if not config_file.exists():
        config_file.write_text(config_content.strip())
        print("  ✅ 创建配置文件")
    
    print("✅ 环境设置完成")

def start_development_stack():
    """启动开发栈"""
    print("\n🚀 启动开发栈...")
    
    manager = ServiceManager()
    
    # 1. 启动数据库
    manager.start_service(
        "PostgreSQL",
        "docker run --name autonews-db -p 5432:5432 -e POSTGRES_PASSWORD=postgres -d postgres:15"
    )
    
    time.sleep(3)  # 等待数据库启动
    
    # 2. 启动Redis
    manager.start_service(
        "Redis",
        "docker run --name autonews-cache -p 6379:6379 -d redis:7-alpine"
    )
    
    time.sleep(2)
    
    # 3. 启动主应用
    manager.start_service(
        "AutoNewsAnalyzer",
        f"{sys.executable} main.py --mode development"
    )
    
    # 4. 启动API服务器
    manager.start_service(
        "API Server",
        f"{sys.executable} main.py api --port 8080"
    )
    
    return manager

def start_monitoring_stack():
    """启动监控栈"""
    print("\n📊 启动监控服务...")
    
    manager = ServiceManager()
    
    # 启动Grafana
    manager.start_service(
        "Grafana",
        "docker run --name autonews-grafana -p 3000:3000 -d grafana/grafana:latest"
    )
    
    # 启动Prometheus
    manager.start_service(
        "Prometheus",
        "docker run --name autonews-prometheus -p 9090:9090 -v $(pwd)/deployments/prometheus.yml:/etc/prometheus/prometheus.yml -d prom/prometheus:latest"
    )
    
    return manager

def interactive_menu():
    """交互式菜单"""
    print("╔══════════════════════════════════════════════════════════╗")
    print("║                AutoNewsAnalyzer v2.0                    ║")
    print("║              🚀 一键启动管理界面                        ║")
    print("╚══════════════════════════════════════════════════════════╝")
    
    while True:
        print("\n" + "="*60)
        print("请选择启动模式:")
        print("  1. 🛠️  环境设置")
        print("  2. 🚀 开发模式 (主应用 + 数据库)")
        print("  3. 📊 完整模式 (开发 + 监控)")
        print("  4. 🧪 测试模式")
        print("  5. 🔍 健康检查")
        print("  6. ❌ 退出")
        print("="*60)
        
        try:
            choice = input("\n请输入选择 (1-6): ").strip()
            
            if choice == "1":
                setup_environment()
            elif choice == "2":
                if check_dependencies():
                    manager = start_development_stack()
                    input("\n⏸️  按回车键停止所有服务...")
                    manager.stop_all()
            elif choice == "3":
                if check_dependencies():
                    dev_manager = start_development_stack()
                    time.sleep(3)
                    mon_manager = start_monitoring_stack()
                    
                    print("\n🌐 服务访问地址:")
                    print("  主应用: http://localhost:8080")
                    print("  Grafana: http://localhost:3000 (admin/admin)")
                    print("  Prometheus: http://localhost:9090")
                    
                    input("\n⏸️  按回车键停止所有服务...")
                    dev_manager.stop_all()
                    mon_manager.stop_all()
                    
            elif choice == "4":
                subprocess.run([sys.executable, "-m", "pytest", "tests/", "-v"])
            elif choice == "5":
                check_dependencies()
            elif choice == "6":
                print("\n👋 再见！")
                break
            else:
                print("❌ 无效选择")
                
        except KeyboardInterrupt:
            print("\n\n🛑 操作已取消")
            break
        except Exception as e:
            print(f"❌ 错误: {e}")

def main():
    """主函数"""
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "setup":
            setup_environment()
        elif command == "dev":
            if check_dependencies():
                manager = start_development_stack()
                try:
                    while True:
                        time.sleep(1)
                except KeyboardInterrupt:
                    manager.stop_all()
        elif command == "full":
            if check_dependencies():
                dev_manager = start_development_stack()
                time.sleep(3)
                mon_manager = start_monitoring_stack()
                
                try:
                    while True:
                        time.sleep(1)
                except KeyboardInterrupt:
                    dev_manager.stop_all()
                    mon_manager.stop_all()
        elif command == "test":
            subprocess.run([sys.executable, "-m", "pytest", "tests/", "-v"])
        else:
            print(f"未知命令: {command}")
            print("可用命令: setup, dev, full, test")
    else:
        interactive_menu()

if __name__ == "__main__":
    main()
# 项目结构

```text
AutoNewsAnalyzer/
│
├── README.md                          # 项目总览文档
├── LICENSE                            # Apache 2.0 开源许可证
├── NOTICE                             # 原创声明
├── .gitignore                         # Git 忽略文件
├── .env.example                       # 环境变量示例
├── pyproject.toml                     # Python 项目配置
├── requirements.txt                   # 生产环境依赖
├── requirements-dev.txt               # 开发环境依赖
├── setup.cfg                          # 配置工具设置
├── docker-compose.yml                 # Docker Compose 配置
│
├── main.py                            # 程序主入口
├── run_pipeline.py                    # 流水线入口
├── launch.py                          # 高级启动脚本
├── start.py                           # Python 启动脚本
├── start.bat                          # Windows 启动脚本
├── 如何加API.md                        # API 配置指南
│
├── config/                            # 配置中心
│   ├── base.py                        # 基础配置类
│   ├── development.yaml               # 开发环境配置
│   ├── production.yaml                # 生产环境配置
│   └── testing.yaml                   # 测试环境配置
│
├── src/                               # 源代码目录（核心）
│   ├── core/                          # 核心系统架构
│   ├── data_acquisition/              # 数据获取层（感知）
│   ├── credibility/                   # 可信度评估层（免疫）
│   ├── knowledge/                     # 知识管理层（大脑）
│   ├── evolution/                     # 自主进化层
│   └── memory/                        # 记忆管理
│
├── docs/                              # 项目文档
│   ├── credibility.md                 # 可信度评估模块设计文档
│   ├── extraction.md                  # 知识提取模块设计文档
│   ├── lifecycle.md                   # 生命周期管理模块设计文档
│   └── system-report.md               # 系统设计报告
│
├── scripts/                           # 实用脚本
├── tests/                             # 测试目录
└── patent_evidence/                   # 专利证据材料

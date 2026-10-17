```
autonews_clean/
├── config/                          # 配置模块
│   ├── schema/                      # 配置模式定义
│   │   ├── crawler.py               # 爬虫配置模式
│   │   ├── credibility.py           # 可信度配置模式
│   │   ├── knowledge.py             # 知识配置模式
│   │   └── __init__.py
│   ├── base.py                      # 配置基类
│   ├── development.yaml             # 开发环境配置
│   ├── production.yaml              # 生产环境配置
│   ├── testing.yaml                 # 测试环境配置
│   └── __init__.py
├── docs/                            # 文档目录（当前为空）
├── patent_evidence/                 # 专利证据目录（当前为空）
├── scripts/                         # 脚本目录
│   ├── run_analyzer.py              # 运行分析器脚本
│   └── setup.py                     # 环境安装脚本
├── src/                             # 主源代码包
│   ├── core/                        # 核心引擎与调度
│   │   ├── engine.py                # 引擎
│   │   ├── feedback_loop.py         # 反馈循环
│   │   ├── lifecycle.py             # 生命周期管理
│   │   ├── orchestrator.py          # 编排器
│   │   ├── state_manager.py         # 状态管理
│   │   └── __init__.py
│   ├── credibility/                 # 可信度评估
│   │   ├── adaptive_validator.py    # 自适应校验器
│   │   ├── base_validator.py        # 校验器基类
│   │   ├── evaluator.py             # 评估器
│   │   ├── rule_based_validator.py  # 基于规则的校验器
│   │   └── __init__.py
│   ├── data_acquisition/            # 数据采集
│   │   ├── adaptive_crawler.py      # 自适应爬虫
│   │   ├── api_client.py            # API 客户端
│   │   ├── base_crawler.py          # 爬虫基类
│   │   ├── manager.py               # 采集管理器
│   │   ├── mock_crawler.py          # 模拟爬虫（测试用）
│   │   ├── web_scraper.py           # 网页抓取器
│   │   └── __init__.py
│   ├── evolution/                   # 进化学习
│   │   ├── learning_planner.py      # 学习规划器
│   │   ├── manager.py               # 进化管理器
│   │   ├── meta_cognitive.py        # 元认知模块
│   │   ├── safety_controller.py     # 安全控制器
│   │   └── __init__.py
│   ├── interfaces/                  # 对外接口
│   │   ├── reporter.py              # 报告器
│   │   └── __init__.py
│   ├── knowledge/                   # 知识图谱
│   │   ├── extractors/              # 知识抽取器
│   │   │   ├── base_extractor.py    # 抽取器基类
│   │   │   ├── ner_extractor.py     # 命名实体识别
│   │   │   ├── relation_extractor.py# 关系抽取
│   │   │   └── __init__.py
│   │   ├── graph/                   # 知识图谱
│   │   │   ├── knowledge_graph.py   # 知识图谱实现
│   │   │   └── __init__.py
│   │   ├── storage/                 # 知识存储
│   │   │   ├── base_storage.py      # 存储基类
│   │   │   ├── example_usage.py     # 使用示例
│   │   │   ├── graph_storage.py     # 图谱存储
│   │   │   ├── hybrid_storage.py    # 混合存储
│   │   │   ├── memory_storage.py    # 内存存储
│   │   │   ├── sql_storage.py       # SQL 存储
│   │   │   ├── vector_storage.py    # 向量存储
│   │   │   └── __init__.py
│   │   ├── utils/                   # 知识工具
│   │   │   └── __init__.py
│   │   ├── base.py                  # 知识基类
│   │   ├── manager.py               # 知识管理器
│   │   └── __init__.py
│   ├── memory/                      # 记忆管理
│   │   ├── example_usage.py         # 使用示例
│   │   ├── forgetting_algorithm.py  # 遗忘算法
│   │   ├── importance_evaluator.py  # 重要度评估
│   │   ├── manager.py               # 记忆管理器
│   │   ├── memory_manager.py        # 记忆管理实现
│   │   ├── retention_policy.py      # 保留策略
│   │   └── __init__.py
│   ├── patent_evidence/             # 专利证据
│   │   ├── collector.py             # 证据收集器
│   │   ├── manager.py               # 证据管理器
│   │   └── __init__.py
│   ├── utils/                       # 通用工具
│   │   ├── helpers.py               # 辅助函数
│   │   ├── llm_client.py            # LLM 客户端
│   │   ├── logger.py                # 日志模块
│   │   ├── metrics.py               # 指标模块
│   │   └── __init__.py
│   ├── version.py                   # 版本号
│   └── __init__.py
├── tests/                           # 测试目录
│   ├── test_engine.py               # 引擎测试
│   └── __init__.py
├── .env                             # 环境变量配置（含敏感信息）
├── .env.example                     # 环境变量示例
├── .gitignore                       # Git 忽略规则
├── docker-compose.yml               # Docker 编排配置
├── launch.py                        # 启动入口
├── main.py                          # 主程序入口
├── pyproject.toml                   # 项目依赖与构建配置
├── README.md                        # 项目说明
├── requirements-dev.txt             # 开发依赖
├── requirements.txt                 # 运行依赖
├── run_pipeline.py                  # 流水线运行脚本
├── setup.cfg                        # 安装配置
├── start.bat                        # Windows 启动批处理
├── start.py                         # 启动脚本
└── 如何加API.md                     # 添加 API 说明文档
```

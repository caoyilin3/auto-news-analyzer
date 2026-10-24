# AutoNewsAnalyzer v2.0

🚀 一个具备自主进化能力的 AI 驱动新闻分析系统

[![Python Version](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://www.apache.org/licenses/LICENSE-2.0)
[![Code Style](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

## 📖 概述

AutoNewsAnalyzer 是一个具备自主进化能力的 AI 系统，能够自动采集、评估、学习新闻信息，并持续优化自身能力。系统借鉴生命体“感知-学习-净化”的生命循环逻辑，实现从信息采集到知识代谢的全流程自动化。

### ✨ 核心特性

- **🧠 自主进化（闭环）**：真实指标评估 → 学习计划 → 安全审查 → **参数落地** → 证据留存
- **📊 智能评估**：五维加权可信度模型 + 双阈值决策，阈值随运行效果自适应
- **🔍 知识提取**：jieba 实体识别 + 模式词典关系抽取，可选大模型三元组增强
- **🔄 动态适应**：反馈总线汇总每周期指标，驱动下一周期的策略调整
- **⚙️ 并行编排**：DAG 调度器按依赖并发执行工作流（进化与记忆可并行）
- **📏 长期效果评估**：周期指标落盘为数据集，自动给出趋势、参数漂移与可复核结论
- **🏗️ 模块化架构**：分层设计 + 生命周期管理 + 状态持久化
- **📈 可观测**：Prometheus `/metrics` 端点 + JSON 运行报告 + 专利证据链

## 🚀 快速开始

### 环境要求

- **Python**：3.10 或更高版本（`numpy>=1.26` 与 `pandas>=2.1` 已不支持 3.8）
- **内存**：建议 8GB+ RAM
- **操作系统**：Windows / Linux / macOS

### 安装

```bash
# 1. 创建虚拟环境（推荐）
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux / macOS
source .venv/bin/activate

# 2. 安装依赖（主流程最小集，推荐）
pip install -r requirements-core.txt

# 需要 spaCy / torch / transformers 等可选增强能力时
# pip install -r requirements.txt

# 3. 复制环境变量模板（可选：只有启用大模型时才需要填 Key）
# Windows  ->  copy .env.example .env
# Linux/macOS -> cp .env.example .env
```

### 运行

```bash
python main.py                        # 运行一个分析周期
python main.py --cycles 5             # 连续运行 5 个周期
python main.py --mock-count 10        # 覆盖模拟新闻条数
python main.py --no-llm               # 只用规则提取
python main.py --mode production      # 使用 config/production.yaml（真实 RSS 源）
python main.py --config my.yaml       # 指定配置文件
python main.py --continuous --interval 600   # 常驻：每 10 分钟一个周期
python main.py --metrics-port 9090    # 同时暴露 Prometheus 指标端点
python main.py --evidence-report      # 汇总专利证据并输出 JSON（不跑分析）
python main.py --verbose              # 详细日志
```

### 命令行参数

| 参数 | 说明 |
| --- | --- |
| `--mode {development,production,testing}` | 选择 `config/<mode>.yaml` |
| `--config PATH` | 指定配置文件，覆盖 `--mode` |
| `--cycles N` | 周期数；常驻模式下不填表示无限循环 |
| `--mock-count N` | 覆盖模拟新闻条数 |
| `--mock / --no-mock` | 强制使用模拟 / 真实数据源 |
| `--no-llm` | 关闭大模型，只用规则提取 |
| `--continuous --interval S` | 常驻运行，周期间隔 S 秒 |
| `--metrics-port PORT` | 开启 Prometheus 指标端点 |
| `--evidence-report` | 只输出证据汇总 |
| `--evaluate` | 只输出长期学习效果评估 |
| `--evaluate-window N` | 评估窗口（最近 N 个周期，默认 50） |
| `--verbose` | 输出详细日志 |

### 配置大模型（可选）

系统默认走「模式词典 + jieba」的规则提取，**不配置密钥也能完整运行**。
如需启用 DeepSeek 三元组抽取，把密钥写进项目根目录的 `.env`（该文件已被 `.gitignore` 忽略）：

```
DEEPSEEK_API_KEY=sk-...
DEEPSEEK_MODEL=deepseek-chat
```

`.env` 由 `config.loader.load_env_file()` 自动加载——装了 `python-dotenv` 就用它，
没装也有内置的简单解析兜底。也可以直接用环境变量覆盖（优先级更高）：

```bash
# Windows PowerShell
$env:DEEPSEEK_API_KEY = "sk-..."
# Linux / macOS
export DEEPSEEK_API_KEY="sk-..."
```

启用前后对比（同样 6 篇模拟新闻、5 篇通过评估）：

| 模式 | 实体 | 关系 | LLM 三元组 |
| --- | --- | --- | --- |
| 规则提取（`--no-llm`） | 8 | 3 | 0 |
| DeepSeek 增强 | 52 | 25 | 22 |

> 每篇文章会发起 1 次大模型调用，注意额度消耗；单次失败会自动降级为规则提取，不影响流程。
> `--no-llm` 可随时强制关闭。

### 测试

```bash
python -m pytest tests/ -q
```

## 🧩 工作流与闭环

```
数据采集 → 可信度评估 → 知识提取 → 进化学习 → 记忆管理 → 报告生成
 (mock/真实)   (五维+双阈值)   (jieba+词典+LLM)  (评估→计划→落地)  (保留/遗忘)    (JSON)
                                              ↓
                         反馈总线 ← 状态持久化 → 专利证据（JSONL）
                                              ↓
                                  Prometheus /metrics（可选）
```

| 步骤 | 模块 | 说明 |
| --- | --- | --- |
| `data_acquisition` | `src/data_acquisition` | 模拟爬虫 / 自适应爬虫；返回**本周期**统计 |
| `credibility_assessment` | `src/credibility` | 来源、新鲜度、作者、内容、URL 五维加权 + 双阈值 |
| `knowledge_extraction` | `src/knowledge` | 实体识别 + 模式关系抽取 + 可选大模型增强 |
| `evolution_learning` | `src/evolution` | 元认知评估 → 学习计划 → 安全审查 → **参数调整** |
| `memory_management` | `src/memory` | 分类保留策略、衰减与遗忘 |
| `report_generation` | `src/interfaces` | 结构化运行报告（含本轮参数调整明细） |

### 进化闭环做了什么

1. **真实指标**：从本周期的决策分布、实体/关系产出、执行成功率计算 `learn_rate`、`reject_rate`、`extraction_yield` 等。
2. **学习计划**：元认知控制器 + 学习规划器据此生成目标与任务（不再是随机数）。
3. **安全审查**：安全控制器校验计划（操作类型、隐私、社会影响、资源占用）。
4. **参数落地**：把结论映射成**有界、可解释**的参数调整，例如
   `credibility.theta_high: 0.80 → 0.78`（原因：learn 决策占比低于目标区间）。
5. **证据留存**：调整写入 `data/evolution_history.jsonl` 与 `data/patent_evidence/evolution_*.jsonl`，
   参数值通过状态管理持久化，**跨进程累积**。

可调参数（由引擎在初始化时注册）：`credibility.theta_high`、`credibility.theta_low`、
`extraction.relation_min_confidence`。

### 执行器：顺序 / 并行

工作流由 `src/core/orchestrator.py` 的 DAG 调度器执行，默认最多 2 个任务并发：

```yaml
# config/*.yaml
workflow:
  executor: orchestrator   # 或 sequential（回退到单线程顺序执行）
  max_workers: 2
```

- `knowledge_extraction` 完成后，`evolution_learning` 与 `memory_management` 互不依赖，会**并行**执行；
- `report_generation` 显式依赖二者（以及提取步骤），保证报告拿到完整数据；
- 任务级 `timeout` / `max_retries` 由调度器落实，失败会向下游传播。

### 长期学习效果评估

每个周期的指标与参数都会写入数据集，并据此给出趋势判定：

```bash
python main.py --evaluate            # 查看评估结果
python main.py --evaluate-window 20  # 只看最近 20 个周期
```

产物：

| 文件 | 内容 |
| --- | --- |
| `data/cycle_metrics.jsonl` | 每周期：指标、调整前后参数、本轮变更 |
| `data/cycle_metrics.csv` | 同一数据集的表格版（Excel/pandas 直接出图） |
| `data/metrics/engine_metrics.json` | `utils.metrics` 收集的周期级指标序列 |

评估输出包含 `trends`（前后半段均值与方向）、`parameter_drift`（参数首末值与漂移量）、
`verdict`（improving / stable / degrading）以及逐条可复算的 `insights`。

## 📈 监控

```bash
python main.py --continuous --metrics-port 9090
curl http://127.0.0.1:9090/metrics
```

输出示例（Prometheus 文本格式）：

```
autonews_cycles_total 3
autonews_theta_high 0.76
autonews_learn_rate 0.5
autonews_entities_total 24
```

`deployments/prometheus.yml` 已配置好对该端点的抓取，`docker-compose.yml`
会一并拉起 Prometheus 与 Grafana。

## 🐳 容器部署

```bash
docker compose up -d --build
# 应用:      python main.py --mode production --continuous --interval 3600 --metrics-port 9090
# 指标:      http://localhost:9090/metrics
# Prometheus: http://localhost:9091
# Grafana:    http://localhost:3000 (admin/admin)
```

镜像基于 `requirements-core.txt`（主流程最小依赖），报告与状态挂载在 `./output`、`./data`。

> **验证方式**：本机未安装 Docker，因此没有执行 `docker build`；取而代之的是
> ① 在干净虚拟环境中仅用 `requirements-core.txt` 完成安装，并跑通容器 `CMD` 等价命令；
> ② `tests/test_deployment.py` 静态校验 Dockerfile 的 COPY 目标、compose 挂载路径、
> Prometheus 抓取目标与最小依赖清单是否一致。有 Docker 的机器上仍建议执行一次 `docker compose up --build`。

## 📁 目录结构

```
├── config/                 # YAML 配置 + loader + pydantic 模式
│   ├── loader.py           # YAML → 引擎配置（命令行/环境变量覆盖）
│   └── {development,production,testing}.yaml
├── src/
│   ├── core/               # 引擎、DAG 调度器、反馈循环、状态/生命周期管理
│   ├── data_acquisition/   # 数据采集层
│   ├── credibility/        # 可信度评估层
│   ├── knowledge/          # 知识提取、图谱与多后端存储
│   ├── evolution/          # 自主进化层（参数落地 + 长期效果评估）
│   ├── memory/             # 记忆与生命周期管理
│   ├── interfaces/         # 报告输出 + Prometheus 指标端点
│   ├── patent_evidence/    # 专利证据采集与汇总
│   └── utils/              # 日志、指标收集、LLM 客户端、控制台兼容
├── tests/                  # 单元 + 集成 + 部署校验（27 个用例）
├── deployments/            # prometheus.yml
├── data/                   # 运行期数据（运行时自动生成：状态、数据集、指标、证据）
├── output/                 # 运行报告（运行时自动生成）
├── Dockerfile
├── main.py                 # 主入口
└── run_pipeline.py         # 全链路冒烟测试
```

## ⚠️ 已知限制

- 并行度默认 2（进化与记忆并行）；若后续步骤进一步拆分，可调 `workflow.max_workers`。
- `data/cycle_metrics.*` 的趋势判定是**描述性统计**（前后半段均值、参数漂移），
  不等于因果归因；样本量很小时 `verdict` 只作参考。
- 生产模式会访问真实 RSS 源，受网络与站点可用性影响；离线环境请使用默认的 development/testing 模式。
- 本机无 Docker，容器镜像只做到了「依赖与命令在干净环境可复现 + 部署文件静态一致」，
  未做真实镜像构建与容器内运行验证。

## 📚 技术报告

本项目的核心算法设计详见以下技术报告：

- 《多维度可信度动态评估模块设计》
- 《模式词典驱动的知识提取模块设计》
- 《分类策略驱动的生命周期管理模块设计》

> 以上文档描述的是 AutoNewsAnalyzer 原型系统的模块设计与功能验证结果，用于工程参考与复现。

## 📄 许可证

本项目采用 **Apache License 2.0** 开源协议，允许自由使用、修改与分发（包含专利授权），
保留版权与署名声明即可。完整条款见 [LICENSE](LICENSE)，署名信息见 [NOTICE](NOTICE)。

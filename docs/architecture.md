# 架构说明

## 1. 分层结构

```
┌─────────────────────────────────────────────────────────────┐
│ 入口层     main.py / run_pipeline.py                          │
│            ├─ config/loader.py       YAML → 引擎配置           │
│            ├─ SystemLifecycleManager 有序初始化/启动/停止       │
│            └─ MetricsServer          Prometheus /metrics       │
├─────────────────────────────────────────────────────────────┤
│ 编排层     src/core/engine.py                                 │
│            ├─ WorkflowStep + 依赖检查 + 超时 + 重试退避         │
│            ├─ SystemStateManager     状态持久化（跨进程）        │
│            ├─ FeedbackLoopController 反馈总线                   │
│            └─ Orchestrator           可选的并行任务编排          │
├─────────────────────────────────────────────────────────────┤
│ 能力层     data_acquisition → credibility → knowledge          │
│            → evolution → memory → interfaces(reporter)         │
├─────────────────────────────────────────────────────────────┤
│ 留存层     output/*.json（报告）                                │
│            data/state/*.pkl（运行状态）                         │
│            data/evolution_history.jsonl（进化历史）             │
│            data/patent_evidence/*.jsonl（专利证据）             │
└─────────────────────────────────────────────────────────────┘
```

## 2. 一个周期里发生了什么

1. `data_acquisition`：按配置选择模拟或真实爬虫，返回本周期文章与本周期统计。
2. `credibility_assessment`：五维加权 `Stotal = Σ wi·Si`，双阈值判定 learn / review / reject。
3. `knowledge_extraction`：jieba 实体识别 + 模式词典关系抽取；可选 DeepSeek 三元组增强。
4. `evolution_learning`：
   - 元认知用**真实指标**（learn 占比、拦截率、抽取产出、执行成功率）做自我评估；
   - 学习规划器生成目标与任务；
   - 安全控制器审查计划；
   - 映射为有界参数调整并**立即生效**（见下节）。
5. `memory_management`：按分类保留策略写入记忆，应用衰减与容量清理。
6. `report_generation`：输出 JSON 报告（含本轮参数调整明细与反馈摘要）。

周期结束时引擎写入状态快照与专利证据；若开启 `--metrics-port`，指标可被 Prometheus 抓取。

## 3. 进化闭环

```
指标 ──► 评估(SelfAssessment) ──► 学习计划(LearningPlan) ──► 安全审查
  ▲                                                              │
  │                                                              ▼
  └──────── 下一周期生效 ◄── 参数落地(有界/可解释) ◄── 变更提案(带证据)
                                   │
                                   ├─► data/evolution_history.jsonl
                                   ├─► data/patent_evidence/evolution_*.jsonl
                                   └─► data/state/engine_state.pkl（跨进程恢复）
```

当前可调参数：

| 参数 | 范围 | 步长 | 触发条件 |
| --- | --- | --- | --- |
| `credibility.theta_high` | 0.60–0.95 | 0.02 | learn 占比 < 50% → 放宽；拦截率 < 2% 且 learn > 90% → 收紧 |
| `credibility.theta_low` | 0.30–0.70 | 0.02 | 拦截率 > 50% → 放宽 |
| `extraction.relation_min_confidence` | 0.30–0.90 | 0.05 | 单篇关系产出 < 0.5 → 放宽 |

约束：`theta_high - theta_low ≥ 0.10`，每个参数每周期最多调整一次，每轮最多 3 项。

## 4. 执行器与并行调度

引擎有两种执行器，由 `workflow.executor` 决定：

| 值 | 行为 |
| --- | --- |
| `sequential` | 按步骤定义顺序串行执行（回退模式） |
| `orchestrator`（默认） | 由 `core/orchestrator.py` 按 DAG 依赖并发执行 |

调度器（`Orchestrator`）的关键点：

- **就绪即派发**：等待队列中依赖已满足的任务立即提交线程池，上限 `workflow.max_workers`；
- **依赖翻译**：任务定义里的依赖写的是任务名，创建时统一翻译成任务 ID；
- **失败传播**：依赖任务失败/超时/取消时，下游任务直接判定失败，不会永久自旋；
- **回调先于解锁**：`task_completed` 回调（引擎在这里合并步骤数据）执行完才允许下游启动，
  保证下游读到的是已合并的上游结果；
- **超时与重试**：到期的任务按 `max_retries` 重排，最终标记 `TIMEOUT`/`FAILED`。

当前工作流的并行点：`evolution_learning` 与 `memory_management` 都只依赖
`knowledge_extraction`，因此可并行；`report_generation` 依赖二者，最后执行。

## 5. 长期学习效果评估

```
每个周期 ──► data/cycle_metrics.jsonl ──► LearningEffectivenessEvaluator
                    │                              │
                    ├─► cycle_metrics.csv          ├─► trends（前后半段均值/方向）
                    │                              ├─► parameter_drift（首末差值）
                    └─► evaluation（写入报告）      ├─► verdict
                                                   └─► insights（逐条可复算）
```

- 记录时机：周期结束后由引擎写入，`tunables_before` 记录**周期开始前**的参数值，
  因此漂移量能覆盖第一轮调整（0.80 → 0.72，而不是 0.78 → 0.72）。
- 判定规则：`learn_rate` 后半段均值比前半段高 0.05 以上且拦截率未恶化 → `improving`；
  反之或拦截率上升 0.1 以上 → `degrading`；无调整 → `no_adaptation`。
- 这些洞察同时作为元认知的 insight provider，替代固定话术。

## 6. 可观测性

| 输出 | 位置 | 用途 |
| --- | --- | --- |
| 运行报告 | `output/report_*.json` | 每周期摘要、各阶段统计、参数调整、长期评估 |
| 进化历史 | `data/evolution_history.jsonl` | 长期对比（论文/答辩取数） |
| 周期数据集 | `data/cycle_metrics.jsonl` / `.csv` | 趋势分析、Excel 出图 |
| 采集指标 | `data/metrics/engine_metrics.json` | `utils.metrics` 的周期级序列 |
| 专利证据 | `data/patent_evidence/*.jsonl` | 创新点取证，`--evidence-report` 汇总 |
| 运行状态 | `data/state/engine_state.pkl` | 跨进程恢复指标与已调参数 |
| 指标端点 | `http://<host>:<port>/metrics` | Prometheus / Grafana |

## 7. 扩展点

- 新增可调参数：在 `SystemEngine._register_tunables()` 里 `evolution.register_tunable(...)`，
  并在 `EvolutionManager._plan_changes()` 中给出调整规则。
- 新增工作流步骤：在 `_define_workflow_steps()` 中追加 `WorkflowStep`，模块需暴露同步或异步函数。
- 调整并行度：`workflow.max_workers`；需要完全串行时把 `workflow.executor` 设为 `sequential`。
- 新增评估指标：在 `src/evolution/effectiveness.py` 的 `TRACKED_METRICS` 中登记，
  并在引擎的 `_record_cycle_dataset()` 里写入对应字段即可自动进入趋势分析。

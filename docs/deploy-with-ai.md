# 让 AI 自动部署（提示词 + 一键脚本）

本页给出一段可直接投喂给 AI Agent 的部署提示词，以及配套的幂等脚本。
脚本在 Windows / Linux 上都能用，**优先让 AI 调用脚本**，而不是由它自由拼命令——这样每次部署的结果一致、可验证。

- Windows：`scripts/deploy.ps1`
- Linux / macOS：`scripts/deploy.sh`

---

## 一、复制这段提示词

```text
# 任务
把 AutoNewsAnalyzer 部署到当前机器，并证明它能正常跑通。

# 角色
你是一名部署工程师。你只负责环境、依赖、配置、启动与验证，不修改业务逻辑。

# 仓库位置
优先在当前工作目录寻找 main.py / requirements-core.txt / src/；
找不到再询问用户路径（Windows 参考：D:\autonews_analyzer_full\autonews_analyzer_full）。

# 第一步：先侦察，再动手
先汇报以下事实（附命令与输出）：
1. 操作系统与架构
2. Python 版本（必须 >= 3.10）
3. 仓库完整性：main.py、requirements-core.txt、tests/、config/ 是否存在
4. 现状：是否已有 .venv、.env、以及是否已有实例在跑（端口 9090 / 9099）
5. 网络：pip 源是否可用；（可选）api.deepseek.com 是否可达

# 第二步：执行部署（优先用仓库自带脚本）
Windows:
  powershell -NoProfile -ExecutionPolicy Bypass -File scripts\deploy.ps1
Linux / macOS:
  bash scripts/deploy.sh

可选参数：
  -Full / --full        安装完整依赖（含 spacy、torch 等，体积大、耗时长）
  -Start / --start      部署完成后常驻启动并验证 /metrics
  -WithLlm / --with-llm 冒烟测试时调用大模型（会产生 API 费用；默认关闭）
  -SkipTests / --skip-tests  跳过 pytest（仅在已确认环境时使用）

脚本依次执行：环境检查 → 创建 .venv → 安装 requirements-core → 生成 .env
→ pytest → 冒烟运行 1 个周期 →（可选）常驻启动 + 指标端点验证。

# 硬性约束（违反即视为部署失败）
- 不得把 API Key 写进任何源码、测试、提交或日志；只允许写入 .env（已被 .gitignore 忽略）
- 不得覆盖已存在的 .env；不得把 .env 提交到版本库
- 不得修改 src/、config/、tests/ 下的任何文件来"让部署通过"
- 不得删除 data/、output/ 以外的文件；清理只允许发生在运行期产物上
- 需要安装系统级组件（Docker、Python、NSSM）、改防火墙或设开机自启时：
  先说明原因和影响，等待用户确认后再执行
- 每一步都必须给出「命令 + 关键输出」作为证据；禁止只回复"已完成"

# 验收标准（全部满足才算成功）
1. .venv 存在，且 python -m pytest tests/ -q 全部通过
2. python main.py --cycles 1 退出码为 0，output/ 下出现新的 report_*.json
3. 该报告 summary.articles_collected > 0，且 stages 齐全
4. 若启用常驻：curl http://127.0.0.1:<port>/metrics 返回 200 且包含 autonews_ 指标
5. 默认（--no-llm）模式下日志中没有 ERROR 级记录

# 失败处理（按表排查，不要跳过验证）
| 现象 | 处理 |
| --- | --- |
| ModuleNotFoundError | 确认使用的是 .venv 里的解释器；补装 requirements-core |
| pip 报 UnicodeDecodeError | requirements 文件编码问题（需 UTF-8 或带 coding 声明），用 .venv 的 python -m pip |
| pytest 失败 | 跑单个失败用例定位；严禁改测试或删测试 |
| 端口被占用 | 换 -MetricsPort / --port，或找出占用进程并询问是否停止 |
| LLM 401/402/超时 | 改用 --no-llm 降级，报告中 llm_triples=0，并在结论里写明降级原因 |
| Windows 中文乱码 | 用 PowerShell 7，或确保 .ps1 为 UTF-8 with BOM |
| 常驻进程随终端退出 | 交互环境用脚本 -Start 即可；服务器请改用 systemd / NSSM / Docker |

# 最终输出格式
1. 部署结果表：步骤 | 命令 | 结果 | 证据（关键输出片段）
2. 部署信息：项目路径、Python 版本、依赖模式（core/full）、启动与停止命令
3. 未解决项与风险（没有就写"无"）
4. 一句话结论：部署成功 / 部署失败（失败必须写明卡在哪一步、下一步建议）
```

---

## 二、脚本做了什么

| 步骤 | 行为 | 失败即中止 |
| --- | --- | --- |
| 0 环境检查 | 确认 Python ≥ 3.10 | 是 |
| 1 虚拟环境 | 不存在才创建 `.venv`（幂等） | 是 |
| 2 依赖 | 安装 `requirements-core.txt`（`--full` 时用 `requirements.txt`） | 是 |
| 3 配置 | 无 `.env` 时从 `.env.example` 复制；**绝不覆盖已有 `.env`** | 否 |
| 4 测试 | `pytest tests/ -q` | 是 |
| 5 冒烟 | `main.py --cycles 1 --no-llm`，并检查 `output/*.json` 是否生成 | 是 |
| 6 常驻（可选） | 后台启动 + 轮询 `/metrics`，PID 写入 `data/run.pid` | 仅告警 |

## 三、等价的手工命令

```bash
# Windows
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-core.txt
copy .env.example .env
.\.venv\Scripts\python.exe -m pytest tests/ -q
.\.venv\Scripts\python.exe main.py --cycles 1 --no-llm

# Linux / macOS
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-core.txt
cp .env.example .env
.venv/bin/python -m pytest tests/ -q
.venv/bin/python main.py --cycles 1 --no-llm
```

## 四、服务器常驻建议

脚本的 `--start` 适合交互式终端演示。生产环境建议交给进程管理器：

- **Linux**：写一个 `systemd` unit，`ExecStart=<repo>/.venv/bin/python main.py --mode production --continuous --metrics-port 9090`，
  配 `Restart=always`；
- **Windows**：用 NSSM 把同样的命令注册为服务；
- **容器**：仓库自带 `Dockerfile` 与 `docker-compose.yml`，`docker compose up -d --build` 即可，
  数据与报告挂载在 `./data`、`./output`。

## 五、停止与重启

```powershell
# 脚本启动的实例
Stop-Process -Id (Get-Content data\run.pid)   # Windows
kill "$(cat data/run.pid)"                     # Linux / macOS
```

```bash
# 重新部署（幂等，不会破坏已有 .env 与数据）
bash scripts/deploy.sh
```

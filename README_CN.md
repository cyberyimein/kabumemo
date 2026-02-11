# Kabumemo

## はじめに

笔者原本使用 notion 来记录交易，不难看出，笔者的需求和 notion 的功能并不匹配，在以前笔者只能用复杂的方式来兼容 notion 的格式。然而如今是 AI 的时代，一个 AI 连测试用例都会编写的时代，笔者尝试用 gpt5codex 来以 Vibe Coding 的方式编写了这个项目。

这个项目没有任何新意，仅仅是一个简单的 CRUD。然而这仅仅是笔者在周末玩游戏同时指挥 ai 编程的产物，成本仅是一点 token。也许将来，每个人都能将自己的独特需求实现为产品，并部署在云端或者个人服务器上。而 AI 与算力，会成为电力与自来水一样给与每一个人平等的力量来实现。

## Kabumemo 介绍

Kabumemo 是一个可以离线使用的股票交易簿，采用 **Vue 3 + Vite 前端** 和 **FastAPI 后端** 的本地化架构：

- **前端界面**：支持多标签页的仪表盘（交易、持仓、资金、纳税），可直接在浏览器完成录入与查询操作。
- **后端 API**：负责存储与业务规则校验，包含交易、资金组、纳税等核心功能，并暴露统一的 REST 接口。
- **数据存储**：JSON 文件是主数据源，所有写入会同时更新 `data/` 下的 JSON 与轻量级 SQLite 数据库 `kabumemo.db`，既保留可手动编辑的备份，也提供结构化查询能力。

仓库中已经集成「一键启动」批处理脚本与端到端删除交易功能，以下为完整的使用说明与能力概览。

## 目录结构

```plaintext
Kabumemo/
├── PLAN.md              # 规划与需求
├── README.md            # 使用说明（本文件）
├── backend/             # FastAPI 后端
│   ├── app/
│   │   ├── api/
│   │   ├── models/
│   │   ├── services/
│   │   └── storage/
│   ├── tests/           # pytest 用例
│   └── pyproject.toml   # 后端依赖定义
├── frontend/            # 预留给 Vue 前端
└── data/                # 本地数据文件与备份
```

## 快速启动

### 一键启动脚本（Windows）

仓库根目录提供 `start_kabumemo.bat`，双击或在命令行执行即可自动完成：

1. 检测/创建后端虚拟环境并安装依赖。
2. 在新窗口中运行 `uvicorn app.main:app --reload --host 127.0.0.1 --port 8000`。
3. 安装前端依赖（如缺失）并在新窗口启动 `npm run dev`。

> 提示：脚本采用 UTF-8 输出，若只需在命令行运行可使用 `start_kabumemo.bat --no-pause` 跳过最后的暂停提示。

### 模拟部署版启动脚本（Windows）

执行 `start_kabumemo_prod.bat` 可以模拟真实部署流程：

1. 检查/创建后端虚拟环境并安装依赖。
2. 若缺失 `node_modules` 则执行 `npm install`，随后运行 `npm run build` 生成 `frontend/dist`。
3. 以无自动重载模式启动 Uvicorn；FastAPI 会在 `/` 路径挂载 `frontend/dist`，同时保留 `/api` 接口。默认绑定地址为 `0.0.0.0`，方便同一局域网内其它设备访问，同时控制台仍会提示可点击的 `http://127.0.0.1:8000` 供本机调试。若需绑定到其他地址，可在运行前设置 `KABUMEMO_HOST`。

脚本结束后窗口会保持打开，以便查看日志；如需自动退出，可附加参数 `--no-pause`。

终止服务时直接在窗口按 `Ctrl+C`。再次运行脚本会在启动前重新构建静态资源。

### 手动启动后端

```bash
cd backend
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -e .
./.venv/Scripts/python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

如需自定义数据目录，设置 `KABUCOUNT_DATA_DIR` 环境变量即可：

```bash
set KABUCOUNT_DATA_DIR=D:\Kabumemo-data

# macOS / Linux
export KABUCOUNT_DATA_DIR="$HOME/kabumemo-data"
```

运行测试：

```bash
cd backend
./.venv/Scripts/python.exe -m pytest
```

### 手动启动前端

```bash
cd frontend
npm install
npm run dev
```

构建与检查：

```bash
npm run build   # 先执行 vue-tsc 类型检查再构建
npm run lint    # 可选：运行 ESLint
```

默认开发环境地址：前端 `http://localhost:5173`，后端 `http://127.0.0.1:8000`。

## Docker 部署（macOS 适用）

`backend/Dockerfile` 已加入仓库，可直接构建后端镜像。镜像默认把 JSON 与 SQLite 数据库写入 `/data`，在 macOS 上请务必通过 bind mount 把本地 `data/` 挂载进去，这样容器重启后数据才会保留。

```bash
cd backend
docker build -t kabumemo-backend .
docker run --rm -p 8000:8000 -v "$(pwd)/../data:/data" kabumemo-backend
```

若需在容器内执行一次性的 JSON → SQLite 导入，可运行：

```bash
docker run --rm -it -v "$(pwd)/../data:/data" kabumemo-backend \
  python scripts/import_json_to_sqlite.py --force
```

FastAPI 服务在容器内监听 `0.0.0.0:8000`，通过 `-p` 映射到宿主机。`../data` 挂载后，`transactions.json`、`funding_groups.json`、`tax_settlements.json` 与 `kabumemo.db` 会随容器同步更新。

## 后端 API 速览

| Method | Path                                   | 描述                                         |
| ------ | -------------------------------------- | -------------------------------------------- |
| GET    | `/api/health`                          | 健康检查                                     |
| GET    | `/api/transactions`                    | 列出全部交易                                 |
| POST   | `/api/transactions`                    | 新增交易，自动生成 UUID 并执行仓位校验       |
| PUT    | `/api/transactions/{transaction_id}`   | 更新指定交易，持续校验资金组与持仓余额       |
| DELETE | `/api/transactions/{transaction_id}`   | 删除指定交易，同时清理关联纳税记录           |
| GET    | `/api/positions`                       | 根据交易计算仓位（含多币种拆分）与已实现盈亏 |
| GET    | `/api/positions/history`               | 查询持仓 1 年日线与买卖点（后端取行情）      |
| GET    | `/api/funds`                           | 输出资金快照与通货汇总（含年度收益指标）     |
| GET    | `/api/funding-groups`                  | 列出资金组，首次启动自动创建 JPY/USD         |
| POST   | `/api/funding-groups`                  | 新增/覆盖资金组                              |
| PATCH  | `/api/funding-groups/{name}`           | 更新资金组的货币、初始资金或备注             |
| DELETE | `/api/funding-groups/{name}`           | 删除资金组（需至少保留一个）                 |
| POST   | `/api/funding-groups/{name}/capital`   | 为指定资金组追加资金，并指定生效日期         |
| POST   | `/api/tax/settlements`                 | 记录纳税结果（返回带 ID 的记录），同步资金组 |
| GET    | `/api/tax/settlements`                 | 查看全部纳税记录一览                         |
| PATCH  | `/api/tax/settlements/{settlement_id}` | 更新纳税金额、货币或汇率                     |
| DELETE | `/api/tax/settlements/{settlement_id}` | 删除纳税记录并恢复交易的纳税状态             |

所有接口均返回 JSON，错误响应统一包含 `detail` 字段。后端依靠 `tests/test_api.py` 覆盖交易买卖、纳税与删除等关键流程。

`GET /api/funds` 返回的对象包含两个字段：`funds`（每个资金组的快照）与 `aggregated`（按货币汇总的总览，包含当年/上一年收益率等指标），前端会同步展示两张表格。

## 前端功能概览

前端以 Tab 形式呈现主要功能：

- **交易表 (Trades)**
  - 新建或编辑买入/卖出交易，数量自动规范化，税务状态给出默认值，编辑时会显示可取消/保存的提示。
  - 行点击可回填表单；操作列提供编辑与删除按钮，均带二次确认以避免误操作。
  - 支持刷新按钮同步后端最新数据。
- **持仓表 (Positions)**：基于交易列表实时计算持仓数量、平均成本和已实现盈亏，并按币种拆分展示明细；支持单选查看 1 年日线与买卖点（ECharts）。
- **资金表 (Funds & Groups)**
  - 管理资金组（新增、修改、删除）并展示包含年度对比指标的资金快照。
  - 新增「通货汇总」视图，可快速对比不同货币下的总体资金、持仓成本与盈亏表现，内置 USD→JPY 汇率输入框，可即时把合并后的总览折算为日元。
  - 通过「追加资金」按钮录入新增资金，并可为资金设置未来生效日期；在生效前不会影响今年的收益率统计。
  - 资金页底部新增「资金追加记录」表格，分页呈现全部追加记录，并为未来生效的条目显示“待生效”标签，方便回溯审计。
  - 删除时会检查至少保留一个资金组，文案已国际化。
- **纳税 (Tax)**
  - 自动筛选未纳税的卖出交易。
  - 填写纳税金额/汇率后提交，后端会把交易税务状态改为已纳税并刷新资金快照。
  - 下方提供「已登记纳税」列表，可查看、编辑或删除既有纳税记录，操作完成后自动刷新资金与交易数据。

界面支持中/英/日三语言切换，通知栏会在数据刷新、创建、删除等操作后提示结果。

## 数据说明

- `transactions.json`：交易流水，后端在接收到首个请求时自动创建。
- `funding_groups.json`：资金组配置，初次运行会生成「JPY / USD」。
- `tax_settlements.json`：纳税记录，由纳税 API 自动维护。
- `capital_adjustments.json`：记录每个资金组的追加资金及生效日期。
- `kabumemo.db`：SQLite 镜像，与 JSON 文件保持完全同步，可用于结构化查询或第三方分析工具。删除该文件可触发 JSON -> SQLite 重新生成。
- `data/backups/`：预留备份目录，后续会提供导入导出脚本。

### 维护脚本

- `backend/scripts/import_json_to_sqlite.py`：升级到双存储结构后可执行一次，把现有 JSON 数据导入 SQLite；如需覆盖旧库可追加 `--force`。
- `backend/scripts/check_data_sync.py`：校验 JSON 与 SQLite 是否一致；检测到缺失或差异时会返回非零退出码，可结合 CI/定时任务使用。

示例命令（仓库根目录执行）：

```bash
python backend/scripts/import_json_to_sqlite.py --data-dir ./data
python backend/scripts/check_data_sync.py --data-dir ./data --verbose
```

## 后续规划

- 扩展交易功能：支持批量导入/导出与高级过滤。
- 增强测试矩阵：覆盖多币种、跨资金组的极端情形。
- 提供数据备份/恢复工具（CSV/ZIP）。
- 引入桌面快捷入口或单文件打包方案。

## 今日更新 · 2025-10-22

- **资金追加记录表**：后端开放 `/api/funding-groups/capital` 接口并完善测试，前端资金页新增分页表格与「待生效」标签，完整展示所有资金追加记录，方便追踪每一笔变动。
- **一轮收益率分析**：新增 `POST /api/transactions/round-yield` 接口与 `compute_round_trip_yield` 服务，自动匹配买卖交易并返回毛利、净利、税费影响与年化收益率；Pydantic 模型和后端测试同步扩充，覆盖成功与校验失败场景。
- **交易页增强**：引入「一轮收益」模式，提供多选复选框、实时汇总卡片、校验提示以及展示全部指标的弹窗；即便校验未通过也可点击计算按钮，警告会通过全局通知条统一显示。
- **体验与多语言打磨**：统一按钮尺寸和配色、重排提示卡片，并补齐中英日三语文案，确保只有在用户明确点击计算后才推送辅助提示。
- **质量保障**：后端运行 `pytest`，前端执行 `npm run build`（含 `vue-tsc` 类型检查），确保改动后的接口与构建流程稳定。

## 今日更新 · 2025-10-07

- **双存储上线**：`LocalDataRepository` 在 JSON 写入的同时同步刷新 SQLite，新增容错逻辑并提供直接读取 SQLite 的辅助方法。
- **脚本工具**：新增 `import_json_to_sqlite.py` 与 `check_data_sync.py`，分别用于一键导入和校验两边数据是否一致；pytest 用例覆盖 JSON/SQLite 的同步场景。
- **容器支持**：提供 `backend/Dockerfile` 与文档说明，确保在 macOS 上通过 Docker 跑后端时 `/data` 挂载即可保留 JSON 与 SQLite 文件。
- **文档与测试**：更新中英文 README，修正 `KABUCOUNT_DATA_DIR` 用法，测试中增加 SQLite 镜像一致性的断言。

### 2025-10-03

- **持仓分析升级**：后端 `analytics` 服务计算每个持仓的资金组拆分，`schemas` 与测试同步调整，保证旧有用例依旧可靠。
- **界面可视化**：持仓表支持展开查看资金组数量、成本与已实现盈亏，信息密度进一步提升。
- **全站分页**：新增 `usePagination` 组合式函数与 `PaginationControls` 组件，并在交易、持仓、资金、纳税四个 Tab 全部启用，默认每页 50 条，浏览超长列表也十分顺畅。
- **多语言同步**：补充中/英/日三语言的分页文案，保持界面一致性。
- **质量验证**：已运行 pytest 以及前端 `npm run build`，确保分析逻辑与构建流程均通过。

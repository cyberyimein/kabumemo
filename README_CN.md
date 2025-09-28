# Kabumemo

## はじめに

笔者原本使用 notion 来记录交易，不难看出，笔者的需求和 notion 的功能并不匹配，在以前笔者只能用复杂的方式来兼容 notion 的格式。然而如今是 AI 的时代，一个 AI 连测试用例都会编写的时代，笔者尝试用 gpt5codex 来以 Vibe Coding 的方式编写了这个项目。

这个项目没有任何新意，仅仅是一个简单的 CRUD。然而这仅仅是笔者在周末玩游戏同时指挥 ai 编程的产物，成本仅是一点 token。也许将来，每个人都能将自己的独特需求实现为产品，并部署在云端或者个人服务器上。而 AI 与算力，会成为电力与自来水一样给与每一个人平等的力量来实现。

## Kabumemo 介绍

Kabumemo 是一个可以离线使用的股票交易簿，采用 **Vue 3 + Vite 前端** 和 **FastAPI 后端** 的本地化架构：

- **前端界面**：支持多标签页的仪表盘（交易、持仓、资金、纳税），可直接在浏览器完成录入与查询操作。
- **后端 API**：负责存储与业务规则校验，包含交易、资金组、纳税等核心功能，并暴露统一的 REST 接口。
- **数据存储**：默认使用仓库根目录下的 `data/` 保存 JSON 数据，可通过环境变量灵活切换。

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

## 后端 API 速览

| Method | Path                                   | 描述                                         |
| ------ | -------------------------------------- | -------------------------------------------- |
| GET    | `/api/health`                          | 健康检查                                     |
| GET    | `/api/transactions`                    | 列出全部交易                                 |
| POST   | `/api/transactions`                    | 新增交易，自动生成 UUID 并执行仓位校验       |
| PUT    | `/api/transactions/{transaction_id}`   | 更新指定交易，持续校验资金组与持仓余额       |
| DELETE | `/api/transactions/{transaction_id}`   | 删除指定交易，同时清理关联纳税记录           |
| GET    | `/api/positions`                       | 根据交易计算仓位与已实现盈亏                 |
| GET    | `/api/funds`                           | 输出资金组快照（初始资金、当前总额、收益）   |
| GET    | `/api/funding-groups`                  | 列出资金组，首次启动自动创建 Default JPY/USD |
| POST   | `/api/funding-groups`                  | 新增/覆盖资金组                              |
| PATCH  | `/api/funding-groups/{name}`           | 更新资金组的货币、初始资金或备注             |
| DELETE | `/api/funding-groups/{name}`           | 删除资金组（需至少保留一个）                 |
| POST   | `/api/tax/settlements`                 | 记录纳税结果（返回带 ID 的记录），同步资金组 |
| GET    | `/api/tax/settlements`                 | 查看全部纳税记录一览                         |
| PATCH  | `/api/tax/settlements/{settlement_id}` | 更新纳税金额、货币或汇率                     |
| DELETE | `/api/tax/settlements/{settlement_id}` | 删除纳税记录并恢复交易的纳税状态             |

所有接口均返回 JSON，错误响应统一包含 `detail` 字段。后端依靠 `tests/test_api.py` 覆盖交易买卖、纳税与删除等关键流程。

## 前端功能概览

前端以 Tab 形式呈现主要功能：

- **交易表 (Trades)**
  - 新建或编辑买入/卖出交易，数量自动规范化，税务状态给出默认值，编辑时会显示可取消/保存的提示。
  - 行点击可回填表单；操作列提供编辑与删除按钮，均带二次确认以避免误操作。
  - 支持刷新按钮同步后端最新数据。
- **持仓表 (Positions)**：基于交易列表实时计算持仓数量、平均成本和已实现盈亏。
- **资金表 (Funds & Groups)**
  - 管理资金组（新增、修改、删除）并展示资金快照。
  - 删除时会检查至少保留一个资金组，文案已国际化。
- **纳税 (Tax)**
  - 自动筛选未纳税的卖出交易。
  - 填写纳税金额/汇率后提交，后端会把交易税务状态改为已纳税并刷新资金快照。
  - 下方提供「已登记纳税」列表，可查看、编辑或删除既有纳税记录，操作完成后自动刷新资金与交易数据。

界面支持中/英/日三语言切换，通知栏会在数据刷新、创建、删除等操作后提示结果。

## 数据说明

- `transactions.json`：交易流水，后端在接收到首个请求时自动创建。
- `funding_groups.json`：资金组配置，初次运行会生成「Default JPY / Default USD」。
- `tax_settlements.json`：纳税记录，由纳税 API 自动维护。
- `data/backups/`：预留备份目录，后续会提供导入导出脚本。

## 后续规划

- 扩展交易功能：支持批量导入/导出与高级过滤。
- 增强测试矩阵：覆盖多币种、跨资金组的极端情形。
- 提供数据备份/恢复工具（CSV/ZIP）。
- 引入桌面快捷入口或单文件打包方案。

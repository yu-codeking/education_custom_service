教育智能客服系统

业务数据底座复用 `edu-data/`（66 张表的教育业务数据中台），核心是一个自研三轨道对话引擎的 AI 客服后端和一个演示前端。

## 项目组成

```
vibe coding/
├── edu-customer-service/     # 【本项目核心】AI 教育客服后端（Python 3.12 + FastAPI + LangChain）
│   ├── 01_项目概述与项目架构.md
│   ├── 02_教育客服-数据中台部署.md
│   ├── flow_config/          # 业务流程定义（YAML 声明式，加流程不改代码）
│   ├── edu_service/          # 对话引擎源码（api / engines / plan / task / knowledge ...）
│   └── scripts/smoke_dialogue.py   # 五场景对话冒烟脚本
├── edu-customer-frontend/    # 调试/演示前端（Vue3 + Vite，端口 5174）
├── edu-data/                 # 教育业务数据中台（数据生成器 + 52 个 REST 接口，已容器化）
├── docker-compose.yaml       # WSL Docker 编排：MySQL(3307) + edu-api(8000)
├── mysql/initdb/             # customer_service 状态库自动初始化脚本
└── ecommerce/                # 电商蓝本项目（仅作参考，不参与运行）
```

## 架构一图

```
浏览器 Demo页:5174 ──► AI教育客服后端:18082 ──HTTP/X-User-Id──► edu-data业务API:8000
 (Windows 本地)         (Windows 本地)              ▲            ( Docker 容器)
                            │                      │
                   customer_service 库 ◄── MySQL8 容器( 映射3307) ──► edu 库(66张表)
                  （对话状态 JSON 持久化）                        （仿真业务数据）
```

三服务隔离原则（沿用蓝本）：AI 客服**不直连业务数据库**，所有课程/订单/学习进度/退费/工单操作均通过 HTTP 调用 edu-data 中台，并以 `X-User-Id` 学员身份执行。

## 快速启动（混合部署）

### 第一步：WSL Ubuntu 中启动数据中台

```bash
cd "/mnt/c/Users/yu/Desktop/projects/vibe coding"

# 首次：构建镜像并启动 MySQL + edu-api
docker compose up -d --build

# 首次或需要重灌数据时：重建 edu 库并生成 smoke 档数据（约几分钟）
docker compose run --rm edu-tools
# 全量档：GEN_PROFILE=full docker compose run --rm edu-tools

# 验证：浏览器打开 http://localhost:8000/docs 看到 Swagger 即成功
curl http://localhost:8000/health
```

> 注意：宿主机 3306 已被电商蓝本的 MySQL 占用，本项目的 MySQL 映射在 **3307**。

### 第二步：Windows 本地启动 AI 客服后端

```bash
cd edu-customer-service
uv sync                                  # 安装依赖
uv run uvicorn edu_service.api.app:app --host 127.0.0.1 --port 18082
# 验证 http://127.0.0.1:18082/docs
```

`.env` 关键配置（已在仓库内配好）：LLM 用 kimi-k3（Moonshot）；`EDU_API_BASE_URL=http://127.0.0.1:8000/api/v1`；`DATABASE_URL=mysql+aiomysql://root:hzk686868@127.0.0.1:3307/customer_service`。

### 第三步：启动演示前端

```bash
cd edu-customer-frontend
npm install
npm run dev      # 打开 http://localhost:5174
```

页面顶部选择「学员身份」（默认 331，该账号有多个订单与在读班次），即可开始对话演示。

## 演示脚本（对照验收标准）

| 场景     | 对学员说                                               | 体现能力                                   |
| -------- | ------------------------------------------------------ | ------------------------------------------ |
| 课程咨询 | 「我想了解一下全栈开发的课程」                         | 意图识别 → 课程搜索 → 班次价格推荐         |
| 订单查询 | 「帮我查下订单 ORD0000000672」                         | 实时业务数据查询                           |
| 学习进度 | 「我在全栈开发系统班的学习进度怎么样」                 | 出勤/视频/作业/考试多维进度                |
| 退费申请 | 「我要退费」→ 报订单号 → 说原因 → 选类型               | 多轮槽位收集 → 创建真实退款单              |
| 工单提交 | 「视频加载不出来，我要投诉」→ 报订单号 → 描述问题      | 工单类型识别（投诉自动高优先级）→ 创建工单 |
| 任务切换 | 退费中途说「帮我查个订单」→「继续刚才的退费」→「取消」 | 中断暂存 / 恢复 / 取消                     |
| 对象消息 | 点击下方按钮发送「订单卡/课程卡/班次卡」               | 卡片自动填充槽位                           |
| 流式响应 | 任意提问（默认走 SSE）                                 | meta/delta/done 事件流                     |

一键回归：

```bash
cd edu-customer-service
uv run python scripts/smoke_dialogue.py            # 全部场景
uv run python scripts/smoke_dialogue.py --scenario refund   # 单场景
```

会话恢复验证：对话几轮后重启客服后端，刷新页面点击左侧历史会话，消息与任务状态完整还原（状态持久化于 MySQL `customer_service.dialogue_states` 表）。

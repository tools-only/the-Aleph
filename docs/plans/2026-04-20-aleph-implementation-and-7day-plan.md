# Aleph 实现说明与 7 日 MVP 落地计划

- 文档版本: `v0.1`
- 日期: `2026-04-20`
- 状态: `implementation-aligned`

## 1. 当前实现版本摘要

这份文档描述的是当前仓库里的 Aleph Python 原型如何具体工作，以及接下来 7 天内如何把它收敛成一个可运行、可演示、可继续迭代的 MVP 产品。

当前代码基线已经完成了 `client runtime orchestration` 的第一版中轴：

- 一个 `client` 对应一个真实 agent，而不是在一个 agent 内再拆 subagent。
- Aleph 作为外层 control plane，统一做 runtime projection、memory 边界控制、handoff 和流式事件分发。
- 当前没有 world model，也没有环境状态引擎。
- 当前支持单 session、单 foreground client。

## 2. 当前大功能模块的具体实现逻辑

### 2.1 ClientBlueprint / ClientInstance

- `ClientBlueprint` 当前由 [aleph/client/registry.py](D:\Aleph\aleph\client\registry.py) 负责归一化，固定产出 role、system_prompt、declared_capability、shared_memory_policy、tools、handoff_rules、runtime_preferences。
- `ClientInstance` 当前与 blueprint 同 id 创建，保存 adapter_kind、runtime_signals 和 agent_native_state，作为 runtime 层而不是设计层对象。
- 当前的隔离级别是`框架级隔离`，不是容器隔离或 sandbox 隔离。

### 2.2 AgentAdapter

- 适配层定义在 [aleph/adapters](D:\Aleph\aleph\adapters\__init__.py)，通过 `BaseAgentAdapter` 抽象具体 runtime。
- `NanobotAdapter` 当前直接调用本地 handler，等价于“把 nanobot 风格 client handler 接到 Aleph 编排链路上”。
- `MockAgentAdapter` 当前用于验证“第二种 runtime 可接入而不需要改 orchestrator 主链路”。

### 2.3 SessionOrchestrator

- 主编排器在 [aleph/core/session_orchestrator.py](D:\Aleph\aleph\core\session_orchestrator.py) 中实现，当前按“收输入 -> 编译 -> 调 agent -> 落 memory -> 评估 handoff -> 发流式事件”的顺序运行。
- 当前只实现单 session、单 foreground client，不做多 foreground 竞争。
- 当前 handoff 是规则型、同步型接管，不是学习型调度。

### 2.4 ProjectionCompiler

- 编译器在 [aleph/core/projection_compiler.py](D:\Aleph\aleph\core\projection_compiler.py) 中实现，分为 prompt、memory、tools、capability、handoff 五类 projection。
- Prompt 编译当前是“system_prompt + role + boundaries + user_input + stream_mode”的轻量组合，而不是把整段长历史直接注入。
- Capability 编译当前只拼接 `Declared Capability + Runtime Signals`，不做自动学习。
- Handoff 编译当前只输出最小接管包，而不是完整上下文转移。

### 2.5 MemoryManager

- memory 管理在 [aleph/core/memory_manager.py](D:\Aleph\aleph\core\memory_manager.py) 中实现，当前分为 `private / shared / handoff / runtime` 四层框架侧 memory。
- `private memory` 按 `session_id + owner_client_id` 隔离。
- `shared memory` 按 `read_domains / write_domains / allowed_kinds / write_mode` 做治理。
- `handoff memory` 默认只写给目标 client。
- 当前 shared memory 采用轻量 append 模型，还没有做复杂 merge 或审批流。

### 2.6 Agent-native state 与 Runtime signals

- `agent_native_state` 当前保存在 SQLite 的 `client_instances.agent_native_state_json` 中，由 agent 输出的 patch 显式更新。
- `runtime_signals` 当前记录最近延迟、最近是否成功等运行态信号，用于后续 routing 和观测。
- 当前这两类状态都还是“轻量可恢复状态”，还没有做到深度会话恢复。

### 2.7 SwitchDaemon / Handoff

- handoff 决策在 [aleph/core/switch_daemon.py](D:\Aleph\aleph\core\switch_daemon.py) 中实现。
- 当前规则是“优先显式 target_client_id，否则按 reason 和 user_input 对 capability tags 做简单匹配”。
- 当前 handoff 输出会被写入 `switch_logs` 和 `handoff memory`，同时通过 presentation stream 对前端可见。

### 2.8 流式输出

- 当前流式事件分为 `internal` 和 `presentation` 两个 channel，存放在 SQLite 的 `session_events` 表。
- 对外 presentation stream 当前最少支持 `status / delta / tool_event / handoff / final` 五类事件。
- 当前是“事件流”级别的流式输出，还不是 HTTP SSE / WebSocket 产品接口。

### 2.9 Runtime acceleration

- 当前已经实现 `projection cache`、`memory slice cache`、`prompt skeleton reuse` 和 `candidate client prewarm`。
- cache key 当前由 `session_id + client_id + memory_epoch + tool_epoch + policy_epoch + blueprint_version + projection_type` 组成。
- prewarm 当前只做无副作用 projection 预编译，不会提前执行外部高成本动作。

### 2.10 存储与可观测

- 当前真值存储在 [aleph/storage/sqlite_store.py](D:\Aleph\aleph\storage\sqlite_store.py) 中，统一由 SQLite 承担。
- 当前表已经覆盖 blueprint、instance、session、turn、event、memory、switch、projection_cache、prewarm_job。
- 当前可观测能力还是开发态，主要依赖 switch logs、presentation events、runtime signals 和测试断言。

## 3. 当前版本离“可运行/落地产品”还差什么

当前原型已经有了架构中轴，但距离一个真正可运行的 MVP 产品，还差四件关键事情：

- 需要一个稳定的产品入口，而不是只靠脚本和 REPL。
- 需要一个明确的 session API 和 stream API，而不是只在进程内调用 Python 方法。
- 需要一个面向框架使用者的 client 配置入口，而不是只能写死在 Python 文件里。
- 需要把“runtime acceleration”从概念性实现推进到可测量的产品指标，例如首包延迟、handoff 延迟、cache hit rate。

## 4. 7 日计划

### Day 1: 固化产品边界与 API 契约

- 目标: 把当前原型收敛成一个明确的 MVP 产品形态。
- 工作:
  - 固定 MVP 只支持文本输入。
  - 定义 `session create / session turn / stream subscribe / client list` 四个对外 API。
  - 固定 presentation stream 的 JSON schema。
  - 固定 client blueprint 的 JSON/YAML 配置格式。
- 产出:
  - 一份 API 契约文档。
  - 一份 client blueprint 配置样例。
- 验收:
  - 不再依赖代码阅读就能知道产品如何接入和调用。

### Day 2: 做最小服务化入口

- 目标: 把当前 Aleph 从进程内原型提升为“可启动服务”。
- 工作:
  - 增加一个轻量 HTTP 服务层，建议 FastAPI。
  - 暴露 `POST /sessions`、`POST /sessions/{id}/turns`、`GET /sessions/{id}`、`GET /clients`。
  - turn 接口先返回完整结果，同时保留 stream 事件落库。
- 产出:
  - 一个可本地启动的 API 服务。
  - 一套 curl 或 Python 调用样例。
- 验收:
  - 外部进程可以不直接 import AlephEngine，也能驱动 session。

### Day 3: 打通真实流式接口

- 目标: 把当前 presentation event 流变成产品可消费的实时输出。
- 工作:
  - 增加 SSE 或 WebSocket stream 接口，优先 SSE。
  - 将 `status / delta / tool_event / handoff / final` 映射为稳定的流式消息。
  - 增加 stream replay 能力，允许前端按 session 获取最近 N 条事件。
- 产出:
  - 一个能在浏览器或命令行实时看到流的接口。
- 验收:
  - 一次 handoff 可以完整看到 status、handoff、delta、final 的时间序列。

### Day 4: 配置化 client 与 adapter 装载

- 目标: 让 client 不再必须写死在 `default_clients.py`。
- 工作:
  - 支持从 `configs/clients/*.yaml` 或 `configs/clients.json` 加载 blueprint。
  - 保留 Python handler 注册机制，但把声明信息配置化。
  - 增加 `adapter_kind -> adapter loader` 的显式注册入口。
- 产出:
  - 配置驱动的 client 注册流程。
  - 至少两个 client 由配置加载并跑通。
- 验收:
  - 修改一个 client 的 role、shared_memory_policy 或 tools，不需要改 orchestrator 代码。

### Day 5: 做最小前端或可视化控制台

- 目标: 把 MVP 从“后端原型”推进成“可演示产品”。
- 工作:
  - 做一个极简 web UI，至少包含 chat 面板、当前 foreground client、最近 handoff、最近 shared memory。
  - 支持发送文本、实时接收 stream、显示 handoff 说明。
  - 增加 session 创建和切换。
- 产出:
  - 一个本地可打开的 MVP 页面。
- 验收:
  - 非开发者不看代码，也能直观看到 Aleph 的 client 切换和 memory 边界。

### Day 6: 做性能和可观测闭环

- 目标: 让“runtime acceleration”真正变成可观测指标。
- 工作:
  - 记录首个 `status` 时间、首个 `delta` 时间、`final` 时间。
  - 增加 cache hit rate、handoff count、average turn latency 的统计。
  - 在 UI 或日志里显示最近 20 次 turn 的延迟拆分。
- 产出:
  - 一份简单的延迟与缓存统计视图。
- 验收:
  - 能回答“快了没有、慢在哪里、handoff 贵不贵”这三个问题。

### Day 7: 打磨可交付 Demo

- 目标: 形成一个能演示核心 idea 的最小产品包。
- 工作:
  - 清理启动脚本和 README。
  - 准备两个 demo 场景。
  - 增加一份“如何新增 client”的开发文档。
  - 回归测试私有 memory、shared memory、handoff、stream、cache。
- 产出:
  - 一套可演示、可运行、可解释的 Aleph MVP。
  - 演示脚本、README、测试、样例配置齐备。
- 验收:
  - 新人按 README 能在本地跑起来并看到核心效果。

## 5. MVP 的明确交付定义

7 天结束时，这个 MVP 应该满足下面的最低标准：

- 可以通过 HTTP API 创建 session 和发送 turn。
- 可以通过 SSE 或 WebSocket 实时看到流式输出。
- 至少有 2 到 3 个真实 client blueprint 可切换。
- private/shared/handoff memory 行为可见且可验证。
- handoff 原因和 handoff summary 对前端可见。
- 能看到至少一层 runtime acceleration 指标。
- README 能指导本地启动、调试和演示。

## 6. 实施注意事项

- 不要在这 7 天里把 world model、设备状态或多模态输入重新拉进核心模型。
- 不要把 shared memory 做成通用知识库，否则 client 边界会很快塌掉。
- 不要一开始就做复杂学习型 routing，先让规则型 handoff 稳定可解释。
- 不要让 prewarm 触发真实副作用动作，保持它只是无副作用准备。
- UI 必须为 handoff 和 memory 边界服务，避免做成普通多 agent chat 面板。

## 7. 建议的执行顺序

如果资源只够做最小闭环，推荐优先级如下：

1. API 服务化
2. SSE 流式输出
3. 配置化 client
4. 极简前端
5. 延迟与缓存观测

这样可以最短路径把 Aleph 从“架构原型”推到“可演示产品”。

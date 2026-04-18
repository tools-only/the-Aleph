# Aleph Client 设计方案

## 背景
Aleph 当前不追求 OS-level sandbox 容器隔离，但必须超越 prompt-level isolation。
目标不是“不同 prompt 的同一个 agent”，而是“共享同一现实、但彼此拥有独立主体边界的 client”。

## 设计目标
- client 共享 `RealityThread`，不共享 private memory 与 private transcript
- client 只能通过受控上下文访问 shared memory 与 reality projection
- client 不能直接切换前台、不能直接写 reality truth、不能直接读其他 client 的私有状态
- client 的隔离通过 runtime API、session、capability facade 和存储 namespace 来实现

## Client 包含的内容
### 1. Identity
- `id`
- `personaId`
- `displayName`
- `voice`
- `specialties`
- `boundaries`
- `permissions`

### 2. Capability View
- `readableSharedDomains`
- `writableSharedDomains`
- `allowedActions`
- `requestOnlyActions`
- `allowedTools`

### 3. Isolation Policy
- `transcriptWindow`
- `privateMemoryWindow`
- `sharedMemoryWindow`
- `consequenceWindow`
- `handoffWindow`

### 4. Runtime State
- 当前 `sessionId`
- 当前是否处于 foreground
- 最近 handoff summary
- 当前可见 reality projection
- 当前 client 的 recent turns

## 隔离方式
### Memory Isolation
- private memory 以 `client.id` 为 namespace
- shared memory 必须按 domain ACL 访问
- context 中不存在 `getOtherClientMemory` 一类接口

### Capability Isolation
- handler 拿到的是 per-client capability facade
- 高权限动作只能发 proposal，不能直接执行
- shared domain 的读写由 context builder 和 store 双重约束

### Session Isolation
- 每个 client 有独立 `client_session`
- 每个 client 有独立 `client_turns`
- 前台切换时，交接摘要写入新 client 的独立 transcript

### Reality Isolation
- client 只能看到 `RealityProjection`
- reality truth 的修改只能通过 turn output 中的受控 proposal 完成
- foreground switch 只能经过 `SwitchDaemon`

## 基于 nanobot 的架构映射
Aleph 这一版实现参考了 nanobot 的轻量 agent runtime 拆法，但做了更强的 client 边界收束。

### nanobot 中可借鉴的结构
- `README.md` 中给出的主骨架：`agent/loop.py`、`agent/context.py`、`agent/memory.py`、`agent/subagent.py`、`session/manager.py`
- `nanobot/agent/context.py`：把可见上下文组装给 agent
- `nanobot/session/manager.py`：管理会话与历史
- `nanobot/agent/subagent.py`：把次级 agent 作为受控 worker 调起

### Aleph 中的对应实现
- `aleph/client/context_builder.py`
  类似 nanobot 的 context builder，但它不是通用 agent prompt assembler，而是 per-client capability gate
- `aleph/client/session_manager.py`
  对应 nanobot 的 session manager，但 transcript 不只是会话便利功能，而是 client 边界的一部分
- `aleph/client/registry.py`
  承担 client definition registry，类似 nanobot 中多个 agent/subagent 配置入口的组合
- `aleph/client/turn_builder.py`
  把 client 能做的事限制为受控 action facade，而不是直接暴露底层 store
- `aleph/core/aleph_engine.py`
  作为 orchestrator，把 reality、client、switch daemon 串起来

## 当前实现要点
- 新增 `client_profiles`、`client_sessions`、`client_turns`
- `AlephEngine` 改为以 `client` 作为一级运行单元
- 默认 personas 变为默认 clients，并通过 `ClientContextBuilder` 执行
- 新测试覆盖：
  - client 切换后现实连续
  - client private memory 隔离
  - shared memory 仍可受控共享
  - shared domain ACL 会在 runtime API 层阻止越权访问

## 结论
Aleph 这一版采用的是“强 client runtime 隔离”，而不是“系统级 sandbox”。
它已经明显超越 prompt 级隔离，足以支撑：

- 不同 client 的私有主体性
- 共享现实但不共享完整内心世界
- 半自动 handoff
- capability-based client 边界

后续如果接入高风险工具、第三方 plugin 或真实设备，再把这层 client runtime 隔离升级成 process / worker / sandbox 隔离会更自然。

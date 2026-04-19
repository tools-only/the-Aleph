# Aleph Client Runtime Design

## 设计目标

Aleph 不直接发明新的 agent 内核，而是在具体 agent runtime 之外增加一层可编译、
可隔离、可切换、可加速的控制层。

核心原则：

- 一个 client 对应一个真实 AI agent
- client 的主体性边界不被 subagent 模拟稀释
- 设计期由框架使用者定义 blueprint
- 运行期由 Aleph 自动投影 prompt、memory、tools、capability 和 handoff

## ClientBlueprint

每个 blueprint 在设计期定义：

- `role`
- `system_prompt`
- `boundaries`
- `declared_capability`
- `shared_memory_policy`
- `tools`
- `handoff_rules`
- `runtime_preferences`

这保证框架使用者只做一次深度设计，而不是在每个运行实例上重复写 glue code。

## ClientInstance

每个 client instance 绑定一个具体 agent runtime：

- `adapter_kind`
- `runtime_signals`
- `agent_native_state`

Aleph 不把 agent-native state 当成唯一真值，但也不会忽略它。v1 采用“受控同步”
策略：通过 adapter 显式写回和恢复。

## ProjectionCompiler

运行时编译五种投影：

- `Prompt Projection`
- `Memory Projection`
- `Tool Projection`
- `Capability Projection`
- `Handoff Projection`

这些投影才是具体 agent runtime 真正接收到的配置表面。

## Shared memory 治理

shared memory 的关键不是内容，而是治理：

- 哪些 domain 可读
- 哪些 domain 可写
- 哪些 kind 可写
- 默认写入模式是什么

v1 采用显式 domain policy 和 append-only 默认策略，防止 shared memory 退化为
“公共大脑”。

## Handoff

handoff 是核心机制，不是附属功能。

v1 特征：

- 规则驱动
- 可解释
- 低歧义
- 默认只传递最小必要接管信息

handoff 产物默认写入 `handoff memory`，而不是自动沉积到 shared memory。

---
name: 主动使用多 agent 并行调度
description: 用户希望在处理任务时主动并行启动多个 subagent，而不是串行处理。适用于研究、代码探索、多文件分析等场景。
type: feedback
---

用户希望开启多 agent 并行调度工作模式。

**Why:** 提高任务处理效率，避免串行等待
**How to apply:**
- 遇到需要搜索/探索多个不同区域的任务时，同时 launch 多个 Explore agent 并行执行
- 需要同时做代码审查 + 记忆检查 + 变更分析时，用多个 general-purpose agent 并行
- 遇到多文件/多目录的读取任务，先用 Glob/Grep 定位，然后并行 Read
- 不要串行地一个一个做可以并行的事情
- 每次任务开始前，快速判断"这些步骤能并行吗"，能则并行

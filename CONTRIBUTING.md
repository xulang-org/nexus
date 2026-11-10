# 开发

本仓库独立维护游戏引擎库；编译器、标准库和其他外部包属于各自仓库。
遵守 Xu 的 [仓库规范](https://github.com/xulang-org/xulang-org/blob/main/.github/REPOSITORY_RULES.md)
和 [Xu 代码规范](https://github.com/xulang-org/xu/blob/dev/.github/XU_CODING_STANDARDS.md)。

当前产品模块版本是根 `xu.xun` 的 `0.1.0`；示例是独立的消费模块。
同一批更改只更新一次受影响模块版本；`xu:` 记录实际选择和验收的 SDK。
日常开发在 `dev` 或其任务分支上完成。提交和推送须有用户明确指示。

先运行 `make check` 和 `make smoke`。具备本机测试目录时，还须运行
`make test` 和 `make gpu-smoke`。平台支持结论须有对应系统的真实 GPU 证据。
本机测试、研发文档、日志、缓存、截图和编译产物保持忽略，不提交。

原生桥接只能负责 ABI、平台事件与 GPU 资源和调用；场景、输入动作、变换、碰撞、
时钟和游戏行为写在 Xu 中。借用的数组只在同步 ABI 调用期间有效，不能保留其地址。
不得用软件渲染器冒充 GPU 后端，也不得忽略设备创建、上传或提交失败。

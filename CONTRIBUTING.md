# 开发

本仓库独立维护游戏引擎库；编译器、标准库和其他外部包属于各自仓库。
遵守 Xu 的 [仓库规范](https://github.com/xulang-org/xulang-org/blob/main/.github/REPOSITORY_RULES.md)
和 [Xu 代码规范](https://github.com/xulang-org/xu/blob/dev/.github/XU_CODING_STANDARDS.md)。

产品模块版本以根 `xu.xun` 为准；示例是独立的消费模块。
同一批更改只更新一次受影响模块版本；`xu:` 记录实际选择和验收的 SDK。
日常开发在 `dev` 或其任务分支上完成。提交和推送须有用户明确指示。

使用 [README 中固定的 Xu SDK](README.md#构建所需的-xu-sdk)，在仓库根目录运行 `make check test smoke gpu-smoke`。
修改场景格式或 3D 绑定时，可用下面的目标复测对应功能。

| 验收范围 | 命令 |
| --- | --- |
| 光源文件校验和无 GPU 的保存、重开 | `make scene-lighting-test` |
| 相机、方向光级联、点光和聚光阴影的保存、重开及像素对照 | `make scene-camera-gpu-test` |
| GLB 距离 LOD 的近景、远景和新进程重开 | `make scene-lod-gpu-test` |
| 3D 静态盒、斜坡、任意三角面连续碰撞与动态刚体求解场景 | `make physics3d-test physics3d-gpu-test character-course-test` |
| 项目 UID、增量资源、发布回滚、场景编辑、可玩关卡 | `make project-test project-gpu-test project-editor-test character-course-test` |
| 编辑器最窄窗口、俯视导航、3D 拾取、LOD、本地轴、吸附、多选变换、撤销与发布 | `make project-picking-test project-editor-test` |
| 固定关卡与 Wasm 帧包性能报告 | `make benchmark-course benchmark-webgl` |

场景字段修改同时更新 [README 的格式版本表](README.md#节点场景文件) 与对应示例。
涉及 WebGL 时还须用 Node.js 运行 `make miniprogram-test douyin-test webgl-3d-test`，并记录对应开发者工具或真机的验证结果。
平台支持结论须有对应系统的真实 GPU 证据。

`assets/design/xu-ui-tokens.json` 是 XUUI Design System `0.1.1-dev.4` 的 MIT 许可原始令牌。原生 XUUI 场景编辑器（`cmd/project_editor/theme.xu`）使用 Light（Paper）配色、字体与尺寸，原生视口的 `EDITOR_*` 颜色也取自同一份令牌。编辑器测试会核对工作区主色、视口令牌和最窄窗口布局。 [设计令牌来源](https://github.com/xulang-org/xu-ui-design/blob/3203d371d0add6320ebc2c1e0e2c6b9b65388908/tokens/tokens.json)
本机测试、研发文档、日志、缓存、截图和编译产物保持忽略，不提交。

原生桥接只能负责 ABI、平台事件与 GPU/音频设备、资源和数据传输；场景、输入动作、变换、碰撞、
时钟、音频混音/重采样/播放状态和游戏行为写在 Xu 中。借用的数组只在同步 ABI 调用期间有效，不能保留其地址。
不得用软件渲染器冒充 GPU 后端，也不得忽略设备创建、上传或提交失败。

首次发布前只维护当前最终接口、包结构和文件格式。移除未发布的旧接口、格式读取分支和原生 ABI；
同步迁移全部示例、工具和验收代码，不为开发中间版本保留兼容门面。通用数学与基础能力独立于引擎服务，
场景不依赖输入、时钟、物理、音频或渲染；跨系统行为通过 integration 包组合。

桌面与 Phone 的 2D/3D 渲染复用 Xu 标准 gpu/window。微信小程序和抖音小游戏的 WebGL 宿主分别消费 `resources/canvas` 的 2D 批次与 `integration/rendering/webgl` 的 3D 网格帧。平台 JavaScript 负责纹理上传、渲染提交和宿主事件。CPU 画布录制禁止导入 GPU 服务。Nexus 仅保留音频设备和 CPU PNG codec 两个原生模块，禁止重新引入 GPU 原生桥接或重复的窗口事件协议。

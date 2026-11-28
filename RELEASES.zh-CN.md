# Nexus Engine 发布说明

## v0.1.2

统一三维项目编辑器、实时 3D 光影/大气/后处理特效管线、XACP 自动化控制与 `>>>` 错误处理语法迁移版本，完整对齐 **Xu SDK v0.14.4**。

### 核心亮点

- **统一项目编辑器（`nexus-project-editor`）**：合并并下线旧版 `cmd/nexus_studio`，将内嵌 Metal 3D 视口、四分/双栏视图、2D 舞台、TileMap 编辑、交互式 3D 白盒建模/CSG 布尔、多选批量编辑以及大纲逐行显示/隐藏拖拽涂抹（含实时回滚与合并撤销）整合进 `nexus-project-editor`。
- **实时 3D 光照、阴影与后处理特效全链路**：在 `hdr_clustered` 着色器补全级联/聚光/方向阴影采样与金属/清漆环境反射；在编辑器与预览中全面启用 `ModernPipeline3D`、512px 阴影（含 64 MiB 显存超限安全回退）、Rayleigh/Mie 天空大气与体积雾、排序透明材质、HDR Bloom/GTAO/SSR/ACES 与 3D GPU 粒子，并在大纲新增光源/环境/粒子一键预设及 3D 视口辅助标记。
- **PBR 材质预设与预览同步**：内置 10 种常用 PBR 材质预设与参数编辑，独立预览与编辑器材质覆盖渲染完全同步。
- **XACP 自动化驱动与截图验证**：为 `nexus-project-editor` 与 `nexus-project-preview` 接入 `xacp`（`ui.tree` / `ui.act` / `ui.input` / `ui.screenshot`）。
- **深度工程体检与 `>>>` 语法升级**：增强 `nexus-project doctor`（支持 `--fix`/`--dry-run`/`--toolchain`），全仓迁移至 `>>>` 语法并固定 **Xu SDK v0.14.4**。
- **跨平台发行工具**：覆盖五大桌面平台（`macos-arm64`、`macos-x64`、`linux-x64`、`linux-arm64`、`windows-x64`）提供 `nexus-project`、`nexus-project-validate`、`nexus-project-viewport`、`xu-nexus-script`、`nexus-project-editor`、`nexus-tilemap-editor`。

## v0.1.1

Nexus Engine（`github.com/xulang-org/nexus`）首个公开正式发行版，完整对齐 **Xu SDK v0.14.2**。

### 核心亮点

- **分层架构契约**：通过 `architecture.json` 与 `tools/check_layers.py` 严格隔离纯 CPU 基础层（`foundation/math`、`color`、`diagnostics`、`events`、`spatial`）、资源模型与格式编解码（`resources/*`、`formats/*`）、确定性运行期子系统（`scene`、`ecs`、`physics2d`、`physics3d`、`navigation`、`ai/bt`、`audio/mixer`、`networking`、`animation`、`input`、`timing`、`modeling`）与 `integration/*` 组合层。
- **2D / 3D 渲染管线**：提供分簇前向光照、Split-Sum 环境光 IBL、Meshlet Visibility Buffer（`ModernPipeline3D`）、HDR Bloom/GTAO/SSR/TAA/ACES 后处理、2D 动态光影与软阴影、GPU 线性蒙皮，以及覆盖 45 个 3D 着色器与 7 个 2D 着色器的 MSL / GLSL 450 / HLSL SM 6.0 三端源码一致校验。
- **开发者核心系统（第 1–4 轮）**：
  - 确定性 `Xoshiro128++` 随机数与二维泊松盘采样、松散二维四叉树 `Quadtree2D`、支持事务合并/回滚的通用 Undo/Redo `CommandHistory`、延迟批处理 `EcsCommandBuffer` 与 `EntityTemplate`。
  - 多瓦片动态 NavMesh 与跨块寻路、Utility AI 效用仲裁器、分帧预算 DAG 任务队列与分区流式调度、分层输入上下文与输入回放。
  - 带 SHA-256 损坏自动降级恢复的多槽位存档目录、支持轮询/随机/无重复洗牌与声道抢占的 `AudioCueBank`、极点安全解析二阶弹簧与 `MotionSequence`。
  - 方向权威校验字节码 `RpcRegistry` + 令牌桶 `PeerRateLimiter` + `PeerHeartbeatTracker`、`ConstraintSolver3D` 三维节点约束求解器与 `NodePool` 对象池。
- **工具链与跨平台原生桥接**：
  - 为五大桌面平台（`macos-arm64`、`macos-x64`、`linux-x64`、`linux-arm64`、`windows-x64`）提供 7 个工具二进制：`nexus-project`、`nexus-project-validate`、`nexus-project-viewport`、`nexus-studio`、`xu-nexus-script`、`nexus-project-editor`、`nexus-tilemap-editor`。
  - 提供全平台打包工具包以及包含多平台切片合并的 `nexus-v0.1.1-native-all.tar.gz`（覆盖 `nexus_audio`、`nexus_image`、`nexus_steam`、`nexus_console`、`nexus_taptap` 五个原生 `.xulib`）。

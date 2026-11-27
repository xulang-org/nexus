# Nexus Engine 发布说明

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

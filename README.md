# Nexus Engine

Nexus Engine 是独立的 Xu 游戏引擎库，模块为 `github.com/xulang-org/nexus`，当前开发版本 `0.1.1-dev.4`。
场景树、可复用场景、变换、相机、图集动画、输入、时钟、碰撞、画布和精灵逻辑使用 Xu。
3D 向量、矩阵、透视相机、网格构建、父子变换、材质参数和场景绘制同样使用 Xu。
音频资源、重采样、声像、总线混音和节点播放状态也由 Xu 实现；设备提交使用独立音频 C ABI。
2D/3D 都通过 Xu 标准 `gpu` / `window` 管理设备、资源、绘制、事件和呈现；nexus 不再维护 GPU 原生桥接。

参考 Godot 的 [Node / SceneTree](https://docs.godotengine.org/en/stable/tutorials/scripting/scene_tree.html)
和 [Resource](https://docs.godotengine.org/en/stable/tutorials/scripting/resources.html) 分工。
Xu 侧使用组合与显式生命周期通知，不依赖类继承。目前已有 2D 库、3D 节点/相机/网格场景、受限 GLB 静态几何与不透明 PBR 材质导入、受限 OBJ 和 ASCII/二进制 STL 静态网格导入，
WAV/总线/声源的场景恢复，以及沿用 Xu 语法的开发态标量脚本 VM、保留状态热重载、脚本处理函数和延迟节点信号。
GLB 已支持受限 TRS 动画采样、CPU 四权重线性蒙皮和相对路径 PNG，真实人物/动物/植物素材验收见下文。
3D 已加入带法线/切线/UV 的金属度/粗糙度直接光材质、基础颜色/ORM/自发光/法线/独立 AO 纹理与 mipmap、单双面渲染、最多 256 个候选方向光/点光/聚光、每网格最多 16 源、场景光源绑定、自发光和曝光。
3D 可选择 GPU 2× 超采样（四个源像素合成一个输出像素）和方向/聚光/点光 3×3 PCF 阴影及 2–4 级 CSM，图片已接通标准库的受限 baseline JPEG 解码。完整 glTF 材质/纹理、IBL、编辑器、完整脚本类型/绑定/协程、生产更新分发、压缩音频/异步解码与 DSP、刚体求解器、用户材质着色器、GPU 粒子和计算纹理仍待实现。

当前使用 Xu **0.12.7-dev.1**。该 SDK 恢复了 Phone game 对象对原生导入的支持，并随生成工程导出原生归档与 C 桥接。编译器、标准库、native/phone 工具必须来自同一 SDK。两个移动示例已用此 SDK 在 Sony XQ-BE72（Android 13）上运行，并完成 iOS 应用构建。iPhone 8（iOS 16.7.16）的真机结果来自此前的 Xu 0.12.5 构建。

## 构建所需的 Xu SDK

开发 SDK 由固定的 Xu 源码提交构建。下面是在 macOS arm64 上的复现命令，需要 Git、已登录的 GitHub CLI（`gh`）、Python 3 和 Xcode 命令行工具。从 Nexus 仓库根目录运行，命令会在相邻目录检出 Xu 并下载官方 0.12.6 自举种子。

```sh
git clone https://github.com/xulang-org/xu.git ../xu-nexus-sdk
NEXUS_XU_SDK="$(cd ../xu-nexus-sdk && pwd)"
(
  cd "$NEXUS_XU_SDK" || exit
  git fetch origin 55a9d12d732b12f873cef02c6222c0d5994728ba &&
    git checkout --detach 55a9d12d732b12f873cef02c6222c0d5994728ba &&
    python3 scripts/restore_product_seed.py --target macos-arm64 --version 0.12.6 --destination build/seed/xu &&
    XU_SEED="$PWD/build/seed/xu" XU_SKIP_CROSS=1 make xu
)
export NEXUS_XU_SDK
export XU_ROOT="$NEXUS_XU_SDK" XU_STDLIB_ROOT="$NEXUS_XU_SDK/src" XU="$NEXUS_XU_SDK/bin/xu"
make sdk
```

`make sdk` 应输出 `PASS: Xu SDK 0.12.7-dev.1`。平台名可用 `python3 scripts/restore_product_seed.py --help` 查询。已有同一提交构建的 SDK 时，直接设置上述环境变量即可。 [Xu SDK 源码](https://github.com/xulang-org/xu/tree/55a9d12d732b12f873cef02c6222c0d5994728ba)

## Phone 原生 2D / 3D 示例

`examples/phone_arena`（2D）与 `examples/phone_3d`（3D）均使用场景树、固定时钟与标准 GPU 渲染，经 `--phone-profile game` 原生宿主直出画面，不经 WebView：
- `integration/viewport` 与 `integration/application`（`AppHost` / `Viewport` / `fit_letterbox`）统一处理 `safe_area()` 屏幕安全区布局、前后台恢复代次、`EVENT_BACK_REQUESTED` 暂停/退出与双端资源/私有存档路径解析。
- `examples/phone_arena`：左下半屏浮动摇杆 + 右侧加速（Hold）+ 暂停（Tap）收集六枚宝石，结合 `nexus_image.xulib`、`nexus_audio.xulib` 与 `arena-v1.json` 原子存档恢复；触摸使用逻辑窗口坐标并按屏幕尺度缩放 HUD 控件，渲染按像素分辨率缩放。
- `examples/phone_3d`：`AppHost` + `TouchControls` + `TouchPad`（未命中按钮区域由单指拖动控制轨道旋转，双指支持捏合缩放/桌面滚轮），通过 `Device3D.set_max_render_pixels(921600)` 控制移动端 3D 渲染像素预算并保留全分辨率 `Overlay2D` + `UiFrame` HUD 叠加、贴图 PBR 立方体与 `Back` 暂停/退出。

```sh
NEXUS_PHONE_SDK=/path/to/xu-0.12.7-dev.1
export XU_ROOT="$NEXUS_PHONE_SDK" XU_STDLIB_ROOT="$NEXUS_PHONE_SDK/src"
python3 tools/build_phone.py --xu "$NEXUS_PHONE_SDK/bin/xu" \
  --example phone_arena --target ios-arm64 --sdl-source /path/to/SDL-3.4.14 \
  --output build/phone-arena-ios --bundle-id org.example.phonearena
./build/phone-arena-ios/build.sh

python3 tools/build_phone.py --xu "$NEXUS_PHONE_SDK/bin/xu" \
  --example phone_3d --target android-arm64 --sdl-source /path/to/SDL-3.4.14 \
  --output build/phone-3d-android --bundle-id org.example.phone3d
./build/phone-3d-android/build.sh
```

SDL 必须是 Git 检出，HEAD 为锁定提交 `147a8ee32dbf9ac02f3794964490687b6bbda1bc`。
生成工程携带源码、对象和资源，之后原生构建可离线执行；iOS 安装需要匹配的开发签名与 provisioning。
Android 准备 Android SDK/NDK、JDK 与 `glslangValidator`，生成 `libmain.so` + `libSDL3.so`（强制 16 KiB ELF 对齐与 `zipalign -P 16` / `apksigner verify`）。
原生 PNG 与音频桥接均提供 `macos-arm64` / `ios-arm64` / `android-arm64` 三切片。示例构建脚本在忽略的 `build` 目录准备 shader、PNG 与 WAV 清单 `phone.resources`，资源通过 `app_host.resolve_resource` / `app.resource_path()` 读取。

`phone_arena` 使用 `app_host.resolve_data("arena-v1.json", "build")` / `app.data_path("arena-v1.json")` 保存位置、六个宝石收集mask和暂停状态：
移动时最多每秒写一次，松手、收集、暂停变化和正常退出会立即写入；同目录临时文件 + rename 原子替换；损坏小文件保留为 `.rejected-<timestamp>` 并重置。

`integration/frame` 本身不依赖 Phone、GPU 或 SceneTree：宿主传入单调时间和恢复代数即可使用；`integration/application.AppHost` 在此基础上收口窗口事件流、恢复复位、`safe_area` 与返回键调度。

## 微信小程序 WebGL

`examples/miniprogram` 是微信小程序页面中的 2D WebGL 1 示例。Xu 编译成随包 WASM，运行碰撞与宝石收集并录制带纹理的画布批次。微信宿主通过 `WXWebAssembly` 加载模块，通过原生 `canvas type="webgl"` 上传图集和顶点，处理触摸、尺寸变化及页面前后台。按住或拖动可以绕过墙壁收集宝石。

使用上文的 SDK 和 Node.js，在 Nexus 根目录运行 `make miniprogram-test`。

用微信开发者工具打开 `build/nexus-miniprogram`。仅生成工程可运行 `make miniprogram`。需要使用自己的小程序 AppID 时，用 `tools/build_miniprogram.py --appid` 生成对应工程。当前 SDK 需要支持 `--wasm-export`，小程序需要提供 `WXWebAssembly` 和 WebGL Canvas。

## 抖音小游戏 WebGL

抖音小游戏与微信小程序共用同一份 2D Wasm 和 WebGL 1 渲染器。抖音入口通过 `tt.createCanvas()` 获取全屏画布，处理触摸、尺寸与前后台，并用 `TTWebAssembly` 加载随包模块。按住或拖动控制角色，集齐三颗宝石后点画布内任意位置可以重开。基础库从 3.7.0.0 提供 `TTWebAssembly`。 [抖音小游戏开发指南](https://developer.open-douyin.com/docs/resource/zh-CN/mini-game/develop/guide/dev-guide/bytedance-mini-game) · [TTWebAssembly](https://developer.open-douyin.com/docs/resource/zh-CN/mini-game/guide/minigame/optimization)

使用上文的 SDK 和 Node.js，在 Nexus 根目录运行 `make douyin-test`。

`make douyin` 仅生成 `build/nexus-douyin`。在抖音开发者工具中按「小游戏」导入此目录并选择自己的小游戏 AppID，也可用 `tools/build_miniprogram.py --platform douyin --appid <AppID>` 写入工程配置。 [导入指南](https://developer.open-douyin.com/docs/resource/zh-CN/mini-game/guide/minigame/develop/)

## 小程序与小游戏 3D WebGL 测试

使用上文的 SDK，安装 Node.js，在 Nexus 根目录运行测试。

```bash
make webgl-3d-test
```

分别导入 `build/nexus-miniprogram-3d` 和 `build/nexus-douyin-3d`。拖动画布旋转相机，观察立方体、球体和棋盘的透视与遮挡。微信页面的「复位」恢复初始视角。测试复用 Nexus 的网格和相机，WebGL 1 使用 reverse-Z 深度缓冲绘制顶点着色。单独生成工程可运行 `make miniprogram-3d` 或 `make douyin-3d`。 [WebGL 帧协议](integration/rendering/webgl/frame.xu)

微信和抖音开发者工具的模拟器已验证 2D 触控、收集与重开，以及 3D 旋转和深度遮挡。两个平台的真机测试仍待执行。3D 示例目前按顶点颜色绘制，PBR 材质和阴影的像素回归使用下文的原生 GPU 测试。

## 功能完整性

完整性按能否制作、编辑、调试、打包并独立运行 2D/3D 游戏验收，各子系统均需可运行样例和失败路径检查。
整体尚未完整；以下状态只反映已经实现并验收的能力，后续对照 Godot 4 的系统范围逐项补齐。

| 子系统 | 当前可用能力 | 继续补齐的验收范围 |
| --- | --- | --- |
| 场景/对象 | 混合 2D/3D 树、变换、分组、生命周期、PackedScene、2D 相机与 3D 透视/正交镜头持久化、GLB/音频/脚本/光源附件、方向光 CSM 配置、初始字段和稳定信号路由 | 全局 UID 索引、实例覆盖、跨世界引用 |
| 2D 渲染 | GPU 批次、精灵、PNG/图集、裁剪、透明、相机、位图/TrueType 文本、SDF 图元 | TileMap、2D 光照/阴影、粒子、画布特效 |
| 标准 GPU | 独立设备/缓冲传输、纹理/mip、采样器、Shader、图形管线、深度/索引/实例化命令、离屏像素读回、缓冲区计算管线/dispatch、独立窗口/键鼠文本/多点触摸队列与 SDR Surface/Frame | 自绘 IME 候选/剪贴板/手柄、HDR 呈现、计算采样/纹理、间接 dispatch、立方体/3D 纹理、MRT/MSAA/存储绑定及其它高级渲染能力 |
| 3D 渲染 | 网格/相机、Reverse-Z、法线/UV、程序网格切线生成、256 候选/每网格 16 源方向/点/聚光材质、范围/锥体剔除、场景网格视锥剔除、距离 LOD/滞回、GPU 2× 超采样、方向/聚光/点光 3×3 PCF 阴影及 2–4 级 CSM、节点光源收集与持久化、五槽贴图、单双面、mipmap 与三线性采样 | glTF MikkTSpace 切线生成、IBL、HDR、后处理、MSAA/TAA/FXAA、屏幕误差 LOD/自动简化与 LOD 持久化、遮挡剔除、分簇光照 |
| 资源管线 | PNG/baseline JPEG、受限 GLB 几何/PBR/图片/采样器、受限 OBJ、ASCII/二进制 STL、实例共享、固定资源 ID/来源哈希与失败回滚 | 完整材质、更多模型格式、异步加载、全局缓存/重导入、其他附件、资源包与热替换 |
| 脚本 | Xu 标量 VM、多入口、场景挂载、稳定 ID 信号与批量热重载 | 完整类型/对象/绑定、普通函数调用、协程、生命周期、调试器、更新分发 |
| 动画 | 图集帧动画、glTF TRS 关键帧/LINEAR/STEP/CUBICSPLINE、四权重 CPU 线性蒙皮与独立实例 | 通用属性时间轴、GPU 蒙皮、morph、混合树、状态机、事件、根运动及动画场景持久化 |
| 物理 | 2D AABB 运动/滑动与碰撞 | 2D/3D 形状查询、宽相位、刚体、约束、连续碰撞与物理事件 |
| 输入/时间 | 键盘与独立模拟输入源、帧边沿、固定/浮动摇杆与按钮、多指捕获/取消、固定步进、暂停 | 手柄、鼠标完整映射、重绑定、回放与时间缩放 |
| 音频 | 静态/流式 WAV、32 路混音、分层总线、音量/声像/暂停/循环、定位/重播、逐样本淡化/交叉淡化、2D/3D 距离与声像、节点生命周期、场景 WAV/总线/声源恢复 | 压缩编解码、异步解码、音效 DSP、遮挡、Doppler、HRTF、调试工具 |
| 游戏 UI | UiFrame 与 Xu 布局/样式、按钮/滑块等控件、文本输入、窗口事件适配、XDF1 回放和 3D HUD 叠加 | 持久控件树、场景级焦点导航/事件路由、无障碍 |
| 导航/AI | 未实现 | 路径查询、导航网格、动态障碍、避让与行为设施 |
| 网络游戏 | 未实现 | 会话、同步/RPC、权限、插值、预测与重连；传输复用 Xu 基础库 |
| 编辑器 | 未实现 | 项目/场景/资源面板、属性检查器、视口、撤销重做、脚本调试 |
| 项目/导出 | Xu CLI 编译；Phone game 原生工程；微信小程序和抖音小游戏 2D/3D WebGL 工程及随包 Wasm | 编辑器导出配置、资源包/热替换、商店发布流程 |
| 调试/性能 | 源位置错误、回归程序、GPU 像素回读 | 断点/堆栈、CPU/GPU 分析、内存/资源监测与性能基线 |
| 平台 | macOS arm64 / Metal / CoreAudio，iPhone 8 / Metal / CoreAudio，Sony XQ-BE72 / Vulkan / AAudio，双端有原生 2D 与 3D 样例，微信/抖音 2D 与 3D 模拟器验收 | 更多手机型号、实机捏合与生命周期压力、音频中断、微信/抖音真机、Linux/Windows 真机与浏览器部署 |

实施顺序优先打通端到端链路：3D 材质/纹理/光照 → 资源与场景持久化 → 动画/物理/音频/UI → 编辑器与独立导出。
每项只有接入示例、错误处理和回归后才更新状态；声明 API 或预留目录不算功能完成。

## 结构分层

产品保持一个 `xu.xun` 和统一版本，包按职责与依赖方向划分；没有把每个目录变成独立模块或仓库。
目标结构如下，资源/服务/编辑器等未完成项仍按前面的完整性表推进：

| 层 | 职责 | 允许依赖 |
| --- | --- | --- |
| 基础 | 数学、几何、通用数据和私有适配器 | Xu 标准库 |
| 平台 | 窗口/事件、GPU/音频设备、原生 ABI | 基础与平台 SDK |
| 数据 | 资源描述、格式解码、字节码 | 基础；格式输出数据描述，不创建运行对象 |
| 服务 | 渲染、物理、音频、导航、网络、VM | 数据、基础与所需平台接口；不直接依赖场景树 |
| 场景模型 | Node、变换、组件、PackedScene | 基础与资源身份；不持有平台指针 |
| 运行整合 | 主循环、场景与服务同步、脚本宿主/对象绑定 | 场景模型和服务 |
| 工具/编辑器 | 导入/构建、检查器、调试、预览、开发轮询 | 公开运行时接口和工具链；运行时不反向依赖工具 |
| 游戏/Runner | 项目内容、游戏入口、导出执行程序 | 引擎公开接口 |

场景和服务由运行整合层连接：渲染器接收绘制数据/快照，物理服务接收形状与状态，场景保存节点与资源引用。
这样可无窗口解码资源、运行 VM 或执行物理，而不要求创建编辑器和 GPU 设备。

当前已落实的包边界：

| 包 | 实际职责 |
| --- | --- |
| `foundation/math` | 唯一的向量、矩阵、四元数、基础矩形算法；无场景/平台/文件依赖 |
| `foundation/color` | RGBA8 数据编码，不包含材质和颜色空间策略 |
| `platform/gpu` | GPU 后端的诊断显示名称；后端常量直接使用标准 `gpu` |
| `platform/sdl_audio` | 独立音频 ABI：设备、PCM 数据复制、暂停/清空；不链接 GPU 或创建窗口 |
| `platform/sdl_image` | 独立 CPU PNG 原生解码；不初始化视频/GPU/音频 |
| `formats/gltf` | GLB 解码与节点/图元/材质/图像/采样器描述；不读文件、不实例化场景、不上传 GPU |
| `formats/obj`、`formats/stl`、`assets/mesh` | 纯 CPU 静态网格解码，以及独立的有界文件读取/扩展名分派；不创建场景或 GPU，不读材质旁文件 |
| `resources/scene`、`formats/scene` | 不可变节点、2D/3D 相机、GLB/WAV/字节码来源、表面/总线/声源/脚本/局部光源描述和版本化 JSON 编解码；无文件、SceneTree 或平台依赖 |
| `integration/scene` | 节点捕获、有界加载、原子文件替换、转换 PackedScene 与节点实例化；不创建 GPU 服务对象 |
| `integration/scene_render` | 固定哈希 GLB 资源准备、共享模型、表面恢复、保留来源信息的捕获与保存 |
| `integration/scene_audio` | 隔离声音世界、固定 WAV 来源/总线/声源恢复、节点暂停/空间参数同步、离线混音或外部设备泵送 |
| `integration/scene_script` | 固定字节码来源、初始字段覆盖、稳定 ID 路由、独立实例与事务重载；无编译器/GPU/音频依赖 |
| `integration/scene_lighting` | 局部光源捕获、整批绑定与节点/光源实例化；无渲染、音频、脚本服务或 GPU 依赖 |
| Xu 标准库 `gpu` | 无窗口 Device/Buffer、异步传输、Texture/Sampler、Shader/Pipeline、离屏 render pass、缓冲区 ComputePipeline/Pass、SDR Surface/Frame、Fence/Readback 和逻辑资源统计；不拥有窗口循环或场景/PBR/预算 |
| Xu 标准库 `window` | 独立窗口生命周期/状态、键盘/浮点鼠标/滚轮/UTF-8 文本/IME 队列及输入控制；不创建设备 |
| Xu 标准库 `window/events` | 纯 Xu 事件数据/常量，包含物理与逻辑键、修饰键、窗口身份及重置原因；无 C/SDL 或设备依赖 |
| Xu 标准库 `gpu/layout` | 20 种通用格式的块大小、2D mip 链、逻辑字节数与传输对齐；纯 Xu，不创建设备或依赖 SDL |
| `resources/image` | CPU 侧 RGBA8 图片数据与校验；不持有解码器、文件或 GPU |
| `assets/image` | 有界 PNG 文件快照/内存解码，调用 SDL CPU codec；不创建窗口或 GPU |
| `resources/mesh` | 类型化 CPU 顶点/索引、校验、程序几何和切线生成；无 SDL、GPU、场景或文件依赖 |
| `resources/lod` | 不可变距离阈值、滞回与级别选择；不依赖向量、网格、场景、相机或设备 |
| `resources/lighting` | 不可变方向/点/聚光描述与有界环境，纯 CPU，无 GPU/窗口/场景依赖 |
| `integration/lighting` | Node3D 光源绑定、世界空间收集与可见性/删除处理，无渲染器或设备依赖 |
| `resources/canvas` | 纯 CPU 2D 顶点、批次、图集 UV 与容量验证，无 GPU/窗口依赖 |
| `rendering/two_d` | 标准 GPU/window 上的画布服务、纹理、裁剪和诊断读回；不依赖场景或资产加载 |
| `rendering/three_d` | 标准 GPU/window 上的 3D 设备、网格、纹理、材质与 Reverse-Z；无 nexus 原生归档 |
| `assets/shaders/two_d`、`three_d` | 分别显式加载离线着色器产物；不运行编译器，不互相导入 |
| `integration/image_render/two_d`、`three_d` | 分别把 CPU 图片上传到对应 GPU 服务；不互相导入 |
| `integration/rendering/two_d`、`three_d` | 2D 仅录制 CPU 批次；3D 连接场景与网格/材质服务 |
| `integration/input` | 标准窗口事件到输入动作的显式适配 |
| `assets/gltf`、`integration/gltf_render` | 文件读取/场景实例化适配，以及独立的 GLB 网格/材质/纹理上传和场景绑定；完整资源管理器尚未实现 |
| `resources/audio`、`formats/wav`、`assets/audio` | 不可变 PCM、共享 WAV 布局/分块解码、有界快照与流式文件读取；均无设备依赖 |
| `audio/mixer`、`audio` | 纯 Xu 混音/空间参数、PCM 环形缓冲与淡化，以及独立设备输出/有界补队列 |
| `integration/audio_stream` | 连接 WAV 文件读取与 PCM 缓冲，不依赖场景、设备或 GPU |
| `integration/audio` | 节点生命周期、暂停和显式 2D/3D 声源/监听者更新 |
| `script/bytecode`、`script/vm` | 纯数据验证与受预算执行；无场景/GPU/编译前端依赖 |
| `script/host` | 节点身份、脚本调度、信号、内存重载；无文件轮询或编译器依赖 |
| `script/development`、`script/compiler` | 分离的开发轮询与编译工具链；不被 VM/host 导入 |

`scene` 保存节点树、PackedScene 与相机；`input`、`timing`、`physics2d`、`animation/sprite` 分别维护动作、固定时钟、运动碰撞和图集动画。
2D/3D 都直接使用 `foundation/math` 的数学类型。`assets/gltf` 读取标准格式数据并实例化场景，没有重复拥有的格式包装。

首次发布前只维护一套当前接口和格式，消费者同步迁移。根包、`gpu` 门面、重复数学类型和开发中间格式已经移除。
`architecture.json` 声明每个包的允许依赖；`make layers` 检查实际导入、包声明、循环、原生/前端归属和资源/运行常量。
`scene` 不依赖输入、时钟、物理、渲染或音频服务；跨系统功能通过整合层组合。

```sh
make layers
python3 tools/check_layers.py --graph
```

场景接口从 `github.com/xulang-org/nexus/scene` 导入；数学从 `foundation/math` 导入；CPU 2D 批次从 `resources/canvas` 导入，设备分别从 `rendering/two_d` 和 `rendering/three_d` 导入。
场景绘制和图片上传也按 `two_d` / `three_d` 分包，GLB 上传由 `integration/gltf_render` 连接。
开发轮询改由 `dev #"github.com/xulang-org/nexus/script/development"` 创建，使用 `file.poll` 或 `file.poll_scene`；
运行时直接调用 `NodeScript.reload` / `SceneScripts.reload`，不需要加载开发轮询器。
整合层目录使用 `integration/`：`runtime/` 保留给语言运行时，场景/服务适配统一放入 `integration/`。

基础数学、GLB/OBJ/STL/WAV 格式解码、CPU 图片/PCM/网格数据、程序几何/切线生成、离线混音和 VM 可以无 SDL 编译与运行。PNG 解码使用 SDL CPU codec，需要原生归档和 SDL，
但无需窗口、视频子系统或 GPU；真正绘制时才创建设备。显式 `capture` 是渲染服务的诊断输出，不属于资源加载；使用标准 PNG 紧凑字节接口和 stored DEFLATE，文件较大但避免通用压缩过程的额外开销。
本机有一个仅复制这些底层包的隔离构建测试，不提供场景/渲染/前端源码或原生归档，并把 SDL 路径设为不存在以验证边界。

## GPU 后端

2D 必须通过标准库成功创建 Window、Device、Surface、着色器、管线和离屏颜色目标；3D 通过标准库创建设备、着色器、管线与颜色/深度目标。
没有软件渲染回退。默认自动选择，也可明确指定后端；指定不可用后端时抛错。

| 后端 | 预期系统 | 当前验收 |
| --- | --- | --- |
| Metal | macOS / iOS | macOS arm64 与 iPhone 8 (iOS 16.7.16) Metal 2D/3D、HUD 叠加、像素回读和资源回收通过 |
| Vulkan | Android / Linux / Windows | Sony XQ-BE72 (Android 13) Vulkan 2D/3D + HUD 实机呈现与事件/Back 暂停通过；Linux/Windows 路径已接入 |
| D3D12 | Windows | SDL GPU 路径已接入；尚未在对应系统运行验收 |

后端来自 [SDL GPU](https://wiki.libsdl.org/SDL3/CategoryGPU)。设备选择方式见
[SDL_CreateGPUDevice](https://wiki.libsdl.org/SDL3/SDL_CreateGPUDevice)。
当前渲染功能包括彩色三角形、带仿射变换的四边形、RGBA GPU 纹理、纹理图集区域、
PNG 文件上传、最近邻/线性采样、透明混合、GPU 裁剪、有序批次提交、垂直同步和显式像素回读 / PNG 截图。
2D 顶点变换在 Xu 侧完成；光栅化、纹理采样和混合在 GPU 执行。
3D 顶点由 GPU 着色器应用 MVP，使用持久顶点/索引缓冲、RGBA8 颜色目标和 D32 Reverse-Z 深度测试。
2D/3D 均由离线工具按指定后端准备 MSL（Metal）、SPIR-V（Vulkan）或 DXIL（D3D12）。
源码位于 `rendering/two_d/shaders` 和 `rendering/three_d/shaders`；目标工具链与真实 GPU 运行须分别验收。

## 运行

需要 **Xu 0.12.7-dev.1**、Clang、Python 3，以及 SDL 3.4+ 开发头文件和运行库。
默认通过 `pkg-config sdl3` 查找头文件；Windows 可显式传入包含 `SDL3/SDL.h` 的目录。
桥接在运行时加载 SDL，不把 SDL 源码或二进制复制进本库。

```sh
# macOS 依赖示例
brew install sdl3 pkg-config

make check
make demo
make demo2d
make demo3d
make demo-glb
make demo-models
make demo-script
make demo-materials
make demo-audio
make demo-audio-stream
make demo-audio-seek
```

示例：WASD / 方向键移动，Space 暂停，Esc 退出。避开墙体收集六颗金色宝石。
右上角方块显示进度。它使用场景实例、固定 60 Hz 更新、连续碰撞、GPU 画布与四帧 PNG 精灵动画。
改变窗口比例时按设计尺寸等比缩放并留黑边；暂停会同时冻结角色、图集动画和宝石旋转。

```sh
# 编译并运行无窗口、2D、3D、GLB、材质和脚本示例，保存实际 GPU 输出
make smoke

# 指定后端；不可用时明确失败
./build/arena --backend metal
./build/arena --backend vulkan
./build/arena --backend d3d12

# 自动输入仅用于有界示例，可重复运行
./build/arena --frames 120 --autoplay --capture build/arena.png

# 宽窗口保持 960×640 的设计比例；可加载自备的四帧横向 PNG 图集
./build/arena --width 1280 --height 640 --texture examples/arena/assets/player.png

# 3D：方向键环绕相机，Space 暂停物体旋转，Esc 退出
./build/three-d --backend metal --frames 120 --capture build/three-d.png

# 导入 GLB 静态几何，使用文件里的层级、变换、顶点颜色和多个图元
./build/glb-preview --frames 120 --capture build/glb-preview.png
./build/glb-preview --model path/to/geometry.glb --backend metal

# 导入 GLB 不透明 PBR 材质与内嵌 PNG
make demo-glb-materials
./build/glb-materials --frames 120 --capture build/glb-materials.png
```

`make sdk` 核对实际编译器版本。默认使用 PATH 中的 `xu`，也可用 `XU` 选择完整的 Xu 0.12.7-dev.1 开发 SDK。
修复内容属于编译器：解析 native 模块、校验归档/目标/ABI、生成 C 调用适配和链接，调用所选 SDK 的配套工具，
并为资源所有者及资源数组生成自动析构。标准库新增 `gpu/layout` 统一纹理格式、mip 链、行 pitch 与 mip offset 的受检计算，UI 图片上传与引擎 2D/3D 纹理共用；标准 `gpu` 已提供无窗口设备、缓冲区与异步传输、fence/读回、纹理/采样器、Shader/Pipeline 和离屏 render pass，以及 compact `[]u8` 借用 ABI。标准窗口/呈现已补齐，2D/3D 均已迁移标准事件、资源和绘制命令；PBR、场景和游戏预算仍在引擎。
完整 SDK 的编译器、标准库和包搜索路径必须一致：

```sh
NEXUS_XU_SDK=/path/to/xu-0.12.7-dev.1
XU_ROOT="$NEXUS_XU_SDK" XU_STDLIB_ROOT="$NEXUS_XU_SDK/src" \
XUPATH="$NEXUS_XU_SDK/src:$NEXUS_XU_SDK/packages" XU="$NEXUS_XU_SDK/bin/xu" \
make native-probe check test gpu-smoke smoke script-live-smoke
```

`make check-core test-core` 覆盖无设备的场景、资源、音频和脚本功能。
纯数据隔离构建使用正式版公开的 `--no-opt` 和 `--release` 两种模式；不再向 Xu 传入开发工具链的 `-O0/-O2/-O3` 参数。原生 C 模块的 Clang 优化参数独立保留。
`make native-probe` 在无 SDL 的独立模块中验证整数、十二参数、混合参数/数组、空数组、结构体字段借用、
可写数组 COW 隔离与 void 返回，编译、链接并执行真实 C 调用。
`make check test gpu-smoke smoke script-live-smoke` 包含设备与运行中热更新检查；失败直接报告。
macOS arm64 回归覆盖独立标准 GPU 传输、Metal 2D/3D 绘制与回读、CoreAudio、资源回收与失败回滚、
场景保存/新进程恢复，以及真实 GPU 进程内 300 帧脚本热重载（状态和信号连接保留，错误源码/产物拒绝）。
SDL 动态库不在标准位置时，标准 GPU/window 与 CPU PNG codec 使用 `XU_SDL_LIBRARY`；音频设备仍使用独立的 `XU_NEXUS_SDL_AUDIO_LIBRARY`。
3D 着色器通过 `make mesh-shaders` 或 `tools/mesh_shaders.py --backend ... --out-dir ...` 显式准备。
macOS 使用 MSL 源码（驱动编译），Vulkan 需 glslangValidator，D3D12 需 DXC；运行服务只接收内存数据。
Linux / Windows 的构建配方与着色器源文件已提供，尚未在对应系统验证。

## 2D 分层接口

2D 服务使用 `rendering/two_d.Renderer2D` / `Texture2D`，CPU 批次使用 `resources/canvas.Batch2D`。 `clear()` 只清空逻辑顶点数并复用已分配容量；后续录制覆盖有效前缀，读取与绘制都受逻辑顶点数限制。
场景画布/精灵位于 `integration/rendering/two_d`，只录制 CPU 数据，可无 GPU 或原生归档运行。
PNG 先解码为 `resources/image` 数据，再显式上传；窗口与 GPU 服务不读取资源文件。

```xu
ren #"github.com/xulang-org/nexus/rendering/two_d"
canvas #"github.com/xulang-org/nexus/resources/canvas"
shaders #"github.com/xulang-org/nexus/assets/shaders/two_d"
images #"github.com/xulang-org/nexus/assets/image"
image_render #"github.com/xulang-org/nexus/integration/image_render/two_d"
#gpu
colors #"github.com/xulang-org/nexus/foundation/color"
fm #"github.com/xulang-org/nexus/foundation/math"

image := images.load_png("examples/arena/assets/player.png") or >>
program := shaders.load_canvas("build/canvas-shaders") or >>
$renderer := ren.open_2d("My 2D Game", 960, 640, gpu.AUTO, &program) or >>
$texture := image_render.upload_image_2d(&renderer, &image, false) or >>
$batch := canvas.new_batch()
white := colors.rgba8(255, 255, 255, 255) or >>
batch.quad_region(fm.rect2(64.0, 64.0, 64.0, 64.0), fm.identity(), white,
    fm.rect2(0.0, 0.0, 0.25, 1.0)) or >>
renderer.begin(colors.rgba8(12, 20, 34, 255) or >>) or >>
renderer.submit_texture(&batch, &texture) or >>
renderer.present() or >>
texture.close() or >>
renderer.close() or >>
```

同一 CPU 图片可上传到不同设备，每次上传同步复制数据并返回独立 GPU 资源。
PNG 的有界读取、尺寸检查和 CPU 解码先于上传，失败不留下部分 GPU 纹理；`decode_png(&raw)` 可复用内存快照。
SDL codec 到 RGBA8 的转换不附加材质色彩空间/伽马策略，不提供 ICC 色彩管理契约。
图片字段公开可编辑，上传适配器会重新校验尺寸、像素数量和值范围；它不是带 UID/缓存/异步驻留的完整资源管理器。

[`examples/two_d/main.xu`](examples/two_d/main.xu) 展示平台事件、输入、PNG 图片、图集动画、场景画布/精灵和独立渲染服务的组合。
方向键移动，Space 暂停，Esc 退出；窗口缩放使用相机适配与裁剪。运行 `make demo2d`，或：

```sh
./build/two-d --backend metal --frames 120 --capture build/two-d.png
```

着色器由调用方显式提供；`open_2d` 不读文件或调用编译器。示例默认读取 `build/canvas-shaders`，可用 `--shaders DIR` 指定目录：

```sh
make canvas-shaders
python3 tools/canvas_shaders.py --backend metal --out-dir build/canvas-shaders
./build/two-d --shaders build/canvas-shaders --frames 120
```

Vulkan 产物需 glslangValidator，D3D12 产物需 DXC。实际设备验收目前仅 Metal。
每帧由应用调用一次标准 `window.pump()`，再按窗口调用 `renderer.poll()`；返回标准 `window/events.Event`，
动作使用 `integration/input.apply_window_input`，物理键直接使用标准 HID 常量。`renderer.window()` 返回标准窗口借用，可查询/缩放窗口或配置文本、指针输入。

服务维护可采样、可读回的 RGBA8 离屏目标，绘制后通过标准 Surface 呈现。
输出最多每边 16384、合计 16M 像素；每用户纹理最多每边 4096、4M 像素，每设备最多 1024 张用户纹理、64 MiB 逻辑纹理预算（不计内部目标与白纹理）。
每帧顶点最多 393216。几何在 CPU 保留 f64，提交时使用标准 `encoding/binary` 编码为 FLOAT2/UNORM8X4/FLOAT2。
读回在同一绘制版本内缓存，后续绘制使缓存失效；`capture` 使用已有标准 `image/png.encode_rgba_bytes` 对读回字节编码，跳过 image.RGBA 图像对象构造，不依赖 CPU 解码桥接。
缩放在下一次 `begin` 更新目标；最小化时保留最后正尺寸离屏目标，Surface 无图像属于正常跳帧。
关闭渲染器回收其设备、所有子资源和窗口，其他渲染器继续可用。

## 3D 绘制接口

```xu
shaders #"github.com/xulang-org/nexus/assets/shaders/three_d"
meshes #"github.com/xulang-org/nexus/resources/mesh"
fm #"github.com/xulang-org/nexus/foundation/math"
colors #"github.com/xulang-org/nexus/foundation/color"
#gpu
ren #"github.com/xulang-org/nexus/rendering/three_d"
nexus #"github.com/xulang-org/nexus/scene"

program := shaders.load_mesh("build/mesh-shaders") or >>
$device := ren.open_3d("My 3D Game", 960, 640, gpu.AUTO, &program) or >>
$data := meshes.new_mesh_data_3d()
red := colors.rgba8(255, 80, 64, 255) or >>
data.vertex(fm.vec3(-1.0, -1.0, 0.0), red) or >>
data.vertex(fm.vec3(1.0, -1.0, 0.0), red) or >>
data.vertex(fm.vec3(0.0, 1.0, 0.0), red) or >>
data.triangle(0, 1, 2) or >>
$mesh := device.upload(&data) or >>
camera := nexus.new_camera_3d()
view := camera.view_projection(1.5) or >>
device.begin(colors.rgba8(12, 20, 34, 255) or >>) or >>
device.draw(&mesh, view) or >>
device.present() or >>
mesh.close() or >>
device.close() or >>
```

`Vec3` / `Vec4` / `Mat4` 使用 f64；提交时明确转换为 IEEE binary32，列向量矩阵顺序为
`projection * view * model`。3D 世界使用右手系、+Y 向上、相机朝 -Z；角度为弧度。
透视投影深度范围为 0...1，近面为 1，远面为 0；深度清零并以 GREATER 比较。
着色器遵循 SDL 的统一裁剪空间，不额外翻转 Vulkan Y。
相机和投影约定独立放在 `camera3d.xu`，向量/矩阵代数位于独立的 `foundation/math` 包。

`Device3D` 独占窗口和交换链；当前不支持在同一窗口混用 `Renderer` 的 2D 通道。
`begin → draw → present` 定义一帧；首次 `read_pixel` / `capture` 会结束绘制并等待 GPU 回读，
此后同帧可继续回读和截图，随后 `present`，不能追加绘制。截图来自 GPU 颜色目标。
窗口尺寸变化时下一帧重建颜色/深度目标；最小化时由应用暂停绘制。
设备关闭会释放其全部网格，子资源随后关闭安全；陈旧或跨设备网格不可绘制。

上面的 `draw` / `demo3d` 保留无光照顶点色路径，双面绘制、单采样、SDR；带法线的材质路径见下文。
每网格最多 262,144 顶点 / 1,048,575 索引；设备网格预算 64 MiB，全局最多 512 网格、8 个 3D 设备。
每帧最多 16,384 次绘制；3D 目标单边最多 4,096、总计最多 4,194,304 像素。
提交标量须有限且绝对值不超过 1e9；浮点转 binary32 使用就近偶数舍入，并将零规范化为正零。

### 3D 场景与资源绑定

`new_scene_tree` 保持 2D 根节点；`new_scene_tree_3d` 创建 3D 根节点。
公共节点只管理身份、层级、可见性与生命周期，2D/3D 变换各有可回收的组件池。
`add_child`、`add_child_3d`、`add_group` 分别创建 2D、3D 和无变换的普通分组。
`node_info` 读取公共信息；`node` / `node_3d` 读取对应维度的快照，维度不符会报错。

已有 `device` 与 `mesh` 时，场景层的关键调用如下；完整主循环见
[`examples/three_d/main.xu`](examples/three_d/main.xu)。

```xu
fm #"github.com/xulang-org/nexus/foundation/math"
colors #"github.com/xulang-org/nexus/foundation/color"
scene_render #"github.com/xulang-org/nexus/integration/rendering/three_d"
nexus #"github.com/xulang-org/nexus/scene"

$tree := nexus.new_scene_tree_3d("World", 64) or >>
root := tree.root()
pivot := tree.add_child_3d(root, "Pivot") or >>
object := tree.add_child_3d(pivot, "Object") or >>
tree.set_transform_3d(pivot, fm.rotation_y(0.5)) or >>
camera_node := tree.add_child_3d(root, "Camera") or >>
tree.set_position_3d(camera_node, fm.vec3(0.0, 0.0, 5.0)) or >>
camera := nexus.new_camera_node_3d(&tree, camera_node) or >>
$scene := scene_render.new_scene_3d(&device) or >>
scene.attach_mesh(&tree, object, &mesh) or >>
view := camera.view_projection(&tree, 1.5) or >>
device.begin(colors.rgba8(12, 20, 34, 255) or >>) or >>
draws := scene.draw($&device, &tree, view) or >>
device.present() or >>
```

普通分组传递同一维度的祖先变换；遇到另一维度的节点时，变换继承从该边界重新开始。
例如 3D 节点下的 2D 节点使用自身的 2D 空间；可见性、暂停和删除仍沿完整公共层级传播。
2D/3D 同树不意味着已支持同窗口合成，当前两个 GPU 绘制通道仍使用独立窗口。

`set_transform_3d` 只接受有限仿射矩阵；投影矩阵属于相机。`Mat4.affine_inverse` 支持非均匀/负缩放与剪切，
归一化行列式绝对值 ≤ 1e-12、非仿射矩阵或结果溢出会报错。
`reparent(..., true)` 可在 2D/3D 节点换父节点时保留世界变换，失败前不修改层级。
普通分组没有本地变换，不能使用 `keep_global=true`；需要保留其后代世界姿态时使用对应维度的空间节点。

`CameraNode3D` 将投影参数绑定到一个现存 Node3D，其视矩阵为节点完整世界仿射矩阵的逆；
父级缩放也会影响观察。奇异、已删除或排队删除的相机节点会报错。
暂停控制游戏更新，场景仍绘制；示例中相机支架设为 `PROCESS_ALWAYS`，暂停后仍可环绕观察。

`Scene3D` 在场景先序中绘制绑定的可见网格，返回实例数和三角形数。
绑定为非拥有引用，须始终配合同一棵树使用；绑定保存完整节点 ID，GPU 句柄也包含复用代次，过期句柄会被拒绝。
`attach_mesh` 为同节点替换绑定，`detach_mesh` 不关闭网格；隐藏或排队删除的节点不产生绘制。
场景绘制自动执行保守视锥剔除；返回的 `instances/triangles` 只计已提交网格，`culled_instances/culled_triangles` 计本次被视锥排除的可见绑定，不包含隐藏或待删除节点。
节点槽复用不会自动继承旧绑定；`prune(tree)` 清除已删除/排队删除节点的引用，返回移除数。
每场景最多保留 65,536 个绑定；关闭一个仍由可见节点引用的网格后继续绘制会明确报错。
当前对象 ID 仍限定于所属树，尚未实现跨世界或磁盘持久化身份。

`PackedScene` 已可复制并实例化混合的 2D、3D 和普通分组节点，其局部变换与实例状态相互独立；
节点文件的保存与重载见下文。
它仍是内存快照；相机投影附件、网格绑定、脚本和 GPU 资源由调用方单独配置。

## 3D 直接光材质

```sh
make demo-materials
```

[`examples/materials`](examples/materials/main.xu) 使用同一份球体网格绘制 15 个场景实例。
三行金属度为 0 / 0.5 / 1，每行从左到右粗糙度由 0.1 增至 1；光照方向随时间变化。
方向键环绕相机，Space 暂停光照变化，Esc 退出。所有高光和明暗均在 GPU 中按法线计算。

`MeshData3D.vertex_lit(position, color, normal)` 接受非零有限法线并归一化，颜色要求不透明。
`vertex` 仍构造无光照顶点；只有所有顶点均有有效法线的网格才能绑定材质。
`sphere_mesh_3d` 生成朝外 CCW 绕序、带法线和接缝 UV 的索引球体，细分上限为 128 segments / 64 rings，并省略极点退化三角形。
GLB 几何上传器 `upload` 会保留 NORMAL / TEXCOORD_0，缺少 NORMAL 的 primitive 继续使用无光照路径；
材质入口 `upload_model` 要求每个 primitive 已有 NORMAL，法线贴图还要求显式切线。

```xu
light_data #"github.com/xulang-org/nexus/resources/lighting"
fm #"github.com/xulang-org/nexus/foundation/math"
ren #"github.com/xulang-org/nexus/rendering/three_d"

material := ren.material_3d(fm.vec3(0.5, 0.15, 0.05), 0.0, 0.4, fm.vec3(0.0, 0.0, 0.0)) or >>
source := light_data.directional(fm.vec3(0.5, 1.0, 1.0), fm.vec3(4.0, 4.0, 4.0)) or >>
lighting := light_data.environment(fm.vec3(0.03, 0.03, 0.03), camera_position, 1.0, [source]) or >>
scene.set_material(&tree, object, material) or >>
device.begin(background) or >>
scene.draw_lit($&device, &tree, view_projection, &lighting) or >>
device.present() or >>
```

材质的 base 为线性 RGB 0...1、metallic 为 0...1、roughness 为 0.045...1、emission 为线性 RGB 0...16。
光照方向是世界空间中的表面指向光源向量；radiance 为线性 RGB 0...64、diffuse ambient 为 0...1、exposure 为 0.01...16。
不是从 8 位 sRGB 自动解码的颜色接口；调用者须按线性颜色提供参数。
算法使用 GGX 分布、Smith 相关可见性、Schlick Fresnel 与漫反射，公式背景见 [Filament 技术说明](https://google.github.io/filament/main/filament.html)。
法线用模型矩阵的逆转置变换，非均匀/负缩放与剪切沿用世界仿射矩阵；奇异矩阵拒绝绘制。
直接光、简单漫反射环境项与自发光先在线性空间组合，再做曝光、Reinhard 色调映射和 sRGB 编码写入 RGBA8。
当前是不透明直接光路径，支持方向光/点光/聚光及单双面策略；已有方向光、聚光灯与点光源阴影，没有 IBL/环境反射、透明排序或 HDR 中间目标。

`Device3D.draw_material` 支持单网格绘制；`Scene3D.set_material` 按节点保存材质值，网格仍为非拥有绑定。
`draw_lit` 绘制有材质节点并允许同时绘制无光照网格；有材质绑定的场景调用无光照 `draw` 会明确报错。
`clear_material` 恢复无光照路径，`detach_mesh` / `prune` 同时清理材质。
替换已有材质节点的网格时，法线与纹理 UV 要求均参与只读预检；GLB 批量绑定在失败前不会部分写入场景。
关闭网格或设备后的 generation 检查仍生效。

MSL、GLSL、HLSL 使用同一份 `lighting.inc` 算法，平台绑定按 [SDL GPU shader 规则](https://wiki.libsdl.org/SDL3/SDL_CreateGPUShader) 编写。
材质验证、网格、法线归一化、场景和矩阵打包在 Xu 中；GPU 着色代码尚未使用 Xu 编译目标。
本次仅 Metal 真机运行通过，GLSL/DXIL 工具链与对应 GPU 仍待验收。

## 3D 基础颜色纹理

```sh
make demo-textures3d
# 有界运行与截图：
./build/textures3d --frames 120 --capture build/textures3d.png
```

[`examples/textures3d`](examples/textures3d/main.xu) 从原创 PNG 加载 CPU 图片，向独立 3D 设备上传并绘制三个旋转球体。
从左到右比较 sRGB 最近邻、sRGB 线性过滤、线性数据过滤；同一张颜色图片按线性数据解释会明显变亮。
方向键环绕相机，Space 暂停旋转，Esc 退出。最后一项展示显式颜色空间选择的差别，普通颜色 PNG 应使用 sRGB。

```xu
images #"github.com/xulang-org/nexus/assets/image"
image_render #"github.com/xulang-org/nexus/integration/image_render/three_d"

image := images.load_png("base-color.png") or >>
// 参数依次为：sRGB、线性过滤、重复寻址；这里使用 sRGB + linear + repeat。
$texture := image_render.upload_image_3d(&device, &image, true, true, true) or >>
textured := material.with_base_texture(&texture) or >>
scene.set_material(&tree, object, textured) or >>
// texture 保持存活直到使用该材质的绘制结束；without_base_texture() 返回移除贴图的材质副本。
```

`Texture3D` 是 **3D 设备上的二维采样图像**，并非体积纹理；它拥有独立 GPU 图像和采样器。
底层 `Device3D.texture_rgba(width, height, &pixels, srgb, linear, repeat)` 接受内存 RGBA8；
图片加载仍由 assets/image 负责，integration/image_render 上传，rendering 不引入文件或场景依赖。
上传同步复制 CPU 数据，可立即修改或释放输入数组；GPU 上传与随后绘制按设备命令顺序执行。

`vertex_lit_uv(position, color, normal, uv)` 提供带法线/UV 的顶点；`vertex_uv` 只提供 UV，仍用于无光照绘制。
UV (0,0) 对应图片首行左端，(1,1) 对应末行右端；允许有限的 ±1,000,000 坐标以支持 repeat。
原 `vertex` / `vertex_lit` 明确标记为无 UV，贴图材质要求每个顶点都有法线和 UV，缺失时拒绝绑定或绘制。
CPU 顶点为 `resources/mesh.Vertex3D`：f64 向量/UV、RGBA8 和属性存在标志。`Device3D.upload` 校验并通过标准 `encoding/binary` 编码为 position3、color4、normal3、UV2、tangent4，共 16 个 float / 64 字节；索引为 uint32。没有 nexus 的顶点 word-span ABI。

| 项目 | 当前约定 |
| --- | --- |
| 颜色空间 | `srgb=true` 使用 GPU sRGB 图像格式，RGB 在过滤前解码；false 使用 UNORM 线性数据。无需修改 CPU 像素 |
| 基础颜色 | 在线性空间将采样 RGB × 材质 base × 顶点 RGB 后参与现有光照、曝光和输出编码；原有参数/顶点 RGB 仍为线性 |
| 过滤/寻址 | 便捷接口提供最近邻/双线性、U/V 同步寻址、一级 mip；显式采样描述支持独立 min/mag、U/V 与 mip 层级过滤，见下节 |
| Alpha | 当前仍为不透明材质，忽略图片 alpha；不提供裁剪/透明混合模式 |
| 预算 | 单边 ≤4096、每张基础层 ≤4,194,304 像素；每设备全部 RGBA8 mip 层 texel 数据总计 ≤64 MiB，与网格/渲染目标分开；全局 ≤512 张活动 3D 纹理 |
| 生命周期 | 材质保存非拥有的 owner/generation 引用；close、析构或设备关闭后失效；复用槽位不会使旧材质采到新图片 |
| 上传时机 | active frame 外；成功绑定材质或提交绘制时检查 owner、generation、法线与 UV；失败不替换已有场景绑定 |

每次绘制均显式绑定图像/采样器；无贴图材质与无光照路径使用设备私有白色图像，避免同帧状态残留。
设备关闭统一释放子资源，显式 close 幂等；资源失效由使用者处理，不会自动延长 GPU 资源寿命。
PNG 解码不建立 ICC 色彩管理契约，sRGB/线性由调用方显式指定。
当前 Metal 上传使用紧密行距，其他后端采用 256 字节对齐；这是对 [SDL 3.4.14 Metal 上传实现](https://github.com/libsdl-org/SDL/blob/release-3.4.14/src/gpu/metal/SDL_gpu_metal.m#L1669) 的适配。

Metal 像素验收覆盖已知 sRGB/线性结果、过滤前解码、2×2 四角/7×3 非对齐行距、U/V 重复与边缘钳制、
GLB UV 上传、缺失/混合 UV、同帧材质切换、过期与跨设备引用，以及 64 MiB / 512 张限额释放恢复。
GLSL/HLSL 绑定与源码同步更新，但 Vulkan/D3D12 尚无本轮构建和真机验收；glTF MikkTSpace 切线生成、各向异性/LOD bias、自定义 mip 链、压缩纹理、完整 glTF 材质兼容与纹理热替换仍待实施。

### Mipmap 与独立采样配置

```sh
make demo-mipmaps3d
# 自动移动相机，执行 120 帧并截图：
./build/mipmaps3d --frames 120 --capture build/mipmaps3d.png
```

[`examples/mipmaps3d`](examples/mipmaps3d/main.xu) 用同一张 Xu 生成的棋盘图片和网格绘制三条延伸到远处的地面。
从左到右为无 mip、最近层级、三线性过滤；近处保留棋盘，远处 mip 过滤抑制明显的走样和相机移动时的闪烁。
Up/Down 调整相机距离，Space 暂停自动移动，Esc 退出。示例采用相同 sRGB 数据、双线性 texel 过滤和环境亮度，比较的是 mip 策略。
各向异性过滤尚未实现，倾斜表面仍可能过度模糊。

```xu
sampling := ren.TextureSampling3D{
    min_linear: true, mag_linear: true,
    repeat_u: true, repeat_v: false,
    mip_filter: ren.MIP_LINEAR,
}
$texture := image_render.upload_image_3d_sampled(&device, &image, true, sampling) or >>
// 也可使用 device.texture_rgba_sampled(width, height, &pixels, srgb, sampling)。
levels := texture.mip_levels() or >>
texel_bytes := texture.storage_bytes() or >>
```

`TextureSampling3D` 只描述上传时的采样策略，不是单独的 GPU 资源所有者；纹理继续拥有图像和采样器。
min_linear / mag_linear 分别控制缩小和放大的 texel 过滤，repeat_u / repeat_v 分别控制两轴寻址。
`MIP_NONE` 只分配基础层；`MIP_NEAREST` 生成完整 mip 链并选最近层级；`MIP_LINEAR` 在相邻层级间线性插值。
`min_linear=true` 与 `MIP_LINEAR` 组合为三线性缩小过滤；层级间过滤与层内 texel 过滤是独立选项。
默认零值为单层、最近邻、两轴 clamp-to-edge；无效 mip_filter 拒绝上传。便捷 `texture_rgba` / `upload_image_3d` 的行为保持单层。

mip 链由 GPU 在上传基础层后生成，命令在 copy/render pass 之外提交，遵守 [SDL mipmap 接口约定](https://wiki.libsdl.org/SDL3/SDL_GenerateMipmapsForGPUTexture)。
层级逐轴向下取整减半并至少为 1，直到 1×1，最多 13 层；支持非 2 的幂尺寸和 1×N / N×1。
sRGB 图像在生成/过滤时按颜色空间处理；Metal 已用黑白 texel 的已知线性平均值回读验证。
奇数尺寸的边缘重采样权重由 GPU 后端决定，不提供严格的面积平均契约。

64 MiB 限额按所有已分配层的 `4 × width × height` 逐层相加计算，不能仅按基础层或粗略 4/3 估算。
例如 128×128 单层为 65,536 字节，8 层为 87,380 字节；1×4096 的 13 层为 32,764 字节。
`storage_bytes()` 返回此预算值，不包含驱动对齐/图像元数据、私有白色图像或渲染目标，不等于 GPU 实际驻留内存；
`mip_levels()` 返回实际分配层数，两者均验证 owner/generation，关闭后查询报错。关闭纹理恢复完整链预算。
没有 CPU mip 回退；设备不支持所需图像格式/用途、创建或提交失败均明确报错。

Metal 验收含层级 0.25 / 0.75 的最近层级与插值对照、sRGB mip 平均、独立 min/mag 和 U/V、NPOT/1D/1×1、
三张 2048×2048 完整链恰好剩余一个 texel 的预算边界，以及释放后重新分配。
单层纹理也保留独立 min/mag；sampler 的 LOD 上限不被固定为零，避免 Metal 在缩小时错误选用放大过滤器。
本轮不改变着色器 ABI，Vulkan/D3D12 仍待对应系统构建与真机验收。

### ORM 与自发光贴图

```sh
make demo-material-maps
./build/material-maps --frames 120 --capture build/material-maps.png
./build/material-maps --frames 120 --lights off --capture build/material-maps-dark.png
```

[`examples/material_maps`](examples/material_maps/main.xu) 使用 Xu 生成的面板颜色、ORM 数据与灯条图像，
四个球体共享同一网格，按左上/右上/左下/右下分别展示基础颜色、基础颜色+ORM、自发光贴图、三槽组合。
方向键环绕相机，Space 切换外部光照，Esc 退出；关灯时下面两个球体仍显示灯条。
这里自发光只贡献自身表面的颜色，尚不照亮其他物体；没有 bloom、GI 或环境反射。

```xu
// CPU 图片和加载入口保持原有分层；ORM 用 srgb=false 上传。
$orm_texture := image_render.upload_image_3d_sampled(&device, &orm_image, false, sampling) or >>
$emission_texture := image_render.upload_image_3d_sampled(&device, &emission_image, true, sampling) or >>
color_material := material.with_base_texture(&base_texture) or >>
orm_material := color_material.with_orm_texture(&orm_texture, 1.0) or >>
mapped := orm_material.with_emission_texture(&emission_texture) or >>
scene.set_material(&tree, object, mapped) or >>
```

贴图计算在 GPU 线性空间内进行，数据通道约定参考 [glTF 材质规范](https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html#materials)。
当前三个槽均使用同一套 UV；各纹理保留独立颜色空间、过滤、mip 和寻址配置。

| 槽位 | 约定与计算 |
| --- | --- |
| 基础颜色 | `with_base_texture`；采样 RGB × 线性 base × 顶点 RGB，保留原有行为 |
| ORM | `with_orm_texture(texture, strength)`；R=环境遮蔽、G=粗糙度、B=金属度；必须为线性图像，sRGB 图像会被拒绝 |
| 粗糙度/金属度 | `max(0.045, material.roughness × G)` 与 `material.metallic × B`；贴图乘以原有材质参数 |
| 遮蔽 | 有限 strength 0...1；`1 + strength × (R - 1)` 只调制现有漫反射环境项，不影响方向光或自发光。strength=0 不会关闭 G/B 的作用 |
| 自发光 | `with_emission_texture`；采样 RGB × 线性 emission，不乘 base/顶点颜色；emission=0 时不发光 |
| 颜色空间 | 基础颜色/自发光通常按 sRGB 上传，也允许显式线性图像；ORM 只接受线性。`texture.is_srgb() or >>` 可查询实际资源格式，关闭后报错 |
| Alpha | 三个槽均忽略图片 alpha，输出仍不透明；没有新增透明/裁剪模式 |

`has_base_texture` / `has_orm_texture` / `has_emission_texture` 与 `has_textures` 查询绑定。
`without_*_texture()` 返回保留其他槽和材质参数的副本；移除自发光贴图后恢复常量 emission，移除 ORM 后恢复常量金属度/粗糙度；环境遮蔽仍可由独立 AO 槽提供。
这些方法不分配/持有 GPU 纹理；所有已绑定纹理须保持存活，三个槽均检查 owner/generation。
任一贴图都要求每个顶点具有法线和 UV，ORM/自发光可单独使用，不要求绑定基础颜色贴图。
`set_material` 和替换网格先完成只读预检；单次 draw 在编码 GPU 命令前验证所有贴图，失效、跨设备或错误格式均报错。

每次绘制显式绑定五个材质图像/采样器（包含法线和独立 AO 槽）以及第六个阴影槽，空槽使用设备私有白色图像；材质槽切换和无光照路径也遵守此约定。
片段 slot 0 是 64 字节材质参数：基础颜色/金属度、自发光/粗糙度、五槽掩码、遮蔽/法线强度、单双面和朝向。slot 1 是 1056 字节环境与光源参数，包含 ambient、相机/曝光及 16 个 64 字节光源描述；slot 2 是 416 字节通用阴影参数。
三种 shader 方言共用 `lighting.inc` 的通道/因子/遮蔽计算与 BRDF，资源有效性与 GPU 绑定由标准 `gpu` 校验，材质与颜色空间政策留在 Xu 渲染服务。
材质语义留在渲染服务；没有修改 Xu 标准库。

Metal 像素验收覆盖八种槽组合、G/B 因子与常量材质对照、粗糙度下限、遮蔽强度/直接光/自发光隔离、
自发光 sRGB/线性结果、忽略 alpha、三槽同帧切换、ORM/自发光 mip 采样、缺失/混合 UV，以及跨设备/关闭/复用后的拒绝。
独立 AO 与受限 GLB 材质导入见下文；程序网格切线生成已实现，glTF MikkTSpace 切线生成、其他 UV 集/变换、完整 glTF 兼容、IBL 仍待实施。
MSL 已在 Metal 实机运行；GLSL/HLSL 源码与绑定已同步，Vulkan/D3D12 的对应构建与真机验收仍待完成。

### 切线空间法线贴图

```sh
make demo-normal-maps
./build/normal-maps --frames 120 --capture build/normal-maps.png
```

[`examples/normal_maps`](examples/normal_maps/main.xu) 使用相同球体几何与原创程序图片。
左上为原有光照，右上为法线强度 0.5，左下为强度 1.5；右下组合基础颜色/ORM/自发光/法线四槽并应用 X 轴负缩放。
明暗在 GPU 中随法线和观察方向计算，轮廓仍为原有球体；方向键环绕，Space 切换外部光照，Esc 退出。

```xu
// 切线 XYZ 为沿纹理 U 的方向，W 为手性 ±1；法线和切线在构建时归一化。
data.vertex_tangent(position, color, normal, uv, fm.vec4(tx, ty, tz, 1.0)) or >>
$normal_texture := image_render.upload_image_3d_sampled(&device, &normal_image, false, sampling) or >>
mapped := material.with_normal_texture(&normal_texture, 1.0) or >>
scene.set_material(&tree, object, mapped) or >>
```

`vertex_tangent` 要求不透明顶点色、有限非零法线/切线 XYZ、二者垂直、W 精确为 -1 或 +1；UV 预算沿用既有约定。
三角形三个切线顶点的 W 必须相同，混合手性会在写入索引前拒绝；UV 接缝与手性边界由作者拆分顶点。
原有 `vertex` / `vertex_lit` / `vertex_lit_uv` 保留，带 UV 不代表已有切线。
`sphere_mesh_3d` 生成与球体 UV 一致的解析切线，包括接缝和极点副本。

CPU 构建统一从 `meshes #"github.com/xulang-org/nexus/resources/mesh"` 导入，包含 `MeshData3D`、
`Vertex3D`、`new_mesh_data_3d` 和 `sphere_mesh_3d`。渲染包只拥有上传后的 `Mesh3D` 设备资源。
公开顶点和索引可编辑；`validate()` 检查数量/索引、有限坐标、单位法线/切线、UV/颜色和手性，上传前也会重新校验。

程序网格可显式调用 `mesh.generate_tangents() or >>`，无需手填切线：

```xu
meshes #"github.com/xulang-org/nexus/resources/mesh"

$source := meshes.new_mesh_data_3d()
// vertex_lit_uv(...) 填充每个顶点的 position / normal / UV，再添加 triangle(...)。
added_vertices := source.generate_tangents() or >>
$uploaded := device.upload(&source) or >>
```

算法按三角形 UV 梯度和顶点夹角加权，正交化到已有法线；按原顶点索引累积，不焊接独立 UV/法线接缝。
共享索引跨越相反手性时自动拆点并重建索引，返回新增顶点数；CPU 顶点上限 262144、索引上限 1048575。
退化几何/UV（归一化面积或条件量不大于 1e-12）、缺少法线/UV、无引用顶点、切线抵消、无效索引或拆点超预算均失败，保留完整原网格。
计算在 Xu 中使用 f64，上传时才编码 binary32；不创建 GPU 或调用原生几何算法。
这是程序网格的角度加权算法；glTF 缺失切线的默认算法建议为 [MikkTSpace](https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html#meshes-overview)。
当前 GLB 材质导入继续要求作者提供 TANGENT，避免改变已烘焙法线贴图的基底。

```sh
make mesh-core-test        # 仅复制数学和网格数据包，无渲染/平台/场景/原生归档
make demo-generated-tangents
./build/generated-tangents --frames 120 --capture build/generated-tangents.png
```

`examples/generated_tangents` 使用带解析法线的曲面网格；左侧显示几何法线，右侧使用自动切线和程序法线贴图。
GPU 回读以独立烘焙法线为参考，覆盖 X/Y 法线、0/1/2 强度、两种手性、自动拆点、镜像/非均匀/剪切变换及 1e±7 比例。

`with_normal_texture(texture, scale)` 要求线性图像及有限 scale 0...8；sRGB 输入拒绝绑定。
法线 RGB 解码为 `2×RGB-1`，+X 沿切线、+Y 沿带手性的副切线、+Z 沿几何法线，alpha 忽略。
scale 乘解码后的 X/Y，再归一化；scale=0 直接使用几何法线。零长度的过滤结果也回退到几何法线。
法线贴图由既有采样器/mip 系统过滤，照明前重新归一化；当前不做法线方差/高光抗锯齿补偿。
`has_normal_texture` 查询，`without_normal_texture()` 返回保留其他槽和参数的副本；前三槽的设置/移除同样保留法线槽和强度。

GPU 顶点阶段用模型矩阵变换切线和本地副切线参考，用逆转置变换法线；片段阶段重新正交化/归一化切线基。
副切线参考保留模型镜像与输入 W 的方向信息，因此非均匀/负缩放、旋转和剪切不依赖不稳定的直接浮点行列式求符号。
这些计算共用 `lighting.inc`，标准 GPU 后端只处理通用资源与命令；顶点编码、网格生成和材质规则均在 Xu。

法线槽为第四个图像/采样器，独立保留过滤、mip 和寻址配置；包含 AO 的所有五槽共享 TEXCOORD_0。
网格每个顶点都必须有法线、UV 和切线，即使 scale=0 也验证完整基底。
场景设置材质/换网格先只读预检，单次 draw 也检查线性格式、owner/generation 和完整切线；关闭/复用/跨设备引用均拒绝。
引擎 Shader 使用五个材质图像槽和一个阴影图像槽、192 字节矩阵 uniform、64 字节材质 uniform、1056 字节环境/光源 uniform 与 416 字节阴影 uniform；空槽绑定内部白纹理。材质引用不拥有纹理，标准 GPU 的类型化引用在场景预检和每次实际绑定时验证，关闭后不能继续使用；已录制命令保留资源直到完成。

受限 GLB 几何导入已支持显式 TANGENT：非 normalized float32 VEC4、数量匹配、单位 XYZ、垂直法线、W=±1，三角形手性一致。
本 profile 要求 TANGENT 同时具有 NORMAL 和 TEXCOORD_0；上传适配器完整保留切线与手性。
无切线的 GLB 不会自动生成；手动绑定或自动导入法线贴图都要求作者提供切线。
完整 glTF 材质/image/texture 导入、MikkTSpace 自动生成、其他 UV 集/变换、GPU 蒙皮、视差/位移、IBL 仍待实施。

Metal 像素验收把世界位置/期望法线独立烘焙到参考网格，对照 X/Y 扰动、scale 0/1/2、W ±1、
旋转/非均匀缩放/镜像/剪切和 1e±7 缩放；还覆盖全部 16 种槽组合、法线 mip、
GLB 正/镜像切线上传与整批绑定预检、混合/缺失基底、无效强度/格式、关闭/复用/跨设备引用。
Vulkan/D3D12 源码与绑定同步更新，仍需对应平台构建和真机验收。

## 多格式静态模型加载

| 输入 | 当前支持 | 明确限制 |
| --- | --- | --- |
| GLB 2.0 | 几何、节点层级、多个图元、不透明 PBR/PNG、受限 TRS 动画和 CPU 蒙皮 | 详细范围见下节；非完整动画系统，无外部 `.gltf` JSON |
| Wavefront OBJ | 位置、独立 UV/法线索引、负索引、三角形、凸平面四边形、UV 接缝 | 仅几何；不读取 MTL，不支持任意多边形、自由曲面、顶点颜色或隐式平滑法线生成 |
| ASCII STL | 单个 solid 的三角形 | 严格 facet/loop/vertex 语法；不支持多个 solid 或厂商颜色 |
| 二进制 STL | 80 字节不透明头、计数、50 字节三角形记录 | 文件长度必须完全匹配；属性字段必须为零，拒绝颜色扩展 |
| FBX、PLY、DAE、Blend、独立 glTF JSON | 尚未实现 | 加载入口明确拒绝扩展名；拒绝测试不代表格式已经支持 |

`formats/obj.decode(&raw)` 和 `formats/stl.decode(&raw)` 返回 `resources/mesh.MeshData3D`，不读文件，也不依赖场景、渲染、平台或原生模块。
`assets/mesh.load(path)` 以大小写无关的 `.obj` / `.stl` 扩展名分派，先检查扩展名，再通过单一文件描述符读取最多 16 MiB 的快照。
GLB 继续使用 `assets/gltf` 的层级/材质接口，没有压成单一网格而丢失语义。

```xu
mesh_files #"github.com/xulang-org/nexus/assets/mesh"

data := mesh_files.load("assets/model.obj") or >>
mesh := device.upload(&data) or >>
scene.attach_mesh(&tree, node, &mesh) or >>
// 调用方持有 mesh 的生命周期；场景仅保存弱引用。
```

OBJ 每个面角展开为独立顶点，保留 UV/法线接缝；`v/vt/vn`、`v//vn`、`v/vt` 和纯位置索引均可用，同一面必须使用一致属性集合。
索引只引用已经声明的元素。显式法线归一化，缺失时按面绕序生成平法线；平滑组必须有显式法线。`o/g` 标签合并到同一网格，不保留层级。
可选顶点齐次权重只接受 1，第三个 UV 分量只接受 0；非平面/凹/交叉四边形、退化或近共线面以及未知语句明确报错。
`mtllib/usemtl`、`call/csh` 不会被忽略或执行，不读取旁文件。

STL 先用计数与精确长度识别二进制布局；即使二进制头以 `solid` 开头也能正确加载。两种 STL 都检查输入法线有限性，并按顶点绕序重建平法线。
导入保持坐标、绕序和单位，不隐式转换坐标轴、焊接顶点、修复拓扑或生成切线；每个网格沿用最多 262,144 顶点、1,048,575 索引及位置 ±1e9 的资源预算。
文本另限制每行 64 KiB、最多 1,048,576 行，拒绝无效 UTF-8/NUL；所有解析失败均不返回部分网格。

```sh
make demo-models
./build/model-formats --model path/to/model.obj --frames 120 --capture build/model.png
./build/model-formats --model path/to/model.stl --backend metal
./build/model-formats --model path/to/model.glb
make mesh-format-core-test model-format-gpu-test
```

示例在 CPU 导入成功后才创建设备，以无光照白色几何检查形状和绕序；自动居中/适配相机只修改预览根节点，不改写导入数据。GLB 材质检查继续使用 `demo-glb-materials`。
窗口缩放更新投影比例，Esc 退出，`--shaders DIR` 指定离线着色器目录。

验收覆盖原创三角形、立方体和非对称四面体，各自导出 GLB/OBJ/ASCII STL/二进制 STL/`solid` 头二进制 STL。
三个优化级别在没有场景、GPU 和原生源码的隔离目录检查逐索引位置/单位法线、UV 接缝及错误输入；Metal 的 15 次 800×600 截图按模型逐像素一致。
43 个损坏文件、5 种不支持的扩展名和缺失文件均在创建设备前报错。独立 Trimesh 5.2.1 读取相同 15 个文件核对三角形数、边界和面积；它另外导出的 320 三角形模型也通过 Xu 四格式加载及真实 GPU PNG 一致性检查。
独立校验器仅安装在忽略的测试虚拟环境，不是产品依赖；Vulkan/D3D12 尚无本项真机证据。

OBJ 语义依据 [Wavefront 原始附录](https://raw.githubusercontent.com/mokiat/java-data-front/master/documents/OBJ%20Specification.txt)，STL 布局参考 [Apache Commons Geometry 实现](https://svn.apache.org/repos/infra/websites/production/commons/content/proper/commons-geometry/commons-geometry-io-euclidean/xref/org/apache/commons/geometry/io/euclidean/threed/stl/StlConstants.html)。上述范围是当前实现的子集。
格式语义和网格预算留在 nexus；UTF-8、文本数值、二进制浮点和文件基础能力复用 Xu 标准库，本项无需修改 Xu 编译器或标准库。

## GLB 静态几何导入

`formats/gltf` 负责纯 CPU 字节解码和格式数据描述；`assets/gltf` 负责读取文件和实例化场景，直接使用格式包的数据类型，`integration/gltf_render` 负责上传与绑定。格式包不依赖 SceneTree 或 GPU。
解析复用标准 `encoding/json`、`encoding/binary`、`os` 与 `crypto/sha256`。
IEEE 位转换复用标准 `math.float32_from_bits`，GLB/WAV 自行检查有限值及领域范围；脚本字面量复用 `math.float64_from_bits`，保留 VM 标量约束。原 `internal/float32` 与 `internal/float64` 已删除，四元数运算仍在引擎数学层。

```xu
assets #"github.com/xulang-org/nexus/assets/gltf"
glb #"github.com/xulang-org/nexus/integration/gltf_render"

asset := assets.load_glb_geometry("model.glb") or >>
root := tree.root()
instance := assets.instantiate(&asset, $&tree, root, "Model") or >>
$model := glb.upload_unlit(&device, &asset) or >>
model.bind($&scene, &tree, &instance) or >>
// 此后通过 scene.draw 绘制；model 保持存活直到这些绑定停止使用。
```

完整示例见 [`examples/glb_preview/main.xu`](examples/glb_preview/main.xu)。
默认加载本仓库原创模型 `tower.glb`：2 个网格、3 个图元、8 个源节点，所选场景生成 11 个网格绑定 / 62 个三角形。
该模型通过本机 Khronos glTF Validator 2.0.0-dev.3.10 验证，0 错误、0 警告。
验证器只用于本机验收，运行/构建引擎不依赖 Node 或 npm。

`glb.upload_unlit` / `GlbUnlit3D` 提供无光照几何预览入口，`glb_preview` 示例仍采用无光照顶点色。
格式解析现已保留受限材质、image、texture、sampler 和 primitive 的材质索引；
`glb.upload_model` / `GlbModel3D` 将这些描述转为拥有网格/纹理的 PBR 模型，再用 `draw_lit` 绘制，详见下一节。
完整格式依据 [Khronos glTF 2.0 规范](https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html)，当前实现限制如下：

| 项目 | 当前支持范围 |
| --- | --- |
| 容器 | GLB 2.0、glTF asset 2.0；第一个 JSON 块、第二个内嵌 BIN 块，未知尾部块按长度跳过 |
| 缓冲 | 单个内嵌 buffer；校验块长度、BIN 填充、bufferView/accessor 范围、stride、角色和对齐 |
| 图元 | TRIANGLES；可有多个网格/图元；索引为 u8/u16/u32 或省略索引；禁止 primitive restart 值 |
| 位置 | float32 VEC3，必须提供 min/max，以相对/绝对 1e-6 容差核对实际值 |
| 法线 | 可选 float32 VEC3，须为单位向量；可查询、上传，手工绑定材质时参与光照 |
| 切线 | 可选 TANGENT：float32 VEC4，单位 XYZ 和 W=±1；要求法线/UV，正交化为引擎基底；平行退化方向拒绝，不自动生成 MikkTSpace |
| UV | 可选 TEXCOORD_0：float32 或 normalized u8/u16 VEC2；保留并上传，可手动绑定基础颜色纹理 |
| 颜色 | 可选 COLOR_0：float32 或 normalized u8/u16 VEC3/VEC4，量化为 RGBA8；颜色范围 0...1，alpha 必须为 1；省略时为白色 |
| 节点 | TRS 或列主序矩阵；矩阵不可与 TRS 混用，须可分解为 TRS；四元数须近似单位长度 |
| 场景 | 验证全部节点构成无环、单父节点森林；导入默认场景，未声明默认场景时选择第 0 个 |
| 名称 | 原名称通过 `node_name` 保留；实例采用 `Node_N` / `Primitive_N` 名称，避免源名称中的路径字符和同级重名 |
| 动画/蒙皮 | TRS 关键帧、LINEAR/STEP/CUBICSPLINE、最短弧四元数插值、JOINTS_0/WEIGHTS_0 与逆绑定矩阵；使用下文显式姿态入口 |
| 明确拒绝 | 外部 buffer / 独立 .gltf、sparse / 无 bufferView accessor、morph、导入相机、超出下文范围的扩展和其他未支持属性 |

`decode_glb_geometry(&raw)` 可从已有字节字符串解码；`load_glb_geometry(path)` 有界读取，错误时不返回部分资产。
普通 `extras` 元数据不被解释为格式语义。当前不是完整 glTF 验证器，超出上述范围的文件会报错。

每文件最多 16 MiB、JSON 块 512 KiB、BIN 块 8 MiB / JSON 节点 32,768；最多 256 个网格、
1,024 个图元、1,024 个源节点、4,096 个 bufferView / accessor、64 个场景，节点深度最多 64。
解码后累计最多 262,144 顶点 / 1,048,575 索引；共享 accessor 跨图元展开时也计入累计预算。
位置和局部变换的绝对值上限为 1e9；非有限浮点数被拒绝。
实例化（含容器和图元子节点）最多 4,096 个节点，先在临时树构建，再复用 PackedScene 的原子容量/命名校验。
这些是数据规模上限，标准库当前以整数数组表示缓冲字节，CPU 峰值内存会高于文件体积。

`GlbInstance.source_node(i)` 返回源节点在当前树中的 ID，未被所选场景包含时返回 0。
每个网格图元拥有一个独立子节点，`primitive_node` / `primitive_index` 用来关联源图元。
`GlbUnlit3D` 拥有每个源图元的 GPU 网格，多实例共享资源；`bind` 会检查原文件 SHA-256、节点和设备，
先完整预检再写入场景绑定。整批上传失败会释放已上传的临时网格，模型析构/显式关闭会释放其全部网格。
GPU 上传同时受全局 512 活动网格和每设备 64 MiB 预算限制；也可用 `glb.upload_primitive` 单独上传一个图元。
当前预览采用双面、不透明顶点色绘制，材质导入入口另行表达 glTF 默认材质与面剔除；尚无线性 HDR 目标或完整色彩管理。

## GLB 不透明 PBR 材质导入

```xu
// asset / tree / instance 的创建与几何示例相同。
$model := glb.upload_model(&device, &asset) or >>
model.bind($&scene, &tree, &instance) or >>
// 每帧使用 scene.draw_lit；model 拥有网格和图片，须保持存活。
```

运行 `make demo-glb-materials`，或参见 [`examples/glb_materials/main.xu`](examples/glb_materials/main.xu)。
原创 `panels.glb` 含八个材质面板、五张内嵌 PNG，覆盖常量、基础颜色、金属度/粗糙度、独立 AO、法线、自发光、五槽组合与双面背部光照。
该资产由本机 Khronos glTF Validator 验证为 0 错误、0 警告；Metal 示例完成 120 帧，上传五个 GPU 图片变体、九个材质值（含默认值），绘制八个绑定 / 16 个三角形。

| 项目 | 当前支持范围 |
| --- | --- |
| PBR | 核心 metallic-roughness；base RGBA、metallic、roughness、emissive RGB；不透明 OPAQUE，忽略 alpha，粗糙度下限 0.045 |
| 纹理 | base/emissive 使用 sRGB，MR/normal/occlusion 使用线性格式；统一 TEXCOORD_0；normal scale 0...8，AO strength 0...1 |
| MR / AO | MR 的 G/B 乘材质粗糙度/金属度；仅有 MR 时不使用其 R；独立 occlusion 的 R 仅遮蔽 diffuse ambient |
| 图片 | bufferView 内嵌或资产目录内的相对 PNG / baseline JPEG；拒绝网络、父路径、百分号编码和图片路径中的符号链接；无 progressive JPEG/CMYK/压缩纹理 |
| 采样器 | 六种核心 minFilter、两种 magFilter；repeat / clamp；缺省采用线性过滤、三线性 mip 与 repeat；不支持 MIRRORED_REPEAT |
| 双面 | 缺省单面，背面剔除；doubleSided=true 绘制两面并翻转背面着色法线，兼容模型/相机镜像 |
| 几何 | 材质入口要求每个图元已有 NORMAL；任意贴图还要求 UV；normal 贴图要求显式 TANGENT，不自动生成法线或 MikkTSpace |
| 限制 | 不支持 MASK/BLEND、其他 UV 集/非恒等纹理变换和材质扩展；接受 KHR_texture_transform 的恒等 UV0 变换。蒙皮/动画使用 upload_animated；这仍是受限 profile |

`Material3D.with_occlusion_texture(texture, strength)` 绑定独立线性 AO 图，覆盖 ORM.R，不叠乘两份 AO；
`without_occlusion_texture()` 移除后恢复既有 ORM.R 行为，`has_occlusion_texture()` 查询。设置/移除其他槽会保留 AO 和表面策略。
`material_3d` 默认单面并剔除逻辑背面；`with_double_sided(true)` 绘制双面并翻转背面法线。GLB 导入使用格式中的策略。
所有贴图均为非拥有代次引用，不延长纹理寿命；`GlbModel3D` 则拥有其上传的全部网格和纹理，关闭或析构后旧绑定失效。

每文件最多 32 张 image、64 个 texture、64 个 sampler、128 个 material；复制的编码图片累计最多 8 MiB，即使多个 image 引用同一 view 也逐项计入。
一次模型上传最多解码 8,388,608 个像素，每次只保留一张 CPU 图片；单图仍受 4,194,304 像素 / 单边 4,096 限制。
GPU 图片去重键为源 image 索引、解析后的完整采样状态和颜色空间；相同图片的线性/sRGB 用途分别上传，各 mip 仍计入每设备 64 MiB 预算。
上传当前处理资产的全部图元和全部声明材质所引用的图片，不局限于选中的场景；没有跨模型全局缓存。
`material_count()` 包括索引 0 的隐式默认材质，其余为源材质；`texture_count()` 是实际 GPU 变体数。

解析与描述在 `formats/gltf`，内存 PNG 解码复用 `assets/image.decode_png_bytes`，上传策略在 `integration/gltf_render`，渲染服务不导入格式包。
上传失败释放临时网格/图片；绑定先验证全部候选表面、源哈希、节点和容量，再统一写入，旧材质失效也可由有效候选替换。
`Scene3D.attach_surface` 可同时替换网格与材质，避免将旧材质的要求错误地用于检查新网格。
本轮没有修改 Xu 标准库；通用 `Mat4.determinant_sign` 位于基础数学包，表面策略和格式语义保留在引擎。
Vulkan/D3D12 的源码与绑定已同步，尚未完成对应平台构建和实机验收。

## 真实人物、动物、植物与 glTF 动画

已从 Kenney 官方下载并固定三份 CC0 素材包，原始压缩包、模型及许可保留在忽略的 `build/external-models`，不作为引擎源码依赖或提交到仓库。

| 类别 | 模型 / 官方素材包 | 三角形 | 动画 / skin |
| --- | --- | --- | --- |
| 人物 | character-male-a / [Mini Characters](https://kenney.nl/assets/mini-characters) | 771 | 32 / 2 |
| 人物 | character-female-a / Mini Characters | 924 | 32 / 2 |
| 动物 | animal-cat / [Cube Pets](https://kenney.nl/assets/cube-pets) | 684 | 8 / 0 |
| 动物 | animal-fox / Cube Pets | 568 | 8 / 0 |
| 植物 | tree_oak / [Nature Kit](https://kenney.nl/assets/nature-kit) | 196 | 0 / 0 |
| 植物 | flower_redA / Nature Kit | 76 | 0 / 0 |

人物和动物直接加载原始 GLB 与随包 PNG，没有先转换为静态几何。Khronos Validator 验证四份原始模型为 0 错误；人物各有两项非根 skinned mesh 提醒。
两份植物源 GLB 含 `SCENE_NON_ROOT_NODE` 错误，仍被引擎明确拒绝。测试另生成 `.scene-root-fixed.glb`：只把已有的恒等父节点作为场景根，BIN/几何/材质不变；修正版各为 0 错误/0 警告。`sources.json` 记录原文件/修正版及压缩包 SHA-256，避免把修复后的文件当作未经修改的源文件。

```sh
# 显式联网下载；若远端素材包内容改变，固定 SHA-256 校验失败。
make external-model-fixtures
make external-model-test

# 使用当前选择的 Xu 开发 SDK 构建后，查看真实蒙皮人物。
./build/model-formats --model build/external-models/original/mini-characters/character-male-a.glb --view pbr --animation walk --loop true
./build/model-formats --model build/external-models/original/cube-pets/animal-fox.glb --view pbr --animation walk --time 0.25 --frames 1 --capture build/fox.png
```

`formats/gltf` 只保存/校验动画与蒙皮数据，并提供无场景/设备依赖的 `animation_count/name/duration`、`sample_pose(clip, time)`、`world_pose(locals)`、`skin_palette(node, worlds)` 和 `skin_matrix(primitive, vertex, palette)`。
采样从作者原始 TRS 开始，clip=-1 为原始姿态；时间按每条轨道钳制，循环由播放器显式处理。旋转使用最短弧 slerp，三次样条按 glTF Hermite 切线与时间间隔采样，旋转结果归一化；矩阵节点不能作为 TRS 动画目标。
最多 128 片段、每片段 4,096 通道/采样器，累计 262,144 个输出键；输入时间有限、非负、严格递增，输出数量/形状和旋转单位长度均检查。单 skin 最多 256 关节、每资产最多 128 skin；联合检查节点、逆绑定矩阵、四个索引/权重及权重总和。

```xu
$player := glb.upload_animated(&device, &asset) or >>
// 每帧 begin 之前显式采样。instance 为 assets/gltf.instantiate 的结果。
player.sample(&device, $&scene, $&tree, &asset, &instance, clip_index, seconds) or >>
device.begin(background) or >>
scene.draw_lit($&device, &tree, view_projection, &lighting) or >>
device.present() or >>
```

`GlbAnimated3D` 为各实例持有独立姿态网格，先准备全部 CPU 姿态和 GPU 网格，再校验节点/绑定并发布；坏片段、失效/待删除节点和上传失败保留上一轮已接受的姿态。CPU 线性混合蒙皮使用 `inverse(meshWorld) * jointWorld * inverseBind`，同时变换位置、法线与切线，更新后的包围盒参与现有视锥/光源筛选。
当前逐姿态上传替换的拥有型网格，由标准 GPU 保留已录制资源并回收旧所有者；这是功能正确性的基础实现，尚未实现 GPU 蒙皮或动态缓冲优化。静态上传入口拒绝带 skin 的资产，避免直接绘制未蒙皮顶点。

外部 PNG 的路径和读取留在 `assets/gltf`，格式包只声明 URI/解析调用方提供的字节；累计编码图片仍不超过 8 MiB。解析后的 `content_hash` 同时覆盖 GLB 与外部 PNG，贴图改变会改变实例/模型指纹。
现有固定哈希的 `.xuscene` 表面恢复仍只支持内嵌图片的静态资产，不会隐式恢复外部图片、动画状态或蒙皮播放器。
`KHR_texture_transform` 目前仅接受默认/恒等 UV0 变换；允许已知但未使用的扩展声明，不代表实现了对应材质扩展。

验收包含 98 张真实 Metal PBR 截图、80 个动画片段、四组各 600 帧连续运行及可见的 walk 姿态变化。
独立 Python 数值实现核对 326 个姿态、2,847 个蒙皮/世界坐标点及全部节点矩阵；解析/采样在缺少场景、资产、渲染及原生源码的目录以 `--no-opt` / `--release` 通过。
另覆盖 LINEAR/STEP/三次样条/四元数反号解析解、27 项非法动画/skin/URI、独立场景实例和待删除节点整批失败、缺失/伪 PNG/文件与目录符号链接。完整引擎回归继续验证原有 OBJ/STL、PBR、场景、音频和脚本热更新。
动画/模型语义留在 nexus；标准库仍只提供基础数学、数值/字节、文件、PNG、窗口和 GPU 能力，本项没有修改 Xu。

## 细节模型与画质预览

之前的 Kenney 人物只有 771 / 924 个三角形，方块轮廓和大色块属于低面数美术风格。提高抗锯齿不会补出这些模型没有的鼻翼、皮肤、叶脉或毛发。
新增 Lee Perry-Smith / Infinite Realities 扫描人头作为细节对照：17,684 个三角形，原始 1K JPEG 颜色和法线图；来源于 [three.js 官方示例](https://threejs.org/examples/webgl_materials_normalmap.html)，按其随包 [CC-BY-3.0 许可](https://github.com/mrdoob/three.js/blob/dev/examples/models/gltf/LeePerrySmith/LeePerrySmith_License.txt) 保留署名。
测试固定上游提交和每文件 SHA-256，原文件留存于忽略的 `build/detail-models`。

原示例在 GLB 之外设置 Phong 材质。测试导入步骤明确生成派生资产：展开原三角形、归一化法线、按原 TextureLoader 约定翻转 V、用离线 mikktspace 1.1.1 生成 glTF 切线，再绑定原 JPEG 到 metallic=0、roughness=0.6 的 PBR 材质。
这是有记录的材质适配，不是未经修改的源 GLB，也不表示引擎已支持皮肤次表面散射或运行时自动 MikkTSpace 生成。派生资产保留 17,684 三角形，因切线接缝展开为 53,052 顶点，Khronos Validator 对外部/内嵌 JPEG 两版均为 0 错误/0 警告。

```sh
make detail-model-fixtures  # 显式下载并校验；npm 工具仅装入忽略的 build 目录
make detail-model-test
./build/model-formats --model build/detail-models/head-prepared.glb --view pbr --studio true --distance 3.2 --fov 40 --yaw 0.15 --pitch 0 --render-scale 2
```

`Device3D.set_render_scale(1|2)` 在帧外设置，缺省为 1。模式 2 在长宽各两倍的颜色/深度目标上执行原有网格与 PBR 绘制，再在 GPU 用线性采样合成到原输出尺寸；窗口呈现和 `capture/read_pixel` 都使用合成结果。
分辨率/模式切换先分配全部新目标，再整体替换；失败保留上一组目标。用户纹理的 512 张 / 64 MiB 预算扣除对应模式的内部目标，不把内部超采样图算作用户纹理。
高分辨率目标仍受 4096 单边 / 4M 像素上限约束。模式 2 增加四倍源片元和颜色/深度存储，尚无 MSAA/TAA/FXAA 或动态分辨率；当前合成位于 RGBA8 显示编码阶段，没有 HDR/线性色彩目标。

预览新增 `--studio true` 的三方向光布置，以及距离、FOV、yaw/pitch 控制，便于近看材质。`--shadows true --ground true` 增加方向光阴影和地面；需要 GLB/PBR，地面按初始包围盒底部固定放置，直立接触预览使用 `--pitch 0`。三灯布置不表示已实现 IBL 或全局光照。
GPU 验收把 64×48 的模式 2 与独立 128×96 渲染的四像素平均核对，最大误差不超过一个 8 位码值；验证边缘部分覆盖、输出尺寸、透明度、缩放/模式恢复及非法帧内调用。

`assets/image.decode_jpeg` / `decode_jpeg_bytes` 在调用 Xu 标准 `image/jpeg` 前检查字节、SOF0、尺寸和调用方像素预算；只支持当前标准库的 8-bit gray / YCbCr baseline 范围。PNG 继续走现有 SDL CPU codec，没有新增原生模块或重复 JPEG 解码器。
RGB 4:4:4、4:2:0、灰度和奇数尺寸结果与独立 libjpeg/Pillow 比较，另验证截断/错误头/超限/progressive/CMYK 拒绝。标准 4:2:0 色度重建与 libjpeg 有差异，本机 19×11 校验的平均误差 3.426、最大 12；不宣称逐像素相同。
扫描模型的外部与内嵌 JPEG 版本产生完全一致的 Metal PNG，关闭法线图的控制组产生不同画面；预览保持 800×600 输出，颜色/法线图与超采样均由实际引擎路径执行。
测试夹具/像素对照需要本机 Pillow，产品构建不依赖 Pillow；离线 MikkTSpace 工具不进入运行时。本项没有修改 Xu 编译器或标准库。

## 节点场景文件

`integration/scene` 将节点场景保存为 `.xuscene`，加载后可转换为既有 `PackedScene`，供多次实例化复用。
保存范围包括普通分组、Node2D/Node3D 的层级、名称、局部变换、可见性、处理模式和相机参数。
场景支持版本 1 至 4，并写出所需的最低版本。方向光的 CSM 配置使用版本 4，2D 相机和正交镜头使用版本 3，透视镜头使用版本 2。各版本使用相同的资源与附件数组，未使用时为空。
树的暂停和执行状态由应用管理。表面、音频、脚本和光源附件由各服务整合包管理。

```xu
files #"github.com/xulang-org/nexus/integration/scene"
camera_data #"github.com/xulang-org/nexus/resources/camera"

lens := camera_data.perspective(0.94, 0.2, 96.0) or >>
tree.set_camera_3d(camera_node, lens) or >>
document := files.capture_nodes(&tree, subtree_root) or >>
files.save("world.xuscene", &document) or >>
loaded := files.load("world.xuscene") or >>
packed := files.to_packed(&loaded) or >>
parent := tree.root()
instance := packed.instantiate($&tree, parent, "Loaded") or >>
// 只实例化一次时，也可 files.instantiate(&loaded, $&tree, parent, "Loaded")。
```

[`examples/scene_file/main.xu`](examples/scene_file/main.xu) 从文件恢复混合节点，显式绑定材质，保留隐藏节点，并通过 `tree.camera_view_projection_3d` 根据节点镜头选择透视或正交投影。普通 Node3D 沿用默认透视镜头。`scene.new_camera_node_2d` 以节点的世界位置和 X 轴方向生成相机，缩放由镜头的 `zoom` 控制。父节点移动后重新读取即可更新视角。
保存后退出，再由新进程加载的运行方式：

```sh
make demo-scene-file
./build/scene-file --frames 1 --save build/saved-world.xuscene
./build/scene-file --scene build/saved-world.xuscene --frames 120 --capture build/scene-file.png
```

运行 `make scene-camera-gpu-test` 可复测同一场景的正交与 2D 画面。该目标用 `scene-file --camera Ortho` 和 `two-d --camera-scene` 渲染原始文件及新进程加载后的存档，并比较 PNG。

| 契约 | 行为 |
| --- | --- |
| 文件 | UTF-8 JSON，`format: "xu.scene"`、整数 `version` 1 至 4、`nodes`、`resources`、`surfaces`、`audio_buses`、`audio_emitters`、`scripts`、`script_connections`、`lights`；未知版本、字段或类型报错 |
| 节点 | 单根、先序数组；根 parent=-1，其他 parent 为数组索引且在当前祖先链内；同级名称唯一 |
| 名称 | 1...255 UTF-8 字节；拒绝控制字符、`/`、`.`、`..`；JSON 标准转义保留引号、反斜杠与 Unicode |
| 变换 | Node2D 的 `[a,b,c,d,tx,ty]`；Node3D 列主序 16 个数，末行 `[0,0,0,1]`；分组无 transform |
| 镜头 | Node3D 透视镜头自版本 2 支持，字段为弧度制 `vertical_fov`、`near`、`far`。版本 3 的 Node3D 正交镜头使用 `projection: "orthographic"`、`vertical_size`、`near`、`far`。版本 3 的 Node2D 相机使用 `design_width`、`design_height`、`zoom`。镜头随 PackedScene 独立复制，3D 投影沿用有限 Reverse-Z |
| 数值 | 有限 f64，使用 SDK 最短可往返十进制，避免普通字符串转换损失精度；支持剪切/负缩放，不强制 TRS 分解 |
| 模式 | inherit / pausable / always / when_paused / disabled；可见性和模式均保存局部值，加载后再沿目标树继承 |
| 规模 | 文件最多 4 MiB、解析 JSON 节点最多 131,072、场景节点最多 4,096、根计入最多 256 层 |
| 实例化 | 先在私有树验证，再复用 PackedScene 的目标名称/容量预检；失败不改变目标树或 ready 通知 |
| 身份 | 每次实例化分配目标树 ID；父索引只属于文件，不是资源 UID 或跨保存稳定的节点身份；根名由实例化参数指定 |
| 文件发布 | 编码完成后写同目录独占临时文件、关闭并 rename；失败保留旧文件并清理临时文件；没有 fsync 持久性或多文件事务承诺 |

`capture_nodes` 保留子树根的局部变换，移除其外部父关系；排队删除或失效的节点拒绝捕获。
各实例拥有独立节点存储；删除、复用与处理通知沿用 SceneTree 契约，没有序列化瞬时执行状态。
纯资源/格式包已在没有 SceneTree、SDL 和原生归档的隔离目录编译执行；场景适配不初始化 SDL/GPU。
场景节点与脚本恢复均已在不提供原生归档、渲染/音频/编译前端源码的临时目录中构建并跨进程运行。音频恢复只链接音频设备归档，不需要 GPU 归档。

所有场景语义留在引擎；JSON、UTF-8 校验、精确浮点格式化与文件操作复用 Xu 标准库。编译器修复单独维护，不把场景语义移入 SDK。
94 项异常文件检查、4,096 节点/256 层边界、失败绑定/文件替换和跨进程重载均有回归。相机保存再恢复后，Metal 示例的正交与 2D 画面逐像素一致。
GLB 来源和表面附件见下节；全局 UID 索引、其他附件、实例覆盖、全局缓存/重导入及热替换仍待实施。

## 场景资源与 GLB 表面恢复

`.xuscene` 的 `resources` 和 `surfaces` 描述固定来源与表面绑定，可在新进程中自动恢复 GLB 网格、材质和五槽贴图。
`resources` 和 `surfaces` 在版本 1 至 4 中采用相同的字段和校验。

```xu
loader #"github.com/xulang-org/nexus/integration/scene_render"

$models := loader.load(&device, "world.xuscene") or >>
parent := tree.root()
instance := models.instantiate($&scene, $&tree, parent, "World") or >>
// 之后使用 scene.draw_lit；models 必须在这些弱引用绘制期间存活。
models.save("saved.xuscene", &tree, instance) or >>
```

资源声明示例（省略节点数组）：

```json
{
  "resources": [{
    "uid": "11001100110011001100110011001100",
    "type": "glb_model",
    "path": "panels.glb",
    "sha256": "9158d7d2f16fc8e869c7eb643de7f533d25525e336015b08b2f55dc7ba1d7200"
  }],
  "surfaces": [{"node": 1, "resource": "11001100110011001100110011001100", "primitive": 0}]
}
```

`sha256` 必须与引用文件完全一致。完整可运行文件见
[`examples/scene_assets/assets/world.xuscene`](examples/scene_assets/assets/world.xuscene)。
其十个节点声明八个表面和一个来源模型，保存后由新进程重开，Metal 完成 120 帧 / 每帧八实例、16 三角形。

```sh
make demo-scene-assets
# 在可写构建目录准备场景及来源文件，再保存并用新进程打开。
mkdir -p build/scene-assets
cp examples/scene_assets/assets/world.xuscene examples/scene_assets/assets/panels.glb build/scene-assets/
./build/scene-assets-demo --scene build/scene-assets/world.xuscene --frames 1 --save build/scene-assets/saved.xuscene
./build/scene-assets-demo --scene build/scene-assets/saved.xuscene --frames 120 --capture build/scene-assets.png
```

| 契约 | 当前行为 |
| --- | --- |
| 身份/版本 | 非零 32 字符小写十六进制资源 ID 表示身份，64 字符 SHA-256 表示来源版本；`integration/scene.new_resource_id()` 复用标准加密随机源生成 128 位 ID |
| 定位 | 路径相对场景文件所在目录，1...1,024 UTF-8 字节，使用 `/`；拒绝绝对路径、盘符、反斜杠、空段和 `.` / `..` 段 |
| 资源 | 当前仅 `glb_model`；文档内 ID/路径唯一，所有资源必须被表面使用；UID 不是全局索引，文件移动后仍须更新路径 |
| 表面 | 每个 Node3D 最多一个表面，声明资源 ID 和源图元序号；按固定来源版本的展平图元读取，不重新导入 GLB 节点层级/变换 |
| 准备 | 有界读取每份来源，先校验完整字节 SHA-256，再解析/上传；同一次准备中，哈希相同的来源共享一个拥有型 GLB 模型，每条路径仍单独读取校验 |
| 预算 | 1...32 个资源、1...4,096 个表面；每个 GLB 最多 16 MiB、全部来源读取累计 32 MiB；已有单模型 PNG 解码与 GPU 网格/图片预算继续生效 |
| 发布 | 上传全部成功并校验实际图元范围后，离树预检全部 GPU 表面，再实例化目标节点和绑定；容量、名称、跨设备或关闭资源失败不留下部分目标节点 |
| 重绑 | `models.bind` 对已有实例先校验完整节点数量/名字/类型/父关系和所有候选资源，再批量写入；运行时可修改局部变换/可见性/处理模式 |
| 拥有 | SceneModels3D 拥有去重后的源模型，源模型拥有网格/图片，场景保存弱引用；关闭或析构后旧绑定失效，`close` 可重复调用 |
| 保存 | `models.capture` 保存当前节点值并保留声明的资源 ID/路径/哈希/图元；`models.save` 根据目标目录调整相对路径，再复用原子文件替换；来源不能位于目标目录之外 |

需要分步组装时，`loader.prepare(&device, document, base_directory)` 接收已验证文档并准备资源；
`resource.with_attachments` 一次提供来源、表面、音频、脚本、路由和光源描述，空的类别显式传空数组。`files.to_packed` / `files.instantiate` 会拒绝含附件文档，
显式 `files.to_packed_nodes` 可只建节点，调用方随后须用 `models.bind` 恢复表面。`capture_nodes` 的范围仍明确为节点。

保存不会复制、打包或改写 GLB，也不推断运行时临时材质替换/附件增删；捕获依赖原声明的拓扑，重命名/增删/换父节点需重建声明。
图元序号属于被哈希固定的来源版本，重导入需要显式核对映射。当前没有自动 UID 搜索、跨场景全局缓存、自动重导入或资源热替换。
GLB 表面、音频、脚本和 2D/3D 相机可保存到场景文件，实例覆盖待实现。GLB 自身沿用 PNG/OPAQUE/UV0/显式法线切线的受限范围。

纯数据与编解码包保持无文件/SceneTree/GPU 依赖，隔离构建包含完整附件描述；新增运行整合包只组合既有服务，没有修改原生渲染器或 Xu 标准库。
新增 54 项资源/路径/绑定异常、4,096 表面往返、SHA 失配/损坏 PNG/无效法线/实际图元越界/累计来源预算失败回滚，
以及跨设备、关闭模型、后部节点失效时不覆盖前部旧材质、保存调整路径与失败保留旧文件的检查。
本轮实机仍为 macOS arm64 / Metal，Vulkan/D3D12 待各自平台验收。

## 场景音频附件与音画组合

`audio_buses` / `audio_emitters` 描述启动音频状态，使用 `wav_clip` 来源。
恢复的是作者定义的初始音频设置：重开时，自动播放的声源从头开始；文件不记录播放游标、淡化进度或声卡队列。
音频、表面和脚本使用同一格式；编码器始终写全所有顶层数组。

```xu
worlds #"github.com/xulang-org/nexus/integration/scene_audio"
audio #"github.com/xulang-org/nexus/audio"

$world := worlds.load("audio.xuscene", 48000) or >>
$output := audio.open_output(world.sample_rate()) or >>
world.pump(&output, 2048, 512) or >>
output.pause(false) or >>
// 游戏循环持续调用 world.pump；编辑 world.tree 中的节点位姿/处理模式。
world.save("saved.xuscene") or >>
// 退出时先 pause/clear/close 外部 output，再关闭 world。
```

`AudioScene` 拥有节点树、私有 Mixer、解码后的 PCM 库及固定声源到 voice 的映射；加载候选不创建设备或操作输出队列。
外部 `audio.Output` 由应用管理。每个 AudioScene 是一个独立声音世界；跨世界混合到同一输出的全局服务尚未整合。

| 内容 | 音频契约 |
| --- | --- |
| WAV 来源 | 沿用非零 128 位资源 ID、相对路径和完整来源 SHA-256；只接收受限静态 WAV，先校验同一快照的哈希再解码 |
| 共享/预算 | 同一准备中的相同文件哈希共享一个 PCM clip；GLB/WAV 来源合计最多 32 项，每源 WAV 32 MiB、WAV 来源累计 64 MiB；解码库累计 8,388,608 个样本，沿用原有 PCM/WAV 格式限制 |
| 总线 | 1...16 个，第一项必须为 Master / parent=-1；其他父项先于子项，名称唯一；保存 volume 0...4、muted 与 paused |
| 声源 | 1...32 个，每节点最多一个；声明 node/resource/bus/volume/pan/looping/autoplay/spatial/listener/max_distance；voice ID 由运行时分配 |
| 普通声源 | spatial=none，可绑定任意节点；pan -1...1、listener=-1、max_distance=0 |
| 空间声源 | spatial=2d/3d，源和监听者维度须匹配；显式监听节点、距离 0...1e9（不含 0），pan=0；沿用平方线性距离衰减和监听者世界 X 轴声像 |
| 同步 | render/pump 前先计算全部活动声源参数，再更新 Mixer；节点暂停/处理模式冻结游标，源或监听者删除停止对应播放，隐藏本身不静音 |
| 控制 | play(index) 重播或启动声源，stop / is_playing / position_frames；set_bus_volume / mute_bus / pause_bus 控制当前声音世界，量化沿用 Mixer 的 0.001 |
| 捕获 | 保存当前节点值并保留作者定义的来源、表面、总线和声源声明；运行时临时播放/总线控制不改写初始声明；拓扑改变需重建声明 |
| 失败/关闭 | 加载失败只丢弃私有候选；sync 的空间计算失败不部分停止其他声音；输出失败保留未提交游标；close 清理未提交的声音和 PCM 库，外部队列仍归输出所有者管理 |

完整文件见 [`examples/scene_audio/assets/world.xuscene`](examples/scene_audio/assets/world.xuscene)，运行 `make demo-scene-audio`。
该示例经 CoreAudio 保存后退出，再由新进程读取并播放；可用 `--scene`、`--seconds`、`--save` 指定输入和保存位置。
保存调整相对路径的规则与 GLB 场景相同；没有复制资产或多文件事务。

同时含音频和表面的文件需要显式组合两类服务，避免漏掉另一类附件：

```xu
$world := worlds.load_audio("av.xuscene", 48000) or >>
document := world.capture() or >>
$models := loader.prepare_surfaces(&device, document, world.base_directory()) or >>
models.bind($&scene, &world.tree, world.root()) or >>
// GPU 资源也准备成功后再开启输出；使用同一 world.tree 绘制和同步声音。
```

这里 loader 是 `integration/scene_render`。普通 `worlds.load` 会拒绝表面，普通 GPU `loader.load/prepare` 会拒绝音频，
只有显式 `load_audio/prepare_audio` 与 `prepare_surfaces` 才允许局部恢复，元数据始终保留两类附件。
`models.save` 与 `world.save` 均复用统一的元数据保留/路径调整，渲染器保存不会剥离 WAV/总线/声源声明。
[`examples/scene_av/main.xu`](examples/scene_av/main.xu) 演示十一节点、八表面和一个声源在新进程恢复，Metal 120 帧与 CoreAudio 同时工作。

```sh
make demo-scene-av
# make smoke 还会在 build 中复制原创来源，分别保存音频/音画场景后用新进程重开。
```

新增 60 项格式异常、精确 PCM/总线/静音/暂停/循环/手动启动/重播、32 voices / 16 buses、二维/三维监听变换和删除、
源读取/PCM 库预算失败隔离、无 SDL 运行库的跨进程重开，以及关闭/采样率错误输出不推进游标的检查。
纯编解码无需 native/SceneTree；音频运行适配只链接音频归档，离线混音不加载 SDL，构建不需要 GPU 源码或归档。
本轮没有修改 Xu 标准库或原生传输桥接；随机、哈希、UTF-8、JSON 和路径继续复用现有公开能力。
流式音乐的场景恢复、压缩解码、DSP/遮挡/Doppler/HRTF、全局音频服务和实例覆盖仍待实现。

## 场景脚本附件、稳定信号与热重载

`scripts` / `script_connections` 描述脚本挂载和稳定路由，来源类型为 `xu_bytecode`。
节点、表面、音频和脚本可从同一场景文档恢复。脚本构建工具保留模板里的镜头。
脚本仍是已有 `xu-scalar-v1` 子集：物理更新和标量信号处理函数、有限 f64 状态；尚无完整对象绑定、协程或通用函数调用。

```xu
scripting #"github.com/xulang-org/nexus/integration/scene_script"

$scripts := scripting.load("scripts.xuscene") or >>
parent := tree.root()
instance := scripts.instantiate($&tree, parent, "Level") or >>
movement := scripts.physics_process(&tree, 0, delta, axis) or >>
report := scripts.dispatch(&tree, 64) or >>
// movement 由应用显式用于更新节点；VM 内部没有持有可变引擎对象。
scripts.save("saved.xuscene", &tree) or >>
```

每个脚本附件声明节点索引、资源 ID 和初始字段覆盖；字段使用 schema 稳定 ID。
每条连接声明源/目标节点索引及 signal/handler 的稳定 ID，名称改变不影响连接。
来源仍受相对路径、资源身份和完整文件 SHA-256 约束；每份字节码最多 128 KiB、最多 32 份声明，共计最多 4 MiB。
当前最多 32 脚本、每脚本 32 初始字段、32 连接；字段值有限且绝对值不超过 1e9，实际字段和信号 ID 在挂载时对字节码校验。

`ScriptScene` 准备编码数据并拥有一个私有 SceneScripts 管理器；每个实例独立执行、保存各自 VM 状态。
`instantiate` 先在临时树完整验证挂载、覆盖字段及路由，再创建目标节点；坏字段/处理函数、容量或命名失败不会留下部分目标场景或 ready 通知。
也可对已恢复的节点调用 `bind`，此时只在全部准备成功后提交新管理器；同一个 ScriptScene 只绑定一次，多个实例分别准备。
`state` / `calls` / `epoch` / `connection_count` 用于检查运行结果，`close` 可重复调用。

热重载是显式的本地候选激活，运行时不引入编译器：

```xu
changed := scripts.reload_from(&tree, resource_uid, "updates/mover.xubc") or >>
```

候选先通过字节码、模块/类身份和场景契约检查，再复制管理器槽位（含字段值、退役 ID 历史和待发信号），
对使用同一资源的全部附件准备新版本，最后一次提交槽位数组。后一个实例失败不会发布前一个候选，已有投递队列和连接 ID 保持。
相同模块指纹不提高 epoch；不同资源 ID 即使原内容相同也可独立更新。缓存只保留当前接受的修订，不按重载次数无限增长。
初始字段覆盖和已声明路由引用的稳定 ID 必须继续存在；改名允许，删除这些被引用的 ID 须先重建场景声明。
底层 VM 仍支持删除未被场景引用的字段/信号/处理函数及其退役约束。

保存记录当前节点值、作者定义的初始覆盖/路由和已经接受的字节码路径/哈希，重开创建新 VM，不保存执行计数、活跃字段或待发信号。
保存前重新校验已接受的字节码文件；文件损坏或丢失时保留旧场景。
含脚本的组合场景应使用 `scripts.save`，普通音频/渲染实例的 save 会明确拒绝，避免用旧元数据覆盖热重载后的脚本修订。

[`examples/scene_scripts`](examples/scene_scripts/main.xu) 的离线构建与运行：

```sh
make demo-scene-scripts
# 构建工具也可单独运行；模板和源码不在运行时编译。
python3 tools/build_script_scene.py --project examples/scene_scripts/project.json --output build/scene-scripts/world.xuscene
./build/scene-scripts-demo --scene build/scene-scripts/world.xuscene --frames 120 --save build/scene-scripts/saved.xuscene
```

工具从 `.xuscene.in` 和源码/schema 构建完整资源代次，之后原子发布场景文件；后续脚本编译失败不改写旧场景或旧引用的资产。构建工具负责资源编译/发布，场景语义仍由 Xu 格式和运行适配验证。
字节码与生成场景只在 build 中，仓库保留源码、schema、模板及原创资源。这里没有多文件 fsync、生成资源回收或生产签名分发协议。

组合恢复使用显式入口：`worlds.load_audio` 准备节点/音频，`loader.prepare_surfaces` 准备表面，
`scripting.prepare_scripts(document, base_directory)` 准备脚本；各服务绑定到同一树，并在全部成功后打开输出。
普通单服务加载器及节点转换会拒绝忽略脚本附件。完整示例恢复十二个文档节点、八个表面、一个声源、两个脚本及一条信号路由。

新增 63 项格式异常、32 脚本/32 路由、初始覆盖、缺失实际 ID、计数/队列/退役历史保留、多实例后部失败、别名独立更新、失败回调和保存版本校验等回归。
隔离进程在没有编译前端/GPU/音频源码、SDL 运行库或任何原生归档时保存并重开。
Metal/CoreAudio 示例在第 60 帧接纳已准备候选，保持计数与路由，完成 120 次更新/信号，再保存接受版本并用新进程重开。
本轮标准库与原生桥接不变。全局 UID 索引、节点稳定身份、完整脚本类型/对象 API/生命周期/协程、镜头附件和实例覆盖仍待实现。

## 音频

`make demo-audio` 构建并运行独立音频示例，无窗口或 GPU。默认加载本仓库原创的单声道 `chime.wav`，
持续循环五秒，并在左右声道间切换声像；可指定 `--file path/to/clip.wav --seconds 10`。
只构建音频可用 `make native-audio`，不要求 GPU 归档、着色器编译器或窗口资源。

```xu
audio #"github.com/xulang-org/nexus/audio"
mix #"github.com/xulang-org/nexus/audio/mixer"
assets #"github.com/xulang-org/nexus/assets/audio"

clip := assets.load_wav("examples/audio/assets/chime.wav") or >>
$mixer := mix.new_mixer(48000, 32) or >>
music := mixer.add_bus(0, "Music", 0.5) or >>
clip_id := mixer.add_clip(clip) or >>
voice := mixer.play(clip_id, music, 0.35, 0.0, true) or >>
$output := audio.open_output(48000) or >>
audio.pump(&output, $&mixer, 2048, 512) or >>
output.pause(false) or >>
// 游戏循环每隔数毫秒调用 pump；输出速度由音频设备消费决定。
// mixer.set_volume / set_pan / pause_voice / stop 控制这次播放。
```

示意代码需要持续补队列才能播放；完整循环和退出清理见 [`examples/audio/main.xu`](examples/audio/main.xu)。
设备默认暂停，显式 `pause(false)` 后消费队列；`close` 和析构关闭其音频流与设备。所有设备调用在拥有者主线程执行。
音频运行库覆盖路径为 `XU_NEXUS_SDL_AUDIO_LIBRARY`，与 GPU 的覆盖路径独立。
设备或运行库不可用时明确报错，不自动退回 dummy；测试可显式设置 `SDL_AUDIO_DRIVER=dummy`。
本机真实验收为 macOS arm64 / SDL 3.4.14 / CoreAudio；dummy 检查仅用于确定性的队列/失败测试。
Linux/Windows 音频配方已提供，尚未在对应设备验收。

| 部分 | 当前契约 |
| --- | --- |
| 数据/加载 | 不可变、交错 PCM16；单声道/立体声，8,000...192,000 Hz；最大 8,388,608 个样本 |
| WAV | RIFF/WAVE 小端，单 fmt/data，可跳过有界未知块；整数 PCM8/16/24/32、有限且在 -1...1 的 float32；加载时归一化为 PCM16 |
| WAV 限制 | 静态加载最多 32 MiB，流式最多 2 GiB；最多 256 块；检查区间、块填充、样本对齐、速率与长度；拒绝 RF64/RIFX、扩展/压缩格式、多声道、重复 fmt/data 和不支持位宽 |
| 混音 | 1...32 个播放槽、最多 64 个静态片段，总样本预算 8,388,608；输出立体声 PCM16，线性插值重采样，合成后饱和裁剪 |
| 总线 | Master 为 0；最多 16 个总线，父总线须已存在，禁止形成环；音量逐级相乘，mute 静音但推进游标，pause 冻结游标 |
| 控制 | 音量 0...4，声像 -1...1，目标精度 0.001；左右线性 balance，中央保留双声道增益；逐样本线性淡化/交叉淡化、循环、停止、暂停与独立播放状态 |
| 身份 | 播放 ID 带槽位 generation；结束/停止槽可复用，旧 ID 不会控制新的播放；片段由混音器持有 |
| 输出 | 每块最多 4,096 帧，输入队列最多 24,000 帧；pump 每次最多提交四块，采样率须匹配 |

`Mixer.prepare` 在状态副本上生成 `MixBlock`；提交成功后才 `commit` 推进播放游标。
块携带 PCM bank 和完整控制/游标状态的指纹，控制改变、PCM 追加/EOF/定位、旧块重复提交、不同状态或不同音频内容的块都会被拒绝。
`audio.pump` 负责这一步骤；设备失败不推进未提交块的游标，此前已成功提交的块保留。
`Mixer.render` 提供无设备的离线混音。片段数据和预算属于 CPU，与 GPU 纹理或网格预算无关。
SDL 只同步复制 PCM 数据并消费队列，不持有 Xu 借用，不从实时音频线程调用 Xu/VM，也不在该线程解码文件。
`queued_frames` 是 SDL 输入队列中的帧数，不是扬声器延迟或已听到的进度。
预混合数据会使音量/停止/暂停等源控制有队列延迟；设备 `pause` / `clear` 与源暂停分开管理。

节点播放通过 `integration/audio.SceneAudio.play` 建立，循环中先 `sync(tree, mixer)`，再 pump。
场景暂停/PROCESS_ALWAYS 控制尚未混合的播放时间；排队删除、释放、节点/播放槽复用会清理绑定，隐藏节点不自动静音。
绑定必须配合同一棵树和同一个混音器使用。替换先创建新播放，容量不足时拒绝并保留旧播放。

2D/3D 源可在混音前显式调用 `SceneAudio.spatial_2d` / `spatial_3d`，传入声源节点、监听者节点、最大距离和基础音量。
位置和监听者右轴使用完整世界变换；距离增益为 `max(0, 1 - distance / maximum)^2`，方向投影转换为左右声像。
纯参数函数在 `audio/mixer`，不依赖场景。当前是距离衰减与立体声 balance，没有 HRTF、遮挡、Doppler 或环绕声编码。
压缩音乐、异步文件/解码任务、音效 DSP、曲线自动化、设备热插拔恢复与音频调试面板仍待实现。

```sh
make audio-test       # 不需要 GPU；包含纯混音/格式隔离与显式 dummy 测试
make audio-smoke      # 默认设备运行静态/流式示例；无设备时明确失败
```

### WAV 流式音乐与淡化

`make demo-audio-stream` 运行两个有界 WAV 流，在中途从左侧声源交叉淡化到右侧声源；
默认五秒，可使用 `--seconds 10 --file path/to/music.wav`。示例使用当前线程补充源数据，未实现后台解码任务。

```xu
music #"github.com/xulang-org/nexus/integration/audio_stream"

$track := music.open($&mixer, "music.wav", 8192, true) or >>
track.refill($&mixer, 4096) or >>
voice := mixer.play_stream(track.source_id(), music_bus, 0.0, 0.0) or >>
mixer.fade_volume(voice, 0.5, 4800, false) or >>
// 循环中先 refill，再 audio.pump；48 kHz 输出下 4800 帧为 0.1 秒。
// 离开时 track.close(mixer)，释放源缓冲并关闭文件。
```

[`examples/audio_stream/main.xu`](examples/audio_stream/main.xu) 给出预填充、循环、交叉淡化和退出的完整顺序。
节点也可通过 `SceneAudio.play_stream` 绑定流式播放，沿用暂停、删除和空间参数更新规则。

- `formats/wav.LayoutParser` 同时服务静态加载与流式读取，校验 RIFF/块范围、编码、速率和数据对齐；`decode_samples` 是唯一的 PCM 归一化实现。
- `assets/audio.WavReader` 持有同一个文件描述符，只读取最多 4096 帧/32768 字节的范围；可跳过大数据区，源文件最大 2 GiB。路径原子替换不会切换已经打开的描述符。
- `audio/mixer` 最多八个 PCM 流，每流只有一个播放消费者；容量为 2...65536 帧，总计最多 524288 个缓冲样本。当前 SDK 使用 int64，环形样本存储最多 4 MiB，独立于静态片段和设备队列预算。
- 每次 feed/refill 最多 4096 帧，先完成样本校验、解码和容量检查再写入；失败不推进逻辑文件游标。较短循环最多缓存 4096 帧，避免每个极短循环都执行文件读取；缓存预算与环形缓冲分开，每个生产者最多 8192 个样本。
- 循环由生产者衔接 PCM 数据，跨块保留插值所需样本；EOF 显式封口。欠载时只有该声源补静音并冻结游标/淡化，其他声源继续；`MixBlock.underruns` / `PumpReport.underruns` 报告该块的欠载声源数/本次提交块计数之和。
- 混音 `prepare` 不消费环形缓冲，只有成功提交后 `commit` 才前移读取边界；成功追加数据或改变播放控制会使旧预览块失效。离线 `render` 返回样本，需要欠载诊断时使用 prepare/commit。
- `fade_volume` 的时长使用输出采样帧，独立于混音块大小；可在结束时停止。`crossfade` 同时安排旧声源淡出停止、新声源从零淡入。目标音量为 0.001 精度，样本之间按浮点线性插值；暂停和欠载冻结该声源的淡化，mute 只对已有可播放数据继续推进。

流式文件在打开期间应保持内容不可变。读取时检测总长度变化和短读；这不是整文件快照，也不承诺检测同一 inode 内相同长度的内容改写。
文件 I/O 发生在调用 refill 的线程，可能阻塞，不在 SDL 实时线程执行。欠载计数只描述源缓冲，不代表检测到了设备硬件队列欠载。
`MusicStream` 拥有文件描述符，PCM 环形缓冲由 mixer 拥有；须对同一 mixer 调用 `close(mixer)` 释放两者，单纯丢弃生产者只会自动关闭文件。
停止后重新 `play_stream` 从当前缓冲头继续。WAV 定位与重播接口如下；压缩格式解码尚未实现。

### 定位与重播

静态片段使用 `Mixer.seek_voice(voice, source_frame)` / `seek_voice_seconds(voice, seconds)`，
流式 WAV 使用生产者的 `seek_frames(mixer, frame)` / `seek_seconds(mixer, seconds)`。
流式定位从目标位置准备最多 4096 帧，成功读取、解码、校验后才替换原环形缓冲并重置消费游标；旧 MixBlock 随之失效。
失败保留原 PCM、逻辑文件游标、播放状态、淡化和有效预览块。已打开的描述符仍固定，定位不会重新打开路径。

```xu
actual_frame := track.seek_seconds($&mixer, 0.5) or >>
position := track.position_seconds(&mixer) or >>
duration := track.duration_seconds()
track.restart($&mixer) or >>
```

- 定位范围包含文件末尾，时间按源采样率舍入到最近帧（中点取偶数）；方法返回实际目标源帧。循环音源定位到末尾会规范化为帧零。
- seek 保留播放/停止、暂停、总线、声像和当前音量，取消后续淡化及 fade-stop；当前音量在淡化步长之间也保持原精度，不重新量化成 0.001。
- 非循环音源定位到 EOF 立即停止；向前定位不会隐式启动已经停止的声音。`Mixer.restart_voice` / `MusicStream.restart` 从头恢复现有播放句柄，同时保留暂停和当前音量；如果音量已经淡到零，重播也保留零音量，须另行设置音量或淡入。
- 流式 restart 要求消费句柄仍有效；槽位已被其他声音复用时拒绝，不会控制复用的新声音。重新播放可先 seek，再使用 `play_stream` 或 `SceneAudio.play_stream` 建立新消费/节点绑定；restart 不会恢复已被场景 sync 清除的绑定。
- `read_position` 是生产者预读位置；`position_seconds` 是混音器已提交的源位置，包含已排队的输出，并非扬声器正在播放的位置。旧消费者槽复用后仍保留源最后提交的位置。
- 源 seek 不修改共享设备队列，已提交的音频按顺序播放，新位置在后续混音生效。若应用显式 pause/clear 输出队列，会影响该队列中的所有声源，且不会回滚其他源的混音进度。

运行 `make demo-audio-seek`，或 `./build/audio-stream --seconds 5 --seek-frame 12000`，
可观察同一播放 ID 的定位、从头重播和后续交叉淡化。只对 WAV/PCM 提供同步定位；异步读取/解码仍待实现。
不要将 `MusicStream` 持有的 source 单独 feed/reset；生产者需要统一维护文件位置与环形缓冲。

静态、流式、原生设备与文件操作的预算分别受限；本次没有引入新的 Xu 标准库或 C 混音代码。

## XuScript 标量脚本与开发热重载

`make demo-script` 会构建独立 Xu 编译工具、编译发送/接收两个脚本，随后启动游戏和两个源码轮询器。
运行时修改 [`examples/script_reload/player.xus`](examples/script_reload/player.xus) 中的 `speed := 180.0`，
例如改为 `360.0`，保存后角色行为在固定更新边界切换；位置、脚本持久字段和成功回调计数保留。
A/D 或方向键移动，Space 暂停，Esc 退出。顶部块数表示模块 epoch，底部条表示持续累积的回调计数。
最下方的小方块是独立的 MovementIndicator 节点，由脚本的 `moved` 信号驱动；速度改变时指示位置随事件数值改变。
它的处理函数位于 [`examples/script_reload/indicator.xus`](examples/script_reload/indicator.xus)；
将 `value * 30.0` 改为 `value * 60.0` 可热替换接收逻辑，同时保留累计事件数。

```sh
make demo-script

# 也可独立检查/构建，再在另一终端运行源码轮询器
make script-tool
./build/xu-nexus-script check examples/script_reload/player.xus examples/script_reload/player.schema.json
./build/xu-nexus-script build examples/script_reload/player.xus examples/script_reload/player.schema.json build/player.xubc
./build/xu-nexus-script build examples/script_reload/indicator.xus examples/script_reload/indicator.schema.json build/indicator.xubc
python3 tools/watch_script.py --tool build/xu-nexus-script \
  --source examples/script_reload/player.xus --schema examples/script_reload/player.schema.json \
  --output build/player.xubc
```

首个 profile 为 `xu-scalar-v1`。编译工具直接复用 SDK 的 `xu/scanner`、`xu/parser`、公开 AST 常量，
再做标量 profile 类型/作用域检查与寄存器指令生成，没有复制一套 Xu 解析器。
SDK 前端在语法错误时会结束进程，因此源码编译由独立子进程执行；游戏只加载、验证并解释编译产物。
每个开发轮询器每 200 ms 检查一个源码和一个 JSON 元数据文件，读取有界快照，编译超时为 5 秒。
编译失败不覆盖现有产物；成功后在同目录写临时文件并重命名发布。退出集成示例会清理其轮询器/编译子进程。

脚本使用真实 Xu 语法，例如：

```xu
@scripts/player

pub struct Player {
    pub ticks f64
    pub distance f64
}

fn (self $&Player) physics_process(delta f64, axis f64) f64 {
    self.ticks += 1.0
    movement := axis * 180.0 * delta
    self.distance += movement
    emit_signal("moved", movement)
    << movement
}
```

`player.schema.json` 显式声明 profile、模块/类，以及每个字段的稳定 ID、名称、`f64` 类型和初值。
示例中 ID 1 为 ticks、ID 2 为 distance；distance 是累计请求位移，实际碰撞与节点移动由 Xu 宿主完成。
本版使用 JSON 的严格数值访问器校验元数据；尚未实现方案中的 XUN 元数据适配。
可选的 `signals` 数组声明信号 ID 和名称，例如 `"signals": [{"id": 1, "name": "moved"}]`。
可选的 `handlers` 数组声明处理函数 ID 和名称，例如 `"handlers": [{"id": 1, "name": "on_moved"}]`。
字段、信号、处理函数使用各自独立的 ID 空间；未声明 `signals` / `handlers` 的现有源码仍可编译。

| 项目 | `xu-scalar-v1` 的实际范围 |
| --- | --- |
| 入口 | 一个状态 struct；可选的 `physics_process(delta f64, axis f64) f64`，以及最多 16 个 schema 声明的 `handler(value f64) f64`；至少一个回调 |
| 状态 | 仅 f64 字段，按稳定 ID 持久化；bool 只用于局部变量/条件寄存器 |
| 表达式 | f64 字面量、局部变量、`self.field`、加减乘除、负号、浮点比较、布尔 `!`、短路 `&&` / `||` |
| 语句 | 不可变/`$` 可变局部变量、显式 f64/bool 局部类型、赋值/复合赋值、if/else-if/else、while、返回 |
| 信号 | 作为独立语句调用 `emit_signal("名称", f64值)`；名称必须是 schema 中声明的字符串字面量，事件在成功回调后延迟交给宿主 |
| 暂未支持 | int/通用字符串/数组/字典/对象字段、导入、脚本中的普通函数/方法调用、泛型/生存期标注、局部同名遮蔽、for、循环跳出/继续、异常语法、void 处理函数、协程和脚本堆/GC |
| 运算语义 | 所有 f64 数值须有限且绝对值 ≤ 1e9；除零/越界是 VM 错误；数字字面量写作 `1.0`，不做 int 隐式转换 |
| 宿主边界 | 不暴露原生句柄、引擎借用或文件/网络调用；physics 参数 delta 为 0...0.25、axis 为 -1...1、结果绝对值最多 1024；信号处理函数的参数/结果仍受标量 ≤ 1e9 约束，派发器忽略返回值 |

每源码/元数据最多 16 KiB，最多 8,192 token / 4,096 AST 节点 / 64 层编译嵌套；
每模块最多 32 个字段、32 个信号、17 个回调、合计 256 个寄存器/常量、2,048 条指令、128 KiB 编译产物。
产物采用 `XUNEXUS-SCRIPT-1` 头和严格 JSON 寄存器指令，是便于检查的可移植文本格式，尚未承诺稳定发布 ABI。
字节码格式固定为 1，包含函数范围和稳定处理函数身份；不读取开发中间格式。运行 `make demo-script` 可构建工具、游戏和产物。
装载器校验格式/profile/API、字段、全部指令和操作数类型/范围、跳转、保留字和源码位置；不依赖“工具输出一定正确”。
函数范围须完整、连续、无重叠地覆盖代码，每个函数以 return 结束，跳转不能越过本函数范围。
每次进入回调都创建独立的临时寄存器状态，只有参数被初始化；局部变量不会在回调之间泄露。
VM 再检查未初始化寄存器读取和每步执行预算。NodeScript 默认每次回调最多 4,096 条指令；底层 VM 允许 1...100,000 的显式预算。

回调先在字段副本和临时事件队列中执行，仅在成功返回且满足宿主结果上限后提交。
除零、标量越界、无限循环预算耗尽、事件超限等失败不改变字段、已有事件或成功调用计数。
示例将脚本错误隔离为本帧零位移并继续输入/渲染，输出一次诊断；可以修复脚本后继续重载。

重载是同步调用之间的一次内存切换：先验证候选和完整状态迁移，再替换代码、状态及 epoch。
相同 ID 的字段保留旧值，改名/重排仍保留；新增字段取纯初值，删除字段被移除并将 ID 标为退役。
退役 ID 不允许重新使用；删除字段后直接退回包含该 ID 的旧 schema 会被拒绝，尚无 schema 回滚适配器。
修改已有字段的默认值不会覆盖其当前值；只修改函数体可正常往返重载。相同产物不重复增加 epoch。
每实例最多分别保留 4,096 个退役字段 ID、退役信号 ID 和退役处理函数 ID。
模块/类身份不匹配、产物非法、迁移失败时保持原实现和状态。
通过结构检查的代码仍可能发生运行时业务错误，按上述回调失败策略处理，不承诺自动回滚已激活模块。

节点暂停或排队删除时不执行 physics 回调；释放后旧节点 ID 不会绑定到复用的节点槽。
NodeScript 必须始终配合同一棵树使用，尚无跨世界 NodeRef、完整生命周期回调、依赖闭包或多模块更新事务。

低层 NodeScript 仍支持 `script.connect(&tree, "moved", target, "on_moved")` 建立连接，再在更新边界调用
`script.collect_signals(&tree)` 取得 `SignalDelivery`，由显式 Xu 代码按 handler 分派。
该接口的 handler 是路由键，调用者负责分派；也可用 `NodeScript.receive_signal` 调用经声明的处理函数 ID。
不会在 VM 内调用宿主或递归进入其他脚本。

每次回调最多发出 32 个事件，实例待取队列最多 128 个，单个 NodeScript 最多 32 个连接；
超出事件额度使整个本次回调失败，超出连接额度明确报错。
`collect_signals` 将事件仅取出一次，按发出顺序、再按连接建立顺序展开，单批最多 4,096 条投递。
没有连接的事件也会被取走。重复建立相同的信号/目标/handler 连接会返回原连接 ID；连接 ID 不复用。
`disconnect(id)` 返回是否删除；`prune_connections` 可主动清理失效连接。
连接列表在收集时确定；收集前新增或断开连接，也会影响已提交但尚未收集的事件。

信号同 ID 改名/重排后连接保留；成功重载删除信号时清除其连接、退役其 ID，再引入旧 ID 会被拒绝。
重载前已提交的事件保留原 epoch、回调序号、ID 和数值；仍有连接时可投递，信号已删除时丢弃。
收集时清理已排队删除/释放的源和目标，generation ID 防止复用节点槽接收旧事件。
已提交事件不受后续暂停影响，目标 process mode 也不阻止投递。
已收集的投递是连接快照，之后断开连接不撤销该快照；处理前若场景发生变更，应重新调用 `delivery.is_live(&tree)` 检查两端节点。

`SceneScripts` 进一步拥有节点脚本和连接，并自动派发到脚本处理函数；示例的指示器已使用此路径。
它支持 1...32 个脚本槽，同一管理器内每个节点只允许一个脚本；attachment ID 带 generation，
同节点卸载并重新挂脚本后也会生成不同 ID。ID 仅属于当前管理器，管理器始终配合同一 SceneTree、同一 owner 线程使用。

```xu
$scripts := host.new_scene_scripts(8) or >>
source := scripts.attach(&tree, actor, player_program) or >>
receiver := scripts.attach(&tree, indicator, indicator_program) or >>
scripts.connect(&tree, source, "moved", receiver, "on_moved") or >>
scripts.physics_process(&tree, source, delta, axis) or >>
report := scripts.dispatch(&tree, host.DEFAULT_DISPATCH_LIMIT) or >>
```

处理函数仍使用 Xu 方法语法，例如 `fn (self $&Indicator) on_moved(value f64) f64`。
`SceneScripts.connect` 在两端解析稳定信号/处理函数 ID，连接在双方改名/函数重排后保留；
删除处理函数会清理连接并退役其 ID。`reload` 支持按 attachment 单独重载，开发包的 `DevelopmentFile.poll_scene` 负责文件轮询后重载，
`epoch` / `calls` / `state` 查询各自实例，`detach` / `prune` 处理卸载和节点生命周期。

管理器全局最多 32 条连接，单个实例待取事件仍最多 128 个，因此一次收集最多 4,096 条投递。
每次 `dispatch` 默认示例传入 64，最多允许 128 次尝试；每个处理函数最多执行 4,096 条指令。
按槽位、该源的事件顺序、连接顺序收集；已有队列优先处理，未处理完时不收集新事件。
只有进入时队列为空才收集新一批，处理函数发出的信号留到后续 dispatch；本轮不会递归执行新事件。
反馈环仍可持续到后续帧，调用方应在固定更新边界按预算调用 dispatch；这不是整个事件图的自动终止保证。

每个回调独立提交：接收失败不会撤销已成功的发送回调，失败投递消耗一次尝试且不重试，其他投递继续。
`DispatchReport` 返回 collected/attempted/delivered/rejected/dropped/remaining/deferred_events 和首个错误；
示例显示错误但继续渲染。暂停不取消已提交事件；排队删除/卸载的两端、已删除的处理函数会使待派发快照丢弃。
已收集队列是连接快照，断开连接影响未来收集；attachment generation 检查防止旧消息进入重挂的新脚本。

生产内容分发、签名/反重放、A/B 持久恢复、源映射调试器和资源热替换仍待实现。
`.xus` 与元数据是源码；`.xubc`、临时文件、测试和截图保持忽略。

分包：`script/compiler` 只用于工具；`script/bytecode` / `script/vm` 不依赖前端或 GPU，
`script/host` 绑定场景暂停/删除与节点信号；`script/development` 单独负责开发态文件更新。通用有限 f64 位解码、文件有界快照/原子发布各自隔离在 `internal/`，
继续作为标准库/基础包候选，本批没有修改 Xu 编译器或标准库。

## 与 Xu 标准库的边界

| 能力 | 归属决策 |
| --- | --- |
| 标量数学、字节序、文件、时钟、序列化、哈希 | 直接复用 Xu 已有公开标准库 |
| IEEE 浮点位转换、二进制浮点读写 | 优先提出标准库扩展；当前私有适配器不依赖 `ui/internal` |
| 通用向量、矩阵、四元数 | 先验证为独立基础数学包，接口成熟且有跨领域使用后再评估入标准库 |
| 文件监听、通用 GPU/RHI、着色器工具、通用脚本 VM | 优先独立包/工具；需要跨平台与生命周期契约，不能因引擎需要就直接入标准库 |
| 相机、Reverse-Z、场景、材质、glTF、动画、物理、编辑器、节点脚本与热更新迁移策略 | 游戏引擎负责 |

标准库不得反向依赖本引擎或 SDL。本批只在 `nexus` 内落地与隔离能力，未修改 Xu 编译器或标准库。

## 场景与服务组合示例

消费项目的 `xu.xun`：

```yaml
module: example/my_game
version: !ver 0.1.0
xu: !ver 0.12.7-dev.1
require:
  "github.com/xulang-org/nexus": file:/path/to/nexus
```

需要 GPU 或音频设备时先在引擎目录运行 `make native`；纯场景和脚本不需要原生归档。

```xu
scene #"github.com/xulang-org/nexus/scene"
fm #"github.com/xulang-org/nexus/foundation/math"
controls #"github.com/xulang-org/nexus/input"
timing #"github.com/xulang-org/nexus/timing"
physics #"github.com/xulang-org/nexus/physics2d"

$tree := scene.new_scene_tree("World", 128) or >>
player := tree.add_child(tree.root(), "Player") or >>
tree.set_position(player, fm.vec2(64.0, 64.0)) or >>
$clock := timing.new_clock(60, 8) or >>
$input := controls.new_input_map()
// 主循环读取平台事件，通过 integration/input 更新 input，
// 用 clock.advance 安排固定步进，physics.move_and_slide 计算位移，
// 再把结果写入 tree；integration/rendering 读取树并提交到 rendering。
```



完整主循环、设备初始化、退出路径和多帧运行见
[`examples/arena/main.xu`](examples/arena/main.xu)。可用
[`examples/headless/main.xu`](examples/headless/main.xu) 单独运行模拟。

## XACP (智能体自动化控制)

本库原生内置了对 **Xu Agent Control Protocol (XACP)** 的完整支持，模块路径为 `github.com/xulang-org/nexus/xacp`。外部 AI 智能体（Agent）、自动化测试套件或调试器可以通过标准 XACP/1 TCP 协议帧连接正在运行的游戏，实现对场景状态的高精度无感检测与闭环控制。

### 核心支持功能

| XACP 操作 | 对应能力 | 说明 |
| --- | --- | --- |
| `xacp.hello` | 握手与能力协商 | 返回 `view_state \| control_input \| step_exec \| pause_resume` 权限集与目标信息 |
| `proc.status` | 运行健康探测 | 返回引擎运行状态、已用时钟及节点统计 |
| `ui.tree` | 场景树序列化 | 递归导出 `SceneTree` 层级结构（节点 ID、名称、类型、可见性、全局坐标与仿射变换） |
| `ui.input` | 虚拟输入注入 | 将虚拟按键、指针位移等事件无损映射并注入到 `InputMap` |
| `ui.act` | 仿真行为控制 | 支持 `pause` / `unpause` 等系统动作 |
| `nexus.step` | 逐帧步进控制 | 支持暂停状态下推进 `N` 物理帧后重新挂起，用于精准逐帧仿真与评测 |
| `nexus.state` | 引擎指标快照 | 查询当前帧序号、节点总数、暂停状态与调试计数 |
| `ui.screenshot` | 渲染周期同步截图 | 配合 GPU 渲染生命周期在 `present()` 前捕获当前画面，支持 Base64 返回或路径回传 |

### 快速启用

启动示例游戏并暴露 XACP 端口：
```sh
# 启用默认 XACP 控制端口（127.0.0.1:19876）
./build/arena --xacp-tcp

# 或自定义端口
./build/arena --xacp-port 20000
```

在自定义游戏中接入：
```xu
xacp #"github.com/xulang-org/nexus/xacp"

// 1. 初始化控制实例（例如监听 19876）
$ctrl := xacp.attach_tcp(19876)

// 2. 在游戏主循环中轮询
while !quit {
    input.begin_frame()
    if ctrl.is_open() {
        ctrl.poll($&tree, $&input)
        if ctrl.screenshot_requested() {
            shot_path := "build/shot.png"
            renderer.capture(shot_path + "") or >>
            ctrl.fulfill_screenshot(renderer.width() or >>, renderer.height() or >>, shot_path)
        }
    }
    // ... 原有事件轮询、物理步进与渲染流程 ...
}
```

### 运行 XACP 回归测试

```sh
# 运行全部 8 项 XACP 协议端到端集成测试
make xacp-test
```

## 核心契约

| 概念 | 本库接口与约定 |
| --- | --- |
| 场景树 | `SceneTree` 独占节点存储；节点 ID 仅对原树有效，释放复用后旧 ID 失效 |
| 节点路径 | `find_node` 支持相对路径、绝对路径、`.`、`..`；同级节点名称唯一 |
| 变换 | `Transform2D` / `Mat4` 分池存储；2D +Y 向下，3D +Y 向上，角度为弧度 |
| 相机 | `Camera2D` 保持设计宽高比；提供位置、旋转、缩放、视口及屏幕/世界坐标互转 |
| 图集动画 | `AtlasAnimation` 定义行列、帧范围、帧率和循环；`SpriteAnimator` 管理暂停、跳帧与单次完成通知 |
| 生命周期 | `take_ready()` 返回一次性的子节点先于父节点通知；由应用分派 Xu 行为 |
| 更新 | `process_order()` 按场景先序给出可更新节点，遵循继承与暂停模式 |
| 删除 | `queue_free` 标记整个子树，立即停用；帧末 `flush_free` 释放并返回子先父后的旧 ID |
| 场景资源 | `pack_scene` / `PackedScene.instantiate` 复制混合节点；`integration/scene` 保存/加载版本化文档，`integration/scene_render` 恢复声明的 GLB 表面；实例节点状态独立 |
| 输入 | 一个动作可绑定多键；自动重复不制造新按下边沿；失焦调用 `release_all` |
| 时钟 | `Clock.advance` 返回固定步数、插值权重及丢弃时间；限制补帧，避免无限追赶 |
| 碰撞 | 静态轴对齐矩形的连续扫掠与滑动；初始穿透明确报错，不提供刚体求解 |
| 纹理 | `Texture2D` 是独占 GPU 资源，RGBA8 输入同步复制；renderer 关闭会释放其纹理 |

### 相机和 PNG 动画

```xu
nexus #"github.com/xulang-org/nexus/scene"
sprite_anim #"github.com/xulang-org/nexus/animation/sprite"
images #"github.com/xulang-org/nexus/assets/image"
image_render #"github.com/xulang-org/nexus/integration/image_render/two_d"

camera := nexus.new_camera_2d(960.0, 640.0) or >>
view := camera.view_transform(f64(width), f64(height)) or >>
viewport := camera.viewport(f64(width), f64(height)) or >>
image := images.load_png("assets/player.png") or >>
$atlas := image_render.upload_image_2d(&renderer, &image, false) or >>
clip := sprite_anim.new_atlas_animation(4, 1, 0, 4, 8.0, true) or >>
$animator := sprite_anim.new_sprite_animator(clip) or >>
```

在固定更新中调用 `animator.advance(delta_seconds)`，绘制前将 `animator.region()` 赋给
`Sprite2D.region`。`renderer.begin()` 后使用 `renderer.clip_rect(viewport)` 限制世界绘制，
随后用 `view` 录制场景。需要在黑边区域绘制其他内容时调用 `renderer.reset_clip()`。
每次 `begin()` 自动重置裁剪；传入的小数裁剪边界向外取整到完整像素。

`camera.position` 是视口中心对应的世界位置，`zoom` 越大物体越大，角度使用弧度。
`screen_to_world` 和 `world_to_screen` 的屏幕单位与输出尺寸一致。
黑边中的点也会映射到世界坐标；拾取前用 `viewport.contains(point)` 排除它们。

图集帧号为从零开始的绝对行优先索引。动画暂停不累计时间；`play()` 在完成后从头播放，
`seek_frame()` 重设帧内时间但保持播放/暂停状态。非循环片段的最后一帧显示一个完整帧间隔，
随后 `advance().finished` 只触发一次；`is_finished()` 保留完成状态。
单次 `advance` 的时间范围为 0...3600 秒，跳过大量帧通过算术处理，不逐帧循环。

核心对象由调用方在同一线程更新。GPU 对象的创建、事件、绘制、关闭和析构必须在应用主线程。
2D/3D 窗口共用标准事件入口：每轮调用一次 `window.pump()`，再按窗口 `poll()`。`InputMap.begin_frame()` 在事件处理前调用；
边沿以渲染帧为单位，跨多个物理步的一次性动作须由游戏消费一次。

`PackedScene` 是内存节点资源，只复制节点类型、局部变换和公共属性；文档的来源与表面声明由 `integration/scene_render` 独立管理。
不序列化 GPU 句柄、脚本执行状态或相机镜头参数；节点转换不会静默丢弃来源/表面/音频声明。
`Canvas2D` 按场景先序录制颜色节点；纹理精灵用 `Sprite2D.record` 录入共享纹理批次。
批次按提交顺序绘制，跨纹理的透明对象需要调用者按需要拆分批次。
回读和截图须在 `submit` 之后、`present` 之前调用，会使 GPU 与 CPU 同步。

容量：每树最多 65,536 节点，单个场景资源最多 4,096 节点；最多 128 个动作 / 512 个键；
每帧最多 393,216 顶点。纹理单边最多 4,096、单纹理最多 4,194,304 像素，
每 renderer 的用户 RGBA 纹理总预算 64 MiB；2D 每设备最多 1,024 张，3D 每设备最多 512 张（计入完整 mip 链）。
CPU 图片与输入字节在当前 SDK 中使用整数数组，CPU 内存不等于压缩文件大小，也不计入这个 GPU 预算。
PNG 输入文件最多 32 MiB，先检查签名和 IHDR 尺寸，再从不可变字节副本解码；
文件、尺寸、解码或 GPU 上传失败都会抛错。解码表面和文件副本不会在返回后保留。

## XACP (智能体自动化控制)

本库原生内置了对 **Xu Agent Control Protocol (XACP)** 的完整支持，模块路径为 `github.com/xulang-org/nexus/xacp`。外部 AI 智能体（Agent）、自动化测试套件或调试器可以通过标准 XACP/1 TCP 协议帧连接正在运行的游戏，实现对场景状态的高精度无感检测与闭环控制。

### 核心支持功能

| XACP 操作 | 对应能力 | 说明 |
| --- | --- | --- |
| `xacp.hello` | 握手与能力协商 | 返回 `view_state \| control_input \| step_exec \| pause_resume` 权限集与目标信息 |
| `proc.status` | 运行健康探测 | 返回引擎运行状态、已用时钟及节点统计 |
| `ui.tree` | 场景树序列化 | 递归导出 `SceneTree` 层级结构（节点 ID、名称、类型、可见性、全局坐标与仿射变换） |
| `ui.input` | 虚拟输入注入 | 将虚拟按键、指针位移等事件无损映射并注入到 `InputMap` |
| `ui.act` | 仿真行为控制 | 支持 `pause` / `unpause` 等系统动作 |
| `nexus.step` | 逐帧步进控制 | 支持暂停状态下推进 `N` 物理帧后重新挂起，用于精准逐帧仿真与评测 |
| `nexus.state` | 引擎指标快照 | 查询当前帧序号、节点总数、暂停状态与调试计数 |
| `ui.screenshot` | 渲染周期同步截图 | 配合 GPU 渲染生命周期在 `present()` 前捕获当前画面，支持 Base64 返回或路径回传 |

### 快速启用

启动示例游戏并暴露 XACP 端口：
```sh
# 启用默认 XACP 控制端口（127.0.0.1:19876）
./build/arena --xacp-tcp

# 或自定义端口
./build/arena --xacp-port 20000
```

在自定义游戏中接入：
```xu
xacp #"github.com/xulang-org/nexus/xacp"

// 1. 初始化控制实例（例如监听 19876）
$ctrl := xacp.attach_tcp(19876)

// 2. 在游戏主循环中轮询
while !quit {
    input.begin_frame()
    if ctrl.is_open() {
        ctrl.poll($&tree, $&input)
        if ctrl.screenshot_requested() {
            shot_path := "build/shot.png"
            renderer.capture(shot_path + "") or >>
            ctrl.fulfill_screenshot(renderer.width() or >>, renderer.height() or >>, shot_path)
        }
    }
    // ... 原有事件轮询、物理步进与渲染流程 ...
}
```

### 运行 XACP 回归测试

```sh
# 运行全部 8 项 XACP 协议端到端集成测试
make xacp-test
```

## 本机验收

按 Xu 项目约定，`tests/` 与生成物保留本机且被 Git 忽略。
本机可运行 `make test`（变换、节点、场景实例、输入、时钟、连续碰撞、相机和动画）和
`make xacp-test`（XACP 协议独立集成测试）与
`make gpu-smoke`（2D GPU 绘制、PNG、图集、透明采样、裁剪，以及 3D 上传、GPU MVP、深度顺序、
逐帧深度清空、近面/背后裁剪、回读、帧状态和生命周期）。`make test` 同时运行 3D 数学和网格验证，以及未初始化视频/GPU 的 PNG 解码检查。
2D/3D 服务分别在不提供 nexus 原生归档、场景、脚本和适配源码的临时目录中编译并完成 Metal 像素回读；
设备和纹理经 12 次窗口自动释放、1,080 张纹理的拥有数组释放检查，验证自动析构释放资源。
音频另覆盖无 SDL 的 WAV/混音/流式隔离构建、48 MB 稀疏文件首尾读取、100 次缓冲回绕与随机定位、欠载/EOF/错误恢复、淡化/交叉淡化、定位不改变共享输出队列、
设备独立构建、16 个坏 WAV、播放代次、总线/循环/重采样、节点空间参数，
以及音频/GPU 同进程关闭任意一个子系统后另一个继续工作。`make audio-test` 可单独运行音频检查。
另覆盖 3D/混合层级、保持世界变换换父节点、组件池复用、混合 PackedScene、相机支架、
场景隐藏/删除、过期资源句柄拒绝和网格引用所有权。GLB 验收覆盖不同索引/颜色/UV 编码、场景与变换、
64 个几何异常与 33 个材质 profile 异常拒绝、共享 GPU 实例、源哈希匹配、整批绑定预检，以及强制容量失败后的上传回滚。
材质 GPU 检查还覆盖五槽已知像素、MR 不误用 R、独立 AO、颜色空间/采样器去重、单/双面与模型/相机镜像，
以及 PNG 损坏、累计解码/GPU 预算和中途网格耗尽后的资源恢复；批量绑定失败保留旧表面，替换可修复旧的陈旧材质。
节点文件另覆盖 70 项异常输入、f64 极值/次正规数/负零、先序/深度/同级命名、4,096 节点实例化、
独立实例/ready/代次、目标树不变、旧文件保留与临时文件清理、无 SDL 初始化的跨进程保存重载。
纯格式、节点场景适配和脚本恢复的隔离构建均无需原生归档；音频场景只链接音频设备归档。
资源场景另覆盖 54 项异常声明、4,096 表面、ID 生成、来源/表面共享、固定哈希、32 MiB 累计来源预算、
全部模型回收、跨设备/关闭拒绝、原子批量绑定与保留元数据的保存/重开。
单独运行 3D GPU 检查可使用 `make gpu3d-smoke`。
脚本验收包括 59 个错误源码/元数据不覆盖有效产物、非法字节码及非当前格式拒绝、零值对象拒绝、
100 轮状态保留重载、字段/信号改名/重排/增删、失败回调无部分状态或事件提交、
事件/连接容量、4,096 条投递边界、函数范围与寄存器隔离、脚本处理函数及 attachment generation，
以及 100 轮有界反馈派发、暂停和节点删除。
`make script-live-smoke` 在真实 GPU 进程运行中修改源码：语法错误保持旧行为、修复后切换速度、
发送端速度 180→360、接收端倍率 30→60 与处理函数改名均能保留状态和连接，
并拒绝/恢复损坏产物，完成 300 帧 / 300 次发送回调 / 300 次接收回调 / 300 条信号投递。
这些目标需要本机测试目录；源码消费者可以运行上面的 `make check` / `make smoke`。
使用普通 Xu 程序执行回归；纯 Xu 与设备链接分别验收，使用同一个修复版 SDK。

Linux / Windows 尚未完成构建、窗口输入与真实 GPU 运行验证；本版不声明这两个系统验收通过。

## GPU 标准库边界

`#gpu/layout` 已在 Xu `0.12.3-dev.2` 实现。它计算格式块、mip 层级、字节范围、row pitch 与 level offset，
不把某个后端的 256/512 字节对齐规则或本引擎的 64 MiB/4096 上限写成标准库默认政策。
2D 复用标准 GPU 的格式与传输校验；3D 上传将其 mip 数量/逻辑字节数与真实设备创建结果核对，不一致则回收新纹理并报错。

本轮 Xu `0.12.6` 的可选 `#gpu` 已实现无窗口设备、Buffer、异步上传/GPU 复制/下载、Fence/Readback 与逻辑资源统计。
`&[]u8` 输入在返回前复制到后端 staging；读回只在完成后写入 exact-size `$&[]u8`，关闭设备统一回收子资源。
传输采用四字节对齐，所有 owner/borrow 留在应用主线程；无窗口仍可能需要平台视频驱动。
导入时用同一 SDK 的 `xu-native` 按 `native.xun` 编译源码后端，设备打开时才加载 SDL；无需应用 native 声明或 SDL 开发头文件。
`make gpu-transfer-smoke` 只编译独立标准库示例，不构建 nexus 的原生归档或 shader，验证 4,096 字节上传/复制/fence/读回；纯 `gpu/layout` 仍不触发 C 编译。

Texture/Sampler/Shader/Pipeline、CommandEncoder 与离屏 render pass 已在标准 GPU 层实现；缓冲区 ComputePipeline/Pass、读写绑定、uniform 与 dispatch 已补齐，计算采样器/纹理、间接 dispatch 继续实施；标准 `window` 与 SDR Surface/Frame 已实现。
开发 SDK 阶段的 GPU/浮点批次与缓冲区计算六平台验收均已通过，包括计算 API 编译、源码后端导入与缺库诊断、字节 span 和 O0/O2/O3 的 912 组浮点检查。真实 GPU 设备仍仅验证 macOS arm64 Metal。
nexus 的 GPU 原生模块、3D C 桥接、shader C 头生成和旧事件协议均已删除。2D/3D 均使用标准 GPU/window；PBR、相机和资源预算留在引擎。
场景、相机、PBR/灯光/阴影策略、批处理、资源导入与应用预算继续属于引擎；窗口和事件也不归 GPU 设备核心所有。
`gpu/layout` 只描述内存布局，不表示某格式、渲染/存储用途或某个 GPU 后端已通过设备支持查询。

License: MIT。

## 独立标准 GPU 离屏示例

```sh
make gpu-offscreen-smoke
```

`examples/gpu_offscreen` 只依赖标准库：创建采样纹理、Shader、图形管线和命令编码器，
通过标准 `encoding/binary.put_f32` 在运行时打包三维顶点、4×4 矩阵与 tint uniform。四帧分别验证矩阵裁剪和 RGB 分量，每帧读回 7×5 像素逐字节检查；最后一帧提前关闭 CPU 资源仍能完成绘制。
独立工作目录验收不包含游戏源码、游戏原生归档或窗口。示例含 MSL、GLSL 和 HLSL 源码；
macOS 直接使用 MSL，Linux 需 glslangValidator，Windows 需 DXC 预编译 Shader。
`tools/gpu_offscreen_shaders.py --backend ... --out-dir ...` 可显式准备对应后端的产物。
真实绘制目前只验收 macOS arm64 Metal，其余后端源码和 API 存在不代表真机通过。

2D/3D 已实际迁移标准 GPU/window，窗口共同使用 `window.pump/poll`；场景、PBR、相机和渲染预算继续留在引擎层。

## 独立标准 GPU 计算示例

```sh
make gpu-compute-smoke
```

`examples/gpu_compute` 只导入标准库；上传 1,027 个 uint32 值，先计算 `3x+7`，在新的计算 Pass 中计算 `5x+11`，
下载后与 CPU 的 uint32 参考逐项对照，包含溢出回绕和不完整的末尾工作组。输入、临时缓冲和管线提前关闭后，
已记录命令仍可完成；fence/readback 关闭后资源归零。该示例也在没有 nexus 源码/原生归档的临时目录通过，包含空格路径。

读缓冲与写目标分开绑定；需要前次结果时结束当前 Pass，不能依赖同一 Pass 内多个 dispatch 的顺序。
通用计算机制位于 Xu `gpu`，粒子、物理、剔除等应用规则留在引擎。
提供 MSL、GLSL 和 HLSL 源码，`tools/gpu_compute_shaders.py` 按宿主准备产物；Vulkan 需 glslangValidator，D3D12 需 DXC。
本轮只有 macOS arm64 Metal 真机通过，其余 Shader 的目标工具链与真机运行仍待验收。

## 浮点存储与标准库分工

Xu `math.float64_bits/from_bits` 保留 binary64 位模式；`float32_bits/from_bits` 提供 binary32 转换，
`encoding/binary` 提供 `[]u8` 的大小端整数/浮点读写、舍入到最近偶数、负零与 NaN 规则和失败不部分写入。
这些能力不依赖 GPU、UI 或 C 工具。引擎的 GLB、WAV、脚本字面量和渲染标量已复用标准转换。
渲染器仍负责有限值、±1e9 上限和正零规范化；格式/VM 各自保留领域约束。
分层检查为 53 个包，无临时浮点解码包或兼容门面。

## 独立标准窗口与 GPU 呈现示例

```sh
make gpu-surface-smoke
./build/gpu-surface --frames 240 --backend auto --shaders build/gpu-surface-shaders
```

`examples/gpu_surface` 只导入标准库：`window` 拥有窗口和生命周期循环，`gpu.Device` 通过类型化借用创建 Surface。
每帧以实际获取的像素尺寸设置 scissor，绘制左红右蓝窗口；无图像时正常跳帧。一次只允许一帧未提交；
帧提交返回 Fence，示例释放 Fence 所有者而不逐帧等待设备空闲。Surface 关闭时才等待在途工作，再释放窗口绑定。
最小化可能仍返回有效图像，不能把窗口标志当成获取结果。

关闭已获取但未提交的 Frame 会结束活动 Pass、清黑并提交，可能显示黑帧；不能调用离屏命令的取消路径。
错误时同样完成清理并保留首个失败。交换链图像不暴露为普通 Texture，不可采样或读回。
`window.pump` 复制自身键鼠/文本事件到有界队列，应用用 `poll` 消费；溢出显式发出输入重置事件；
外部窗口、用户事件和全局退出事件留给各自消费者。游戏动作、场景和材质仍留在引擎。

新标准库共用私有 `internal/sdl` 后端；显式运行库路径统一为 `XU_SDL_LIBRARY`，不保留未发布的 GPU 专属旧变量。
nexus 不再有 GPU 原生模块；标准 GPU/window 和独立 CPU PNG codec 使用 `XU_SDL_LIBRARY`。隔离验收不提供 nexus 原生归档。
2D/3D 已统一到标准按窗口队列；独立构建检查共同泵送与窗口身份、缩放和关闭隔离。
MSL、GLSL、HLSL 源码与独立 shader 准备工具均已提供；本机真实呈现/视觉验证仅覆盖 macOS arm64 Metal，
其它平台 SDK 的编译/安装验收不代表 Vulkan/D3D12 GPU 已执行。

## 标准窗口输入与引擎动作示例

```sh
NEXUS_XU_SDK=/path/to/xu-0.12.7-dev.1
XU_ROOT="$NEXUS_XU_SDK" XU_STDLIB_ROOT="$NEXUS_XU_SDK/src" XUPATH="$NEXUS_XU_SDK/src" XU="$NEXUS_XU_SDK/bin/xu" make window-input-smoke
./build/window-input --frames 600
```

`examples/window_input` 使用标准窗口、事件、GPU Surface，只复用 nexus 的 CPU 动作映射和输入整合，
不构建引擎原生归档、场景或 Shader。W/Space 按住为绿色，松开为蓝色；Escape 请求退出；
文本与 IME 组合打印到终端。自动 smoke 验证真实 Metal 清屏、呈现和资源归零，不把未实际输入按键的运行当成交互验收。

标准 `window/events` 是纯 Xu 数据，包含窗口身份、物理 USB HID 键、逻辑键、便携修饰键、
小数坐标/相对量/滚轮、独立 UTF-8 文本和以 Unicode 码点计数的 IME 选区。`window` 提供按窗口的
`pump/poll`、按键/鼠标快照、文本启停/输入区域、相对指针与抓取请求；平台不支持时直接报告失败。

每窗口最多 256 个事件、每份文本 64 KiB、排队文本合计 256 KiB。超额、分配失败、非法输入会清空待消费历史与按下状态，
发出带原因的 INPUT_RESET；消费该事件前丢弃后续自有输入，其他窗口互不影响。关闭请求始终锁存；焦点丢失/重置后，
没有新按下的重复键不能恢复按住状态。返回文本在后续事件推进、队列复用和窗口关闭后仍然有效。

`integration/input.apply_window_input` 只把物理按键送入 nexus 的动作映射；重置、失焦、关闭释放所有动作，
忽略重复按下/未知键和文本/指针事件；松键不因重复标志而丢弃。纯动作验收在没有 C 编译器、SDL、场景或引擎原生源码的临时目录以 `--no-opt` / `--release` 通过。
标准窗口/GPU 示例在只复制上述 CPU 包的临时目录通过。2D/3D 均使用标准事件与动作适配，旧全局事件循环已移除。

输入链路已通过真实 SDL 队列的注入事件与公开 Xu ABI 验证，包括中文/emoji 复制、IME 选区、小数鼠标/滚轮、
溢出/内存失败、外部事件保留和重复键恢复；这与真实 OS 键入不同。macOS 已观察到焦点通知、鼠标点击、物理按键和英文文本；中文/emoji/IME 的 OS 交互仍待补验收，
其它系统真实输入、剪贴板、触摸、手柄和自绘 IME 候选尚未完成。

macOS 端到端 OS 交互已补验：W/Space 触发引擎动作并提交绿色 GPU 帧，松开恢复蓝色，Escape 退出且资源归零。中文/emoji 与原生 IME 组合仍只有注入检查，未据此宣称真实 OS 组合通过。

3D 运行时与 2D 共用标准窗口事件，`Device3D.window()` 返回借用；Shader 由 `open_3d` 的显式参数提供。所有 3D 示例支持 `--shaders DIR`，默认 `build/mesh-shaders`。
网格每设备最多 512 个 / 64 MiB，纹理每设备最多 512 张 / 64 MiB（完整 mip 链）；内部颜色、深度和白纹理另计。目标最多每边 4096、合计 4M 像素，每帧最多 16384 次 draw。上传须在帧外完成，readback 会封闭本帧绘制。
标准 `DeviceRef/BufferRef/TextureRef/SamplerRef` 不延长所有者生命周期，不暴露原生整数或指针；关闭/跨设备检查在预检和实际绑定时均执行。

本机 Metal 失败注入可运行 `make gpu-failure-test`：验证已消费的命令提交失败及缩放时深度目标分配失败，保留首个错误并恢复下一帧。必要时用 `XU_TEST_SYSROOT` 为该测试的 Clang 指定兼容 macOS SDK。

## 3D 多光源与场景绑定

`resources/lighting` 定义纯 CPU 的 `Light3D` 和 `Environment3D`，材质、场景与 GPU 不互相拥有；`rendering/three_d.draw_material` / `Scene3D.draw_lit` 接收 `&Environment3D`。

```xu
lights #"github.com/xulang-org/nexus/resources/lighting"
light_scene #"github.com/xulang-org/nexus/integration/lighting"

$world := light_scene.new_scene_lights_3d()
source := lights.point(fm.vec3(0.0, 0.0, 0.0), fm.vec3(12.0, 2.0, 1.0), 8.0) or >>
world.attach(&tree, light_node, source) or >>
// 修改 Node3D 的变换/可见性后重新收集；不创建 GPU 资源。
sources := world.gather(&tree) or >>
environment := lights.environment(fm.vec3(0.02, 0.02, 0.02), camera_position, 1.0, sources) or >>
scene.draw_lit($&device, &tree, view_projection, &environment) or >>
```

- `directional(toward_light, radiance)`：方向为表面指向光源，归一化后使用。
- `point(position, radiance, radius)`：反平方强度乘平滑半径截止 `(1-(distance/radius)^4)^2`；半径边界及以外不贡献，近场在 0.01 世界单位处钳制，重合点没有定义的入射方向，贡献为零。
- `spot(position, forward, radiance, radius, inner_half_angle, outer_half_angle)`：方向从光源射向锥体，半角为弧度，`0 <= inner < outer < pi/2`；cosine 间距至少 1e-6，内外锥之间使用 cosine 域平滑过渡。

线性 RGB 强度每通道 0...64，半径 0.001...1e6 世界单位，位置和相机坐标 ±1e9，曝光 0.01...16，环境光每通道 0...1。环境与场景收集最多 256 个候选源；按每个网格的包围盒筛选后，可能影响该网格的源最多 16 个，超额在 GPU 编码前报错，不自动截断。直接光在线性空间相加，环境光和自发光各加入一次，最后统一曝光、Reinhard 和 sRGB 编码；AO 只作用于环境项。

`SceneLights3D` 每个 Node3D 绑定一个光源，可原子替换；按场景先序收集。位置继承仿射变换，方向使用线性部分并归一化；非均匀缩放/剪切不改变世界半径和锥角。隐藏/待删除/已释放节点不发光，暂停处理仍保持照明。全代次节点 ID 避免旧绑定指向复用槽；`prune` 回收退休绑定。绑定集合必须搭配原来的 SceneTree，当前不处理跨世界引用。

```sh
make demo-lighting
./build/lighting --frames 120 --capture build/lighting.png
./build/lighting --mode point --frames 120 --capture build/lighting-point.png
./build/lighting --mode spot --frames 120 --capture build/lighting-spot.png
make lighting-core-test lighting-gpu-test lighting-demo-test
```

D/P/S 分别切换方向光/点光/聚光，方向键环绕，Space 暂停光源运动，Esc 退出；`--mode all|directional|point|spot|none` 可做有界对照，`--shaders DIR` 指定离线着色器目录。示例使用同一份网格绘制 15 个材质球与光源标记。

方向/点/聚光已支持场景文件保存和恢复；光源空间索引/分簇和 IBL 尚待实现。MSL/GLSL/HLSL 共用同一 BRDF 与衰减方程；真实 GPU 像素验收当前仅 macOS arm64 Metal。

## 方向光、聚光灯与点光源阴影

`resources/shadow.ShadowDescription3D` 保存纯 CPU 光源描述与投影；`rendering/three_d.ShadowMap3D` 拥有双缓冲 GPU 目标；`integration/rendering/three_d.Scene3D.shadow_casters` 组合可见节点、当前 LOD、世界变换和弱网格引用。资源层只依赖数学和纯光源数据，不导入 GPU、场景或文件。

```xu
// 方向光：固定世界覆盖体，朝向光源的方向与环境中相应灯一致。
description := shadow.directional(center, toward_light, 4.0, 16.0, 1024) or >>
// 聚光灯使用 shadow.spot(source, 0.1, 1024)。
// 点光源使用 shadow.point(source, 0.1, 512)。source 是对应 Light3D。
program := shaders.load_shadow("build/mesh-shaders") or >>
$shadow_map := device.shadow_map(description, &program) or >>
// 每帧先应用动画/LOD，在主帧 begin 前更新全部投影。
casters := scene.shadow_casters(&tree) or >>
submitted_triangles := shadow_map.render(&device, &casters, description) or >>
device.begin(255) or >>
scene.draw_lit_shadowed($&device, &tree, view_projection, &environment, &shadow_map, 0) or >>
device.present() or >>
```

`directional(center,toward_light,half_extent,depth,resolution)` 使用 texel 对齐的正交 Reverse-Z 覆盖体；`spot(source,near,resolution)` 从聚光灯的位置、发射方向、影响半径和外锥余弦生成透视投影。
`point(source,near,resolution)` 从点光源生成世界轴对齐的六个 90° 透视投影，顺序为 +X、−X、+Y、−Y、+Z、−Z。`face_count()` 为普通单面 1、级联 2–4 或点光六面 6，`view_projection(face)` 显式验证索引。六面/90° 覆盖的基础概念参见 [立方体映射](https://learn.microsoft.com/en-us/windows/win32/direct3d9/cubic-environment-mapping)。这里使用普通二维图集，并非标准 GPU 已提供立方体纹理。

聚光灯和点光源的 near 至少 0.0001，远近间距至少为 near 的 0.000001 倍，远平面取光源影响半径；实际照明仍受球形范围和聚光灯圆形锥体限制。聚光灯外锥余弦至少 0.001，极宽锥明确拒绝。点光源六个近裁面在源点周围形成小立方体空区；位于近裁面内或投影体外的接收点按不遮挡处理，应用应选择合适 near。

方向光/聚光灯分辨率为 128...1024、点光源每面为 128...512，均为 2 次幂。图创建后分辨率与面数不变，同面数的描述可刷新。`with_bias(constant,slope)` 设置非负归一化深度偏置（各不超过 0.05）：方向光默认 0.0003 / 0.001，聚光灯/点光源为 0.00002 / 0.00005。透视深度精度与偏置效果随 near/far、距离变化，过大偏置会使阴影脱离表面。[偏置与投影范围参考](https://learn.microsoft.com/en-us/windows/win32/dxtecharts/common-techniques-to-improve-shadow-depth-maps)

每次绘制最多对一个光源使用阴影，索引是环境中的原始源序号；每网格筛选后保留同一身份，重复灯不会一起变暗。阴影只衰减该源的直接光，环境和自发光不变。绑定及实际绘制验证源类型，方向光验证方向，聚光灯验证位置/方向/半径/外锥，点光源验证位置/半径。移动后应生成新描述并刷新；仅改颜色、强度或聚光灯内锥可复用图。

阴影 pass 查询标准 `gpu` 的 R32_FLOAT 可采样颜色目标能力，配合 D32_FLOAT Reverse-Z 深度测试。方向光/聚光灯使用共享 NDC 接收面导数补偿和 3×3 PCF。点光源用现有 `RenderPass.viewport/scissor` 把六面写入 3×2 图集；每个 PCF tap 跨越面边缘时重新投影到正确相邻面，量化到该面的实际 texel 中心，并用射线/接收几何平面交点计算参考深度，避免平滑法线、跨面导数或相邻图集块导致错误遮挡。
点光源的 3×3 帐篷权重随采样位置连续变化，减少等权采样在纹素边界的亮度跳变。MSL/GLSL/HLSL 共用 `shadow.inc`，最近邻/显式 LOD 0 采样，不依赖 comparison sampler、立方体纹理或新的原生桥接。

收集可见、未排队删除的绑定，不按主相机视锥剔除遮挡物。当前全部不透明三角形执行双面投射，无独立投射/接收开关、alpha cutout 或透明阴影。CPU 蒙皮后更新阴影，不是 GPU 蒙皮。所有网格、所有面和矩阵在录制前完整预检，空列表也验证投影能否编码到 GPU；主帧期间禁止刷新。点光源一次提交六面，成功后才整体公布新图，失败保留旧六面。

每张逻辑图持有四张物理纹理（两组颜色/深度）：方向光/聚光灯 1024² 共 16 MiB；点光源每面 512 时图集为 1536×1024，共 24 MiB。全部计入共享 512 张 / 64 MiB 用户纹理预算，不计驱动在途分配。`render` 返回各投影累计提交三角形数，不是可见数或 GPU 性能；目前逐投影提交全部遮挡网格，由 GPU 裁剪，尚无逐投影 CPU 筛选或自动更新调度。
`binding` 是短期弱引用，刷新后重新获取，不能跨多次更新缓存；场景入口自动获取，关闭所有者后拒绝使用。

```sh
make shadow-core-test shadow-gpu-test gpu-failure-test
./build/model-formats --model build/detail-models/head-prepared.glb --view pbr --studio true --distance 3.5 --fov 40 --yaw 0.4 --pitch 0 --render-scale 2 --ground true --shadow-light point --shadows true --frames 1 --capture build/point-shadows/head-on.png
```

`--shadow-light directional|spot|point` 选择主灯类型，`--shadows true|false` 独立开关阴影以保持同灯光对照。地面固定在初始包围盒底部，直立接触使用 `--pitch 0`。
纯策略以 `--no-opt` / `--release` 隔离运行；Metal 覆盖三类光、关闭/跨设备、源身份、帧恢复、预算和故障保留。点光源用 26 个真实遮挡盒覆盖六面、12 条边和 8 个角；独立 Python 相机射线/房间平面/AABB 参考逐项核对 28,672 个像素、3,672 次跨面采样和移动源，最大误差 1 个码值，没有跳过纹素边界样本。轻微相机抖动两帧最大差 1 个码值；跨面斜面自投影与无阴影 PNG 完全一致。
扫描人头已完成开关对照；人物和猫的 walk 各运行 120 帧，树模型也通过点光源阴影。树仍使用有记录的 scene-root 修正版，原始错误文件不静默修复。三类投影的提交/深度分配故障均保留旧 PNG 并恢复。

### 方向光级联（CSM）

`shadow.cascade_camera(view,projection)` 接受仿射世界到相机矩阵与居中的有限 Reverse-Z 投影，支持透视和正交镜头。`integration/rendering/three_d.cascade_scene_camera` 从 Node3D 当前镜头及父级世界变换取得两种投影。显式透视相机可继续使用 `cascade_camera` 或 `cascade_node_camera`。偏轴和抖动投影仍待支持。

```xu
shadow_camera := scene_render.cascade_scene_camera(&tree, camera_node, aspect) or >>
$settings := shadow.default_cascades()
settings.count=4
settings.distance=50.0
description := shadow.cascaded(directional_light,shadow_camera,settings) or >>
$shadow_map := device.shadow_map(description,&program) or >>
// 相机、镜头或光源方向变化后，重新构造 description 并在主帧外 render。
```

| CascadeSettings3D | 默认 | 范围与单位 |
| --- | --- | --- |
| count | 4 | 2、3、4；创建图后不改变 |
| resolution | 512 | 每级 128...1024 的 2 次幂；创建图后不改变 |
| distance | 100 | 相机空间阴影距离，截取到相机 far，必须大于 near |
| split_lambda | 0.6 | 0...1，控制透视镜头的均匀与对数分段比例；正交镜头始终等距分段 |
| blend_fraction | 0.1 | 0...0.3，各级尾段的交界混合比例及最后一级淡出比例；0 关闭混合 |
| caster_padding | 20 | 世界单位，沿光轴对拟合球两侧增加的遮挡物深度余量 |
| stabilization_step | 0.0625 | 世界单位，拟合球半径量化步长，按项目尺度选择 |
| raster_bias_texels | 1/256 | 0...0.5，接收面的几何斜率偏置，以每级局部纹素为单位 |

各段用透视视锥或正交盒拟合覆盖球，量化尺寸并将光平面中心对齐到纹素网格。预留三个纹素覆盖中心取整与过滤范围。下一级提前覆盖前一级混合带。片元按线性相机深度选级，在重叠带以 smoothstep 混合两图，最远端平滑淡出到受光状态。只计算首级投影导数，再按各级尺度换算，避免在空间选择分支中求导。
CSM 默认深度/角度偏置为 0.0003 / 0.001，可通过 `with_bias` 调整；按首级深度换算其它级，使基础深度/法线角度偏置的世界距离一致。几何斜率纹素偏置额外处理栅格精度与平滑作者法线。偏置过大会损失接触细节，可按模型尺度调整。

图集为两列：2 级一行，3/4 级两行。512/级的四纹理双缓冲分别占 8 MiB 或 16 MiB；1024/级、3/4 级占满 64 MiB 共享纹理预算，存在其它用户纹理时会明确拒绝。所有投影和接收端参数均在录制前验证；一次提交后整体发布。缓存的旧图只适用于其拟合相机，场景入口和直接材质绘制都拒绝不同 view-projection，避免相机移动后静默使用旧分段。

`caster_padding` 不会自动扫描整个世界来拟合遮挡物；超出深度余量的远处遮挡物可能被裁掉。仍逐级提交当前遮挡列表，由 GPU 裁剪。相机/灯光变化时由应用显式重拟合/更新，没有更新调度器或多灯共享分配器。[CSM 分段、稳定性与交界混合参考](https://learn.microsoft.com/en-us/windows/win32/dxtecharts/cascaded-shadow-maps)

```sh
./build/model-formats --model build/detail-models/head-prepared.glb --view pbr --studio true --pitch 0 --ground true --render-scale 2 --shadows true --cascades 4 --shadow-distance 15 --camera-motion true --frames 120 --capture build/cascaded-shadows/head-on.png
make scene-camera-gpu-test
./build/scene-camera-gpu/scene-file --camera Ortho --frames 1 --capture build/scene-camera-gpu/ortho-preview.png
```

模型预览的 `--cascades 0|2|3|4`（默认 0）只允许方向光。`--shadow-distance` 为 0.1...100，默认 15。`--camera-motion true` 绕目标移动相机并逐帧重拟合。场景示例从文件读取镜头和 CSM 参数，`--cascades` 可临时覆盖预览的级数，0 关闭预览阴影。保存时保留场景里的配置。

纯 CPU 隔离检查覆盖旋转和缩放后的相机、全部重叠角点与纹素稳定。独立参考以相机射线、斜面交点、解析包围球、遮挡矩形和帐篷 PCF 核对 110,592 个像素，其中正交画面 49,152 个。全部样本包含 10,944 个混合带像素和 2,784 个远端淡出像素，最大误差为 1 个 8 位码值。测试几何先验证边界远离硬件覆盖的亚像素平局，随后核对所有输出像素。
Metal 另覆盖斜面自阴影、错误相机与不可编码参数保留旧图、父级相机适配、64 MiB 预算恢复及级联分配/提交故障；扫描人头开关对照、人物/猫/树分别用 4/2/3 级完成移动相机运行。

当前仍缺多灯共享图集/分配器、自动更新调度、透明阴影、点光及聚光阴影配置持久化与 IBL。真实 GPU 证据仅 macOS arm64 Metal，GLSL/HLSL 已同步，Vulkan/D3D12 尚未编译或真机执行。未发布接口统一为 `ShadowDescription3D` / `ShadowMap3D`，无历史门面；六面投影、图集和过滤策略属于 nexus，通用设备/纹理/viewport/scissor/采样/提交复用 Xu 0.12.6 标准库。

## 光源场景保存与恢复

`xu.scene` 版本 1 至 4 均要求 `lights` 数组，无光源时使用 `[]`。
每项 `node` 为文件中的 Node3D 索引，同一节点只能有一个源；参数均为节点局部空间，世界坐标在每次收集时计算。

| type | 其余必需字段 |
| --- | --- |
| `directional` | `node`、`radiance: [r,g,b]`、`direction: [x,y,z]`（表面指向光源） |
| `point` | `node`、`radiance`、`position: [x,y,z]`、`radius` |
| `spot` | `node`、`radiance`、`position`、`radius`、`direction`（光源射向锥体）、`inner_cosine`、`outer_cosine` |

版本 4 的方向光可带 `cascades`，包含前节列出的 `CascadeSettings3D` 八个字段。[场景文件示例](examples/scene_file/assets/world.xuscene)

`shadow.cascade_profile(settings)` 校验配置，光源绑定在捕获时保存该配置。隐藏光源的配置也会被保存。`SceneLights3D.gather_with_cascades` 返回按场景先序排列的可见候选光源，并把第一个带配置的可见方向光的配置及候选索引写入 `CascadeSelection3D`。渲染端按当前镜头拟合并生成阴影图。配置字段和数字范围在读文件时校验，相机裁剪面和 GPU 预算在渲染时校验。

文件存聚光锥的 cosine 值，避免反复 acos/cos 转换；`spot(...)` 继续接收弧度半角，`spot_cosines(...)` 接收上述数值并执行相同校验。位置、强度、半径和 cosine 使用最短可往返 f64 十进制；方向在解码时归一化。未知/缺失/重复字段、非法类型、节点重复、非有限值、零方向和过窄锥域均报错。
每个文件最多 256 个光源，包含隐藏节点上的源；运行时环境最多 256 个可见候选源，每个网格筛选后最多 16 源。文件保存不受当前隐藏状态影响，候选或单网格筛选结果超额时明确报错。

```xu
light_files #"github.com/xulang-org/nexus/integration/scene_lighting"
files #"github.com/xulang-org/nexus/integration/scene"

// 显式捕获节点和当前局部光源，不推断其它服务附件。
document := light_files.capture_nodes(&world, &tree, light_root) or >>
files.save("lights.xuscene", &document) or >>

restored := files.load("lights.xuscene") or >>
parent := target.root()
root := light_files.instantiate(&restored, $&target_lights, $&target, parent, "Lights") or >>
```

`instantiate` 在目标树变更前检查光源容量，并复用 PackedScene 的名称/节点容量预检；`bind(document, world, tree, root)` 用于已建立的混合服务场景，按完整拓扑匹配后整批预检。任何预期绑定错误均不发布部分替换；文件未声明的既有绑定保持不变，移除时显式 `detach`。
普通节点实例化和各服务的完整加载入口会拒绝无法恢复的附件。混合场景显式组合 `to_packed_nodes` 或音频树、`prepare_surfaces`、`prepare_scripts` 和光源 `bind`；没有跨服务的隐式初始化。

`capture(document, world, tree, root)` 在拓扑匹配时捕获当前节点/可见性、光源增删和局部参数，同时保留其它附件与来源信息。其它服务的 `capture/save` 保留声明的光源参数；若运行时改过光源，最后用光源 `capture` 合并，再调用 `files.save_rebased`。脚本更新后以 `scripts.capture` 的已接受版本作为输入，避免覆盖新的字节码哈希。保存不包含动画播放相位或 VM 执行状态。

```sh
./build/lighting --mode spot --frames 120 --capture build/saved-lights.png --save-scene build/lights.xuscene
./build/lighting --scene build/lights.xuscene --frames 1 --capture build/restored-lights.png
make scene-lighting-test scene-lighting-services-test lighting-demo-test
```

灯光示例默认从 `examples/lighting/assets/lights.xuscene` 读取四个源；自定义文件沿用示例中的命名节点。`--scene` 加载后保持保存的姿态/可见性，Space 可恢复运动，显式 `--mode` 可覆盖类型开关。
自动验收在独立进程保存和加载，验证恢复前后的 Metal PNG 一致。仅修改存档里的阴影距离时，阴影画面随之改变。纯 CPU 验收在无原生归档、SDL、GPU、音频和脚本服务的隔离目录以 `--no-opt` / `--release` 运行。组合验收覆盖同一场景的 PBR 绘制、PCM、脚本信号，以及保存光源编辑和已接受脚本版本时保留其它附件。

## 每网格光源剔除与计数

`resources/lighting.Environment3D` 和 `SceneLights3D.gather` 接受最多 256 个候选源。所有材质绘制入口自动按当前网格的世界包围盒筛选，Shader 仍接收最多 16 源的 1056 字节环境块。方向光始终保留；点光检查球形影响范围与 AABB；聚光另用外锥的保守支撑平面和 AABB 包围球排除无交集的源。边界、不确定的浮点情形保留，筛选后超过 16 个可能影响源时报错，不按强度或距离截取。

`MeshData3D.bounds()` 返回包含全部 CPU 顶点（含未索引顶点）的闭 AABB。上传的 `Mesh3D` / `MeshRef3D.local_bounds()` 对应实际 binary32 顶点；`world_bounds(world)` 对应 Shader 使用的 binary32 模型系数，包含乘加/插值余量，避免反射、剪切、非均匀缩放和浮点消减造成漏光。包围盒适用于当前静态或刚性变换网格；未来顶点变形须同步更新边界。
大坐标、较大包围盒或锥体边界会保留更多候选，可能触发预算限制。这里没有按摄像机视锥、表面朝向或遮挡推断光源不可见。

```xu
// 纯 CPU 查询：不依赖 Mesh3D、SceneTree、GPU 或窗口。
selected := environment.for_bounds(world_box) or >>
assert(selected.source_count() <= lights.MAX_LIGHTS)

// 绘制后读取当前/最后一帧的 CPU 录制计数。
stats := device.lighting_stats() or >>
println("candidates=" + str(stats.candidates) + " selected=" + str(stats.selected))
```

`LightingStats3D.draws/candidates/selected/culled` 累计成功录制的材质绘制及其候选、选中、排除数量。成功 `begin` 清零；失败的绘制不增加计数；无材质绘制不计入。环境 uniform 每次绘制仍固定为 1056 字节，空槽补零；减少的是有效光源记录及 Shader 光源循环次数。计数不是传输字节数、实际片元数量、GPU 时间或性能提升比例。

```sh
./build/lighting --extra-lights 252 --frames 120 --capture build/lighting-many.png --save-scene build/lighting-many.xuscene
./build/lighting --scene build/lighting-many.xuscene --frames 1
make light-culling-core-test light-culling-gpu-test lighting-demo-test
```

示例在原四灯外加入最多 252 个远处点光，结束时输出最后一帧的提交计数；额外光源也进入场景保存。自动检查以同一帧对照原四灯 PNG，像素完全一致，18 次材质绘制的 4,608 个候选筛选后最多保留 72 条可能影响光源的记录。另验证全场景 17 个灯向两个网格分别分配 9/8 源、超额失败恢复、关闭资源验证、浮点边界，以及 512 个由独立 Python 点在锥内判据生成的必留包围盒。纯 CPU 检查在 `--no-opt` / `--release` 隔离运行。
当前算法逐网格扫描候选，CPU 工作量为 O(材质绘制数 × 候选数)；尚无空间索引、clustered/tiled light list 或整体帧时间基准。

## 场景网格视锥剔除

`Scene3D.draw` 与 `draw_lit` 在 GPU 提交前，用已上传顶点的局部包围盒检查 Shader 实际收到的 binary32 MVP。先计算 `view_projection * world`，再量化该乘积；不以分别量化后的矩阵乘积代替。直接调用 `Device3D.draw` / `draw_material` 仍显式提交，可用于自定义可见性策略和 GPU 对照。

裁剪体为 `-w <= x,y <= w`、`0 <= z <= w`，对应 Metal/Vulkan/D3D12 的深度范围；引擎相机继续使用 reverse-Z。逐个检查六个平面的包围盒最大支撑值，只有整个包围盒明确位于任一平面外才剔除。计算不做透视除法或平面归一化，支持近远面、相机背后、跨越 w=0 及包含相机的包围盒。
触碰边界、乘加消减、binary32 舍入或计算溢出引起的不确定情况会保留。基础数学 `Aabb3.intersects_clip(matrix, relative_error, absolute_error)` 可独立于场景/设备使用；渲染层负责选择浮点容差与 GPU 量化策略。

```xu
device.begin(background) or >>
report := scene.draw_lit($&device, &tree, view_projection, &environment) or >>
println("submitted=" + str(report.instances) + " culled=" + str(report.culled_instances))
device.present() or >>
```

离屏网格仍校验弱资源、材质贴图及原有变换/标量约束；关闭/跨设备资源、奇异法线变换或超出 ±1e9 的 GPU 标量不会被剔除隐藏。全场景无提交时仍要求有效且未 readback 封闭的活动帧。隐藏/排队删除节点沿用原有跳过规则。
视锥排除发生在逐网格光源筛选之前，离屏网格不消耗绘制预算、材质/光源提交计数或单网格 16 灯预算。整个环境的 256 候选预算与数据校验仍执行。

```sh
./build/lighting --extra-lights 252 --distant-meshes 128 --frames 120 --capture build/lighting-distant.png
make frustum-core-test frustum-gpu-test lighting-demo-test
```

灯光示例结束时输出最后一帧的已提交/剔除网格数。默认相机下，新增的 128 个远处共享网格全部被排除，保留 18 次材质提交；PNG 与无额外网格版本逐字节一致。独立 Metal 验收还验证单个可见网格加 128 个离屏绑定时提交从 129 次降为 1 次，无材质/材质两条路径均与原始直接绘制得到完全一致的 PNG。
检查覆盖六个面、near/far reverse-Z、接触边界、反射/剪切/旋转后的部分相交、MVP 量化边界、错误恢复，以及无场景/资源/GPU 源码的 `--no-opt` / `--release` 数学隔离与 512 个独立 Python 可见点样本。
这是逐网格的保守裁剪检查，尚无层次 BVH、遮挡/Hi-Z 或 GPU 间接绘制；计数不代表实际着色片元或帧率提升。

## 距离 LOD 与滞回

`resources/lod.distance_lod(thresholds, hysteresis)` 定义 1～8 级策略：阈值数量为级别数减一，必须严格递增、有限且在 `(0, 1e9]` 世界单位内；滞回比例为 `[0, 0.5)`。级别 0 为最高精度。
首次选择按名义阈值决定级别，恰好位于阈值时选择较粗一级。后续远离至 `threshold*(1+h)` 才变粗，靠近至严格小于 `threshold*(1-h)` 才变细。一次相机移动可跨多级；滞回抑制边界抖动，不做几何混合或渐隐。

```xu
lod_data #"github.com/xulang-org/nexus/resources/lod"

policy := lod_data.distance_lod([12.0, 22.0], 0.1) or >>
scene.attach_lods(&tree, node, [high.reference(), medium.reference(), low.reference()], &policy) or >>
// 每次相机/节点变换更新后、绘制前显式选择。
selection := scene.select_lods(&tree, camera_position) or >>
device.begin(background) or >>
report := scene.draw_lit($&device, &tree, view_projection, &environment) or >>
device.present() or >>
```

距离为相机位置到 Node3D 世界原点的欧氏距离，包含祖先平移；网格尺寸或节点缩放不会自动改变阈值。策略不解析投影矩阵，也不使用光照眼点隐式切换。多相机若需独立滞回历史，使用独立 Scene3D 绑定集合，GPU 网格所有者可共享。

`attach_lods` 接收弱引用，所有级别继续由调用方持有 Mesh3D；级别数须匹配策略，三角形数只能不变或减少。各级使用同一节点局部坐标系和材质，调用方负责几何质量和对齐。安装、材质替换先校验每一级的设备、生命期及必需属性；低级缺 UV/切线时不会静默丢掉贴图。任一级已关闭，后续选择和绘制会报错。

多级组首次安装后 `lod_level(node)` 为 -1，需先调用 `select_lods`；单级组预选 0，普通网格也返回 0。`select_lods` 预检全部节点可见的 LOD 组后整批发布，后面节点失败时前面的选择不变。隐藏/待删除组不参与选择，保持既有状态直到恢复或 prune。
`LodSelection3D.nodes/changed/levels` 统计本次选择的节点、级别变化及固定 8 项级别分布；此时尚未视锥剔除。实际绘制使用所选级别自己的包围盒进行视锥和光源筛选。

`SceneDraw3D.lod_instances` 为实际提交且级别大于 0 的实例数；`lod_triangles_saved` 为这些提交相对各自级别 0 少的三角形数。被视锥剔除的对象不重复计入节省量，`culled_triangles` 使用所选级别数量。普通网格/完整表面替换会清除 LOD 组；detach/prune 不关闭 GPU 所有者，节点代次沿用已有隔离规则。

```sh
make demo-lod
./build/lod --mode lod --distance 6 --frames 120 --capture build/lod-near.png
./build/lod --mode lod --distance 18 --frames 120 --capture build/lod-middle.png
./build/lod --mode lod --distance 36 --frames 120 --capture build/lod-far.png
./build/lod --mode high --distance 36 --frames 120 --capture build/lod-fixed-high.png
make lod-core-test lod-gpu-test lod-demo-test
```

示例 Up/Down 移动相机，Esc 退出，`--shaders DIR` / `--backend auto|metal|vulkan|d3d12` 指定产物和后端。15 个实例共享三份球体网格：每份 2208/224/48 三角形；近/中/远实际提交 33,120/3,360/720 个，固定高精度对照为 33,120 个，绘制次数仍为 15。退出时输出级别分布与实际提交/节省数量，未据此推断帧率收益。

纯策略在无向量/场景/GPU 源码的临时目录以 `--no-opt` / `--release` 通过，包含一万次边界抖动与多级跳转；Metal 验证 4/2/1 三角形真实网格切换，与直接绘制相应网格的整张 PNG 一致，并检查全级材质/资源验证、批量回滚、独立节点、重绑、代次复用和所有权。
当前为运行时显式距离 LOD；屏幕误差/自动简化、级间渐变及场景/GLB 中的 LOD 链声明仍待实现。现有场景保存保留原始表面来源，不从 GPU 弱引用推断 LOD 附件，恢复后由调用方重新绑定。

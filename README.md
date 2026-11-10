# Xu Game

独立的 Xu 2D 游戏引擎库，模块为 `github.com/xulang-org/game`，当前版本 `0.1.0`。
场景树、可复用场景、变换、输入、时钟、碰撞、画布和精灵逻辑使用 Xu。
GPU 平台接入是一个 C ABI 薄桥接，调用 SDL 3.4+ 的 GPU 渲染器。

参考 Godot 的 [Node / SceneTree](https://docs.godotengine.org/en/stable/tutorials/scripting/scene_tree.html)
和 [Resource](https://docs.godotengine.org/en/stable/tutorials/scripting/resources.html) 分工。
Xu 侧使用组合与显式生命周期通知，不依赖类继承。它是可以运行的首版 2D 库，
尚未包含编辑器、3D、音频、刚体求解器、用户着色器或 GPU 计算接口。

## GPU 后端

必须成功创建 `SDL_GPUDevice` 和 `SDL_CreateGPURenderer` 才能打开窗口。
没有软件渲染回退。默认自动选择，也可明确指定后端；指定不可用后端时抛错。

| 后端 | 预期系统 | 当前验收 |
| --- | --- | --- |
| Metal | macOS | macOS arm64，Xu 0.11.4 / SDL 3.4.14，真实绘制与回读通过 |
| Vulkan | Linux、支持 Vulkan 的 Windows | SDL GPU 路径已接入；尚未在对应系统运行验收 |
| D3D12 | Windows | SDL GPU 路径已接入；尚未在对应系统运行验收 |

后端来自 [SDL GPU](https://wiki.libsdl.org/SDL3/CategoryGPU)。设备选择方式见
[SDL_CreateGPUDevice](https://wiki.libsdl.org/SDL3/SDL_CreateGPUDevice)。
当前渲染功能包括彩色三角形、带仿射变换的四边形、RGBA GPU 纹理、纹理图集区域、
最近邻/线性采样、透明混合、有序批次提交、垂直同步和显式像素回读 / PNG 截图。
顶点变换在 Xu 侧完成；光栅化、纹理采样和混合在 GPU 执行。

## 运行

需要 Xu 产品 SDK 0.11.4、Clang、Python 3，以及 SDL 3.4+ 开发头文件和运行库。
默认通过 `pkg-config sdl3` 查找头文件；Windows 可显式传入包含 `SDL3/SDL.h` 的目录。
桥接在运行时加载 SDL，不把 SDL 源码或二进制复制进本库。

```sh
# macOS 依赖示例
brew install sdl3 pkg-config

make check
make demo
```

示例：WASD / 方向键移动，Space 暂停，Esc 退出。避开墙体收集六颗金色宝石。
右上角方块显示进度。它使用场景实例、固定 60 Hz 更新、连续碰撞、GPU 画布与纹理精灵。

```sh
# 编译两个示例，运行无窗口模拟和有界 GPU 示例，保存实际 GPU 输出
make smoke

# 指定后端；不可用时明确失败
./build/arena --backend metal
./build/arena --backend vulkan
./build/arena --backend d3d12

# 自动输入仅用于有界示例，可重复运行
./build/arena --frames 120 --autoplay --capture build/arena.png
```

可通过 `XU=/path/to/xu make demo` 选择其他产品编译器；本版实际验收 SDK 为 0.11.4。
新拉取的编译器 `dev` 源码尚未重建，不能当作本库的已验收二进制。
SDL 动态库不在标准位置时，设置 `XU_GAME_SDL_LIBRARY` 为完整路径。

## 接入一个 Xu 项目

在本库根目录先运行 `make native`。消费项目的 `xu.xun`：

```xun
module: example/my_game
version: !ver 0.1.0
xu: !ver 0.11.4
require:
  "github.com/xulang-org/game": file:../game
```

```xu
@main

game #"github.com/xulang-org/game"
gpu #"github.com/xulang-org/game/gpu"

fn run() int {
    $tree := game.new_scene_tree("World", 1024) or >>
    player := tree.add_child(tree.root(), "Player") or >>
    tree.set_position(player, game.vec2(64.0, 64.0)) or >>

    $renderer := gpu.open("My Game", 800, 600, gpu.AUTO) or >>
    $batch := gpu.new_batch()
    color := gpu.rgba(96, 230, 192, 255) or >>
    transform := tree.global_transform(player) or >>
    batch.quad(game.rect2(0.0, 0.0, 32.0, 32.0), transform, color) or >>
    renderer.begin(gpu.rgba(14, 20, 32, 255) or >>) or >>
    renderer.submit(&batch) or >>
    renderer.present() or >>
    renderer.close() or >>
    << 0
}
fn main() int { << run() or (err) { eprintln(err.msg())
    << 1 } }
```

这是单帧接口示意；实际游戏主循环、退出路径、输入和多帧运行见
[`examples/arena/main.xu`](examples/arena/main.xu)。可用
[`examples/headless/main.xu`](examples/headless/main.xu) 单独运行模拟。

## 核心契约

| 概念 | 本库接口与约定 |
| --- | --- |
| 场景树 | `SceneTree` 独占节点存储；节点 ID 仅对原树有效，释放复用后旧 ID 失效 |
| 节点路径 | `find_node` 支持相对路径、绝对路径、`.`、`..`；同级节点名称唯一 |
| 变换 | `Transform2D` 为二维仿射矩阵；角度为弧度，坐标 +Y 向下 |
| 生命周期 | `take_ready()` 返回一次性的子节点先于父节点通知；由应用分派 Xu 行为 |
| 更新 | `process_order()` 按场景先序给出可更新节点，遵循继承与暂停模式 |
| 删除 | `queue_free` 标记整个子树，立即停用；帧末 `flush_free` 释放并返回子先父后的旧 ID |
| 场景资源 | `pack_scene` / `PackedScene.instantiate` 复制节点数据；实例互不共享可变节点状态 |
| 输入 | 一个动作可绑定多键；自动重复不制造新按下边沿；失焦调用 `release_all` |
| 时钟 | `Clock.advance` 返回固定步数、插值权重及丢弃时间；限制补帧，避免无限追赶 |
| 碰撞 | 静态轴对齐矩形的连续扫掠与滑动；初始穿透明确报错，不提供刚体求解 |
| 纹理 | `Texture2D` 是独占 GPU 资源，RGBA8 输入同步复制；renderer 关闭会释放其纹理 |

核心对象由调用方在同一线程更新。GPU 对象的创建、事件、绘制、关闭和析构必须在应用主线程。
当前事件轮询仅支持一个活动窗口。`InputMap.begin_frame()` 在事件处理前调用；
边沿以渲染帧为单位，跨多个物理步的一次性动作须由游戏消费一次。

`PackedScene` 是内存资源，只复制节点属性；不序列化脚本、GPU 资源或画布附件。
`Canvas2D` 按场景先序录制颜色节点；纹理精灵用 `Sprite2D.record` 录入共享纹理批次。
批次按提交顺序绘制，跨纹理的透明对象需要调用者按需要拆分批次。
回读和截图须在 `submit` 之后、`present` 之前调用，会使 GPU 与 CPU 同步。

容量：每树最多 65,536 节点，单个场景资源最多 4,096 节点；最多 128 个动作 / 512 个键；
每帧最多 393,216 顶点。纹理单边最多 4,096、单纹理最多 4,194,304 像素，
每 renderer 的 RGBA 纹理总预算 64 MiB；原生桥接最多 1,024 个活动纹理。

## 本机验收

按 Xu 项目约定，`tests/` 与生成物保留本机且被 Git 忽略。
本机可运行 `make test`（变换、节点、场景实例、输入、时钟、连续碰撞）和
`make gpu-smoke`（GPU 绘制、纹理采样、像素回读、生命周期）。
这些目标需要本机测试目录；源码消费者可以运行上面的 `make check` / `make smoke`。
使用普通 Xu 程序执行回归，因为 Xu 0.11.4 的 `xu test` 尚不支持原生模块链接。

Linux / Windows 尚未完成构建、窗口输入与真实 GPU 运行验证；本版不声明这两个系统验收通过。

License: MIT。

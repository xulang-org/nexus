# 原创场景与表面资源

`panels.glb` 复用本项目 `glb_materials` 示例的原创八面板模型和五张 PNG。
`world.xuscene` 使用格式版本 1，包含十个节点、一个 GLB 来源和八个表面。资源路径相对场景文件解析，SHA-256 固定来源版本。示例恢复网格、材质贴图和相机节点的位姿，并使用默认透视镜头。

在仓库根目录运行 `make scene-lod-gpu-test` 可生成并验收版本 6 的 LOD 场景。近景和远景示例在 `build/scene-asset-fixtures/`，保存前后的截图在 `build/scene-lod-preview-results/`。[LOD 声明与复现步骤](../../../README.md#在场景中声明距离-lod)

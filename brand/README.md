# Nexus Engine 品牌视觉资产 (Brand Assets)

Nexus Engine 采用 **Topological Node N-Mark（极简拓扑节点 N 标）** 作为核心主图腾，结合**独立冷调引擎光谱**，与 XU 语言主品牌（朱砂金石红 `#FF385C` / `#E11D48`）形成冷暖双星协同。

## 色彩规范 (Color Tokens)

| 通道 | 暗黑发光 / App Icon | 明亮纸感 / 高对比 | 用途 |
| :--- | :--- | :--- | :--- |
| **Cyan 起点** | `#38BDF8` | `#0284C7` | 左上部拓扑通路与起点光效 |
| **Indigo 桥接** | `#6366F1` | `#4F46E5` | 中央枢纽圆环与过渡笔划 |
| **Violet 终点** | `#A855F7` | `#7E22CE` | 右下部折返与 `NEXUS` 渐变后缀 |
| **曜石黑底** | `#0B0A0F` | — | App Icon 底座、暗色页面与 OG 分享图 |
| **宣纸白底** | — | `#FAF9F6` | 文档、浅色 GitHub 视图与印刷物料 |
| **字标文字** | `#F8FAFC` / `#94A3B8` | `#111827` / `#4B5563` | `NEXUS` 主文字与副标题 |

## 资产索引 (Asset Inventory)

| 资产文件 | 规格 / 用途 |
| :--- | :--- |
| [`nexus_app_icon.svg`](nexus_app_icon.svg) / [`nexus_app_icon.png`](nexus_app_icon.png) (`1024×1024`) / [`nexus_app_icon_512.png`](nexus_app_icon_512.png) (`512×512`) | Apple 超椭圆曜石底座应用图标 |
| [`nexus_favicon.svg`](nexus_favicon.svg) / [`nexus_favicon.png`](nexus_favicon.png) (`64×64`) | 小尺寸锐利描边浏览器与 CLI 图标 |
| [`nexus_mark.svg`](nexus_mark.svg) / [`nexus_mark_light.svg`](nexus_mark_light.svg) | 透明底主图腾（深色背景 / 浅色背景） |
| [`nexus_mark_monochrome_white.svg`](nexus_mark_monochrome_white.svg) / [`nexus_mark_monochrome_black.svg`](nexus_mark_monochrome_black.svg) | 纯白 / 纯黑单色图腾 |
| [`nexus_lockup_horizontal_dark.svg`](nexus_lockup_horizontal_dark.svg) / [`nexus_lockup_horizontal_light.svg`](nexus_lockup_horizontal_light.svg) | `680×180` 横向标准组合 |
| [`nexus_lockup_vertical_dark.svg`](nexus_lockup_vertical_dark.svg) / [`nexus_lockup_vertical_light.svg`](nexus_lockup_vertical_light.svg) | `420×460` 纵向标准组合 |
| [`nexus_wordmark_dark.svg`](nexus_wordmark_dark.svg) / [`nexus_wordmark_light.svg`](nexus_wordmark_light.svg) | `420×110` 独立 `NEXUS` 字标 |
| [`nexus_og_card.svg`](nexus_og_card.svg) / [`nexus_og_card.png`](nexus_og_card.png) (`1280×640`) | GitHub Social Preview / 社交分享头图 |

## 使用约定 (Guidelines)

- **最小尺寸**：常规 UI 图腾不小于 `32px`，小尺寸场景使用简化增粗的 [`nexus_favicon.svg`](nexus_favicon.svg)（可下探至 `16px`）。
- **安全留白**：主图腾四周保留不少于其高度 `0.25×` 的净空区域；禁止拉伸变形或替换官方渐变色阶。
- **桌面工具图标自动嵌入**：`xu build --desktop` 会优先查找工作目录下的 `brand/icon.png`；仓库已同步内置 [cmd/project_editor/brand/icon.png](../cmd/project_editor/brand/icon.png) 与 [cmd/tilemap_editor/brand/icon.png](../cmd/tilemap_editor/brand/icon.png)。

## GitHub README 自适应深浅色嵌入片段

```html
<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="brand/nexus_lockup_horizontal_dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="brand/nexus_lockup_horizontal_light.svg">
    <img alt="Nexus Engine" src="brand/nexus_lockup_horizontal_light.svg" width="420">
  </picture>
</p>
```

`cube.obj` 是本仓库原创的静态立方体，包含六个凸四边形，解析后为十二个三角形，不需要 MTL 或纹理旁文件。

`make demo-models` 使用它启动无光照几何预览。通过 `--model FILE` 可加载当前受限的 GLB、OBJ、ASCII STL 或二进制 STL；GLB 材质预览使用 `make demo-glb-materials`。

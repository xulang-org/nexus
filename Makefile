XU ?= xu
PYTHON ?= python3
export XU

.PHONY: taptap-data-test taptap-test taptap-native-test native-taptap console-data-test console-test console-native-test native-console steam-data-test steam-test steam-native-test native-steam prefab-runtime-test ai-bt-nav-test input-replay-timing-test timeline-test project-bundle-cli-test ui-tree-test profiler-test bundle-test shader-cross-backend-test scene-v9-test scene-soa-test ecs-parallel-test navigation-test networking-test audio-dsp-test script-aot-test script-host-coroutines-test physics3d-joints-ragdoll-test physics3d-advanced-test gpu-skinning-test skeletal-animation-test particles-vfx-gpu-test terrain-foliage-gpu-test decals-atmosphere-gpu-test ddgi-gi-gpu-test engine-integration-gpu-test all-modern-tests clustered-lighting-gpu-test indirect-cull-hiz-gpu-test hdr-postprocess-gpu-test meshlet-visbuffer-gpu-test transparent-pbr-gpu-test streaming-lru-gpu-test xacp-test lighting-demo-test demo-lighting lighting-core-test lighting-gpu-test gpu-failure-test present-fallback-test text-2d-test ui-hud-test demo-ui-hud mesh-shaders canvas-shaders native-image window-input-smoke gpu-surface-smoke sdk gpu-compute-smoke native-probe gpu-offscreen-smoke gpu-transfer-smoke check-core test-core mesh-core-test audio-core-test audio-device-test native native-audio audio-fixtures audio-test audio-smoke demo-audio demo-audio-stream demo-audio-seek check layers test demo demo2d demo3d demo-glb demo-script demo-materials demo-textures3d demo-mipmaps3d demo-material-maps demo-normal_maps demo-generated-tangents demo-glb-materials smoke gpu-smoke gpu3d-smoke image-fixtures glb-fixtures script-tool script-fixtures script-live-smoke glb-material-fixtures scene-fixtures demo-scene-file scene-asset-fixtures demo-scene-assets scene-audio-fixtures demo-scene-audio demo-scene-av scene-script-assets scene-script-fixtures demo-scene-scripts
xacp-test: sdk
	mkdir -p build
	$(XU) build tests/xacp_checks.xu -o build/xacp-tests
	./build/xacp-tests

native: native-audio native-image native-steam native-console native-taptap

native-image: sdk
	$(PYTHON) native/build.py --xu "$(XU)" --only-image

native-steam: sdk
	$(PYTHON) native/build.py --xu "$(XU)" --only-steam

native-console: sdk
	$(PYTHON) native/build.py --xu "$(XU)" --only-console

native-taptap: sdk
	$(PYTHON) native/build.py --xu "$(XU)" --only-taptap

mesh-shaders: sdk
	$(PYTHON) tools/mesh_shaders.py

canvas-shaders: sdk
	$(PYTHON) tools/canvas_shaders.py

native-audio: sdk
	$(PYTHON) native/build.py --xu "$(XU)" --only-audio

sdk:
	$(PYTHON) tools/check_sdk.py --xu "$(XU)"

native-probe: sdk
	$(PYTHON) tools/probe_native.py --xu "$(XU)"

layers:
	$(PYTHON) tools/check_layers.py

check: layers native canvas-shaders mesh-shaders
	$(XU) check examples/model_formats/main.xu
	$(XU) check examples/lod/main.xu
	$(XU) check examples/lighting/main.xu
	$(XU) check examples/window_input/main.xu
	$(XU) check examples/gpu_surface/main.xu
	$(XU) check examples/gpu_offscreen/main.xu
	$(XU) check examples/gpu_compute/main.xu
	$(XU) check examples/arena/main.xu
	$(XU) check examples/phone_arena
	$(XU) check examples/phone_3d
	$(XU) check examples/miniprogram
	$(XU) check examples/webgl_3d/main.xu
	$(XU) check examples/headless/main.xu
	$(XU) check examples/two_d/main.xu
	$(XU) check examples/three_d/main.xu
	$(XU) check examples/isometric_2d
	$(XU) check examples/hd2d_scene
	$(XU) check examples/physics_3d/main.xu
	$(XU) check examples/character_course/main.xu
	$(XU) check examples/glb_preview/main.xu
	$(XU) check cmd/scriptc/main.xu
	$(XU) check cmd/project_validate/main.xu
	$(XU) check cmd/project_viewport
	$(XU) check cmd/project
	XU_UI_PACK=1 $(XU) check cmd/project_editor
	$(XU) check cmd/tilemap_editor
	$(XU) check tests/project_import_checks.xu
	$(XU) check tests/project_editor_checks.xu
	$(XU) check examples/script_reload/main.xu
	$(XU) check examples/materials/main.xu
	$(XU) check examples/textures3d/main.xu
	$(XU) check examples/mipmaps3d/main.xu
	$(XU) check examples/material_maps/main.xu
	$(XU) check examples/normal_maps/main.xu
	$(XU) check examples/generated_tangents/main.xu
	$(XU) check examples/scene_scripts/main.xu
	$(XU) check examples/modern_sandbox/main.xu
	$(XU) check examples/scene_audio/main.xu
	$(XU) check examples/scene_av/main.xu
	$(XU) check examples/scene_assets/main.xu
	$(XU) check examples/scene_file/main.xu
	$(XU) check examples/glb_materials/main.xu
	$(XU) check examples/audio/main.xu
	$(XU) check examples/audio_stream/main.xu
	$(XU) check examples/ui_hud/main.xu

script-tool: sdk
	mkdir -p build
	$(XU) build cmd/scriptc/main.xu -o build/xu-nexus-script

.PHONY: project-validator
project-validator: native-image
	mkdir -p build
	$(XU) build cmd/project_validate/main.xu -o build/nexus-project-validate

.PHONY: project-cli project-editor project-test project-preview project-gpu-test
project-cli: sdk
	mkdir -p build
	$(XU) build cmd/project -o build/nexus-project

project-editor: sdk
	mkdir -p build
	XU_UI_PACK=1 $(XU) build --desktop --no-webview cmd/project_editor -o build/nexus-project-editor

project-test: project-cli project-validator
	$(XU) build tests/project_import_checks.xu -o build/project-import-checks
	./build/project-import-checks --validator build/nexus-project-validate --project-cli build/nexus-project

project-preview: mesh-shaders native-image
	$(XU) build examples/scene_assets/main.xu -o build/nexus-project-preview

.PHONY: project-viewport
project-viewport: mesh-shaders canvas-shaders native-image
	$(XU) build cmd/project_viewport -o build/nexus-project-viewport

project-gpu-test: project-cli project-validator project-preview
	$(XU) build tests/project_import_checks.xu -o build/project-import-checks
	./build/project-import-checks --validator build/nexus-project-validate --project-cli build/nexus-project --preview build/nexus-project-preview

.PHONY: project-picking-test
project-picking-test: mesh-shaders native-image scene-asset-fixtures
	$(XU) build tests/scene_picker_gpu_checks.xu -o build/scene-picker-checks
	./build/scene-picker-checks

.PHONY: demo-project-editor demo-course-editor project-editor-test
demo-project-editor: project-cli project-editor project-validator project-preview project-viewport
	mkdir -p build/project-example/assets
	cp -n examples/scene_assets/project.json build/project-example/
	cp -n examples/scene_assets/assets/world.xuscene examples/scene_assets/assets/panels.glb build/project-example/assets/
	./build/nexus-project-editor build/project-example/project.json --output build/project-gallery

demo-course-editor: project-cli project-editor project-validator character-course project-viewport
	mkdir -p build/course-authoring/assets
	cp -n examples/character_course/project.json build/course-authoring/
	cp -n examples/character_course/assets/course.xuscene examples/character_course/assets/course.glb build/course-authoring/assets/
	./build/nexus-project-editor build/course-authoring/project.json --output build/course-edits --preview build/nexus-character-course

project-editor-test: project-cli project-editor project-validator project-preview character-course project-viewport
	XU_UI_SIM=1 XU_UI_PACK=1 $(XU) test cmd/project_editor/draft.xu cmd/project_editor/draft_components.xu cmd/project_editor/editor.xu cmd/project_editor/editor_components.xu cmd/project_editor/editor_i18n.xu cmd/project_editor/editor_icons.xu cmd/project_editor/editor_inspector.xu cmd/project_editor/editor_modals.xu cmd/project_editor/editor_panels.xu cmd/project_editor/project.xu cmd/project_editor/snap_modal.xu cmd/project_editor/theme.xu cmd/project_editor/top_view.xu cmd/project_editor/ui_checks.xu cmd/project_editor/test.editor.xu
	$(XU) build tests/project_editor_checks.xu -o build/project-editor-checks
	./build/project-editor-checks --editor build/nexus-project-editor --project-cli build/nexus-project --validator build/nexus-project-validate --preview build/nexus-project-preview --viewport build/nexus-project-viewport --course build/nexus-character-course

.PHONY: tilemap-editor demo-tilemap-editor tilemap-editor-test
tilemap-editor: sdk
	mkdir -p build
	$(XU) build --desktop cmd/tilemap_editor -o build/nexus-tilemap-editor

demo-tilemap-editor: tilemap-editor
	mkdir -p build/isometric-edit
	test -f build/isometric-edit/world.xuscene || cp examples/isometric_2d/assets/world.xuscene build/isometric-edit/
	test -f build/isometric-edit/iso_tiles.png || cp examples/isometric_2d/assets/iso_tiles.png build/isometric-edit/
	./build/nexus-tilemap-editor build/isometric-edit/world.xuscene

tilemap-editor-test: tilemap-editor isometric-2d
	./build/nexus-tilemap-editor examples/isometric_2d/assets/world.xuscene --check build/tilemap-editor-check
	cp examples/isometric_2d/assets/iso_tiles.png build/tilemap-editor-check/
	./build/isometric-2d --scene build/tilemap-editor-check/edited.xuscene --frames 10 --autoplay --capture build/tilemap-editor-check/runtime.png

.PHONY: isometric-campaign-test
isometric-campaign-test: tilemap-editor isometric-2d project-validator
	$(PYTHON) tests/isometric_campaign_checks.py

.PHONY: character-course demo-character-course character-course-test
character-course: mesh-shaders native-image
	$(XU) build examples/character_course/main.xu -o build/nexus-character-course

demo-character-course: character-course
	./build/nexus-character-course

character-course-test: character-course
	./build/nexus-character-course --frames 240 --autoplay --capture build/character-course.png

.PHONY: character-course-project benchmark-course benchmark-webgl
character-course-project: project-cli project-validator
	./build/nexus-project build examples/character_course/project.json --output build/character-course-project --validator build/nexus-project-validate

benchmark-course: character-course character-course-project
	$(PYTHON) tools/benchmark_course.py --project-build build/character-course-project --output build/nexus-benchmark

benchmark-webgl: miniprogram-3d douyin-3d
	node tools/benchmark_webgl.cjs

script-fixtures: script-tool
	$(PYTHON) tests/make_script_fixtures.py

image-fixtures:
	$(PYTHON) tests/make_png_fixtures.py

glb-fixtures:
	$(PYTHON) tests/make_glb_fixtures.py

glb-material-fixtures:
	$(PYTHON) tests/make_glb_material_fixtures.py

scene-asset-fixtures: glb-material-fixtures
	$(PYTHON) tests/make_scene_asset_fixtures.py

scene-audio-fixtures:
	$(PYTHON) tests/make_scene_audio_fixtures.py

scene-script-assets: script-tool
	$(PYTHON) tools/build_script_scene.py --project examples/scene_scripts/project.json --output build/scene-scripts/world.xuscene

scene-script-fixtures: scene-script-assets
	$(PYTHON) tests/make_scene_script_fixtures.py

scene-fixtures:
	$(PYTHON) tests/make_scene_fixtures.py

check-core: layers sdk
	$(XU) check examples/headless/main.xu
	$(XU) check cmd/scriptc/main.xu

# Pure Xu validation stays usable while a compiler/platform backend is incomplete.
# The aggregate check/test/gpu targets still fail on real device build failures.
test-core: taptap-data-test console-data-test steam-data-test prefab-runtime-test ai-bt-nav-test input-replay-timing-test timeline-test project-bundle-cli-test ui-tree-test profiler-test bundle-test shader-cross-backend-test scene-v9-test scene-soa-test ecs-parallel-test navigation-test audio-dsp-test script-aot-test 25d-core-test shadow-core-test gltf-animation-test mesh-format-core-test lod-core-test frustum-core-test physics3d-test scene-lighting-test lighting-core-test check-core mesh-core-test glb-fixtures glb-material-fixtures script-fixtures audio-core-test scene-fixtures scene-asset-fixtures scene-audio-fixtures scene-script-fixtures
	mkdir -p build
	$(PYTHON) tests/layer_rules_checks.py
	$(PYTHON) tests/layer_headless_checks.py
	$(PYTHON) tests/canvas_isolation.py
	$(XU) build tests/scene_file_checks.xu -o build/scene-file-tests
	SDL_VIDEODRIVER=nonexistent XU_NEXUS_SDL_LIBRARY=/nonexistent/scene-no-sdl ./build/scene-file-tests
	$(PYTHON) tests/scene_process_checks.py
	$(XU) build tests/scene_resource_checks.xu -o build/scene-resource-tests
	SDL_VIDEODRIVER=nonexistent ./build/scene-resource-tests
	$(XU) build tests/scene_audio_format_checks.xu -o build/scene-audio-format-tests
	SDL_VIDEODRIVER=nonexistent ./build/scene-audio-format-tests
	$(XU) build tests/scene_script_format_checks.xu -o build/scene-script-format-tests
	./build/scene-script-format-tests
	$(XU) build tests/scene_script_checks.xu -o build/scene-script-tests
	XU_NEXUS_SDL_LIBRARY=/nonexistent XU_NEXUS_SDL_AUDIO_LIBRARY=/nonexistent ./build/scene-script-tests
	$(XU) build tests/script_reload_batch_checks.xu -o build/script-reload-batch-tests
	./build/script-reload-batch-tests
	$(PYTHON) tests/scene_script_isolation.py
	$(PYTHON) tests/script_scene_builder_checks.py
	$(XU) build tests/core_checks.xu -o build/core-tests
	./build/core-tests
	$(XU) build tests/xacp_checks.xu -o build/xacp-tests
	./build/xacp-tests
	$(XU) build tests/glb_checks.xu -o build/glb-tests
	./build/glb-tests
	$(XU) build tests/glb_material_checks.xu -o build/glb-material-tests
	SDL_VIDEODRIVER=nonexistent ./build/glb-material-tests
	$(XU) build tests/script_checks.xu -o build/script-tests
	./build/script-tests
	$(XU) build tests/script_signal_checks.xu -o build/script-signal-tests
	./build/script-signal-tests
	$(XU) build tests/script_callbacks_checks.xu -o build/script-callbacks-tests
	./build/script-callbacks-tests
	$(XU) build tests/audio_scene_checks.xu -o build/audio-scene-tests
	./build/audio-scene-tests

test: canvas-memory-test phone-input-test phone-viewport-test phone-pinch-test phone-app-test phone-3d-budget-test phone-frame-test phone-state-test phone-audio-test jpeg-test test-core project-test native audio-device-test image-fixtures
	$(XU) build tests/scene_audio_checks.xu -o build/scene-audio-tests
	XU_NEXUS_SDL_LIBRARY=/nonexistent XU_NEXUS_SDL_AUDIO_LIBRARY=/nonexistent ./build/scene-audio-tests
	$(XU) build tests/scene_audio_output_checks.xu -o build/scene-audio-output-tests
	SDL_AUDIO_DRIVER=dummy ./build/scene-audio-output-tests
	$(PYTHON) tests/scene_audio_isolation.py
	$(XU) build tests/image_checks.xu -o build/image-tests
	SDL_VIDEODRIVER=nonexistent ./build/image-tests
	$(XU) build tests/three_d_checks.xu -o build/three-d-tests
	./build/three-d-tests
	$(XU) build tests/scene3d_checks.xu -o build/scene3d-tests
	./build/scene3d-tests

.PHONY: phone-input-test phone-viewport-test phone-pinch-test phone-app-test phone-3d-budget-test
phone-input-test: sdk
	mkdir -p build
	$(XU) build tests/phone_input_checks.xu -o build/phone-input-tests
	./build/phone-input-tests

phone-viewport-test: sdk
	mkdir -p build
	$(XU) build tests/phone_viewport_checks.xu -o build/phone-viewport-tests
	./build/phone-viewport-tests

phone-pinch-test: sdk
	mkdir -p build
	$(XU) build tests/phone_pinch_checks.xu -o build/phone-pinch-tests
	./build/phone-pinch-tests

phone-app-test: sdk
	mkdir -p build
	$(XU) build tests/phone_app_checks.xu -o build/phone-app-tests
	SDL_VIDEODRIVER=dummy ./build/phone-app-tests

phone-3d-budget-test: sdk mesh-shaders
	mkdir -p build
	$(XU) build tests/phone_3d_budget_checks.xu -o build/phone-3d-budget-tests
	./build/phone-3d-budget-tests

.PHONY: physics3d-test
physics3d-test: sdk
	mkdir -p build
	$(XU) build tests/physics3d_checks.xu -o build/physics3d-checks
	./build/physics3d-checks
	$(XU) build tests/character3d_checks.xu -o build/character3d-checks
	./build/character3d-checks
	$(XU) build tests/capsule3d_checks.xu -o build/capsule3d-checks
	./build/capsule3d-checks
	$(XU) build tests/rigid3d_checks.xu -o build/rigid3d-checks
	./build/rigid3d-checks
	$(XU) build tests/physics3d_bvh_sap_checks.xu -o build/physics3d-bvh-sap
	./build/physics3d-bvh-sap
	$(XU) build tests/physics3d_xpbd_checks.xu -o build/physics3d-xpbd
	./build/physics3d-xpbd

scene-v9-test: layers sdk
	mkdir -p build
	$(XU) build tests/scene_v9_modern_checks.xu -o build/scene-v9-tests
	./build/scene-v9-tests

shader-cross-backend-test: sdk
	python3 tests/shader_cross_backend_checks.py

ui-tree-test: layers sdk canvas-shaders mesh-shaders
	mkdir -p build
	$(XU) build tests/ui_tree_focus_checks.xu -o build/ui-tree-checks
	./build/ui-tree-checks

profiler-test: layers sdk canvas-shaders
	mkdir -p build
	$(XU) build tests/profiler_telemetry_checks.xu -o build/profiler-checks
	./build/profiler-checks

bundle-test: layers sdk
	mkdir -p build
	$(XU) build tests/bundle_hotreload_checks.xu -o build/bundle-checks
	./build/bundle-checks

prefab-runtime-test: layers sdk
	mkdir -p build
	$(XU) build tests/scene_prefab_runtime_checks.xu -o build/prefab-runtime-checks
	./build/prefab-runtime-checks

ai-bt-nav-test: layers sdk
	mkdir -p build
	$(XU) build tests/ai_bt_nav_checks.xu -o build/ai-bt-nav-checks
	./build/ai-bt-nav-checks

input-replay-timing-test: layers sdk
	mkdir -p build
	$(XU) build tests/input_replay_timing_checks.xu -o build/input-replay-timing-checks
	./build/input-replay-timing-checks

timeline-test: layers sdk
	mkdir -p build
	$(XU) build tests/animation_timeline_checks.xu -o build/animation-timeline-checks
	./build/animation-timeline-checks

project-bundle-cli-test: layers sdk project-cli
	mkdir -p build
	$(XU) build tests/project_bundle_cli_checks.xu -o build/project-bundle-cli-checks
	./build/project-bundle-cli-checks

scene-soa-test: sdk
	mkdir -p build
	$(XU) build tests/scene_soa_transform_checks.xu -o build/scene-soa-tests
	./build/scene-soa-tests

ecs-parallel-test: layers sdk
	mkdir -p build
	$(XU) build tests/ecs_archetype_parallel_checks.xu -o build/ecs-parallel-checks
	./build/ecs-parallel-checks

navigation-test: layers sdk
	mkdir -p build
	$(XU) build tests/navigation_checks.xu -o build/navigation-checks
	./build/navigation-checks

audio-dsp-test: layers sdk
	mkdir -p build
	$(XU) build tests/audio_dsp_adpcm_checks.xu -o build/audio-dsp-checks
	./build/audio-dsp-checks

.PHONY: phone-frame-test phone-state-test phone-audio-test miniprogram miniprogram-test douyin douyin-test miniprogram-3d douyin-3d webgl-3d-test
miniprogram: layers sdk
	$(PYTHON) tools/build_miniprogram.py --xu "$(XU)"

miniprogram-test: miniprogram
	node tests/miniprogram_webgl.cjs

douyin: layers sdk
	$(PYTHON) tools/build_miniprogram.py --platform douyin --xu "$(XU)"

douyin-test: douyin
	node tests/douyin_webgl.cjs

miniprogram-3d: layers sdk
	$(PYTHON) tools/build_miniprogram.py --scene 3d --xu "$(XU)"

douyin-3d: layers sdk
	$(PYTHON) tools/build_miniprogram.py --platform douyin --scene 3d --xu "$(XU)"

webgl-3d-test: miniprogram-3d douyin-3d
	node tests/webgl_3d.cjs

phone-frame-test: sdk
	mkdir -p build
	$(XU) build tests/phone_frame_checks.xu -o build/phone-frame-tests
	SDL_VIDEODRIVER=nonexistent XU_SDL_LIBRARY=/nonexistent ./build/phone-frame-tests

phone-state-test: sdk
	$(PYTHON) tests/phone_arena_state_checks.py

phone-audio-test: sdk
	$(PYTHON) tests/phone_audio_checks.py

.PHONY: canvas-memory-test
canvas-memory-test: sdk
	$(PYTHON) tests/canvas_memory_checks.py

demo: canvas-shaders native-image
	mkdir -p build
	$(XU) build examples/arena/main.xu -o build/arena
	./build/arena

demo2d: canvas-shaders native-image
	mkdir -p build
	$(XU) build examples/two_d/main.xu -o build/two-d
	./build/two-d

demo3d: mesh-shaders native
	mkdir -p build
	$(XU) build examples/three_d/main.xu -o build/three-d
	./build/three-d

.PHONY: isometric-2d hd2d-scene demo-isometric-2d demo-hd2d 25d-core-test 25d-gpu-test phone-isometric-test phone-hd2d-test
isometric-2d: canvas-shaders native-image
	mkdir -p build
	$(XU) build examples/isometric_2d -o build/isometric-2d

hd2d-scene: mesh-shaders native-image
	mkdir -p build
	$(XU) build examples/hd2d_scene -o build/hd2d-scene

demo-isometric-2d: isometric-2d
	./build/isometric-2d

demo-hd2d: hd2d-scene
	./build/hd2d-scene

25d-core-test: sdk
	mkdir -p build
	$(XU) build tests/scene_25d_checks.xu -o build/scene-25d-checks
	./build/scene-25d-checks

25d-gpu-test: isometric-2d hd2d-scene
	$(PYTHON) tests/scene_25d_gpu_checks.py

phone-isometric-test: isometric-2d
	$(PYTHON) tests/phone_isometric_checks.py

phone-hd2d-test: hd2d-scene
	$(PYTHON) tests/phone_hd2d_checks.py

.PHONY: physics3d-demo-build demo-physics3d physics3d-gpu-test
physics3d-demo-build: mesh-shaders
	$(XU) build examples/physics_3d/main.xu -o build/physics3d-demo

demo-physics3d: physics3d-demo-build
	./build/physics3d-demo

physics3d-gpu-test: physics3d-demo-build
	./build/physics3d-demo --autoplay --frames 120 --capture build/physics3d.png

demo-glb: mesh-shaders native
	mkdir -p build
	$(XU) build examples/glb_preview/main.xu -o build/glb-preview
	./build/glb-preview

demo-script: canvas-shaders native-image script-tool
	$(XU) build examples/script_reload/main.xu -o build/script-reload
	$(PYTHON) tools/run_script_demo.py

demo-materials: mesh-shaders native
	$(XU) build examples/materials/main.xu -o build/materials
	./build/materials

demo-textures3d: mesh-shaders native
	mkdir -p build
	$(XU) build examples/textures3d/main.xu -o build/textures3d
	./build/textures3d

demo-mipmaps3d: mesh-shaders native
	mkdir -p build
	$(XU) build examples/mipmaps3d/main.xu -o build/mipmaps3d
	./build/mipmaps3d

demo-material-maps: mesh-shaders native
	mkdir -p build
	$(XU) build examples/material_maps/main.xu -o build/material-maps
	./build/material-maps

demo-normal-maps: mesh-shaders native
	mkdir -p build
	$(XU) build examples/normal_maps/main.xu -o build/normal-maps
	./build/normal-maps

demo-scene-scripts: mesh-shaders native scene-script-assets
	$(XU) build examples/scene_scripts/main.xu -o build/scene-scripts-demo
	./build/scene-scripts-demo

demo-scene-audio: native
	mkdir -p build
	$(XU) build examples/scene_audio/main.xu -o build/scene-audio-demo
	./build/scene-audio-demo

demo-scene-av: mesh-shaders native
	mkdir -p build
	$(XU) build examples/scene_av/main.xu -o build/scene-av-demo
	./build/scene-av-demo

demo-scene-assets: mesh-shaders native
	mkdir -p build
	$(XU) build examples/scene_assets/main.xu -o build/scene-assets-demo
	./build/scene-assets-demo

demo-scene-file: mesh-shaders native
	mkdir -p build
	$(XU) build examples/scene_file/main.xu -o build/scene-file
	./build/scene-file

demo-glb-materials: mesh-shaders native
	mkdir -p build
	$(XU) build examples/glb_materials/main.xu -o build/glb-materials
	./build/glb-materials

smoke: mesh-shaders canvas-shaders native script-tool audio-smoke scene-script-assets gpu-transfer-smoke gpu-offscreen-smoke gpu-compute-smoke gpu-surface-smoke window-input-smoke
	$(XU) build examples/model_formats/main.xu -o build/model-formats
	./build/model-formats --frames 120 --capture build/model-formats.png
	$(XU) build examples/lod/main.xu -o build/lod
	./build/lod --frames 120 --distance 18 --capture build/lod.png
	mkdir -p build
	$(XU) build examples/headless/main.xu -o build/headless
	./build/headless
	$(XU) build examples/arena/main.xu -o build/arena
	./build/arena --width 1280 --height 640 --frames 120 --autoplay --capture build/arena.png
	$(XU) build examples/two_d/main.xu -o build/two-d
	./build/two-d --frames 120 --capture build/two-d.png
	$(XU) build examples/three_d/main.xu -o build/three-d
	./build/three-d --frames 120 --capture build/three-d.png
	$(XU) build examples/glb_preview/main.xu -o build/glb-preview
	./build/glb-preview --frames 120 --capture build/glb-preview.png
	$(XU) build examples/materials/main.xu -o build/materials
	./build/materials --frames 120 --capture build/materials.png
	$(XU) build examples/lighting/main.xu -o build/lighting
	./build/lighting --frames 120 --capture build/lighting.png
	$(XU) build examples/textures3d/main.xu -o build/textures3d
	./build/textures3d --frames 120 --capture build/textures3d.png
	$(XU) build examples/mipmaps3d/main.xu -o build/mipmaps3d
	./build/mipmaps3d --frames 120 --capture build/mipmaps3d.png
	$(XU) build examples/material_maps/main.xu -o build/material-maps
	./build/material-maps --frames 120 --capture build/material-maps.png
	./build/material-maps --frames 120 --lights off --capture build/material-maps-dark.png
	$(XU) build examples/normal_maps/main.xu -o build/normal-maps
	./build/normal-maps --frames 120 --capture build/normal-maps.png
	$(XU) build examples/generated_tangents/main.xu -o build/generated-tangents
	./build/generated-tangents --frames 120 --capture build/generated-tangents.png
	$(XU) build examples/glb_materials/main.xu -o build/glb-materials
	./build/glb-materials --frames 120 --capture build/glb-materials.png
	$(XU) build examples/scene_file/main.xu -o build/scene-file
	./build/scene-file --frames 1 --save build/saved-world.xuscene
	./build/scene-file --scene build/saved-world.xuscene --frames 120 --capture build/scene-file.png
	$(XU) build examples/scene_assets/main.xu -o build/scene-assets-demo
	mkdir -p build/scene-assets
	cp examples/scene_assets/assets/world.xuscene examples/scene_assets/assets/panels.glb build/scene-assets/
	./build/scene-assets-demo --scene build/scene-assets/world.xuscene --frames 1 --save build/scene-assets/saved.xuscene
	./build/scene-assets-demo --scene build/scene-assets/saved.xuscene --frames 120 --capture build/scene-assets.png
	$(XU) build examples/scene_audio/main.xu -o build/scene-audio-demo
	mkdir -p build/scene-audio
	cp examples/scene_audio/assets/world.xuscene examples/scene_audio/assets/chime.wav build/scene-audio/
	./build/scene-audio-demo --scene build/scene-audio/world.xuscene --seconds 1 --save build/scene-audio/saved.xuscene
	./build/scene-audio-demo --scene build/scene-audio/saved.xuscene --seconds 1
	$(XU) build examples/scene_av/main.xu -o build/scene-av-demo
	mkdir -p build/scene-av
	cp examples/scene_av/assets/world.xuscene examples/scene_av/assets/panels.glb examples/scene_av/assets/chime.wav build/scene-av/
	./build/scene-av-demo --scene build/scene-av/world.xuscene --frames 1 --save build/scene-av/saved.xuscene
	./build/scene-av-demo --scene build/scene-av/saved.xuscene --frames 120 --capture build/scene-av.png
	$(XU) build examples/scene_scripts/main.xu -o build/scene-scripts-demo
	./build/scene-scripts-demo --scene build/scene-scripts/world.xuscene --frames 120 --save build/scene-scripts/saved.xuscene --capture build/scene-scripts.png
	./build/scene-scripts-demo --scene build/scene-scripts/saved.xuscene --frames 1
	./build/xu-nexus-script build examples/script_reload/player.xus examples/script_reload/player.schema.json build/player.xubc
	./build/xu-nexus-script build examples/script_reload/indicator.xus examples/script_reload/indicator.schema.json build/indicator.xubc
	$(XU) build examples/script_reload/main.xu -o build/script-reload
	./build/script-reload --frames 120 --autoplay --capture build/script-reload.png

script-live-smoke: mesh-shaders canvas-shaders native script-tool
	$(XU) build examples/script_reload/main.xu -o build/script-reload
	$(PYTHON) tests/script_live_checks.py

gpu-smoke: 25d-gpu-test present-fallback-test text-2d-test ui-hud-test scene-camera-gpu-test scene-lod-gpu-test physics3d-gpu-test physics3d-joints-ragdoll-test project-gpu-test project-picking-test character-course-test shadow-gpu-test render-quality-test gltf-animation-gpu-test gpu-skinning-test clustered-lighting-gpu-test indirect-cull-hiz-gpu-test hdr-postprocess-gpu-test meshlet-visbuffer-gpu-test streaming-lru-gpu-test model-format-gpu-test lod-gpu-test lod-demo-test frustum-gpu-test scene-lighting-services-test lighting-demo-test lighting-gpu-test mesh-shaders canvas-shaders gpu-offscreen-smoke gpu-compute-smoke gpu-surface-smoke window-input-smoke native glb-fixtures glb-material-fixtures image-fixtures scene-asset-fixtures scene-audio-fixtures scene-script-fixtures
	mkdir -p build
	$(XU) build tests/gpu_smoke.xu -o build/gpu-smoke
	./build/gpu-smoke
	$(PYTHON) tests/renderer2d_isolation.py
	$(PYTHON) tests/renderer3d_isolation.py
	$(PYTHON) tests/stdlib_gpu_isolation.py
	$(PYTHON) tests/stdlib_gpu_offscreen_isolation.py
	$(PYTHON) tests/stdlib_gpu_compute_isolation.py
	$(PYTHON) tests/stdlib_gpu_surface_isolation.py
	$(PYTHON) tests/stdlib_window_input_isolation.py
	$(XU) build tests/stdlib_gpu_coexist.xu -o build/stdlib-gpu-coexist
	./build/stdlib-gpu-coexist
	$(XU) build tests/gpu2d_layers_checks.xu -o build/gpu2d-layers-tests
	./build/gpu2d-layers-tests
	$(XU) build tests/audio_gpu_coexist.xu -o build/audio-gpu-coexist
	SDL_AUDIO_DRIVER=dummy ./build/audio-gpu-coexist
	$(XU) build tests/gpu3d_smoke.xu -o build/gpu3d-smoke
	./build/gpu3d-smoke
	$(XU) build tests/gpu3d_scene_smoke.xu -o build/gpu3d-scene-smoke
	./build/gpu3d-scene-smoke
	$(XU) build tests/glb_gpu_smoke.xu -o build/glb-gpu-smoke
	./build/glb-gpu-smoke
	$(XU) build tests/material_gpu_checks.xu -o build/material-gpu-tests
	./build/material-gpu-tests
	$(XU) build tests/texture3d_gpu_checks.xu -o build/texture3d-gpu-tests
	./build/texture3d-gpu-tests
	$(XU) build tests/mipmap3d_gpu_checks.xu -o build/mipmap3d-gpu-tests
	./build/mipmap3d-gpu-tests
	$(XU) build tests/material_maps_gpu_checks.xu -o build/material-maps-gpu-tests
	./build/material-maps-gpu-tests
	$(XU) build tests/normal_map_gpu_checks.xu -o build/normal-map-gpu-tests
	./build/normal-map-gpu-tests
	$(XU) build tests/glb_material_gpu_checks.xu -o build/glb-material-gpu-tests
	./build/glb-material-gpu-tests
	$(XU) build tests/scene_assets_gpu_checks.xu -o build/scene-assets-gpu-tests
	./build/scene-assets-gpu-tests
	$(XU) build tests/scene_av_gpu_checks.xu -o build/scene-av-gpu-tests
	./build/scene-av-gpu-tests
	$(XU) build examples/scene_scripts/main.xu -o build/scene-scripts-demo
	$(PYTHON) tests/scene_script_gpu_checks.py

gpu3d-smoke: lighting-gpu-test mesh-shaders canvas-shaders native glb-fixtures glb-material-fixtures scene-asset-fixtures scene-audio-fixtures scene-script-fixtures
	mkdir -p build
	$(XU) build tests/gpu3d_smoke.xu -o build/gpu3d-smoke
	./build/gpu3d-smoke
	$(XU) build tests/gpu3d_scene_smoke.xu -o build/gpu3d-scene-smoke
	./build/gpu3d-scene-smoke
	$(XU) build tests/glb_gpu_smoke.xu -o build/glb-gpu-smoke
	./build/glb-gpu-smoke
	$(XU) build tests/material_gpu_checks.xu -o build/material-gpu-tests
	./build/material-gpu-tests
	$(XU) build tests/texture3d_gpu_checks.xu -o build/texture3d-gpu-tests
	./build/texture3d-gpu-tests
	$(XU) build tests/mipmap3d_gpu_checks.xu -o build/mipmap3d-gpu-tests
	./build/mipmap3d-gpu-tests
	$(XU) build tests/material_maps_gpu_checks.xu -o build/material-maps-gpu-tests
	./build/material-maps-gpu-tests
	$(XU) build tests/normal_map_gpu_checks.xu -o build/normal-map-gpu-tests
	./build/normal-map-gpu-tests
	$(XU) build tests/glb_material_gpu_checks.xu -o build/glb-material-gpu-tests
	./build/glb-material-gpu-tests
	$(XU) build tests/scene_assets_gpu_checks.xu -o build/scene-assets-gpu-tests
	./build/scene-assets-gpu-tests
	$(XU) build tests/scene_av_gpu_checks.xu -o build/scene-av-gpu-tests
	./build/scene-av-gpu-tests
	$(XU) build examples/scene_scripts/main.xu -o build/scene-scripts-demo
	$(PYTHON) tests/scene_script_gpu_checks.py

audio-fixtures:
	$(PYTHON) tests/make_audio_fixtures.py

mesh-core-test: sdk
	$(PYTHON) tests/mesh_isolation.py

demo-generated-tangents: mesh-shaders
	$(XU) build examples/generated_tangents/main.xu -o build/generated-tangents
	./build/generated-tangents

audio-core-test: sdk audio-fixtures
	mkdir -p build
	$(PYTHON) tests/audio_isolation.py --core-only

audio-device-test: native-audio audio-fixtures
	$(PYTHON) tests/audio_isolation.py --device-only

audio-test: audio-core-test audio-device-test
	$(XU) build tests/audio_scene_checks.xu -o build/audio-scene-tests
	./build/audio-scene-tests

audio-smoke: native-audio
	mkdir -p build
	$(XU) build examples/audio/main.xu -o build/audio-demo
	./build/audio-demo --seconds 1
	$(XU) build examples/audio_stream/main.xu -o build/audio-stream
	./build/audio-stream --seconds 1 --seek-frame 12000

demo-audio: native-audio
	mkdir -p build
	$(XU) build examples/audio/main.xu -o build/audio-demo
	./build/audio-demo

demo-audio-stream: native-audio
	mkdir -p build
	$(XU) build examples/audio_stream/main.xu -o build/audio-stream
	./build/audio-stream

demo-audio-seek: native-audio
	mkdir -p build
	$(XU) build examples/audio_stream/main.xu -o build/audio-stream
	./build/audio-stream --seconds 5 --seek-frame 12000

# Independent standard GPU consumer; no nexus native bridge or shader build.
gpu-transfer-smoke: sdk
	mkdir -p build
	$(XU) build examples/gpu_transfer/main.xu -o build/gpu-transfer
	./build/gpu-transfer

gpu-compute-smoke: sdk
	$(PYTHON) tools/gpu_compute_shaders.py
	$(XU) build examples/gpu_compute/main.xu -o build/gpu-compute
	./build/gpu-compute

gpu-offscreen-smoke: sdk
	$(PYTHON) tools/gpu_offscreen_shaders.py
	$(XU) build examples/gpu_offscreen/main.xu -o build/gpu-offscreen
	./build/gpu-offscreen

# A standard window and presentation consumer; no engine native bridge.
gpu-surface-smoke: sdk
	$(PYTHON) tools/gpu_surface_shaders.py
	$(XU) build examples/gpu_surface/main.xu -o build/gpu-surface
	./build/gpu-surface --frames 60

window-input-smoke: sdk
	mkdir -p build
	$(XU) build examples/window_input/main.xu -o build/window-input
	./build/window-input --frames 60

# Metal fault injection is separate from the portable GPU smoke targets.
gpu-failure-test: mesh-shaders
	$(PYTHON) tests/renderer3d_failure_checks.py
	$(PYTHON) tests/shadow_failure_checks.py

lighting-core-test: light-culling-core-test sdk
	$(PYTHON) tests/lighting_isolation.py

lighting-gpu-test: light-culling-gpu-test mesh-shaders lighting-core-test
	$(XU) build tests/multilight_gpu_checks.xu -o build/multilight-gpu
	./build/multilight-gpu

demo-lighting: mesh-shaders
	$(XU) build examples/lighting/main.xu -o build/lighting
	./build/lighting

lighting-demo-test: mesh-shaders
	$(XU) build examples/lighting/main.xu -o build/lighting
	$(PYTHON) tests/lighting_demo_checks.py

.PHONY: scene-lighting-test scene-lighting-services-test
scene-lighting-test: sdk
	$(PYTHON) tests/make_scene_lighting_fixtures.py
	$(PYTHON) tests/scene_lighting_isolation.py

scene-lighting-services-test: mesh-shaders native scene-script-fixtures
	$(XU) build tests/scene_lighting_services_checks.xu -o build/scene-lighting-services
	./build/scene-lighting-services

.PHONY: light-culling-core-test light-culling-gpu-test
light-culling-core-test: sdk
	$(PYTHON) tests/light_culling_isolation.py

light-culling-gpu-test: mesh-shaders light-culling-core-test
	$(XU) build tests/light_culling_gpu_checks.xu -o build/light-culling-gpu
	./build/light-culling-gpu

.PHONY: frustum-core-test frustum-gpu-test
frustum-core-test: sdk
	$(PYTHON) tests/frustum_isolation.py

frustum-gpu-test: mesh-shaders frustum-core-test
	$(XU) build tests/frustum_gpu_checks.xu -o build/frustum-gpu
	./build/frustum-gpu

.PHONY: lod-core-test lod-gpu-test lod-demo-test demo-lod
.PHONY: scene-lod-gpu-test
scene-lod-gpu-test: mesh-shaders native-image scene-asset-fixtures
	$(XU) build examples/scene_assets/main.xu -o build/scene-lod-preview
	$(PYTHON) tests/scene_lod_preview_checks.py

lod-core-test: sdk
	$(PYTHON) tests/lod_isolation.py

lod-gpu-test: mesh-shaders lod-core-test
	$(XU) build tests/lod_gpu_checks.xu -o build/lod-gpu
	./build/lod-gpu

demo-lod: mesh-shaders
	$(XU) build examples/lod/main.xu -o build/lod
	./build/lod

lod-demo-test: mesh-shaders
	$(XU) build examples/lod/main.xu -o build/lod
	$(PYTHON) tests/lod_demo_checks.py

.PHONY: mesh-format-fixtures mesh-format-core-test model-format-gpu-test demo-models
mesh-format-fixtures:
	$(PYTHON) tests/make_mesh_format_fixtures.py

mesh-format-core-test: sdk mesh-format-fixtures
	$(PYTHON) tests/mesh_format_isolation.py

model-format-gpu-test: mesh-shaders native-image mesh-format-fixtures
	$(XU) build examples/model_formats/main.xu -o build/model-formats
	$(PYTHON) tests/model_format_gpu_checks.py

demo-models: mesh-shaders native-image
	$(XU) build examples/model_formats/main.xu -o build/model-formats
	./build/model-formats

.PHONY: gltf-animation-test gltf-animation-gpu-test external-model-fixtures external-model-test
gltf-animation-test: sdk
	$(PYTHON) tests/make_gltf_animation_fixtures.py
	$(PYTHON) tests/gltf_animation_isolation.py
	$(XU) build tests/gltf_animation_lifecycle_checks.xu -o build/gltf-animation-lifecycle
	./build/gltf-animation-lifecycle

gltf-animation-gpu-test: mesh-shaders native-image gltf-animation-test
	$(XU) build tests/gltf_animation_gpu_checks.xu -o build/gltf-animation-gpu
	./build/gltf-animation-gpu

gpu-skinning-test: mesh-shaders native-image gltf-animation-gpu-test
	$(XU) build tests/gpu_skinning_checks.xu -o build/gpu-skinning-checks
	./build/gpu-skinning-checks

skeletal-animation-test: layers sdk mesh-shaders
	mkdir -p build
	$(XU) build tests/skeletal_animation_checks.xu -o build/skeletal-animation-checks
	./build/skeletal-animation-checks

particles-vfx-gpu-test: layers sdk mesh-shaders
	mkdir -p build
	$(XU) build tests/particles_vfx_gpu_checks.xu -o build/particles-vfx-checks
	./build/particles-vfx-checks

clustered-lighting-gpu-test: mesh-shaders lighting-core-test
	$(XU) build tests/clustered_lighting_gpu_checks.xu -o build/clustered-lighting-checks
	./build/clustered-lighting-checks

indirect-cull-hiz-gpu-test: mesh-shaders lighting-core-test
	$(XU) build tests/indirect_cull_hiz_gpu_checks.xu -o build/indirect-cull-hiz-checks
	./build/indirect-cull-hiz-checks

hdr-postprocess-gpu-test: mesh-shaders lighting-core-test
	$(XU) build tests/hdr_postprocess_gpu_checks.xu -o build/hdr-postprocess-checks
	./build/hdr-postprocess-checks

meshlet-visbuffer-gpu-test: mesh-shaders lighting-core-test
	mkdir -p build
	$(XU) build tests/meshlet_visbuffer_gpu_checks.xu -o build/meshlet-visbuffer-checks
	./build/meshlet-visbuffer-checks

transparent-pbr-gpu-test: mesh-shaders lighting-core-test
	mkdir -p build
	$(XU) build tests/transparent_pbr_gpu_checks.xu -o build/transparent-pbr-checks
	./build/transparent-pbr-checks

physics3d-joints-ragdoll-test: mesh-shaders physics3d-test
	mkdir -p build
	$(XU) build tests/physics3d_joints_ragdoll_checks.xu -o build/physics3d-joints-ragdoll
	./build/physics3d-joints-ragdoll

physics3d-advanced-test: layers sdk
	mkdir -p build
	$(XU) build tests/physics3d_advanced_checks.xu -o build/physics3d-advanced
	./build/physics3d-advanced

script-aot-test: script-tool
	mkdir -p build
	$(PYTHON) tests/script_aot_checks.py --xu "$(XU)"

script-host-coroutines-test: layers sdk
	mkdir -p build
	$(XU) build tests/script_host_coroutines_checks.xu -o build/script-host-coroutines-checks
	./build/script-host-coroutines-checks

streaming-lru-gpu-test: mesh-shaders native-image gltf-animation-test
	$(XU) build tests/streaming_lru_gpu_checks.xu -o build/streaming-lru-checks
	./build/streaming-lru-checks

# Network downloads are explicit and never part of the default test targets.
external-model-fixtures:
	$(PYTHON) tests/fetch_external_models.py

external-model-test: mesh-shaders native-image
	$(XU) build examples/model_formats/main.xu -o build/model-formats
	$(PYTHON) tests/external_model_oracle.py
	$(XU) build tests/external_model_checks.xu -o build/external-models/cpu-checks
	./build/external-models/cpu-checks
	$(PYTHON) tests/gltf_external_file_checks.py
	$(PYTHON) tests/external_model_gpu_checks.py

.PHONY: jpeg-test render-quality-test detail-model-fixtures detail-model-test
jpeg-test: native-image
	$(PYTHON) tests/make_jpeg_fixtures.py
	$(XU) build tests/jpeg_checks.xu -o build/jpeg-checks
	./build/jpeg-checks
	$(PYTHON) tests/jpeg_pixels.py

render-quality-test: mesh-shaders
	$(XU) build tests/render_quality_checks.xu -o build/render-quality
	./build/render-quality
	$(PYTHON) tests/render_quality_pixels.py

present-fallback-test: canvas-shaders mesh-shaders
	mkdir -p build
	$(PYTHON) tests/present_fallback_checks.py

text-2d-test: canvas-shaders mesh-shaders
	mkdir -p build
	$(PYTHON) tests/text_2d_checks.py

ui-hud-test: canvas-shaders mesh-shaders
	mkdir -p build
	$(PYTHON) tests/ui_hud_checks.py

.PHONY: scene-camera-gpu-test
scene-camera-gpu-test: mesh-shaders canvas-shaders native-image
	mkdir -p build/scene-camera-gpu
	$(XU) build examples/scene_file/main.xu -o build/scene-camera-gpu/scene-file
	$(XU) build examples/two_d/main.xu -o build/scene-camera-gpu/two-d
	$(PYTHON) tests/scene_camera_gpu_checks.py

demo-ui-hud: canvas-shaders mesh-shaders
	mkdir -p build
	$(XU) build examples/ui_hud/main.xu -o build/ui-hud
	./build/ui-hud --hidden --frames 4

detail-model-fixtures:
	$(PYTHON) tests/fetch_detail_model.py
	npm install --prefix build/detail-model-tools --no-audit --no-fund mikktspace@1.1.1
	node tests/prepare_detail_head.cjs

detail-model-test: mesh-shaders native-image
	$(XU) build examples/model_formats/main.xu -o build/model-formats
	$(PYTHON) tests/detail_model_checks.py

.PHONY: shadow-core-test shadow-gpu-test
shadow-core-test: sdk
	$(PYTHON) tests/shadow_isolation.py

shadow-gpu-test: mesh-shaders shadow-core-test
	$(XU) build tests/shadow_gpu_checks.xu -o build/shadow-gpu-checks
	./build/shadow-gpu-checks
	$(PYTHON) tests/shadow_pixels.py
	$(XU) build tests/spot_shadow_gpu_checks.xu -o build/spot-shadow-gpu-checks
	./build/spot-shadow-gpu-checks
	$(PYTHON) tests/spot_shadow_pixels.py
	$(XU) build tests/point_shadow_gpu_checks.xu -o build/point-shadow-gpu-checks
	./build/point-shadow-gpu-checks
	$(PYTHON) tests/point_shadow_pixels.py
	$(XU) build tests/cascade_gpu_checks.xu -o build/cascade-gpu-checks
	./build/cascade-gpu-checks
	$(PYTHON) tests/cascade_pixels.py

terrain-foliage-gpu-test: mesh-shaders
	mkdir -p build
	$(XU) build tests/terrain_foliage_gpu_checks.xu -o build/terrain-foliage-gpu-checks
	./build/terrain-foliage-gpu-checks

decals-atmosphere-gpu-test: mesh-shaders
	mkdir -p build
	$(XU) build tests/decals_atmosphere_gpu_checks.xu -o build/decals-atmosphere-gpu-checks
	./build/decals-atmosphere-gpu-checks

ddgi-gi-gpu-test: mesh-shaders
	mkdir -p build
	$(XU) build tests/ddgi_gi_gpu_checks.xu -o build/ddgi-gi-gpu-checks
	./build/ddgi-gi-gpu-checks

engine-integration-gpu-test: layers mesh-shaders
	mkdir -p build
	$(XU) build tests/engine_full_integration_gpu_checks.xu -o build/engine-integration-gpu-checks
	./build/engine-integration-gpu-checks

all-modern-tests: modern-sandbox-test steam-test steam-native-test console-test console-native-test taptap-test taptap-native-test engine-integration-gpu-test ddgi-gi-gpu-test physics3d-advanced-test networking-test decals-atmosphere-gpu-test terrain-foliage-gpu-test script-host-coroutines-test particles-vfx-gpu-test skeletal-animation-test transparent-pbr-gpu-test
	@echo "ALL MODERN ENGINE TESTS PASSED"

console-data-test: sdk
	mkdir -p build
	$(XU) build tests/console_data_checks.xu -o build/console-data-checks
	./build/console-data-checks

console-test: native-steam native-console native-taptap project-cli
	mkdir -p build
	$(XU) build tests/console_platform_checks.xu -o build/console-platform-checks
	XU_NEXUS_STEAM_LIBRARY=/nonexistent/no-steam XU_NEXUS_XBOX_DRIVER=/nonexistent/no-xbox XU_NEXUS_PS_DRIVER=/nonexistent/no-ps XU_NEXUS_SWITCH_DRIVER=/nonexistent/no-switch XU_NEXUS_TAPTAP_LIBRARY=/nonexistent/no-taptap ./build/console-platform-checks
	$(XU) build tests/console_cli_checks.xu -o build/console-cli-checks
	./build/console-cli-checks --project-cli build/nexus-project

console-native-test: native-console
	mkdir -p build
	$(PYTHON) tests/console_native_bridge_checks.py --xu "$(XU)"

taptap-data-test: sdk
	mkdir -p build
	$(XU) build tests/taptap_data_checks.xu -o build/taptap-data-checks
	./build/taptap-data-checks

taptap-test: native-taptap native-steam native-console project-cli
	mkdir -p build
	$(XU) build tests/taptap_integration_checks.xu -o build/taptap-integration-checks
	XU_NEXUS_TAPTAP_LIBRARY=/nonexistent/no-taptap ./build/taptap-integration-checks
	$(XU) build tests/taptap_cli_checks.xu -o build/taptap-cli-checks
	./build/taptap-cli-checks --project-cli build/nexus-project

taptap-native-test: native-taptap
	mkdir -p build
	$(PYTHON) tests/taptap_native_bridge_checks.py --xu "$(XU)"

steam-data-test: sdk
	mkdir -p build
	$(XU) build tests/steam_data_checks.xu -o build/steam-data-checks
	./build/steam-data-checks

steam-test: native-steam project-cli
	mkdir -p build
	$(XU) build tests/steam_integration_checks.xu -o build/steam-integration-checks
	XU_NEXUS_STEAM_LIBRARY=/nonexistent/no-steam ./build/steam-integration-checks
	$(XU) build tests/steam_cli_checks.xu -o build/steam-cli-checks
	./build/steam-cli-checks --project-cli build/nexus-project

steam-native-test: native-steam
	mkdir -p build
	$(PYTHON) tests/steam_native_bridge_checks.py --xu "$(XU)"

.PHONY: modern-sandbox demo-modern-sandbox modern-sandbox-test
modern-sandbox: mesh-shaders canvas-shaders native-image script-tool
	$(XU) build examples/modern_sandbox/main.xu -o build/nexus-modern-sandbox

demo-modern-sandbox: modern-sandbox
	./build/nexus-modern-sandbox

modern-sandbox-test: modern-sandbox
	./build/nexus-modern-sandbox --hidden --frames 60 --autoplay --capture build/modern-sandbox.png
	test -s build/modern-sandbox.png

networking-test: sdk
	mkdir -p build
	$(XU) build tests/networking_multiplayer_checks.xu -o build/networking-multiplayer-checks
	./build/networking-multiplayer-checks

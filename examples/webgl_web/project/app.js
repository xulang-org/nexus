import { OrbitController } from "./runtime/orbit.js";

const DESIGN_WIDTH = 360;
const DESIGN_HEIGHT = 240;
const CAMERA_MAGIC = 0x3143584e;
const CAMERA_BYTES = 68;
const COLLECTED_ALL = 7;

const SCENE_HINTS = {
    "3d": "左键拖拽旋转 · Shift+拖拽或右键平移 · 滚轮缩放 · 双击或按 R 复位",
    "2d": "按住或拖拽控制角色移动 · 绕过墙壁收集宝石 · 按 R 重开",
};

const SCENE_STATUS = {
    "3d": "拖动画布旋转 3D 模型，滚轮缩放，Shift+拖拽平移。",
    "2d": "按住或拖动，绕过墙壁收集宝石。",
};

async function instantiateWasm(url, imports) {
    const response = await fetch(url);
    if (!response.ok) {
        throw new Error(`无法加载 WebAssembly (${response.status}): ${url}`);
    }
    if (typeof WebAssembly.instantiateStreaming === "function") {
        const contentType = response.headers.get("content-type") || "";
        if (contentType.includes("application/wasm")) {
            return WebAssembly.instantiateStreaming(response, imports);
        }
    }
    const bytes = await response.arrayBuffer();
    return WebAssembly.instantiate(bytes, imports);
}

async function fetchBinary(url) {
    const response = await fetch(url);
    if (!response.ok) {
        throw new Error(`无法加载资源 (${response.status}): ${url}`);
    }
    return new Uint8Array(await response.arrayBuffer());
}

function loadAtlasImage(url) {
    return new Promise((resolve, reject) => {
        const image = new Image();
        image.decoding = "async";
        image.onload = () => resolve(image);
        image.onerror = () => reject(new Error(`无法加载图集: ${url}`));
        image.src = url;
    });
}

function createCameraPacketBuffer() {
    const packet = new Uint8Array(CAMERA_BYTES);
    const view = new DataView(packet.buffer);
    view.setUint32(0, CAMERA_MAGIC, true);
    return { packet, view };
}

function encodeCameraMatrix(matrixOrPacket, buffer) {
    if (matrixOrPacket && matrixOrPacket.byteLength === CAMERA_BYTES) {
        return matrixOrPacket;
    }
    for (let i = 0; i < 16; i += 1) {
        buffer.view.setFloat32(4 + i * 4, matrixOrPacket[i], true);
    }
    return buffer.packet;
}

function getRuntimeApi() {
    const api = globalThis.NexusWebGL;
    if (!api || !api.WebGLCanvas || !api.loadGame) {
        throw new Error("NexusWebGL 运行时未就绪");
    }
    return api;
}

function resolveDemoConfig(api) {
    if (api.demo && api.demo.scenes) {
        return api.demo;
    }
    return {
        mesh: true,
        defaultScene: "3d",
        scenes: {
            "3d": { wasm: "game-3d.wasm", model: "assets/crate.glb" },
            "2d": { wasm: "game-2d.wasm", atlas: "assets/player.png" },
        },
    };
}

export function createWebApp(doc = document, win = window) {
    const api = getRuntimeApi();
    const { WebGLCanvas, loadGame } = api;
    const demo = resolveDemoConfig(api);

    const canvas = doc.getElementById("arena");
    const statusEl = doc.getElementById("status");
    const readoutEl = doc.getElementById("readout");
    const fpsEl = doc.getElementById("fps");
    const memoryEl = doc.getElementById("memory");
    const hintsEl = doc.getElementById("hints");
    const resetBtn = doc.getElementById("reset-btn");
    const overlayEl = doc.getElementById("overlay");
    const overlayTextEl = doc.getElementById("overlay-text");
    const modeButtons = Array.from(doc.querySelectorAll(".mode-btn[data-scene]"));

    const cameraBuffer = createCameraPacketBuffer();
    const orbit = new OrbitController({
        target: [0, 0.65, 0],
        distance: 9.2,
        yaw: 0.58,
        pitch: 0.22,
        fov: 0.87,
        far: 40,
        reverseZ: true,
    });

    const state = {
        destroyed: false,
        scene: demo.defaultScene || (demo.mesh ? "3d" : "2d"),
        loadToken: 0,
        renderer: null,
        game: null,
        wasmState: 0,
        score: 0,
        contextLost: false,
        animationId: null,
        lastTimestamp: null,
        activePointerId: null,
        target: [-1, -1],
        fpsFrames: 0,
        fpsStartedAt: 0,
        forceRender: true,
    };

    function setOverlay(message) {
        if (!overlayEl || !overlayTextEl) return;
        if (message) {
            overlayTextEl.textContent = message;
            overlayEl.hidden = false;
        } else {
            overlayTextEl.textContent = "";
            overlayEl.hidden = true;
        }
    }

    function setStatus(message, isError = false) {
        if (!statusEl) return;
        statusEl.textContent = message;
        statusEl.classList.toggle("is-error", isError);
    }

    function updateSceneButtons() {
        const available = demo.scenes || {};
        for (const button of modeButtons) {
            const name = button.dataset.scene;
            const supported = Boolean(available[name]);
            button.disabled = !supported;
            const active = name === state.scene;
            button.classList.toggle("is-active", active);
            button.setAttribute("aria-pressed", String(active));
        }
        if (canvas) {
            canvas.classList.toggle("is-2d", state.scene === "2d");
        }
        if (hintsEl) {
            hintsEl.textContent = SCENE_HINTS[state.scene] || "";
        }
        if (resetBtn) {
            resetBtn.textContent = state.scene === "3d" ? "复位 (R)" : "重开 (R)";
        }
    }

    function updateTelemetry(now) {
        if (state.fpsStartedAt === 0) state.fpsStartedAt = now;
        state.fpsFrames += 1;
        const span = now - state.fpsStartedAt;
        if (span >= 450) {
            const fps = Math.round((state.fpsFrames * 1000) / span);
            if (fpsEl) fpsEl.textContent = `${fps} FPS`;
            state.fpsFrames = 0;
            state.fpsStartedAt = now;
        }
        if (memoryEl && state.game) {
            memoryEl.textContent = `${Math.round(state.game.memoryBytes() / 1024)} KB`;
        }
        if (!readoutEl) return;
        if (state.scene === "3d") {
            const cam = orbit.getState();
            const yaw = Number(cam.yaw || 0).toFixed(2);
            const pitch = Number(cam.pitch || 0).toFixed(2);
            const dist = Number(cam.distance || 0).toFixed(1);
            readoutEl.textContent = `yaw ${yaw} · pitch ${pitch} · dist ${dist}`;
        } else {
            readoutEl.textContent = `宝石 ${state.score} / 3`;
        }
    }

    function releaseActivePointer() {
        if (state.activePointerId !== null && canvas && typeof canvas.releasePointerCapture === "function") {
            try {
                if (!canvas.hasPointerCapture || canvas.hasPointerCapture(state.activePointerId)) {
                    canvas.releasePointerCapture(state.activePointerId);
                }
            } catch {
                // Ignore if pointer capture already ended natively.
            }
        }
        state.activePointerId = null;
        state.target = [-1, -1];
        if (canvas) canvas.classList.remove("is-dragging");
    }

    function stopLoop() {
        if (state.animationId !== null) {
            win.cancelAnimationFrame(state.animationId);
            state.animationId = null;
        }
        state.lastTimestamp = null;
    }

    function teardownScene() {
        stopLoop();
        releaseActivePointer();
        if (state.renderer) {
            state.renderer.close();
            state.renderer = null;
        }
        if (state.game && typeof state.game.destroy === "function") {
            state.game.destroy();
        }
        state.game = null;
        state.contextLost = false;
        if (resetBtn) resetBtn.disabled = true;
    }

    function resizeCanvas() {
        if (!state.renderer || !canvas) return;
        const rect = canvas.getBoundingClientRect();
        if (rect.width <= 0 || rect.height <= 0) return;
        state.renderer.resize(
            { left: rect.left, top: rect.top, width: rect.width, height: rect.height },
            win.devicePixelRatio || 1,
        );
        state.forceRender = true;
    }

    function scheduleFrame() {
        if (state.destroyed || state.contextLost || !state.renderer || !state.game || state.animationId !== null) {
            return;
        }
        state.animationId = win.requestAnimationFrame(renderFrame);
    }

    function renderFrame(timestamp) {
        state.animationId = null;
        if (state.destroyed || state.contextLost || !state.renderer || !state.game) return;
        try {
            const now = Number.isFinite(timestamp) ? timestamp : performance.now();
            const dtMs = state.lastTimestamp === null ? 16.667 : Math.max(0, Math.min(50, now - state.lastTimestamp));
            state.lastTimestamp = now;

            if (state.scene === "3d") {
                const moved = orbit.step(dtMs / 1000);
                if (moved || state.forceRender) {
                    const aspect = DESIGN_WIDTH / DESIGN_HEIGHT;
                    const matrix = orbit.getCameraMatrix(aspect);
                    state.renderer.draw(encodeCameraMatrix(matrix, cameraBuffer));
                    state.forceRender = false;
                }
            } else {
                const { state: nextState, packet } = state.game.advance(
                    state.wasmState,
                    state.target[0],
                    state.target[1],
                    Math.round(dtMs * 1000),
                );
                state.renderer.draw(packet);
                state.wasmState = nextState;
                const mask = (nextState >>> 24) & COLLECTED_ALL;
                const score = (mask & 1) + ((mask >>> 1) & 1) + ((mask >>> 2) & 1);
                if (score !== state.score) {
                    state.score = score;
                    if (score === 3) setStatus("宝石已集齐。");
                }
            }
            updateTelemetry(now);
            scheduleFrame();
        } catch (error) {
            fail(error);
        }
    }

    function fail(error) {
        teardownScene();
        const message = error && error.message ? error.message : String(error);
        setStatus(message, true);
        setOverlay(message);
    }

    function resetScene() {
        if (!state.game || !state.renderer || state.contextLost) return;
        releaseActivePointer();
        if (state.scene === "3d") {
            orbit.reset();
            state.forceRender = true;
        } else {
            state.wasmState = state.game.reset();
            state.score = 0;
        }
        setStatus(SCENE_STATUS[state.scene] || "");
    }

    async function loadScene(sceneName) {
        const config = demo.scenes && demo.scenes[sceneName];
        if (!config) {
            throw new Error(`未打包场景: ${sceneName}`);
        }
        const token = ++state.loadToken;
        state.scene = sceneName;
        updateSceneButtons();
        teardownScene();
        setOverlay("");
        setStatus("正在加载 WebAssembly…");
        if (fpsEl) fpsEl.textContent = "0 FPS";
        if (memoryEl) memoryEl.textContent = "-- KB";

        try {
            const is3d = sceneName === "3d";
            const [modelBytes, atlas] = await Promise.all([
                is3d ? fetchBinary(config.model) : Promise.resolve(null),
                is3d ? Promise.resolve(null) : loadAtlasImage(config.atlas),
            ]);
            if (state.destroyed || token !== state.loadToken) return;

            const game = await loadGame(instantiateWasm, config.wasm, modelBytes);
            if (state.destroyed || token !== state.loadToken) {
                if (typeof game.destroy === "function") game.destroy();
                return;
            }

            const renderer = new WebGLCanvas(
                canvas,
                is3d ? game.model : atlas,
                DESIGN_WIDTH,
                DESIGN_HEIGHT,
                is3d,
                {
                    onContextLost() {
                        state.contextLost = true;
                        stopLoop();
                        releaseActivePointer();
                        setStatus("WebGL 上下文已丢失，等待恢复…", true);
                        setOverlay("WebGL 上下文已丢失，正在等待浏览器恢复…");
                    },
                    onContextRestored() {
                        state.contextLost = false;
                        state.forceRender = true;
                        state.lastTimestamp = null;
                        setOverlay("");
                        setStatus(SCENE_STATUS[state.scene] || "");
                        scheduleFrame();
                    },
                },
            );
            game.model = null;

            state.renderer = renderer;
            state.game = game;
            state.wasmState = game.reset();
            state.score = 0;
            state.fpsFrames = 0;
            state.fpsStartedAt = 0;
            state.forceRender = true;
            if (is3d) orbit.reset();

            resizeCanvas();
            if (resetBtn) resetBtn.disabled = false;
            setStatus(SCENE_STATUS[sceneName] || "");
            scheduleFrame();
        } catch (error) {
            if (!state.destroyed && token === state.loadToken) {
                fail(error);
            }
        }
    }

    function onPointerDown(event) {
        if (!state.renderer || !state.game || state.contextLost || state.activePointerId !== null) return;
        if (event.button !== undefined && event.button !== 0 && event.button !== 1 && event.button !== 2) return;
        const point = state.renderer.point(event.clientX, event.clientY, { clamp: false });
        if (point[0] < 0) return;

        if (state.scene === "2d" && (state.wasmState >>> 24) === COLLECTED_ALL) {
            state.wasmState = state.game.reset();
            state.score = 0;
            setStatus(SCENE_STATUS["2d"]);
        }

        const pointerId = event.pointerId ?? 0;
        state.activePointerId = pointerId;
        if (typeof canvas.setPointerCapture === "function" && event.pointerId !== undefined) {
            try {
                canvas.setPointerCapture(event.pointerId);
            } catch {
                // Ignore synthetic events without active browser pointerId.
            }
        }
        canvas.classList.add("is-dragging");

        if (state.scene === "3d") {
            orbit.onPointerDown(event.clientX, event.clientY, {
                pointerId,
                shiftKey: Boolean(event.shiftKey),
                button: event.button,
            });
            state.forceRender = true;
        } else {
            state.target = point;
        }
    }

    function onPointerMove(event) {
        const pointerId = event.pointerId ?? 0;
        if (!state.renderer || state.activePointerId === null || pointerId !== state.activePointerId) return;
        if (state.scene === "3d") {
            orbit.onPointerMove(event.clientX, event.clientY, {
                pointerId,
                shiftKey: Boolean(event.shiftKey),
            });
            state.forceRender = true;
        } else {
            state.target = state.renderer.point(event.clientX, event.clientY, { clamp: true });
        }
    }

    function onPointerUp(event) {
        const pointerId = event.pointerId ?? 0;
        if (state.activePointerId === null || pointerId !== state.activePointerId) return;
        if (state.scene === "3d") {
            orbit.onPointerUp(pointerId);
        }
        releaseActivePointer();
    }

    function onWheel(event) {
        if (!state.renderer || state.contextLost || state.scene !== "3d") return;
        event.preventDefault();
        orbit.onWheel(event.deltaY, event.deltaX || 0);
        state.forceRender = true;
    }

    function onDoubleClick() {
        if (state.scene === "3d") resetScene();
    }

    function onContextMenu(event) {
        if (state.scene === "3d") event.preventDefault();
    }

    function onKeyDown(event) {
        if (event.key === "r" || event.key === "R") {
            resetScene();
        }
    }

    function onModeClick(event) {
        const sceneName = event.currentTarget && event.currentTarget.dataset.scene;
        if (sceneName && sceneName !== state.scene) {
            void loadScene(sceneName);
        }
    }

    const resizeObserver = typeof win.ResizeObserver === "function"
        ? new win.ResizeObserver(() => resizeCanvas())
        : null;

    if (canvas) {
        canvas.addEventListener("pointerdown", onPointerDown);
        canvas.addEventListener("pointermove", onPointerMove);
        canvas.addEventListener("pointerup", onPointerUp);
        canvas.addEventListener("pointercancel", onPointerUp);
        canvas.addEventListener("wheel", onWheel, { passive: false });
        canvas.addEventListener("dblclick", onDoubleClick);
        canvas.addEventListener("contextmenu", onContextMenu);
        if (resizeObserver) resizeObserver.observe(canvas);
    }
    if (resetBtn) resetBtn.addEventListener("click", resetScene);
    for (const button of modeButtons) button.addEventListener("click", onModeClick);
    win.addEventListener("resize", resizeCanvas);
    win.addEventListener("keydown", onKeyDown);

    function destroy() {
        state.destroyed = true;
        state.loadToken += 1;
        teardownScene();
        if (resizeObserver) resizeObserver.disconnect();
        if (canvas) {
            canvas.removeEventListener("pointerdown", onPointerDown);
            canvas.removeEventListener("pointermove", onPointerMove);
            canvas.removeEventListener("pointerup", onPointerUp);
            canvas.removeEventListener("pointercancel", onPointerUp);
            canvas.removeEventListener("wheel", onWheel);
            canvas.removeEventListener("dblclick", onDoubleClick);
            canvas.removeEventListener("contextmenu", onContextMenu);
        }
        if (resetBtn) resetBtn.removeEventListener("click", resetScene);
        for (const button of modeButtons) button.removeEventListener("click", onModeClick);
        win.removeEventListener("resize", resizeCanvas);
        win.removeEventListener("keydown", onKeyDown);
    }

    win.addEventListener("pagehide", destroy, { once: true });

    const initialLoad = loadScene(state.scene);
    return {
        ready: initialLoad,
        loadScene,
        reset: resetScene,
        destroy,
        getState: () => ({ ...state, orbit: orbit.getState() }),
    };
}

if (typeof document !== "undefined" && typeof window !== "undefined") {
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", () => createWebApp(document, window), { once: true });
    } else {
        createWebApp(document, window);
    }
}

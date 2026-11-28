const { WebGLCanvas } = require("../../runtime/canvas");
const { loadGame } = require("../../runtime/wasm");
const { mesh } = require("../../runtime/demo");
const hint = mesh ? "拖动画布查看 GLB 模型与贴图。" : "按住或拖动，绕过墙壁收集宝石。";

function locate() {
    return new Promise((resolve, reject) => {
        wx.createSelectorQuery().select("#arena")
            .fields({ node: true, size: true, rect: true })
            .exec(([result]) => {
                if (result && result.node) resolve(result);
                else reject(new Error("找不到 WebGL Canvas"));
            });
    });
}

function loadAtlas(canvas) {
    return new Promise((resolve, reject) => {
        const image = canvas.createImage();
        image.onload = () => resolve(image);
        image.onerror = () => reject(new Error("无法加载角色图集"));
        image.src = "/assets/player.png";
    });
}

function resize(runtime, bounds) {
    runtime.bounds = bounds;
    const screen = typeof wx.getWindowInfo === "function" ? wx.getWindowInfo() : wx.getSystemInfoSync();
    runtime.renderer.resize(bounds, screen.pixelRatio);
    if (mesh) runtime.lastFrame = null;
}

Page({
    data: { collected: 0, ready: false, mesh, status: "正在加载 Nexus…" },

    onLoad() {
        this.runtime = { visible: false, closed: false, contextLost: false, animation: null, lastFrame: null,
            touchId: null, x: -1, y: -1, state: 0, score: 0 };
    },

    async onReady() {
        const runtime = this.runtime;
        try {
            const bounds = await locate();
            if (runtime.closed) return;
            const canvas = bounds.node;
            if (typeof WXWebAssembly === "undefined" || typeof WXWebAssembly.instantiate !== "function") {
                throw new Error("当前微信基础库无法加载 WebAssembly");
            }
            const model = mesh ? wx.getFileSystemManager().readFileSync("assets/crate.glb") : null;
            const [game, atlas] = await Promise.all([
                loadGame((path, imports) => WXWebAssembly.instantiate(path, imports), "/game.wasm", model),
                mesh ? null : loadAtlas(canvas),
            ]);
            if (runtime.closed) return;
            runtime.renderer = new WebGLCanvas(canvas, mesh ? game.model : atlas, 360, 240, mesh, {
                onContextLost: () => this.handleContextLost(),
                onContextRestored: () => this.handleContextRestored(),
            });
            game.model = null;
            resize(runtime, bounds);
            runtime.game = game;
            runtime.state = game.reset();
            this.setData({ ready: true, status: hint });
            this.schedule();
        } catch (error) {
            this.fail(error);
        }
    },

    onShow() {
        this.runtime.visible = true;
        this.schedule();
    },

    onHide() {
        this.runtime.visible = false;
        this.stop();
    },

    onUnload() {
        const runtime = this.runtime;
        runtime.closed = true;
        this.stop();
        if (runtime.renderer) runtime.renderer.close();
    },

    async onResize() {
        const runtime = this.runtime;
        if (!runtime.renderer) return;
        this.releaseTouch();
        try {
            const bounds = await locate();
            if (!runtime.closed) resize(runtime, bounds);
        } catch (error) {
            this.fail(error);
        }
    },

    schedule() {
        const runtime = this.runtime;
        if (runtime.closed || !runtime.visible || runtime.contextLost || !runtime.game || runtime.animation !== null) return;
        runtime.animation = runtime.renderer.canvas.requestAnimationFrame((timestamp) => {
            runtime.animation = null;
            if (!runtime.visible || runtime.closed || runtime.contextLost) return;
            try {
                if (mesh && runtime.lastFrame !== null &&
                    runtime.x === runtime.drawnX && runtime.y === runtime.drawnY) {
                    this.schedule();
                    return;
                }
                const now = Number.isFinite(timestamp) ? timestamp : Date.now();
                const elapsed = runtime.lastFrame === null ? 0 : Math.max(0, now - runtime.lastFrame);
                runtime.lastFrame = now;
                const { state, packet } = runtime.game.advance(runtime.state, runtime.x, runtime.y,
                    Math.round(Math.min(50, elapsed) * 1000));
                runtime.renderer.draw(packet);
                runtime.state = state;
                if (mesh) {
                    runtime.drawnX = runtime.x;
                    runtime.drawnY = runtime.y;
                } else {
                    const mask = (state >>> 24) & 7;
                    const score = (mask & 1) + ((mask >>> 1) & 1) + ((mask >>> 2) & 1);
                    if (score !== runtime.score) {
                        runtime.score = score;
                        this.setData({ collected: score, status: score === 3 ? "宝石已集齐。" : this.data.status });
                    }
                }
                this.schedule();
            } catch (error) {
                this.fail(error);
            }
        });
    },

    handleContextLost() {
        const runtime = this.runtime;
        if (runtime.closed) return;
        runtime.contextLost = true;
        this.stop();
        this.setData({ status: "WebGL 上下文已丢失，等待恢复…" });
    },

    handleContextRestored() {
        const runtime = this.runtime;
        if (runtime.closed) return;
        runtime.contextLost = false;
        runtime.lastFrame = null;
        if (mesh) {
            runtime.drawnX = undefined;
            runtime.drawnY = undefined;
        }
        this.setData({ status: hint });
        this.schedule();
    },

    stop() {
        const runtime = this.runtime;
        if (runtime.animation !== null) runtime.renderer.canvas.cancelAnimationFrame(runtime.animation);
        runtime.animation = null;
        runtime.lastFrame = null;
        this.releaseTouch();
    },

    fail(error) {
        const runtime = this.runtime;
        if (runtime.closed) return;
        this.stop();
        if (runtime.renderer) runtime.renderer.close();
        runtime.renderer = null;
        runtime.game = null;
        this.setData({ ready: false, status: error.message || String(error) });
    },

    resetGame() {
        const runtime = this.runtime;
        if (!runtime.game) return;
        this.releaseTouch();
        runtime.state = runtime.game.reset();
        runtime.score = 0;
        if (mesh) {
            runtime.lastFrame = null;
            runtime.drawnX = undefined;
            runtime.drawnY = undefined;
        }
        this.setData({ collected: 0, status: hint });
    },

    touchStart(event) {
        const runtime = this.runtime;
        if (!runtime.game || runtime.contextLost || runtime.touchId !== null || !event.changedTouches.length) return;
        const touch = event.changedTouches[0];
        const point = this.resolvePoint(touch, false);
        if (point[0] < 0) return;
        runtime.touchId = touch.identifier;
        [runtime.x, runtime.y] = point;
    },

    touchMove(event) {
        const runtime = this.runtime;
        if (!runtime.game || runtime.touchId === null) return;
        const touch = event.changedTouches.find(({ identifier }) => identifier === runtime.touchId);
        if (touch) [runtime.x, runtime.y] = this.resolvePoint(touch, true);
    },

    touchEnd(event) {
        if (event.changedTouches.some(({ identifier }) => identifier === this.runtime.touchId)) this.releaseTouch();
    },

    touchCancel(event) {
        const touches = event && Array.isArray(event.changedTouches) ? event.changedTouches : null;
        if (!touches || !touches.length || touches.some(({ identifier }) => identifier === this.runtime.touchId)) {
            this.releaseTouch();
        }
    },

    releaseTouch() {
        const runtime = this.runtime;
        runtime.touchId = null;
        runtime.x = runtime.y = -1;
    },

    resolvePoint(touch, clamp = false) {
        const runtime = this.runtime;
        const x = Number.isFinite(touch.clientX) ? touch.clientX : runtime.bounds.left + touch.x;
        const y = Number.isFinite(touch.clientY) ? touch.clientY : runtime.bounds.top + touch.y;
        return runtime.renderer.point(x, y, { clamp });
    },
});

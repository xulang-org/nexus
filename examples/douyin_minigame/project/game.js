const { WebGLCanvas } = require("./runtime/canvas");
const { loadGame } = require("./runtime/wasm");
const { mesh } = require("./runtime/demo");

const DESIGN_WIDTH = 360;
const DESIGN_HEIGHT = 240;
const COLLECTED_ALL = 7;

function loadAtlas() {
    return new Promise((resolve, reject) => {
        const bytes = tt.getFileSystemManager().readFileSync("assets/player.png");
        const image = tt.createImage();
        function cleanup() {
            image.removeEventListener("load", loaded);
            image.removeEventListener("error", failed);
        }
        function loaded() {
            cleanup();
            resolve(image);
        }
        function failed() {
            cleanup();
            reject(new Error("无法解码角色图集"));
        }
        image.addEventListener("load", loaded);
        image.addEventListener("error", failed);
        image.src = bytes;
    });
}

async function start() {
    let renderer;
    let game;
    let state;
    let visible = true;
    let contextLost = false;
    let animation = null;
    let lastFrame = null;
    let touchId = null;
    let target = [-1, -1];
    let drawnTarget;

    function releaseTouch() {
        touchId = null;
        target = [-1, -1];
    }

    function stop() {
        if (animation !== null) cancelAnimationFrame(animation);
        animation = null;
        lastFrame = null;
        releaseTouch();
    }

    function fail(error) {
        stop();
        if (renderer) renderer.close();
        renderer = null;
        game = null;
        console.error(error);
        tt.showModal({ title: "Nexus 无法运行", content: error.message || String(error), showCancel: false });
    }

    function resize() {
        const display = tt.getSystemInfoSync();
        renderer.resize({
            left: 0, top: 0,
            width: display.windowWidth || display.screenWidth,
            height: display.windowHeight || display.screenHeight,
        }, display.pixelRatio);
        releaseTouch();
        if (mesh) lastFrame = null;
    }

    function schedule() {
        if (visible && !contextLost && game && animation === null) animation = requestAnimationFrame(draw);
    }

    function draw(timestamp) {
        animation = null;
        if (!visible || contextLost || !game) return;
        try {
            if (mesh && lastFrame !== null && target[0] === drawnTarget[0] && target[1] === drawnTarget[1]) {
                schedule();
                return;
            }
            const now = Number.isFinite(timestamp) ? timestamp : Date.now();
            const elapsed = lastFrame === null ? 0 : Math.max(0, now - lastFrame);
            lastFrame = now;
            const next = game.advance(state, target[0], target[1], Math.round(Math.min(elapsed, 50) * 1000));
            renderer.draw(next.packet);
            if (mesh) drawnTarget = target;
            else if ((state >>> 24) !== COLLECTED_ALL && (next.state >>> 24) === COLLECTED_ALL) {
                tt.showToast({ title: "宝石已集齐，点击重开", icon: "none" });
            }
            state = next.state;
            schedule();
        } catch (error) {
            fail(error);
        }
    }

    function onResize() {
        if (!renderer) return;
        try {
            resize();
        } catch (error) {
            fail(error);
        }
    }

    function touchPoint(touch, clamp = false) {
        const x = Number.isFinite(touch.clientX) ? touch.clientX : touch.pageX;
        const y = Number.isFinite(touch.clientY) ? touch.clientY : touch.pageY;
        return renderer.point(x, y, { clamp });
    }

    try {
        if (typeof TTWebAssembly === "undefined" || typeof TTWebAssembly.instantiate !== "function") {
            throw new Error("当前抖音基础库缺少 TTWebAssembly");
        }
        // The first Canvas created by the host is the on-screen surface.
        const canvas = tt.createCanvas();
        tt.onHide(() => { visible = false; stop(); });
        tt.onShow(() => { visible = true; onResize(); schedule(); });
        if (typeof tt.onDeviceOrientationChange === "function") tt.onDeviceOrientationChange(onResize);
        tt.onTouchStart(({ changedTouches }) => {
            if (!visible || contextLost || !game || touchId !== null || !changedTouches.length) return;
            const touch = changedTouches[0];
            const point = touchPoint(touch, false);
            if (point[0] < 0) return;
            if (!mesh && (state >>> 24) === COLLECTED_ALL) state = game.reset();
            touchId = touch.identifier;
            target = point;
        });
        tt.onTouchMove(({ changedTouches }) => {
            if (!game || touchId === null) return;
            const touch = changedTouches.find((entry) => entry.identifier === touchId);
            if (touch) target = touchPoint(touch, true);
        });
        tt.onTouchEnd(({ changedTouches }) => {
            if (changedTouches.some((entry) => entry.identifier === touchId)) releaseTouch();
        });
        tt.onTouchCancel((event) => {
            const touches = event && Array.isArray(event.changedTouches) ? event.changedTouches : null;
            if (!touches || !touches.length || touches.some((entry) => entry.identifier === touchId)) {
                releaseTouch();
            }
        });
        const model = mesh ? tt.getFileSystemManager().readFileSync("assets/crate.glb") : null;
        const [loadedGame, atlas] = await Promise.all([
            loadGame((path, imports) => TTWebAssembly.instantiate(path, imports), "game.wasm", model),
            mesh ? null : loadAtlas(),
        ]);
        renderer = new WebGLCanvas(canvas, mesh ? loadedGame.model : atlas, DESIGN_WIDTH, DESIGN_HEIGHT, mesh, {
            onContextLost() {
                contextLost = true;
                stop();
            },
            onContextRestored() {
                contextLost = false;
                lastFrame = null;
                drawnTarget = undefined;
                schedule();
            },
        });
        loadedGame.model = null;
        resize();
        game = loadedGame;
        state = game.reset();
        schedule();
    } catch (error) {
        fail(error);
    }
}

start();

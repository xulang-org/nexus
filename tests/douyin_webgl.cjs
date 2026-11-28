const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { createRequire } = require("node:module");
const vm = require("node:vm");

const project = path.join(__dirname, "..", "build", "nexus-douyin");
const entry = path.join(project, "game.js");
const source = fs.readFileSync(entry, "utf8");

function host(hasWasm = true) {
    const callbacks = {};
    const scheduled = new Map();
    const toasts = [];
    const errors = [];
    const frames = [];
    const display = { windowWidth: 840, windowHeight: 390, pixelRatio: 2 };
    const canvasListeners = new Map();
    let frameID = 0;
    let newCanvasCount = 0;
    let vertices;
    let solid;
    let wasmMemory = null;
    const gl = new Proxy({
        getShaderParameter: () => true,
        getProgramParameter: () => true,
        getError: () => 0,
        NO_ERROR: 0,
        createShader: () => ({}),
        createProgram: () => ({}),
        createTexture: () => ({}),
        createBuffer: () => ({}),
        bufferData(_, bytes) { vertices = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength); },
        bufferSubData(_, _offset, bytes) { vertices = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength); },
        drawArrays(_, start, count) {
            if (start === 0) {
                solid = count;
                return;
            }
            assert.equal(count, 6);
            frames.push({ solid, x: vertices.getFloat32(start * 20, true),
                y: vertices.getFloat32(start * 20 + 4, true) });
        },
    }, { get: (object, name) => object[name] ?? (() => {}) });
    const canvas = {
        width: 0,
        height: 0,
        addEventListener(name, cb) {
            if (!canvasListeners.has(name)) canvasListeners.set(name, new Set());
            canvasListeners.get(name).add(cb);
        },
        removeEventListener(name, cb) {
            canvasListeners.get(name)?.delete(cb);
        },
        dispatch(name, event = {}) {
            for (const cb of canvasListeners.get(name) || []) cb(event);
        },
    };
    canvas.getContext = (...args) => { assert.deepEqual(args, ["webgl"]); return gl; };
    const tt = {
        createCanvas() { newCanvasCount += 1; return canvas; },
        getSystemInfoSync: () => display,
        getFileSystemManager: () => ({
            readFileSync(file) {
                assert.equal(file, "assets/player.png");
                const data = fs.readFileSync(path.join(project, file));
                return data.buffer.slice(data.byteOffset, data.byteOffset + data.byteLength);
            },
        }),
        createImage() {
            const listeners = {};
            return {
                addEventListener(name, cb) { listeners[name] = cb; },
                removeEventListener(name) { delete listeners[name]; },
                set src(data) {
                    assert.deepEqual([...new Uint8Array(data, 0, 4)], [137, 80, 78, 71]);
                    queueMicrotask(() => listeners.load());
                },
            };
        },
        showModal({ content }) { errors.push(content); },
        showToast({ title }) { toasts.push(title); },
    };
    for (const event of ["Show", "Hide", "TouchStart", "TouchMove", "TouchEnd", "TouchCancel",
        "DeviceOrientationChange"]) {
        tt["on" + event] = (cb) => { callbacks[event] = cb; };
    }
    const context = {
        require: createRequire(entry), tt, console: { error: () => {} },
        requestAnimationFrame(cb) { scheduled.set(++frameID, cb); return frameID; },
        cancelAnimationFrame(id) { scheduled.delete(id); },
    };
    if (hasWasm) {
        context.TTWebAssembly = {
            async instantiate(file, imports) {
                assert.equal(file, "game.wasm");
                const result = await WebAssembly.instantiate(fs.readFileSync(path.join(project, file)), imports);
                wasmMemory = result.instance.exports.memory;
                return result;
            },
        };
    }
    const ready = vm.runInNewContext(source, context, { filename: entry });
    return { ready, callbacks, canvas, canvasListeners, display, errors, frames, scheduled, toasts,
        memoryBytes: () => wasmMemory ? wasmMemory.buffer.byteLength : 0,
        numCanvases: () => newCanvasCount };
}

async function test() {
    const game = host();
    const { callbacks, canvas, canvasListeners, display, frames, scheduled, toasts } = game;
    callbacks.Hide();
    await game.ready;
    assert.equal(game.numCanvases(), 1);
    assert.equal(scheduled.size, 0, "startup respects a hide during Wasm load");
    assert.deepEqual(game.errors, []);
    assert.ok(game.memoryBytes() > 0, "Wasm linear memory initialized");
    callbacks.Show();
    assert.equal(canvas.width, 1680);
    assert.equal(canvas.height, 780);

    let now = 0;
    function run(count = 1) {
        for (let i = 0; i < count; i += 1) {
            assert.equal(scheduled.size, 1);
            const [[id, frame]] = scheduled;
            scheduled.delete(id);
            frame(now += 16.667);
        }
        return frames.at(-1);
    }
    function touch(event, x = 0, y = 0, identifier = 0) {
        const scale = Math.min(display.windowWidth / 360, display.windowHeight / 240);
        const clientX = (display.windowWidth - 360 * scale) / 2 + x * scale;
        const clientY = (display.windowHeight - 240 * scale) / 2 + y * scale;
        const point = event === "TouchMove" ? { pageX: clientX, pageY: clientY } : { clientX, clientY };
        callbacks[event]({ changedTouches: [{ identifier, ...point }] });
    }

    const initial = run();
    assert.deepEqual(initial, { solid: 60, x: 24, y: 108 });
    const steadyMemory = game.memoryBytes();
    touch("TouchStart", 74, 46);
    touch("TouchMove", 304, 43, 1);
    assert.equal(run(60).solid, 54, "another finger cannot move the active touch");
    touch("TouchMove", 74, 190);
    run(15);
    callbacks.Hide();
    assert.equal(scheduled.size, 0);
    const paused = frames.at(-1);
    callbacks.Show();
    now += 30000;
    const resumed = run(5);
    assert.equal(resumed.solid, paused.solid);
    for (const axis of ["x", "y"]) {
        assert.equal(Math.round(resumed[axis] * 8), Math.round(paused[axis] * 8),
            "resume discards suspended time and the old touch");
    }

    display.windowWidth = 390;
    display.windowHeight = 840;
    callbacks.DeviceOrientationChange();
    assert.equal(canvas.width, 780);
    assert.equal(canvas.height, 1680);
    touch("TouchStart", 74, 190);
    run(70);
    touch("TouchMove", 179, 186);
    assert.equal(run(70).solid, 48);
    touch("TouchMove", 190, 52);
    run(70);
    touch("TouchMove", 304, 43);
    assert.equal(run(80).solid, 42);
    assert.equal(toasts.length, 1);

    touch("TouchEnd");
    touch("TouchStart", 30, 110);
    touch("TouchCancel");
    assert.deepEqual(run(), initial, "a new touch after victory restarts the arena");

    // Clamped dragging: active drag outside letterbox clamps to viewport edge rather than aborting.
    const beforeClampDrag = frames.at(-1);
    touch("TouchStart", 30, 110);
    run(1);
    touch("TouchMove", 30, -140);
    const afterClampDrag = run(10);
    assert.ok(afterClampDrag.y < beforeClampDrag.y,
        "clamped TouchMove outside top letterbox keeps moving upward");
    touch("TouchCancel");
    const afterCancel = run(1);
    const afterCancelNext = run(5);
    assert.equal(afterCancelNext.x, afterCancel.x, "TouchCancel clears active touch");
    assert.equal(afterCancelNext.y, afterCancel.y, "TouchCancel stops movement");

    // WebGL context lost/restored pauses RAF and resumes rendering cleanly.
    assert.ok(canvasListeners.has("webglcontextlost"), "registers webglcontextlost listener");
    assert.ok(canvasListeners.has("webglcontextrestored"), "registers webglcontextrestored listener");
    let prevented = false;
    canvas.dispatch("webglcontextlost", { preventDefault() { prevented = true; } });
    assert.equal(prevented, true, "webglcontextlost calls preventDefault");
    assert.equal(scheduled.size, 0, "webglcontextlost pauses requestAnimationFrame");
    canvas.dispatch("webglcontextrestored", {});
    assert.equal(scheduled.size, 1, "webglcontextrestored resumes requestAnimationFrame");
    run(1);

    assert.equal(game.memoryBytes(), steadyMemory, "Wasm linear memory must not grow across frames");

    const unsupported = host(false);
    await unsupported.ready;
    assert.equal(unsupported.scheduled.size, 0);
    assert.match(unsupported.errors[0], /TTWebAssembly/);
    console.log("PASS: Douyin game.js, clamped drag, context lost/restored, zero memory growth, victory and restart");
}

test().catch((error) => { console.error(error); process.exitCode = 1; });

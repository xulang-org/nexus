const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const root = path.join(__dirname, "..");
const sourceDir = path.join(root, "examples", "webgl_web", "project");
const buildDir = path.join(root, "build", "nexus-web");

function createMockGl() {
    const commands = [];
    let getErrorCalls = 0;
    const gl = new Proxy({
        NO_ERROR: 0,
        COLOR_BUFFER_BIT: 0x4000,
        DEPTH_BUFFER_BIT: 0x0100,
        DEPTH_BITS: 0x0d56,
        DEPTH_TEST: 0x0b71,
        GREATER: 0x0204,
        ARRAY_BUFFER: 0x8892,
        STATIC_DRAW: 0x88e4,
        STREAM_DRAW: 0x88e0,
        FLOAT: 0x1406,
        UNSIGNED_BYTE: 0x1401,
        TRIANGLES: 4,
        BLEND: 0x0be2,
        SRC_ALPHA: 0x0302,
        ONE: 1,
        ONE_MINUS_SRC_ALPHA: 0x0303,
        TEXTURE_2D: 0x0de1,
        TEXTURE_MIN_FILTER: 0x2801,
        TEXTURE_MAG_FILTER: 0x2800,
        TEXTURE_WRAP_S: 0x2802,
        TEXTURE_WRAP_T: 0x2803,
        NEAREST: 0x2600,
        LINEAR: 0x2601,
        CLAMP_TO_EDGE: 0x812f,
        getError: () => { getErrorCalls += 1; return 0; },
        getParameter: (name) => name === 0x0d56 ? 24 : 0,
        getShaderParameter: () => true,
        getProgramParameter: () => true,
        createShader: () => ({}),
        createProgram: () => ({}),
        createTexture: () => ({}),
        createBuffer: () => ({}),
        getUniformLocation: (_prog, name) => ({ name }),
    }, {
        get(object, name) {
            return object[name] ?? ((...args) => { commands.push([name, ...args]); return {}; });
        },
    });
    return {
        gl,
        commands,
        getErrorCount: () => getErrorCalls,
        resetErrorCount: () => { getErrorCalls = 0; },
    };
}

function createMockCanvas(gl) {
    const listeners = new Map();
    return {
        width: 0,
        height: 0,
        listeners,
        getContext(type) {
            assert.equal(type, "webgl");
            return gl;
        },
        addEventListener(name, cb) {
            if (!listeners.has(name)) listeners.set(name, new Set());
            listeners.get(name).add(cb);
        },
        removeEventListener(name, cb) {
            listeners.get(name)?.delete(cb);
        },
        dispatch(name, event = {}) {
            for (const cb of listeners.get(name) || []) cb(event);
        },
    };
}

function matrixToPacket(matrix) {
    if (matrix && matrix.byteLength === 68) return matrix;
    const packet = new Uint8Array(68);
    const view = new DataView(packet.buffer);
    view.setUint32(0, 0x3143584e, true);
    for (let i = 0; i < 16; i += 1) {
        view.setFloat32(4 + i * 4, matrix[i], true);
    }
    return packet;
}

function testSourceAndArtifacts() {
    for (const file of ["index.html", "app.js", "style.css"]) {
        assert.ok(fs.existsSync(path.join(sourceDir, file)), `missing source file ${file}`);
        assert.ok(fs.existsSync(path.join(buildDir, file)), `missing built file ${file}`);
    }
    const html = fs.readFileSync(path.join(buildDir, "index.html"), "utf8");
    for (const ref of [
        "./style.css",
        "./runtime/canvas.js",
        "./runtime/wasm.js",
        "./runtime/demo.js",
        "./app.js",
    ]) {
        assert.ok(html.includes(ref), `index.html missing ${ref}`);
    }
    const appSource = fs.readFileSync(path.join(buildDir, "app.js"), "utf8");
    assert.ok(appSource.includes("./runtime/orbit.js"), "app.js imports OrbitController from ./runtime/orbit.js");
    for (const file of ["game-3d.wasm", "game-2d.wasm", "assets/crate.glb", "assets/player.png",
        "runtime/canvas.js", "runtime/wasm.js", "runtime/orbit.js", "runtime/demo.js"]) {
        assert.ok(fs.existsSync(path.join(buildDir, file)), `missing build artifact ${file}`);
    }
    const demo = require(path.join(buildDir, "runtime", "demo"));
    assert.equal(demo.defaultScene, "3d");
    assert.equal(demo.scenes["3d"].wasm, "game-3d.wasm");
    assert.equal(demo.scenes["2d"].wasm, "game-2d.wasm");
    assert.deepEqual(globalThis.NexusWebGL.demo, demo);
}

function testOrbitController(OrbitController) {
    assert.equal(globalThis.NexusWebGL.OrbitController, OrbitController,
        "OrbitController is exposed on globalThis.NexusWebGL");
    const orbit = new OrbitController({
        target: [0, 0.65, 0],
        distance: 9.2,
        yaw: 0.58,
        pitch: 0.22,
        fov: 0.87,
        far: 40,
        reverseZ: true,
    });
    const initialState = orbit.getState();
    const initialMatrix = Array.from(orbit.getCameraMatrix(360 / 240));
    assert.equal(initialMatrix.length, 16);
    assert.ok(initialMatrix.every(Number.isFinite));

    // Pressing at an off-center point must NOT jump camera angles.
    orbit.onPointerDown(280, 190, { pointerId: 1, button: 0, shiftKey: false });
    orbit.step(0.016);
    assert.equal(orbit.getState().yaw, initialState.yaw, "pointer down alone does not jump yaw");
    assert.equal(orbit.getState().pitch, initialState.pitch, "pointer down alone does not jump pitch");
    assert.deepEqual(Array.from(orbit.getCameraMatrix(360 / 240)), initialMatrix,
        "pointer down alone does not jump camera matrix");

    // Dragging applies smooth relative delta.
    orbit.onPointerMove(340, 220, { pointerId: 1, shiftKey: false });
    orbit.step(0.016);
    const draggedState = orbit.getState();
    assert.notEqual(draggedState.yaw, initialState.yaw, "drag changes yaw");
    assert.notEqual(draggedState.pitch, initialState.pitch, "drag changes pitch");
    const draggedMatrix = Array.from(orbit.getCameraMatrix(360 / 240));
    assert.notDeepEqual(draggedMatrix, initialMatrix);

    // Releasing must preserve orientation (not snap back).
    orbit.onPointerUp(1);
    for (let i = 0; i < 60; i += 1) orbit.step(0.016);
    const settledState = orbit.getState();
    assert.notEqual(settledState.yaw, initialState.yaw, "release preserves rotated yaw");

    // Shift+drag pans target.
    const beforePan = orbit.getState();
    orbit.onPointerDown(200, 150, { pointerId: 2, button: 0, shiftKey: true });
    orbit.onPointerMove(250, 180, { pointerId: 2, shiftKey: true });
    orbit.step(0.016);
    orbit.onPointerUp(2);
    const afterPan = orbit.getState();
    assert.notDeepEqual(afterPan.target, beforePan.target, "Shift+drag pans camera target");

    // Wheel zooms distance.
    const beforeZoom = orbit.getState().distance;
    orbit.onWheel(-120, 0);
    orbit.step(0.016);
    assert.ok(orbit.getState().distance < beforeZoom, "wheel up zooms in");
    orbit.onWheel(240, 0);
    orbit.step(0.016);
    assert.ok(orbit.getState().distance > 0, "wheel down zooms out");

    // Reset restores initial state and matrix.
    orbit.reset();
    orbit.step(0.016);
    assert.deepEqual(orbit.getState(), initialState, "reset restores initial state");
    assert.deepEqual(Array.from(orbit.getCameraMatrix(360 / 240)), initialMatrix,
        "reset restores initial camera matrix");

    // attachCanvas binds and detaches cleanly.
    const { gl } = createMockGl();
    const mockCanvas = createMockCanvas(gl);
    const detach = orbit.attachCanvas(mockCanvas);
    assert.ok(mockCanvas.listeners.has("pointerdown"));
    assert.ok(mockCanvas.listeners.has("wheel"));
    if (typeof detach === "function") {
        detach();
        assert.equal(mockCanvas.listeners.get("pointerdown").size, 0);
    }
    return orbit;
}

async function testWebGLCanvasAndWasm() {
    const { WebGLCanvas } = require(path.join(buildDir, "runtime", "canvas"));
    const { loadGame } = require(path.join(buildDir, "runtime", "wasm"));
    const { OrbitController } = require(path.join(buildDir, "runtime", "orbit"));

    const orbit = testOrbitController(OrbitController);

    // Test 3D Wasm + GLB + WebGLCanvas (drawModel + context lost/restored + zero getError).
    const wasm3d = fs.readFileSync(path.join(buildDir, "game-3d.wasm"));
    const glb = fs.readFileSync(path.join(buildDir, "assets", "crate.glb"));
    const game3d = await loadGame(WebAssembly.instantiate, wasm3d, glb);
    const mem3d = game3d.memoryBytes();
    let state3d = game3d.reset();
    for (let i = 0; i < 60; i += 1) state3d = game3d.advance(state3d, 100 + i, 120, 16667).state;
    assert.equal(game3d.memoryBytes(), mem3d, "3D Wasm linear memory does not grow");

    const mock3d = createMockGl();
    const canvas3d = createMockCanvas(mock3d.gl);
    let lostCount = 0;
    let restoredCount = 0;
    const renderer3d = new WebGLCanvas(canvas3d, game3d.model, 360, 240, true, {
        onContextLost: () => { lostCount += 1; },
        onContextRestored: () => { restoredCount += 1; },
    });
    renderer3d.resize({ left: 0, top: 0, width: 840, height: 400 }, 2);
    assert.deepEqual(renderer3d.point(10, 200), [-1, -1]);
    assert.deepEqual(renderer3d.point(10, 200, { clamp: true }), [0, 120]);
    assert.deepEqual(renderer3d.point(900, 450, { clamp: true }), [359, 239]);

    const cameraPacket = matrixToPacket(orbit.getCameraMatrix(360 / 240));
    mock3d.resetErrorCount();
    for (let i = 0; i < 50; i += 1) {
        renderer3d.draw(cameraPacket);
    }
    assert.equal(mock3d.getErrorCount(), 0, "drawModel hot loop calls gl.getError() zero times");

    let prevented = false;
    canvas3d.dispatch("webglcontextlost", { preventDefault() { prevented = true; } });
    assert.equal(prevented, true);
    assert.equal(lostCount, 1);
    canvas3d.dispatch("webglcontextrestored", {});
    assert.equal(restoredCount, 1);
    mock3d.resetErrorCount();
    renderer3d.draw(cameraPacket);
    assert.equal(mock3d.getErrorCount(), 0, "drawModel after context restore calls gl.getError() zero times");
    renderer3d.close();

    // Test 2D Wasm + WebGLCanvas (draw + zero getError + zero memory growth).
    const wasm2d = fs.readFileSync(path.join(buildDir, "game-2d.wasm"));
    const game2d = await loadGame(WebAssembly.instantiate, wasm2d);
    let state2d = game2d.reset();
    state2d = game2d.advance(state2d, 200, 120, 16667).state;
    const steadyMem2d = game2d.memoryBytes();
    const mock2d = createMockGl();
    const canvas2d = createMockCanvas(mock2d.gl);
    const renderer2d = new WebGLCanvas(canvas2d, { width: 64, height: 16 }, 360, 240, false);
    renderer2d.resize({ left: 0, top: 0, width: 720, height: 480 }, 2);
    mock2d.resetErrorCount();
    for (let i = 0; i < 50; i += 1) {
        const frame = game2d.advance(state2d, 200, 120, 16667);
        state2d = frame.state;
        renderer2d.draw(frame.packet);
    }
    assert.equal(mock2d.getErrorCount(), 0, "2D draw hot loop calls gl.getError() zero times");
    assert.equal(game2d.memoryBytes(), steadyMem2d, "2D Wasm linear memory does not grow after warmup");
    renderer2d.close();
}

function testClassicScriptGlobalIsolation() {
    const context = {};
    context.globalThis = context;
    vm.createContext(context);
    for (const file of ["canvas.js", "wasm.js", "demo.js"]) {
        const script = fs.readFileSync(path.join(buildDir, "runtime", file), "utf8");
        assert.doesNotThrow(
            () => vm.runInContext(script, context, { filename: file }),
            `${file} must load cleanly as a classic <script> in shared global scope`,
        );
    }
    assert.equal(typeof context.NexusWebGL?.WebGLCanvas, "function");
    assert.equal(typeof context.NexusWebGL?.loadGame, "function");
    assert.equal(typeof context.NexusWebGL?.demo, "object");
}

async function run() {
    testSourceAndArtifacts();
    testClassicScriptGlobalIsolation();
    await testWebGLCanvasAndWasm();
    console.log("PASS: webgl_web artifacts, OrbitController, WebGLCanvas context lost/restored, zero getError, zero memory growth");
}

run().catch((error) => {
    console.error(error);
    process.exitCode = 1;
});

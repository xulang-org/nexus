const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const MODEL_HEADER = 20;
const VERTEX_BYTES = 24;

function buildNxm1Model(width, height) {
    const solid = 3;
    const textured = 3;
    const verticesBytes = (solid + textured) * VERTEX_BYTES;
    const total = MODEL_HEADER + verticesBytes + width * height * 4;
    const packet = Buffer.alloc(total);
    packet.write("NXM1", 0, 4, "ascii");
    packet.writeUInt32LE(solid, 4);
    packet.writeUInt32LE(textured, 8);
    packet.writeUInt32LE(width, 12);
    packet.writeUInt32LE(height, 16);
    for (let i = MODEL_HEADER; i < MODEL_HEADER + verticesBytes; i += VERTEX_BYTES) {
        packet.writeUInt8(255, i + 23);
    }
    return packet;
}

function createGlMock(commands) {
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
        FLOAT: 0x1406,
        UNSIGNED_BYTE: 0x1401,
        TRIANGLES: 4,
        TEXTURE_2D: 0x0de1,
        TEXTURE_MIN_FILTER: 0x2801,
        TEXTURE_MAG_FILTER: 0x2800,
        TEXTURE_WRAP_S: 0x2802,
        TEXTURE_WRAP_T: 0x2803,
        NEAREST: 0x2600,
        LINEAR: 0x2601,
        LINEAR_MIPMAP_LINEAR: 0x2703,
        REPEAT: 0x2901,
        CLAMP_TO_EDGE: 0x812f,
        getError: () => { getErrorCalls += 1; return 0; },
        getParameter: (name) => name === 0x0d56 ? 24 : 0,
        getShaderParameter: () => true,
        getProgramParameter: () => true,
    }, {
        get(object, name) {
            return object[name] ?? ((...args) => { commands.push([name, ...args]); return {}; });
        },
    });
    return {
        gl,
        getErrorCount: () => getErrorCalls,
        resetErrorCount: () => { getErrorCalls = 0; },
    };
}

function verifyRenderer(WebGLCanvas, model, first, second) {
    const commands = [];
    const { gl, getErrorCount, resetErrorCount } = createGlMock(commands);
    const canvas = {
        getContext(type, options) {
            assert.equal(type, "webgl");
            assert.deepEqual(options, { depth: true });
            return gl;
        },
    };
    const renderer = new WebGLCanvas(canvas, model, 360, 240, true);
    renderer.resize({ left: 0, top: 0, width: 840, height: 400 }, 2);
    assert.deepEqual(renderer.point(420, 200), [180, 120]);
    assert.deepEqual(renderer.point(20, 200), [-1, -1], "unclamped point outside letterbox returns [-1, -1]");
    assert.deepEqual(renderer.point(20, 200, { clamp: true }), [0, 120],
        "clamped point outside left letterbox clamps to design viewport");
    assert.deepEqual(renderer.point(830, 450, { clamp: true }), [359, 239],
        "clamped point outside bottom-right letterbox clamps to max design coordinate");

    resetErrorCount();
    renderer.draw(first);
    renderer.draw(second);
    assert.equal(getErrorCount(), 0, "draw/drawModel must not call gl.getError() in hot loop");

    const solid = model.readUInt32LE(4);
    for (const expected of [
        ["enable", gl.DEPTH_TEST], ["depthFunc", gl.GREATER], ["clearDepth", 0],
        ["clear", gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT],
        ["vertexAttribPointer", 0, 3, gl.FLOAT, false, VERTEX_BYTES, 0],
        ["vertexAttribPointer", 1, 2, gl.FLOAT, false, VERTEX_BYTES, 12],
        ["vertexAttribPointer", 2, 4, gl.UNSIGNED_BYTE, true, VERTEX_BYTES, 20],
        ["drawArrays", gl.TRIANGLES, 0, solid], ["drawArrays", gl.TRIANGLES, solid, 36],
    ]) {
        assert.ok(commands.some((call) => JSON.stringify(call) === JSON.stringify(expected)), expected[0]);
    }
    const uploads = commands.filter(([name]) => name === "bufferData");
    assert.equal(uploads.length, 1, "camera changes reuse static geometry");
    assert.equal(uploads[0][2].byteLength, (solid + 36) * VERTEX_BYTES);
    assert.equal(uploads[0][3], gl.STATIC_DRAW);
    const images = commands.filter(([name]) => name === "texImage2D");
    assert.equal(images.length, 2, "white and embedded textures are uploaded once");
    assert.deepEqual(images[1].slice(4, 7), [256, 128, 0]);

    const texParams = commands.filter(([name]) => name === "texParameteri");
    assert.ok(texParams.some(([, target, pname, param]) =>
        target === gl.TEXTURE_2D && pname === gl.TEXTURE_MIN_FILTER && param === gl.LINEAR_MIPMAP_LINEAR),
        "POT 3D texture enables trilinear mipmap filtering");
    assert.ok(commands.some(([name, target]) => name === "generateMipmap" && target === gl.TEXTURE_2D),
        "POT 3D texture generates mipmaps");
    assert.ok(texParams.some(([, target, pname, param]) =>
        target === gl.TEXTURE_2D && pname === gl.TEXTURE_WRAP_S && param === gl.REPEAT),
        "POT 3D texture uses REPEAT wrapS");
    assert.ok(texParams.some(([, target, pname, param]) =>
        target === gl.TEXTURE_2D && pname === gl.TEXTURE_WRAP_T && param === gl.REPEAT),
        "POT 3D texture uses REPEAT wrapT");

    assert.equal(commands.filter(([name]) => name === "uniformMatrix4fv").length, 2);
    assert.throws(() => renderer.draw(Buffer.from("NXG3")), /相机帧长度无效/);
    const damaged = Buffer.from(first);
    damaged.writeFloatLE(Infinity, 4);
    assert.throws(() => renderer.draw(damaged), /相机矩阵无效/);
    assert.throws(() => new WebGLCanvas(canvas, model.subarray(0, model.length - 1), 360, 240, true), /模型包格式无效/);
    renderer.close();

    // Verify WebGL1-safe NPOT texture parameters on non-power-of-two model textures.
    const npotCommands = [];
    const npotMock = createGlMock(npotCommands);
    const npotCanvas = { getContext: () => npotMock.gl };
    const npotRenderer = new WebGLCanvas(npotCanvas, buildNxm1Model(100, 75), 360, 240, true);
    const npotTexParams = npotCommands.filter(([name]) => name === "texParameteri");
    assert.ok(npotTexParams.some(([, , pname, param]) =>
        pname === npotMock.gl.TEXTURE_MIN_FILTER && param === npotMock.gl.LINEAR),
        "NPOT textures fall back to LINEAR minification");
    assert.ok(npotTexParams.some(([, , pname, param]) =>
        pname === npotMock.gl.TEXTURE_WRAP_S && param === npotMock.gl.CLAMP_TO_EDGE));
    assert.ok(npotTexParams.some(([, , pname, param]) =>
        pname === npotMock.gl.TEXTURE_WRAP_T && param === npotMock.gl.CLAMP_TO_EDGE));
    assert.ok(!npotTexParams.some(([, , pname, param]) =>
        pname === npotMock.gl.TEXTURE_MIN_FILTER && param === npotMock.gl.LINEAR_MIPMAP_LINEAR),
        "NPOT textures must not use mipmap minification in WebGL1");
    npotRenderer.close();
}

async function platformFrame(name) {
    const root = path.join(__dirname, "..");
    const project = path.join(root, "build", name);
    const { WebGLCanvas } = require(path.join(project, "runtime", "canvas"));
    const { loadGame } = require(path.join(project, "runtime", "wasm"));
    assert.equal(require(path.join(project, "runtime", "demo")).mesh, true);
    const wasm = fs.readFileSync(path.join(project, "game.wasm"));
    const glb = fs.readFileSync(path.join(project, "assets", "crate.glb"));
    assert.equal(glb.toString("ascii", 0, 4), "glTF");
    const jsonEnd = 20 + glb.readUInt32LE(12);
    const document = JSON.parse(glb.toString("utf8", 20, jsonEnd));
    const primitive = document.meshes[0].primitives[0];
    assert.equal(document.accessors[primitive.indices].count, 36);
    const image = document.bufferViews[document.images[0].bufferView];
    const imageStart = jsonEnd + 8 + image.byteOffset;
    assert.deepEqual(glb.subarray(imageStart, imageStart + image.byteLength),
        fs.readFileSync(path.join(root, "examples", "textures3d", "assets", "uv-grid.png")));
    await assert.rejects(loadGame(WebAssembly.instantiate, wasm, glb.subarray(0, 20)));
    await assert.rejects(loadGame(WebAssembly.instantiate, wasm, new Uint8Array(524289)), /GLB 大小/);
    const game = await loadGame(WebAssembly.instantiate, wasm, glb);
    const model = Buffer.from(game.model);
    assert.equal(model.toString("ascii", 0, 4), "NXM1");
    const solid = model.readUInt32LE(4);
    assert.ok(solid > 100 && solid % 3 === 0);
    assert.equal(model.readUInt32LE(8), 36);
    assert.equal(model.readUInt32LE(12), 256);
    assert.equal(model.readUInt32LE(16), 128);
    const modelStart = MODEL_HEADER + solid * VERTEX_BYTES;
    const pixelsAt = modelStart + 36 * VERTEX_BYTES;
    assert.equal(model.length, pixelsAt + 256 * 128 * 4);
    const uvs = new Set();
    for (let i = modelStart; i < pixelsAt; i += VERTEX_BYTES) {
        uvs.add(`${model.readFloatLE(i + 12)},${model.readFloatLE(i + 16)}`);
        assert.equal(model[i + 23], 255);
    }
    assert.deepEqual(uvs, new Set(["0,1", "1,1", "1,0", "0,0"]));
    const colors = new Set();
    for (let i = pixelsAt; i < model.length; i += 4) colors.add(model.readUInt32LE(i));
    assert.ok(colors.size > 4, "GLB produced the nonuniform embedded PNG");

    const initial = game.reset();
    const matrix = Buffer.from(game.advance(initial, -1, -1, 0).packet);
    assert.equal(matrix.toString("ascii", 0, 4), "NXC1");
    assert.equal(matrix.length, 68);
    const pressed = game.advance(initial, 264, 64, 16667);
    const pressedMatrix = Buffer.from(pressed.packet);
    assert.deepEqual(pressedMatrix, matrix, "pressing at an off-center coordinate does not jump camera");
    const dragged = game.advance(pressed.state, 300, 96, 16667);
    const draggedMatrix = Buffer.from(dragged.packet);
    assert.notDeepEqual(draggedMatrix, matrix, "dragging applies relative camera rotation");
    const draggedMore = game.advance(dragged.state, 316, 108, 16667);
    const draggedMoreMatrix = Buffer.from(draggedMore.packet);
    assert.notDeepEqual(draggedMoreMatrix, draggedMatrix, "continued drag smoothly updates camera");
    const released = game.advance(draggedMore.state, -1, -1, 0);
    assert.deepEqual(Buffer.from(released.packet), draggedMoreMatrix,
        "releasing preserves the camera without snapping back");
    const repressed = game.advance(released.state, 50, 180, 16667);
    assert.deepEqual(Buffer.from(repressed.packet), draggedMoreMatrix,
        "pressing again at another off-center coordinate does not jump camera");
    assert.deepEqual(Buffer.from(game.advance(game.reset(), -1, -1, 0).packet), matrix, "reset restores camera");
    const memory = game.memoryBytes();
    let dragState = initial;
    for (let i = 0; i < 300; i += 1) {
        dragState = game.advance(dragState, i % 360, 80 + (i % 40), 16667).state;
    }
    assert.equal(game.memoryBytes(), memory, "camera updates require no additional Wasm pages");
    verifyRenderer(WebGLCanvas, model, matrix, draggedMoreMatrix);
    console.log(`${name}: GLB=${glb.length} B, model=${model.length} B, Wasm=${wasm.length} B, linear memory=${memory} B`);
    return { glb, model, matrix };
}

Promise.all([platformFrame("nexus-miniprogram-3d"), platformFrame("nexus-douyin-3d")])
    .then(([wechat, douyin]) => {
        assert.deepEqual(wechat, douyin);
        console.log("PASS: both 3D hosts decode the same GLB/PNG, reuse static WebGL resources, orbit and reset");
    })
    .catch((error) => { console.error(error); process.exitCode = 1; });

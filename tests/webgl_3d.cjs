const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const MODEL_HEADER = 20;
const VERTEX_BYTES = 24;

function verifyRenderer(WebGLCanvas, model, first, second) {
    const commands = [];
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
        getError: () => 0,
        getParameter: (name) => name === 0x0d56 ? 24 : 0,
        getShaderParameter: () => true,
        getProgramParameter: () => true,
    }, {
        get(object, name) {
            return object[name] ?? ((...args) => { commands.push([name, ...args]); return {}; });
        },
    });
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
    renderer.draw(first);
    renderer.draw(second);
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
    assert.equal(commands.filter(([name]) => name === "uniformMatrix4fv").length, 2);
    assert.throws(() => renderer.draw(Buffer.from("NXG3")), /相机帧长度无效/);
    const damaged = Buffer.from(first);
    damaged.writeFloatLE(Infinity, 4);
    assert.throws(() => renderer.draw(damaged), /相机矩阵无效/);
    assert.throws(() => new WebGLCanvas(canvas, model.subarray(0, model.length - 1), 360, 240, true), /模型包格式无效/);
    renderer.close();
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
    const rotated = game.advance(initial, 264, 64, 16667);
    assert.equal(rotated.state, 264 | (64 << 9));
    const rotatedMatrix = Buffer.from(rotated.packet);
    assert.notDeepEqual(rotatedMatrix, matrix, "touch changes camera projection");
    assert.deepEqual(Buffer.from(game.advance(rotated.state, -1, -1, 0).packet), rotatedMatrix,
        "release preserves the camera");
    assert.deepEqual(Buffer.from(game.advance(game.reset(), -1, -1, 0).packet), matrix, "reset restores camera");
    const memory = game.memoryBytes();
    for (let i = 0; i < 300; i += 1) game.advance(initial, i, 80, 16667);
    assert.equal(game.memoryBytes(), memory, "camera updates require no additional Wasm pages");
    verifyRenderer(WebGLCanvas, model, matrix, rotatedMatrix);
    console.log(`${name}: GLB=${glb.length} B, model=${model.length} B, Wasm=${wasm.length} B, linear memory=${memory} B`);
    return { glb, model, matrix };
}

Promise.all([platformFrame("nexus-miniprogram-3d"), platformFrame("nexus-douyin-3d")])
    .then(([wechat, douyin]) => {
        assert.deepEqual(wechat, douyin);
        console.log("PASS: both 3D hosts decode the same GLB/PNG, reuse static WebGL resources, orbit and reset");
    })
    .catch((error) => { console.error(error); process.exitCode = 1; });

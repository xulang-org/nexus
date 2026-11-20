const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const HEADER_BYTES = 12;
const VERTEX_BYTES = 20;

function verifyRenderer(WebGLCanvas, packet, count) {
    const commands = [];
    const gl = new Proxy({
        NO_ERROR: 0,
        COLOR_BUFFER_BIT: 0x4000,
        DEPTH_BUFFER_BIT: 0x0100,
        DEPTH_BITS: 0x0d56,
        DEPTH_TEST: 0x0b71,
        GREATER: 0x0204,
        ARRAY_BUFFER: 0x8892,
        STREAM_DRAW: 0x88e0,
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
    const renderer = new WebGLCanvas(canvas, null, 360, 240, true);
    renderer.resize({ left: 0, top: 0, width: 840, height: 400 }, 2);
    assert.deepEqual(renderer.point(420, 200), [180, 120]);
    renderer.draw(packet);
    for (const expected of [
        ["enable", gl.DEPTH_TEST], ["depthFunc", gl.GREATER], ["clearDepth", 0],
        ["clear", gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT],
        ["vertexAttribPointer", 0, 4, gl.FLOAT, false, VERTEX_BYTES, 0],
        ["vertexAttribPointer", 2, 4, gl.UNSIGNED_BYTE, true, VERTEX_BYTES, 16],
        ["drawArrays", gl.TRIANGLES, 0, count],
    ]) {
        assert.ok(commands.some((call) => JSON.stringify(call) === JSON.stringify(expected)), expected[0]);
    }
    const damaged = Buffer.from(packet);
    damaged[3] = "1".charCodeAt(0);
    assert.throws(() => renderer.draw(damaged), /帧格式无效/);
    renderer.close();
}

async function platformFrame(name) {
    const project = path.join(__dirname, "..", "build", name);
    const { WebGLCanvas } = require(path.join(project, "runtime", "canvas"));
    const { loadGame } = require(path.join(project, "runtime", "wasm"));
    assert.equal(require(path.join(project, "runtime", "demo")).mesh, true);
    const game = await loadGame(WebAssembly.instantiate, fs.readFileSync(path.join(project, "game.wasm")));
    const initial = game.reset();
    const packet = Buffer.from(game.advance(initial, -1, -1, 0).packet);
    assert.equal(packet.toString("ascii", 0, 4), "NXG3");
    const count = packet.readUInt32LE(4);
    assert.ok(count > 100 && count % 3 === 0);
    assert.equal(packet.readUInt32LE(8), 0);
    assert.equal(packet.length, HEADER_BYTES + count * VERTEX_BYTES);
    const depth = new Set();
    for (let offset = HEADER_BYTES; offset < packet.length; offset += VERTEX_BYTES) {
        const x = packet.readFloatLE(offset);
        const y = packet.readFloatLE(offset + 4);
        const z = packet.readFloatLE(offset + 8);
        const w = packet.readFloatLE(offset + 12);
        assert.ok([x, y, z, w].every(Number.isFinite));
        assert.ok(w > 0 && z > -w && z < w);
        assert.equal(packet[offset + 19], 255);
        depth.add(z / w);
    }
    assert.ok(depth.size > 20, "perspective uses distinct depths");

    const rotated = game.advance(initial, 264, 64, 16667);
    assert.equal(rotated.state, 264 | (64 << 9));
    const rotatedPacket = Buffer.from(rotated.packet);
    assert.notDeepEqual(rotatedPacket, packet, "touch changes the camera projection");
    assert.deepEqual(Buffer.from(game.advance(rotated.state, -1, -1, 0).packet), rotatedPacket,
        "release preserves the camera");
    assert.deepEqual(Buffer.from(game.advance(game.reset(), -1, -1, 0).packet), packet,
        "reset restores the camera");
    verifyRenderer(WebGLCanvas, packet, count);
    return packet;
}

Promise.all([platformFrame("nexus-miniprogram-3d"), platformFrame("nexus-douyin-3d")])
    .then(([wechat, douyin]) => {
        assert.deepEqual(wechat, douyin);
        console.log("PASS: shared 3D Wasm mesh, perspective, reverse-Z WebGL state, touch orbit and reset");
    })
    .catch((error) => { console.error(error); process.exitCode = 1; });

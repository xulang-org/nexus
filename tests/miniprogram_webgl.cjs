const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const project = path.join(__dirname, "..", "build", "nexus-miniprogram");
const { loadGame } = require(path.join(project, "runtime", "wasm"));

async function test() {
    const bytes = fs.readFileSync(path.join(project, "game.wasm"));
    const game = await loadGame(WebAssembly.instantiate, bytes);
    let state = game.reset();

    const advance = (x, y, frames, delta = 16667) => {
        let packet;
        for (let i = 0; i < frames; i += 1) {
            ({ state, packet } = game.advance(state, x, y, delta));
        }
        const view = new DataView(packet.buffer, packet.byteOffset, packet.length);
        assert.equal(view.getUint32(0, true), 0x3147584e);
        assert.equal(view.getUint32(8, true), 6);
        const solid = view.getUint32(4, true);
        assert.equal(packet.length, 12 + (solid + 6) * 20);
        const sprite = 12 + solid * 20;
        assert.equal(view.getFloat32(sprite, true), (state & 4095) / 8);
        assert.equal(view.getFloat32(sprite + 4, true), ((state >>> 12) & 4095) / 8);
        assert.equal(view.getFloat32(sprite + 20 + 8, true), 0.25);
        assert.deepEqual([...packet.subarray(sprite + 16, sprite + 20)], [255, 255, 255, 255]);
        return solid;
    };
    assert.equal(advance(-1, -1, 1), 60);
    advance(190, 117, 100);
    assert.equal((state & 4095) / 8, 96, "wall stops the player");
    state = game.reset();
    assert.equal(advance(74, 46, 60), 54);
    assert.equal(state >>> 24, 1, "collect the first gem and hide its geometry");
    advance(74, 190, 70);
    advance(179, 186, 70);
    assert.equal(state >>> 24, 3);
    advance(190, 52, 70);
    assert.equal(advance(304, 43, 80), 42);
    assert.equal(state >>> 24, 7);
    const paused = state;
    advance(-1, -1, 1000);
    assert.equal(state, paused, "released touch keeps the player still");
    assert.equal(game.reset() >>> 24, 0);
    console.log("PASS: repeated Wasm steps, WebGL packet layout, texture UVs, walls and all three gems");
}

test().catch((error) => { console.error(error); process.exitCode = 1; });

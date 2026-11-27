#!/usr/bin/env node
"use strict";

const fs = require("node:fs");
const path = require("node:path");
const { performance } = require("node:perf_hooks");

function percentiles(samples) {
    samples.sort((a, b) => a - b);
    return Object.fromEntries([50, 95, 99].map(percent => [
        `p${percent}`, Number(samples[Math.ceil(samples.length * percent / 100) - 1].toFixed(6)),
    ]));
}

async function sample(project) {
    const { loadGame } = require(path.join(project, "runtime", "wasm"));
    const wasm = fs.readFileSync(path.join(project, "game.wasm"));
    const glb = fs.readFileSync(path.join(project, "assets", "crate.glb"));
    const started = performance.now();
    const game = await loadGame(WebAssembly.instantiate, wasm, glb);
    const startupMs = performance.now() - started;
    let state = game.reset();
    for (let i = 0; i < 300; i += 1) state = game.advance(state, i % 320, 80, 16667).state;
    const initialMemory = game.memoryBytes();
    const samples = [];
    for (let i = 0; i < 3000; i += 1) {
        const before = performance.now();
        const frame = game.advance(state, i % 320, 80, 16667);
        samples.push(performance.now() - before);
        state = frame.state;
    }
    if (game.memoryBytes() !== initialMemory) throw new Error("Wasm memory grew after warmup");
    return { project: path.basename(project), sample_frames: samples.length, warmup_frames: 300,
        wasm_bytes: wasm.length, glb_bytes: glb.length, wasm_linear_memory_bytes: initialMemory,
        wasm_load_ms: Number(startupMs.toFixed(4)), wasm_frame_ms: percentiles(samples) };
}

async function run() {
    const results = [];
    for (const name of ["nexus-miniprogram-3d", "nexus-douyin-3d"]) {
        results.push(await sample(path.resolve("build", name)));
    }
    const report = JSON.stringify({ runtime: process.version, platform: process.platform,
        arch: process.arch, workload: "Wasm 3D orbit and packet generation", results }, null, 2) + "\n";
    fs.mkdirSync("build/nexus-benchmark", { recursive: true });
    fs.writeFileSync("build/nexus-benchmark/webgl-wasm.json", report);
    process.stdout.write(report);
}

run().catch(error => { console.error(error); process.exitCode = 1; });

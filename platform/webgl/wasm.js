(function () {
"use strict";
const _canvasModule = typeof require === "function"
    ? require("./canvas")
    : (typeof globalThis !== "undefined" && globalThis.NexusWebGL ? globalThis.NexusWebGL : {});

const MAX_FRAME_BYTES = _canvasModule.MAX_FRAME_BYTES ?? (12 + 20 * 65532);
const MAX_MODEL_BYTES = _canvasModule.MAX_MODEL_BYTES ?? (20 + 24 * 65532 + 256 * 256 * 4);
const CAMERA_BYTES = _canvasModule.CAMERA_BYTES ?? 68;

// Xu's wasm32-wasi module declares the Preview 1 imports up front. This host
// supplies the packaged GLB on stdin, packet output and no arguments/environment. Other services
// return ENOSYS so programs cannot mistake an unavailable service for success.
const UNSUPPORTED = [
    "clock_time_get", "fd_close", "fd_seek", "fd_filestat_get",
    "fd_readdir", "fd_prestat_get", "fd_prestat_dir_name", "path_create_directory",
    "path_filestat_get", "path_open", "path_readlink", "path_remove_directory",
    "path_rename", "path_symlink", "path_unlink_file", "poll_oneoff", "random_get",
    "sched_yield", "fd_fdstat_get",
];

function fits(buffer, offset, size) {
    return offset >= 0 && size >= 0 && offset <= buffer.byteLength - size;
}

async function loadGame(instantiate, source, modelBytes = null) {
    let memory = null;
    let cachedBuffer = null;
    let cachedView = null;
    let cachedBytes = null;

    function syncMemory() {
        const buffer = memory.buffer;
        if (buffer !== cachedBuffer) {
            cachedBuffer = buffer;
            cachedView = new DataView(buffer);
            cachedBytes = new Uint8Array(buffer);
        }
        return cachedBuffer;
    }

    let input = modelBytes === null ? null : new Uint8Array(modelBytes);
    if (input && (input.byteLength < 1 || input.byteLength > 524288)) {
        throw new Error("Nexus GLB 大小超出范围");
    }
    let inputOffset = 0;
    let packet = new Uint8Array(input ? MAX_MODEL_BYTES : MAX_FRAME_BYTES);
    let length = 0;
    let diagnostic = "";
    let destroyed = false;

    function zeroSizes(count, size) {
        const buffer = syncMemory();
        if (!fits(buffer, count, 4) || !fits(buffer, size, 4)) return 21;
        cachedView.setUint32(count, 0, true);
        cachedView.setUint32(size, 0, true);
        return 0;
    }

    const wasi = {
        args_get: () => 0,
        environ_get: () => 0,
        args_sizes_get: zeroSizes,
        environ_sizes_get: zeroSizes,
        proc_exit(status) {
            if (status !== 0) throw new Error(diagnostic.trim() || "Xu 退出（" + status + "）");
        },
        fd_read(fd, iovs, count, result) {
            if (fd !== 0 || !input) return 8;
            const buffer = syncMemory();
            if (!fits(buffer, result, 4) || count < 0 || count > 16 ||
                !fits(buffer, iovs, count * 8)) return 21;
            const view = cachedView;
            for (let i = 0; i < count; i += 1) {
                if (!fits(buffer, view.getUint32(iovs + i * 8, true), view.getUint32(iovs + i * 8 + 4, true))) return 21;
            }
            const start = inputOffset;
            for (let i = 0; i < count && inputOffset < input.length; i += 1) {
                const ptr = view.getUint32(iovs + i * 8, true);
                const size = Math.min(view.getUint32(iovs + i * 8 + 4, true), input.length - inputOffset);
                if (size > 0) {
                    cachedBytes.set(input.subarray(inputOffset, inputOffset + size), ptr);
                    inputOffset += size;
                }
            }
            view.setUint32(result, inputOffset - start, true);
            return 0;
        },
        fd_write(fd, iovs, count, result) {
            if (fd !== 1 && fd !== 2) return 8; // EBADF
            const buffer = syncMemory();
            if (!fits(buffer, result, 4) || count < 0 || count > 16 ||
                !fits(buffer, iovs, count * 8)) return 21; // EFAULT
            const view = cachedView;
            let written = 0;
            for (let i = 0; i < count; i += 1) {
                const ptr = view.getUint32(iovs + i * 8, true);
                const size = view.getUint32(iovs + i * 8 + 4, true);
                if (!fits(buffer, ptr, size)) return 21;
                if (fd === 1) {
                    if (!packet || size > packet.byteLength - length) {
                        throw new Error("Nexus WebGL 帧超出缓冲区");
                    }
                    if (size > 0) {
                        packet.set(cachedBytes.subarray(ptr, ptr + size), length);
                        length += size;
                    }
                } else {
                    for (let at = 0; at < size && diagnostic.length < 1024; at += 1) {
                        diagnostic += String.fromCharCode(cachedBytes[ptr + at]);
                    }
                }
                written += size;
            }
            view.setUint32(result, written, true);
            return 0;
        },
    };
    for (const name of UNSUPPORTED) wasi[name] = () => 52; // ENOSYS

    const { instance } = await instantiate(source, { wasi_snapshot_preview1: wasi });
    const api = instance.exports;
    memory = api.memory;
    syncMemory();
    api._start();

    let model = null;
    if (input) {
        if (typeof api.nexus_load_model !== "function" || api.nexus_load_model(input.length) !== 0 ||
            inputOffset !== input.length || length === 0) {
            throw new Error(diagnostic.trim() || "Xu 无法加载 GLB");
        }
        model = packet.slice(0, length);
        input = null;
        packet = new Uint8Array(CAMERA_BYTES);
        length = 0;
    }

    return {
        model,
        memoryBytes: () => (memory ? memory.buffer.byteLength : 0),
        packetBytes: () => length,
        isDestroyed: () => destroyed,
        reset() {
            if (destroyed) throw new Error("Nexus Wasm 实例已销毁");
            length = 0;
            diagnostic = "";
            return api.nexus_reset();
        },
        advance(state, x, y, delta) {
            if (destroyed) throw new Error("Nexus Wasm 实例已销毁");
            length = 0;
            diagnostic = "";
            const next = api.nexus_frame(state, x, y, delta);
            if (next < 0 || length === 0 || length > packet.byteLength) {
                throw new Error(diagnostic.trim() || "Xu 未生成 WebGL 帧");
            }
            return { state: next, packet: packet.subarray(0, length) };
        },
        destroy() {
            destroyed = true;
            input = null;
            packet = null;
            model = null;
            memory = null;
            cachedBuffer = null;
            cachedView = null;
            cachedBytes = null;
            length = 0;
            diagnostic = "";
        },
    };
}

const exported = { loadGame };

if (typeof globalThis !== "undefined") {
    globalThis.NexusWebGL = Object.assign(globalThis.NexusWebGL || {}, exported);
}
if (typeof module !== "undefined" && module.exports) {
    module.exports = exported;
}
})();

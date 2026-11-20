const { MAX_FRAME_BYTES } = require("./canvas");

// Xu's wasm32-wasi module declares the Preview 1 imports up front. This host
// only supplies frame output and zero arguments/environment. Other services
// return ENOSYS so programs cannot mistake an unavailable service for success.
const UNSUPPORTED = [
    "clock_time_get", "fd_close", "fd_read", "fd_seek", "fd_filestat_get",
    "fd_readdir", "fd_prestat_get", "fd_prestat_dir_name", "path_create_directory",
    "path_filestat_get", "path_open", "path_readlink", "path_remove_directory",
    "path_rename", "path_symlink", "path_unlink_file", "poll_oneoff", "random_get",
    "sched_yield", "fd_fdstat_get",
];

async function loadGame(instantiate, source) {
    let memory;
    const packet = new Uint8Array(MAX_FRAME_BYTES);
    let length = 0;
    let diagnostic = "";
    const wasi = {
        args_get: () => 0,
        environ_get: () => 0,
        args_sizes_get: zeroSizes,
        environ_sizes_get: zeroSizes,
        proc_exit(status) {
            if (status !== 0) throw new Error(diagnostic.trim() || "Xu 退出（" + status + "）");
        },
        fd_write(fd, iovs, count, result) {
            if (fd !== 1 && fd !== 2) return 8; // EBADF
            const buffer = memory.buffer;
            if (!fits(buffer, result, 4) || count < 0 || count > 16 ||
                !fits(buffer, iovs, count * 8)) return 21; // EFAULT
            const view = new DataView(buffer);
            let written = 0;
            for (let i = 0; i < count; i += 1) {
                const ptr = view.getUint32(iovs + i * 8, true);
                const size = view.getUint32(iovs + i * 8 + 4, true);
                if (!fits(buffer, ptr, size)) return 21;
                const chunk = new Uint8Array(buffer, ptr, size);
                if (fd === 1) {
                    if (size > packet.length - length) throw new Error("Nexus WebGL 帧超出缓冲区");
                    packet.set(chunk, length);
                    length += size;
                } else {
                    for (let at = 0; at < chunk.length && diagnostic.length < 1024; at += 1) {
                        diagnostic += String.fromCharCode(chunk[at]);
                    }
                }
                written += size;
            }
            view.setUint32(result, written, true);
            return 0;
        },
    };
    for (const name of UNSUPPORTED) wasi[name] = () => 52; // ENOSYS

    function zeroSizes(count, size) {
        const buffer = memory.buffer;
        if (!fits(buffer, count, 4) || !fits(buffer, size, 4)) return 21;
        const view = new DataView(buffer);
        view.setUint32(count, 0, true);
        view.setUint32(size, 0, true);
        return 0;
    }

    const { instance } = await instantiate(source, { wasi_snapshot_preview1: wasi });
    const api = instance.exports;
    memory = api.memory;
    api._start();
    return {
        reset: () => api.nexus_reset(),
        advance(state, x, y, delta) {
            length = 0;
            diagnostic = "";
            const next = api.nexus_frame(state, x, y, delta);
            if (next < 0 || length === 0) {
                throw new Error(diagnostic.trim() || "Xu 未生成 WebGL 帧");
            }
            return { state: next, packet: packet.subarray(0, length) };
        },
    };
}

function fits(buffer, offset, size) {
    return offset >= 0 && size >= 0 && offset <= buffer.byteLength - size;
}

module.exports = { loadGame };

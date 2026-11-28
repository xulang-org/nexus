const DEFAULT_MIN_PITCH = -1.45;
const DEFAULT_MAX_PITCH = 1.45;
const DEFAULT_MIN_DISTANCE = 1.5;
const DEFAULT_MAX_DISTANCE = 40.0;

function clamp(value, min, max) {
    return value < min ? min : (value > max ? max : value);
}

function finiteOr(value, fallback) {
    return Number.isFinite(value) ? value : fallback;
}

function normalize3(x, y, z) {
    const len = Math.hypot(x, y, z);
    if (!(len > 0)) return [0, 0, 0];
    return [x / len, y / len, z / len];
}

function cross3(ax, ay, az, bx, by, bz) {
    return [
        ay * bz - az * by,
        az * bx - ax * bz,
        ax * by - ay * bx,
    ];
}

function computeCameraBasis(yaw, pitch) {
    const cp = Math.cos(pitch);
    const sp = Math.sin(pitch);
    const sy = Math.sin(yaw);
    const cy = Math.cos(yaw);
    // Offset from target to eye: rotation_y(yaw) * rotation_x(-pitch) * (0, 0, 1).
    const backX = cp * sy;
    const backY = sp;
    const backZ = cp * cy;
    // Camera right = normalize(up(0,1,0) x back) = normalize(backZ, 0, -backX).
    const right = normalize3(backZ, 0, -backX);
    const up = cross3(backX, backY, backZ, right[0], right[1], right[2]);
    return { back: [backX, backY, backZ], right, up };
}

/**
 * Relative-delta 3D orbit, pan, and zoom camera controller with inertia damping.
 */
export class OrbitController {
    constructor(options = {}) {
        const minPitch = finiteOr(options.minPitch, DEFAULT_MIN_PITCH);
        const maxPitch = finiteOr(options.maxPitch, DEFAULT_MAX_PITCH);
        const minDistance = Math.max(0.05, finiteOr(options.minDistance, DEFAULT_MIN_DISTANCE));
        const maxDistance = Math.max(minDistance, finiteOr(options.maxDistance, DEFAULT_MAX_DISTANCE));
        const targetSrc = Array.isArray(options.target) && options.target.length >= 3
            ? options.target
            : [0, 0.65, 0];

        this.minPitch = Math.min(minPitch, maxPitch);
        this.maxPitch = Math.max(minPitch, maxPitch);
        this.minDistance = minDistance;
        this.maxDistance = maxDistance;

        this.yaw = finiteOr(options.yaw, 0.58);
        this.pitch = clamp(finiteOr(options.pitch, 0.45), this.minPitch, this.maxPitch);
        this.distance = clamp(finiteOr(options.distance, 9.2), this.minDistance, this.maxDistance);
        this.target = [
            finiteOr(targetSrc[0], 0),
            finiteOr(targetSrc[1], 0.65),
            finiteOr(targetSrc[2], 0),
        ];

        this.fov = clamp(finiteOr(options.fov, 0.87), 0.05, 3.0);
        this.near = Math.max(0.001, finiteOr(options.near, 0.1));
        this.far = Math.max(this.near + 0.1, finiteOr(options.far, 40.0));
        this.rotateSpeed = finiteOr(options.rotateSpeed, 0.008);
        this.panSpeed = finiteOr(options.panSpeed, 0.002);
        this.zoomSpeed = finiteOr(options.zoomSpeed, 0.0015);
        this.damping = clamp(finiteOr(options.damping, 0.88), 0, 0.999);
        this.inertia = options.inertia !== false;
        this.reverseZ = Boolean(options.reverseZ);

        this._initial = {
            yaw: this.yaw,
            pitch: this.pitch,
            distance: this.distance,
            target: [this.target[0], this.target[1], this.target[2]],
        };

        this._pointers = new Map();
        this._mode = "none";
        this._lastX = 0;
        this._lastY = 0;
        this._lastPinchDist = 0;
        this._lastPinchMidX = 0;
        this._lastPinchMidY = 0;

        this._velYaw = 0;
        this._velPitch = 0;
        this._velPanX = 0;
        this._velPanY = 0;
        this._velPanZ = 0;

        this._matrix = new Float32Array(16);
    }

    /**
     * Records the initial pointer anchor without modifying camera angles or target.
     */
    onPointerDown(x, y, options = {}) {
        if (!Number.isFinite(x) || !Number.isFinite(y)) return;
        const pointerId = options.pointerId ?? 0;
        this._pointers.set(pointerId, { x, y });
        this._clearVelocity();

        if (this._pointers.size === 1) {
            const isPan = Boolean(options.shiftKey) || options.button === 1 || options.button === 2 || options.mode === "pan";
            this._mode = isPan ? "pan" : "orbit";
            this._lastX = x;
            this._lastY = y;
        } else if (this._pointers.size >= 2) {
            this._mode = "pinch";
            this._syncPinchAnchor();
        }
    }

    /**
     * Applies relative pointer motion for orbit, Shift/2-finger pan, or pinch zoom.
     */
    onPointerMove(x, y, options = {}) {
        if (!Number.isFinite(x) || !Number.isFinite(y)) return false;
        const pointerId = options.pointerId ?? 0;
        if (!this._pointers.has(pointerId)) return false;
        this._pointers.set(pointerId, { x, y });

        if (this._pointers.size === 1) {
            const dx = x - this._lastX;
            const dy = y - this._lastY;
            this._lastX = x;
            this._lastY = y;
            if (dx === 0 && dy === 0) return false;

            const isPan = Boolean(options.shiftKey) || this._mode === "pan" || options.mode === "pan";
            if (isPan) {
                this._applyPanDelta(dx, dy, true);
            } else {
                const dYaw = -dx * this.rotateSpeed;
                const dPitch = dy * this.rotateSpeed;
                this.yaw += dYaw;
                this.pitch = clamp(this.pitch + dPitch, this.minPitch, this.maxPitch);
                this._velYaw = dYaw;
                this._velPitch = dPitch;
                this._velPanX = 0;
                this._velPanY = 0;
                this._velPanZ = 0;
            }
            return true;
        }

        const pair = this._firstTwoPointers();
        if (!pair) return false;
        const [a, b] = pair;
        const dist = Math.hypot(b.x - a.x, b.y - a.y);
        const midX = (a.x + b.x) * 0.5;
        const midY = (a.y + b.y) * 0.5;
        let changed = false;

        if (this._lastPinchDist > 1 && dist > 1) {
            const scale = this._lastPinchDist / dist;
            const nextDistance = clamp(this.distance * scale, this.minDistance, this.maxDistance);
            if (nextDistance !== this.distance) {
                this.distance = nextDistance;
                changed = true;
            }
        }
        const panDx = midX - this._lastPinchMidX;
        const panDy = midY - this._lastPinchMidY;
        if (panDx !== 0 || panDy !== 0) {
            this._applyPanDelta(panDx, panDy, false);
            changed = true;
        }

        this._lastPinchDist = dist;
        this._lastPinchMidX = midX;
        this._lastPinchMidY = midY;
        return changed;
    }

    onPointerUp(pointerId = 0) {
        if (arguments.length === 0 && this._pointers.size === 1) {
            this._pointers.clear();
        } else {
            this._pointers.delete(pointerId);
        }

        if (this._pointers.size >= 2) {
            this._mode = "pinch";
            this._syncPinchAnchor();
        } else if (this._pointers.size === 1) {
            const [remaining] = this._pointers.values();
            this._mode = "orbit";
            this._lastX = remaining.x;
            this._lastY = remaining.y;
            this._clearVelocity();
        } else {
            this._mode = "none";
        }
    }

    onWheel(deltaY, _deltaX = 0) {
        if (!Number.isFinite(deltaY) || deltaY === 0) return false;
        const clampedDelta = clamp(deltaY, -500, 500);
        const nextDistance = clamp(this.distance * Math.exp(clampedDelta * this.zoomSpeed), this.minDistance, this.maxDistance);
        if (nextDistance === this.distance) return false;
        this.distance = nextDistance;
        return true;
    }

    /**
     * Advances damped inertia when no pointers are held. Returns true if state changed.
     */
    step(dtSeconds = 1 / 60) {
        if (!this.inertia || this._pointers.size > 0) return false;
        const dt = Number.isFinite(dtSeconds) && dtSeconds > 0 ? dtSeconds : 0;
        if (dt === 0) return false;

        let changed = false;
        const decay = Math.pow(this.damping, dt * 60);
        if (Math.abs(this._velYaw) > 1e-5 || Math.abs(this._velPitch) > 1e-5) {
            this.yaw += this._velYaw;
            this.pitch = clamp(this.pitch + this._velPitch, this.minPitch, this.maxPitch);
            this._velYaw *= decay;
            this._velPitch *= decay;
            if (Math.abs(this._velYaw) <= 1e-5) this._velYaw = 0;
            if (Math.abs(this._velPitch) <= 1e-5) this._velPitch = 0;
            changed = true;
        }
        if (Math.abs(this._velPanX) > 1e-5 || Math.abs(this._velPanY) > 1e-5 || Math.abs(this._velPanZ) > 1e-5) {
            this.target[0] += this._velPanX;
            this.target[1] += this._velPanY;
            this.target[2] += this._velPanZ;
            this._velPanX *= decay;
            this._velPanY *= decay;
            this._velPanZ *= decay;
            if (Math.abs(this._velPanX) <= 1e-5) this._velPanX = 0;
            if (Math.abs(this._velPanY) <= 1e-5) this._velPanY = 0;
            if (Math.abs(this._velPanZ) <= 1e-5) this._velPanZ = 0;
            changed = true;
        }
        return changed;
    }

    update(dtSeconds = 1 / 60) {
        return this.step(dtSeconds);
    }

    reset() {
        this.yaw = this._initial.yaw;
        this.pitch = this._initial.pitch;
        this.distance = this._initial.distance;
        this.target[0] = this._initial.target[0];
        this.target[1] = this._initial.target[1];
        this.target[2] = this._initial.target[2];
        this._pointers.clear();
        this._mode = "none";
        this._clearVelocity();
    }

    getEyePosition() {
        const { back } = computeCameraBasis(this.yaw, this.pitch);
        return [
            this.target[0] + back[0] * this.distance,
            this.target[1] + back[1] * this.distance,
            this.target[2] + back[2] * this.distance,
        ];
    }

    getState() {
        return {
            yaw: this.yaw,
            pitch: this.pitch,
            distance: this.distance,
            target: [this.target[0], this.target[1], this.target[2]],
            eye: this.getEyePosition(),
            dragging: this._pointers.size > 0,
            mode: this._mode,
        };
    }

    /**
     * Writes a column-major Float32Array(16) projection * view matrix.
     */
    getCameraMatrix(aspect = 1.5, out = this._matrix, options = {}) {
        const validAspect = Number.isFinite(aspect) && aspect > 0 ? aspect : 1.5;
        const targetOut = out instanceof Float32Array && out.length >= 16 ? out : this._matrix;
        const useReverseZ = options.reverseZ !== undefined ? Boolean(options.reverseZ) : this.reverseZ;

        const { back, right, up } = computeCameraBasis(this.yaw, this.pitch);
        const eyeX = this.target[0] + back[0] * this.distance;
        const eyeY = this.target[1] + back[1] * this.distance;
        const eyeZ = this.target[2] + back[2] * this.distance;

        // View matrix rows: [right, -dot(right, eye)], [up, -dot(up, eye)], [back, -dot(back, eye)], [0,0,0,1].
        const tx = -(right[0] * eyeX + right[1] * eyeY + right[2] * eyeZ);
        const ty = -(up[0] * eyeX + up[1] * eyeY + up[2] * eyeZ);
        const tz = -(back[0] * eyeX + back[1] * eyeY + back[2] * eyeZ);

        const f = 1.0 / Math.tan(this.fov * 0.5);
        const fx = f / validAspect;
        const invRange = 1.0 / (this.far - this.near);
        const p22 = useReverseZ ? (this.far + this.near) * invRange : -(this.far + this.near) * invRange;
        const p32 = useReverseZ ? (2.0 * this.far * this.near) * invRange : -(2.0 * this.far * this.near) * invRange;

        // Column 0..3 = P * V (column-major).
        targetOut[0] = fx * right[0];
        targetOut[1] = f * up[0];
        targetOut[2] = p22 * back[0];
        targetOut[3] = -back[0];

        targetOut[4] = fx * right[1];
        targetOut[5] = f * up[1];
        targetOut[6] = p22 * back[1];
        targetOut[7] = -back[1];

        targetOut[8] = fx * right[2];
        targetOut[9] = f * up[2];
        targetOut[10] = p22 * back[2];
        targetOut[11] = -back[2];

        targetOut[12] = fx * tx;
        targetOut[13] = f * ty;
        targetOut[14] = p22 * tz + p32;
        targetOut[15] = -tz;

        return targetOut;
    }

    /**
     * Attaches pointer, wheel, and double-click listeners to a canvas element.
     * Returns a detach() function removing all listeners.
     */
    attachCanvas(canvas, options = {}) {
        if (!canvas || typeof canvas.addEventListener !== "function") {
            return () => {};
        }
        const win = typeof window !== "undefined" ? window : null;
        const onChange = typeof options.onChange === "function" ? options.onChange : null;
        const doubleClickReset = options.doubleClickReset !== false;
        const activeIds = new Set();

        const notify = () => {
            if (onChange) onChange(this.getState());
        };

        const pointerCoords = (event) => {
            if (typeof canvas.getBoundingClientRect === "function") {
                const rect = canvas.getBoundingClientRect();
                if (rect && rect.width > 0 && rect.height > 0) {
                    return [event.clientX - rect.left, event.clientY - rect.top];
                }
            }
            return [finiteOr(event.offsetX, event.clientX), finiteOr(event.offsetY, event.clientY)];
        };

        const onDown = (event) => {
            if (event.button !== undefined && event.button !== 0 && event.button !== 1 && event.button !== 2) return;
            const [x, y] = pointerCoords(event);
            const id = event.pointerId ?? 0;
            activeIds.add(id);
            if (typeof canvas.setPointerCapture === "function" && event.pointerId !== undefined) {
                try {
                    canvas.setPointerCapture(event.pointerId);
                } catch (_) {
                    // Ignore capture errors on synthetic or detached elements.
                }
            }
            this.onPointerDown(x, y, {
                pointerId: id,
                shiftKey: event.shiftKey,
                button: event.button,
            });
            notify();
        };

        const onMove = (event) => {
            const id = event.pointerId ?? 0;
            if (!activeIds.has(id)) return;
            const [x, y] = pointerCoords(event);
            if (this.onPointerMove(x, y, { pointerId: id, shiftKey: event.shiftKey })) {
                notify();
            }
        };

        const onUp = (event) => {
            const id = event.pointerId ?? 0;
            if (!activeIds.has(id)) return;
            activeIds.delete(id);
            if (typeof canvas.releasePointerCapture === "function" && event.pointerId !== undefined) {
                try {
                    if (typeof canvas.hasPointerCapture !== "function" || canvas.hasPointerCapture(event.pointerId)) {
                        canvas.releasePointerCapture(event.pointerId);
                    }
                } catch (_) {
                    // Ignore release errors when pointer capture was already dropped.
                }
            }
            this.onPointerUp(id);
            notify();
        };

        const onWheel = (event) => {
            if (typeof event.preventDefault === "function") event.preventDefault();
            if (this.onWheel(event.deltaY, event.deltaX)) {
                notify();
            }
        };

        const onDblClick = () => {
            if (!doubleClickReset) return;
            this.reset();
            notify();
        };

        const onContextMenu = (event) => {
            if (options.preventContextMenu && typeof event.preventDefault === "function") {
                event.preventDefault();
            }
        };

        canvas.addEventListener("pointerdown", onDown);
        canvas.addEventListener("pointermove", onMove);
        canvas.addEventListener("pointerup", onUp);
        canvas.addEventListener("pointercancel", onUp);
        canvas.addEventListener("wheel", onWheel, { passive: false });
        if (doubleClickReset) canvas.addEventListener("dblclick", onDblClick);
        if (options.preventContextMenu) canvas.addEventListener("contextmenu", onContextMenu);
        if (win && typeof win.addEventListener === "function") {
            win.addEventListener("pointermove", onMove);
            win.addEventListener("pointerup", onUp);
            win.addEventListener("pointercancel", onUp);
        }

        return () => {
            canvas.removeEventListener("pointerdown", onDown);
            canvas.removeEventListener("pointermove", onMove);
            canvas.removeEventListener("pointerup", onUp);
            canvas.removeEventListener("pointercancel", onUp);
            canvas.removeEventListener("wheel", onWheel);
            if (doubleClickReset) canvas.removeEventListener("dblclick", onDblClick);
            if (options.preventContextMenu) canvas.removeEventListener("contextmenu", onContextMenu);
            if (win && typeof win.removeEventListener === "function") {
                win.removeEventListener("pointermove", onMove);
                win.removeEventListener("pointerup", onUp);
                win.removeEventListener("pointercancel", onUp);
            }
            activeIds.clear();
        };
    }

    _clearVelocity() {
        this._velYaw = 0;
        this._velPitch = 0;
        this._velPanX = 0;
        this._velPanY = 0;
        this._velPanZ = 0;
    }

    _firstTwoPointers() {
        if (this._pointers.size < 2) return null;
        const iter = this._pointers.values();
        return [iter.next().value, iter.next().value];
    }

    _syncPinchAnchor() {
        const pair = this._firstTwoPointers();
        if (!pair) return;
        const [a, b] = pair;
        this._lastPinchDist = Math.hypot(b.x - a.x, b.y - a.y);
        this._lastPinchMidX = (a.x + b.x) * 0.5;
        this._lastPinchMidY = (a.y + b.y) * 0.5;
    }

    _applyPanDelta(dx, dy, trackVelocity) {
        const { right, up } = computeCameraBasis(this.yaw, this.pitch);
        const scale = this.panSpeed * this.distance;
        const moveX = (-right[0] * dx + up[0] * dy) * scale;
        const moveY = (-right[1] * dx + up[1] * dy) * scale;
        const moveZ = (-right[2] * dx + up[2] * dy) * scale;
        this.target[0] += moveX;
        this.target[1] += moveY;
        this.target[2] += moveZ;
        if (trackVelocity) {
            this._velPanX = moveX;
            this._velPanY = moveY;
            this._velPanZ = moveZ;
            this._velYaw = 0;
            this._velPitch = 0;
        }
    }
}

if (typeof globalThis !== "undefined") {
    globalThis.NexusWebGL = Object.assign(globalThis.NexusWebGL || {}, { OrbitController });
}

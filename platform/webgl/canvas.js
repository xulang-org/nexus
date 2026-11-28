(function () {
"use strict";
const HEADER_BYTES = 12;
const VERTEX_BYTES = 20;
const MODEL_HEADER_BYTES = 20;
const MODEL_VERTEX_BYTES = 24;
const MAX_VERTICES = 65532;
const MAX_FRAME_BYTES = HEADER_BYTES + VERTEX_BYTES * MAX_VERTICES;
const MAX_MODEL_BYTES = MODEL_HEADER_BYTES + MODEL_VERTEX_BYTES * MAX_VERTICES + 256 * 256 * 4;
const CAMERA_BYTES = 68;
const MAX_PIXELS = 2097152;

const VERTEX_SHADER = `
attribute vec2 position;
attribute vec2 texcoord;
attribute vec4 color;
uniform vec2 design;
varying vec2 uv;
varying vec4 tint;
void main() {
    vec2 clip = position / design * 2.0 - 1.0;
    gl_Position = vec4(clip.x, -clip.y, 0.0, 1.0);
    uv = texcoord;
    tint = color;
}
`;

const FRAGMENT_SHADER = `
precision mediump float;
uniform sampler2D atlas;
varying vec2 uv;
varying vec4 tint;
void main() {
    gl_FragColor = texture2D(atlas, uv) * tint;
}
`;

const MESH_VERTEX_SHADER = `
attribute vec3 position;
attribute vec2 texcoord;
attribute vec4 color;
uniform mat4 camera;
varying vec2 uv;
varying vec4 tint;
void main() {
    gl_Position = camera * vec4(position, 1.0);
    uv = texcoord;
    tint = color;
}
`;

function isPowerOfTwo(value) {
    return value > 0 && (value & (value - 1)) === 0;
}

function checkGl(gl) {
    const error = gl.getError();
    if (error !== gl.NO_ERROR) throw new Error("WebGL 绘制失败（" + error + "）");
}

function shader(gl, type, source) {
    const handle = gl.createShader(type);
    if (!handle) throw new Error("WebGL 无法分配着色器");
    gl.shaderSource(handle, source);
    gl.compileShader(handle);
    if (!gl.getShaderParameter(handle, gl.COMPILE_STATUS)) {
        const log = gl.getShaderInfoLog(handle);
        gl.deleteShader(handle);
        throw new Error("WebGL 着色器编译失败：" + log);
    }
    return handle;
}

function program(gl, mesh) {
    const handle = gl.createProgram();
    if (!handle) throw new Error("WebGL 无法分配管线");
    let vert;
    let frag;
    try {
        vert = shader(gl, gl.VERTEX_SHADER, mesh ? MESH_VERTEX_SHADER : VERTEX_SHADER);
        frag = shader(gl, gl.FRAGMENT_SHADER, FRAGMENT_SHADER);
        gl.attachShader(handle, vert);
        gl.attachShader(handle, frag);
        gl.bindAttribLocation(handle, 0, "position");
        gl.bindAttribLocation(handle, 1, "texcoord");
        gl.bindAttribLocation(handle, 2, "color");
        gl.linkProgram(handle);
        if (!gl.getProgramParameter(handle, gl.LINK_STATUS)) {
            throw new Error("WebGL 管线链接失败：" + gl.getProgramInfoLog(handle));
        }
        checkGl(gl);
        return handle;
    } catch (error) {
        gl.deleteProgram(handle);
        throw error;
    } finally {
        if (vert) gl.deleteShader(vert);
        if (frag) gl.deleteShader(frag);
    }
}

function texture(gl, image, width, height, options = {}) {
    const handle = gl.createTexture();
    if (!handle) throw new Error("WebGL 无法分配纹理");
    try {
        gl.bindTexture(gl.TEXTURE_2D, handle);
        gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, false);
        if (width) {
            gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, width, height, 0, gl.RGBA, gl.UNSIGNED_BYTE, image);
        } else if (image) {
            gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, image);
        } else {
            gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, 1, 1, 0, gl.RGBA,
                gl.UNSIGNED_BYTE, new Uint8Array([255, 255, 255, 255]));
        }

        if (options && options.linear) {
            const texWidth = width || (image && image.width) || 0;
            const texHeight = height || (image && image.height) || 0;
            const pot = isPowerOfTwo(texWidth) && isPowerOfTwo(texHeight);
            gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
            if (pot) {
                const wrapS = options.clamp ? gl.CLAMP_TO_EDGE : (options.wrapS || gl.REPEAT);
                const wrapT = options.clamp ? gl.CLAMP_TO_EDGE : (options.wrapT || gl.REPEAT);
                gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, wrapS);
                gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, wrapT);
                gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR_MIPMAP_LINEAR);
                gl.generateMipmap(gl.TEXTURE_2D);
            } else {
                gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
                gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
                gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
            }
        } else {
            gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.NEAREST);
            gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.NEAREST);
            gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
            gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
        }
        checkGl(gl);
        return handle;
    } catch (error) {
        gl.deleteTexture(handle);
        throw error;
    }
}

function parseFrame(packet) {
    if (!packet || packet.byteLength < HEADER_BYTES || packet.byteLength > MAX_FRAME_BYTES) {
        throw new Error("Nexus WebGL 帧长度无效");
    }
    const header = new DataView(packet.buffer, packet.byteOffset, HEADER_BYTES);
    const solid = header.getUint32(4, true);
    const atlas = header.getUint32(8, true);
    if (header.getUint32(0, true) !== 0x3147584e || solid % 3 !== 0 || atlas % 3 !== 0 ||
        HEADER_BYTES + (solid + atlas) * VERTEX_BYTES !== packet.byteLength) {
        throw new Error("Nexus WebGL 帧格式无效");
    }
    return { solid, atlas };
}

function parseModel(packet) {
    if (!packet || packet.byteLength < MODEL_HEADER_BYTES || packet.byteLength > MAX_MODEL_BYTES) {
        throw new Error("Nexus WebGL 模型包长度无效");
    }
    const header = new DataView(packet.buffer, packet.byteOffset, MODEL_HEADER_BYTES);
    const solid = header.getUint32(4, true);
    const textured = header.getUint32(8, true);
    const width = header.getUint32(12, true);
    const height = header.getUint32(16, true);
    const pixelsAt = MODEL_HEADER_BYTES + (solid + textured) * MODEL_VERTEX_BYTES;
    if (header.getUint32(0, true) !== 0x314d584e || solid === 0 || textured === 0 ||
        solid % 3 !== 0 || textured % 3 !== 0 || solid + textured > MAX_VERTICES ||
        width < 1 || width > 256 || height < 1 || height > 256 ||
        pixelsAt + width * height * 4 !== packet.byteLength) {
        throw new Error("Nexus WebGL 模型包格式无效");
    }
    return { solid, textured, width, height, pixelsAt };
}

function parseCamera(packet, out = new Float32Array(16)) {
    if (!packet || packet.byteLength !== CAMERA_BYTES) {
        throw new Error("Nexus WebGL 相机帧长度无效");
    }
    const view = new DataView(packet.buffer, packet.byteOffset, CAMERA_BYTES);
    if (view.getUint32(0, true) !== 0x3143584e) {
        throw new Error("Nexus WebGL 相机帧格式无效");
    }
    for (let i = 0; i < 16; i += 1) {
        const value = view.getFloat32(4 + i * 4, true);
        if (!Number.isFinite(value)) throw new Error("Nexus WebGL 相机矩阵无效");
        out[i] = value;
    }
    return out;
}

class WebGLCanvas {
    constructor(canvas, image, width, height, mesh = false, options = {}) {
        const opts = typeof mesh === "object" && mesh !== null ? mesh : (options || {});
        const isMesh = typeof mesh === "object" && mesh !== null ? Boolean(mesh.mesh) : Boolean(mesh);

        this.canvas = canvas;
        this.width = width;
        this.height = height;
        this.mesh = isMesh;
        this.debugGl = Boolean(opts.debugGl);
        this.onContextLost = typeof opts.onContextLost === "function" ? opts.onContextLost : null;
        this.onContextRestored = typeof opts.onContextRestored === "function" ? opts.onContextRestored : null;

        this._image = isMesh ? null : image;
        this._modelPacket = isMesh ? image : null;
        this._contextLost = false;
        this._vbo2d = null;
        this._vbo2dCapacity = 0;
        this._attribLayout = null;
        this._boundBuffer = null;
        this._boundTexture = null;
        this._lastViewport = null;
        this.camera = new Float32Array(16);

        this.gl = isMesh ? canvas.getContext("webgl", { depth: true }) : canvas.getContext("webgl");
        if (!this.gl) throw new Error("当前 Canvas 无法创建 WebGL 上下文");

        this._onContextLost = (event) => {
            if (event && typeof event.preventDefault === "function") event.preventDefault();
            this._contextLost = true;
            this._clearGlHandles();
            if (this.onContextLost) this.onContextLost(event);
        };
        this._onContextRestored = (event) => {
            this._contextLost = false;
            try {
                this._initGl();
                if (this.onContextRestored) this.onContextRestored(event);
            } catch (error) {
                if (this.onContextRestored) this.onContextRestored(event, error);
            }
        };
        if (typeof canvas.addEventListener === "function") {
            canvas.addEventListener("webglcontextlost", this._onContextLost, false);
            canvas.addEventListener("webglcontextrestored", this._onContextRestored, false);
        }

        try {
            this._initGl();
        } catch (error) {
            this.close();
            throw error;
        }
    }

    _clearGlHandles() {
        this.atlas = null;
        this.white = null;
        this.buffer = null;
        this._vbo2d = null;
        this._vbo2dCapacity = 0;
        this.program = null;
        this.cameraUniform = null;
        this._attribLayout = null;
        this._boundBuffer = null;
        this._boundTexture = null;
        this._lastViewport = null;
    }

    _initGl() {
        const gl = this.gl;
        this._clearGlHandles();
        this.program = program(gl, this.mesh);
        this.buffer = gl.createBuffer();
        if (!this.buffer) throw new Error("WebGL 无法分配顶点缓冲");
        gl.useProgram(this.program);
        this.white = texture(gl);
        gl.uniform1i(gl.getUniformLocation(this.program, "atlas"), 0);
        if (this.mesh) {
            if (!(gl.getParameter(gl.DEPTH_BITS) > 0)) throw new Error("WebGL 缺少深度缓冲");
            gl.enable(gl.DEPTH_TEST);
            gl.depthFunc(gl.GREATER);
            gl.clearDepth(0);
            this.loadModel(this._modelPacket);
        } else {
            this._vbo2d = this.buffer;
            this._vbo2dCapacity = 0;
            this.atlas = this._image ? texture(gl, this._image) : null;
            gl.uniform2f(gl.getUniformLocation(this.program, "design"), this.width, this.height);
            gl.enable(gl.BLEND);
            gl.blendFuncSeparate(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA, gl.ONE, gl.ONE_MINUS_SRC_ALPHA);
        }
        gl.clearColor(0.04, 0.07, 0.11, 1);
        checkGl(gl);
    }

    isContextLost() {
        return this._contextLost || (this.gl && typeof this.gl.isContextLost === "function" && this.gl.isContextLost() === true);
    }

    loadModel(packet) {
        const { gl } = this;
        const { solid, textured, width, height, pixelsAt } = parseModel(packet);
        this._modelPacket = packet;
        if (this.atlas) gl.deleteTexture(this.atlas);
        this.atlas = texture(gl, packet.subarray(pixelsAt), width, height, { linear: true });
        this._boundTexture = this.atlas;
        this.solid = solid;
        this.textured = textured;
        this.meshBytes = packet.byteLength - MODEL_HEADER_BYTES;
        this.cameraUniform = gl.getUniformLocation(this.program, "camera");
        gl.bindBuffer(gl.ARRAY_BUFFER, this.buffer);
        this._boundBuffer = this.buffer;
        gl.bufferData(gl.ARRAY_BUFFER, packet.subarray(MODEL_HEADER_BYTES, pixelsAt), gl.STATIC_DRAW);
        this._configureMeshAttribs(gl);
        checkGl(gl);
    }

    _configureMeshAttribs(gl) {
        if (this._attribLayout === "3d") return;
        gl.enableVertexAttribArray(0);
        gl.enableVertexAttribArray(1);
        gl.enableVertexAttribArray(2);
        gl.vertexAttribPointer(0, 3, gl.FLOAT, false, MODEL_VERTEX_BYTES, 0);
        gl.vertexAttribPointer(1, 2, gl.FLOAT, false, MODEL_VERTEX_BYTES, 12);
        gl.vertexAttribPointer(2, 4, gl.UNSIGNED_BYTE, true, MODEL_VERTEX_BYTES, 20);
        this._attribLayout = "3d";
    }

    _configure2DAttribs(gl) {
        if (this._attribLayout === "2d") return;
        gl.enableVertexAttribArray(0);
        gl.enableVertexAttribArray(1);
        gl.enableVertexAttribArray(2);
        gl.vertexAttribPointer(0, 2, gl.FLOAT, false, VERTEX_BYTES, 0);
        gl.vertexAttribPointer(1, 2, gl.FLOAT, false, VERTEX_BYTES, 8);
        gl.vertexAttribPointer(2, 4, gl.UNSIGNED_BYTE, true, VERTEX_BYTES, 16);
        this._attribLayout = "2d";
    }

    resize(boundsOrWidth, pixelRatioOrHeight, extraRatio) {
        let left = 0;
        let top = 0;
        let width;
        let height;
        let requestedRatio;

        if (typeof boundsOrWidth === "number") {
            width = boundsOrWidth;
            height = pixelRatioOrHeight;
            requestedRatio = extraRatio ?? 1;
        } else if (boundsOrWidth && typeof boundsOrWidth === "object") {
            left = Number.isFinite(boundsOrWidth.left) ? boundsOrWidth.left : 0;
            top = Number.isFinite(boundsOrWidth.top) ? boundsOrWidth.top : 0;
            width = boundsOrWidth.width;
            height = boundsOrWidth.height;
            requestedRatio = pixelRatioOrHeight;
        } else {
            width = 0;
            height = 0;
            requestedRatio = 1;
        }

        if (!Number.isFinite(width) || !Number.isFinite(height) || width <= 0 || height <= 0) {
            this.viewport = { x: 0, y: 0, w: 0, h: 0 };
            this.input = { left, top, width: 0, height: 0 };
            this._lastViewport = null;
            return false;
        }

        const safeDpr = Number.isFinite(requestedRatio) && requestedRatio > 0 ? requestedRatio : 1;
        const ratio = Math.min(safeDpr, 4096 / Math.max(width, height),
            Math.sqrt(MAX_PIXELS / width / height));
        const pixelWidth = Math.max(1, Math.floor(width * ratio));
        const pixelHeight = Math.max(1, Math.floor(height * ratio));
        if (this.canvas.width !== pixelWidth) this.canvas.width = pixelWidth;
        if (this.canvas.height !== pixelHeight) this.canvas.height = pixelHeight;

        const scale = Math.min(pixelWidth / this.width, pixelHeight / this.height);
        const w = Math.max(1, Math.round(this.width * scale));
        const h = Math.max(1, Math.round(this.height * scale));
        const x = Math.floor((pixelWidth - w) / 2);
        const y = Math.floor((pixelHeight - h) / 2);
        this.viewport = { x, y, w, h };
        this.input = {
            left: left + x * width / pixelWidth,
            top: top + (pixelHeight - y - h) * height / pixelHeight,
            width: w * width / pixelWidth,
            height: h * height / pixelHeight,
        };
        this._lastViewport = null;
        return true;
    }

    point(clientX, clientY, options = {}) {
        const area = this.input;
        if (!area || !(area.width > 0) || !(area.height > 0) ||
            !Number.isFinite(clientX) || !Number.isFinite(clientY)) {
            return [-1, -1];
        }
        const rawX = (clientX - area.left) * this.width / area.width;
        const rawY = (clientY - area.top) * this.height / area.height;
        if (options && options.clamp) {
            const x = Math.max(0, Math.min(this.width - 1, Math.floor(rawX)));
            const y = Math.max(0, Math.min(this.height - 1, Math.floor(rawY)));
            return [x, y];
        }
        if (!(rawX >= 0 && rawX < this.width && rawY >= 0 && rawY < this.height)) return [-1, -1];
        return [Math.floor(rawX), Math.floor(rawY)];
    }

    clampPoint(clientX, clientY) {
        return this.point(clientX, clientY, { clamp: true });
    }

    _syncViewport(gl) {
        const vp = this.viewport;
        if (!vp) return true;
        if (vp.w <= 0 || vp.h <= 0) return false;
        const last = this._lastViewport;
        if (!last || last.x !== vp.x || last.y !== vp.y || last.w !== vp.w || last.h !== vp.h) {
            gl.viewport(vp.x, vp.y, vp.w, vp.h);
            this._lastViewport = { x: vp.x, y: vp.y, w: vp.w, h: vp.h };
        }
        return true;
    }

    _bindTexture(gl, handle) {
        if (this._boundTexture !== handle) {
            gl.bindTexture(gl.TEXTURE_2D, handle);
            this._boundTexture = handle;
        }
    }

    draw(packet) {
        if (this.isContextLost()) return false;
        const gl = this.gl;
        if (!this._syncViewport(gl)) return false;
        if (this.mesh) {
            return this.drawModel(packet);
        }
        const { solid, atlas } = parseFrame(packet);
        if (atlas && !this.atlas) throw new Error("Nexus WebGL 帧缺少图集");
        gl.clear(gl.COLOR_BUFFER_BIT);
        const payload = packet.subarray(HEADER_BYTES);
        if (this._boundBuffer !== this._vbo2d) {
            gl.bindBuffer(gl.ARRAY_BUFFER, this._vbo2d);
            this._boundBuffer = this._vbo2d;
        }
        if (payload.byteLength > 0) {
            if (payload.byteLength > this._vbo2dCapacity) {
                this._vbo2dCapacity = payload.byteLength;
                gl.bufferData(gl.ARRAY_BUFFER, payload, gl.STREAM_DRAW);
            } else {
                gl.bufferSubData(gl.ARRAY_BUFFER, 0, payload);
            }
        }
        this._configure2DAttribs(gl);
        if (solid) {
            this._bindTexture(gl, this.white);
            gl.drawArrays(gl.TRIANGLES, 0, solid);
        }
        if (atlas) {
            this._bindTexture(gl, this.atlas);
            gl.drawArrays(gl.TRIANGLES, solid, atlas);
        }
        if (this.debugGl) checkGl(gl);
        return true;
    }

    drawModel(packet) {
        if (this.isContextLost()) return false;
        parseCamera(packet, this.camera);
        const gl = this.gl;
        if (!this._syncViewport(gl)) return false;
        gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
        gl.uniformMatrix4fv(this.cameraUniform, false, this.camera);
        this._bindTexture(gl, this.white);
        gl.drawArrays(gl.TRIANGLES, 0, this.solid);
        this._bindTexture(gl, this.atlas);
        gl.drawArrays(gl.TRIANGLES, this.solid, this.textured);
        if (this.debugGl) checkGl(gl);
        return true;
    }

    close() {
        if (this.canvas && typeof this.canvas.removeEventListener === "function") {
            if (this._onContextLost) this.canvas.removeEventListener("webglcontextlost", this._onContextLost, false);
            if (this._onContextRestored) this.canvas.removeEventListener("webglcontextrestored", this._onContextRestored, false);
        }
        const gl = this.gl;
        if (gl && !this._contextLost) {
            if (this.atlas) gl.deleteTexture(this.atlas);
            if (this.white) gl.deleteTexture(this.white);
            if (this.buffer) gl.deleteBuffer(this.buffer);
            if (this.program) gl.deleteProgram(this.program);
        }
        this._clearGlHandles();
        this._image = null;
        this._modelPacket = null;
    }
}

const exported = {
    HEADER_BYTES,
    VERTEX_BYTES,
    MODEL_HEADER_BYTES,
    MODEL_VERTEX_BYTES,
    MAX_VERTICES,
    MAX_FRAME_BYTES,
    MAX_MODEL_BYTES,
    CAMERA_BYTES,
    parseFrame,
    parseModel,
    parseCamera,
    WebGLCanvas,
};

if (typeof globalThis !== "undefined") {
    globalThis.NexusWebGL = Object.assign(globalThis.NexusWebGL || {}, exported);
}
if (typeof module !== "undefined" && module.exports) {
    module.exports = exported;
}
})();

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
        return handle;
    } catch (error) {
        gl.deleteProgram(handle);
        throw error;
    } finally {
        if (vert) gl.deleteShader(vert);
        if (frag) gl.deleteShader(frag);
    }
}

function texture(gl, image, width, height) {
    const handle = gl.createTexture();
    if (!handle) throw new Error("WebGL 无法分配纹理");
    try {
        gl.bindTexture(gl.TEXTURE_2D, handle);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.NEAREST);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.NEAREST);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
        gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, false);
        if (width) {
            gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, width, height, 0, gl.RGBA, gl.UNSIGNED_BYTE, image);
        } else if (image) {
            gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, image);
        } else {
            gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, 1, 1, 0, gl.RGBA,
                gl.UNSIGNED_BYTE, new Uint8Array([255, 255, 255, 255]));
        }
        return handle;
    } catch (error) {
        gl.deleteTexture(handle);
        throw error;
    }
}

function checkGl(gl) {
    const error = gl.getError();
    if (error !== gl.NO_ERROR) throw new Error("WebGL 绘制失败（" + error + "）");
}

function decodeFrame(packet) {
    if (packet.byteLength < HEADER_BYTES || packet.byteLength > MAX_FRAME_BYTES) {
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

function decodeModel(packet) {
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

class WebGLCanvas {
    constructor(canvas, image, width, height, mesh = false) {
        this.canvas = canvas;
        this.width = width;
        this.height = height;
        this.mesh = mesh;
        this.gl = mesh ? canvas.getContext("webgl", { depth: true }) : canvas.getContext("webgl");
        if (!this.gl) throw new Error("当前 Canvas 无法创建 WebGL 上下文");
        const gl = this.gl;
        try {
            this.program = program(gl, mesh);
            this.buffer = gl.createBuffer();
            if (!this.buffer) throw new Error("WebGL 无法分配顶点缓冲");
            gl.useProgram(this.program);
            this.white = texture(gl);
            gl.uniform1i(gl.getUniformLocation(this.program, "atlas"), 0);
            if (mesh) {
                if (!(gl.getParameter(gl.DEPTH_BITS) > 0)) throw new Error("WebGL 缺少深度缓冲");
                gl.enable(gl.DEPTH_TEST);
                gl.depthFunc(gl.GREATER);
                gl.clearDepth(0);
                this.loadModel(image);
            } else {
                this.atlas = image ? texture(gl, image) : null;
                gl.uniform2f(gl.getUniformLocation(this.program, "design"), width, height);
                gl.enable(gl.BLEND);
                gl.blendFuncSeparate(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA, gl.ONE, gl.ONE_MINUS_SRC_ALPHA);
            }
            gl.clearColor(0.04, 0.07, 0.11, 1);
            checkGl(gl);
        } catch (error) {
            this.close();
            throw error;
        }
    }

    loadModel(packet) {
        const { gl } = this;
        const { solid, textured, width, height, pixelsAt } = decodeModel(packet);
        this.atlas = texture(gl, packet.subarray(pixelsAt), width, height);
        this.solid = solid;
        this.textured = textured;
        this.meshBytes = packet.byteLength - MODEL_HEADER_BYTES;
        this.camera = new Float32Array(16);
        this.cameraUniform = gl.getUniformLocation(this.program, "camera");
        gl.bindBuffer(gl.ARRAY_BUFFER, this.buffer);
        gl.bufferData(gl.ARRAY_BUFFER, packet.subarray(MODEL_HEADER_BYTES, pixelsAt), gl.STATIC_DRAW);
        gl.enableVertexAttribArray(0);
        gl.enableVertexAttribArray(1);
        gl.enableVertexAttribArray(2);
        gl.vertexAttribPointer(0, 3, gl.FLOAT, false, MODEL_VERTEX_BYTES, 0);
        gl.vertexAttribPointer(1, 2, gl.FLOAT, false, MODEL_VERTEX_BYTES, 12);
        gl.vertexAttribPointer(2, 4, gl.UNSIGNED_BYTE, true, MODEL_VERTEX_BYTES, 20);
    }

    resize(bounds, pixelRatio) {
        const { width, height } = bounds;
        if (!Number.isFinite(width) || !Number.isFinite(height) || width <= 0 || height <= 0) {
            throw new Error("WebGL Canvas 尚无可绘制尺寸");
        }
        const ratio = Math.min(pixelRatio || 1, 4096 / Math.max(width, height),
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
            left: bounds.left + x * width / pixelWidth,
            top: bounds.top + (pixelHeight - y - h) * height / pixelHeight,
            width: w * width / pixelWidth,
            height: h * height / pixelHeight,
        };
    }

    point(clientX, clientY) {
        const area = this.input;
        const x = (clientX - area.left) * this.width / area.width;
        const y = (clientY - area.top) * this.height / area.height;
        if (!(x >= 0 && x < this.width && y >= 0 && y < this.height)) return [-1, -1];
        return [Math.floor(x), Math.floor(y)];
    }

    draw(packet) {
        const gl = this.gl;
        const { x, y, w, h } = this.viewport;
        gl.viewport(x, y, w, h);
        if (this.mesh) {
            this.drawModel(packet);
            return;
        }
        const { solid, atlas } = decodeFrame(packet);
        if (atlas && !this.atlas) throw new Error("Nexus WebGL 帧缺少图集");
        gl.clear(gl.COLOR_BUFFER_BIT);
        gl.bindBuffer(gl.ARRAY_BUFFER, this.buffer);
        gl.bufferData(gl.ARRAY_BUFFER, packet.subarray(HEADER_BYTES), gl.STREAM_DRAW);
        gl.enableVertexAttribArray(0);
        gl.enableVertexAttribArray(2);
        gl.vertexAttribPointer(0, 2, gl.FLOAT, false, VERTEX_BYTES, 0);
        gl.vertexAttribPointer(2, 4, gl.UNSIGNED_BYTE, true, VERTEX_BYTES, 16);
        gl.enableVertexAttribArray(1);
        gl.vertexAttribPointer(1, 2, gl.FLOAT, false, VERTEX_BYTES, 8);
        if (solid) {
            gl.bindTexture(gl.TEXTURE_2D, this.white);
            gl.drawArrays(gl.TRIANGLES, 0, solid);
        }
        if (atlas) {
            gl.bindTexture(gl.TEXTURE_2D, this.atlas);
            gl.drawArrays(gl.TRIANGLES, solid, atlas);
        }
        checkGl(gl);
    }

    drawModel(packet) {
        if (packet.byteLength !== CAMERA_BYTES) throw new Error("Nexus WebGL 相机帧长度无效");
        const view = new DataView(packet.buffer, packet.byteOffset, CAMERA_BYTES);
        if (view.getUint32(0, true) !== 0x3143584e) throw new Error("Nexus WebGL 相机帧格式无效");
        for (let i = 0; i < 16; i += 1) {
            const value = view.getFloat32(4 + i * 4, true);
            if (!Number.isFinite(value)) throw new Error("Nexus WebGL 相机矩阵无效");
            this.camera[i] = value;
        }
        const gl = this.gl;
        gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
        gl.uniformMatrix4fv(this.cameraUniform, false, this.camera);
        gl.bindTexture(gl.TEXTURE_2D, this.white);
        gl.drawArrays(gl.TRIANGLES, 0, this.solid);
        gl.bindTexture(gl.TEXTURE_2D, this.atlas);
        gl.drawArrays(gl.TRIANGLES, this.solid, this.textured);
        checkGl(gl);
    }

    close() {
        const gl = this.gl;
        if (this.atlas) gl.deleteTexture(this.atlas);
        if (this.white) gl.deleteTexture(this.white);
        if (this.buffer) gl.deleteBuffer(this.buffer);
        if (this.program) gl.deleteProgram(this.program);
        this.atlas = this.white = this.buffer = this.program = null;
    }
}

module.exports = { WebGLCanvas, MAX_FRAME_BYTES, MAX_MODEL_BYTES, CAMERA_BYTES };

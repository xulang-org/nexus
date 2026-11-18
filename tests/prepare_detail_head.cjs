// Explicit offline test-asset preparation; not a game runtime dependency.
const fs=require('fs'),path=require('path');
const {generateTangents}=require('../build/detail-model-tools/node_modules/mikktspace');
const root=path.join(__dirname,'../build/detail-models');
const source=fs.readFileSync(path.join(root,'LeePerrySmith.glb'));
const size=source.readUInt32LE(12),doc=JSON.parse(source.subarray(20,20+size).toString());
const bin=source.subarray(28+size),primitive=doc.meshes[0].primitives[0];
function read(index){const a=doc.accessors[index],v=doc.bufferViews[a.bufferView],components={SCALAR:1,VEC2:2,VEC3:3,VEC4:4}[a.type],bytes=a.componentType===5123?2:4;
 return Array.from({length:a.count},(_,i)=>Array.from({length:components},(_,c)=>{const at=(v.byteOffset||0)+(a.byteOffset||0)+i*(v.byteStride||components*bytes)+c*bytes;return bytes===2?bin.readUInt16LE(at):bin.readFloatLE(at);}));}
const indices=read(primitive.indices).flat(),p0=read(primitive.attributes.POSITION),n0=read(primitive.attributes.NORMAL),uv0=read(primitive.attributes.TEXCOORD_0);
const positions=new Float32Array(indices.flatMap(i=>p0[i]));
const normals=new Float32Array(indices.flatMap(i=>{const n=n0[i],length=Math.hypot(...n);return n.map(v=>v/length);}));
// The upstream three.js sample assigns these JPEGs through TextureLoader's
// default flipY=true. Bake that convention explicitly into glTF UV0.
const uvs=new Float32Array(indices.flatMap(i=>[uv0[i][0],1-uv0[i][1]]));
const tangents=generateTangents(positions,normals,uvs);
for(let i=3;i<tangents.length;i+=4)tangents[i]*=-1; // MikkTSpace -> glTF UV convention.
let data=Buffer.alloc(0);const views=[],accessors=[];
function add(values,components,type,bounds=false){const at=data.length;const bytes=Buffer.alloc(values.length*4);values.forEach((v,i)=>bytes.writeFloatLE(v,i*4));data=Buffer.concat([data,bytes]);views.push({buffer:0,byteOffset:at,byteLength:bytes.length,target:34962});const a={bufferView:views.length-1,componentType:5126,count:values.length/components,type};
 if(bounds){a.min=Array.from({length:components},(_,c)=>{let min=Infinity;for(let i=c;i<values.length;i+=components)min=Math.min(min,values[i]);return min;});a.max=Array.from({length:components},(_,c)=>{let max=-Infinity;for(let i=c;i<values.length;i+=components)max=Math.max(max,values[i]);return max;});}accessors.push(a);return accessors.length-1;}
const attributes={POSITION:add(positions,3,'VEC3',true),NORMAL:add(normals,3,'VEC3'),TEXCOORD_0:add(uvs,2,'VEC2'),TANGENT:add(tangents,4,'VEC4')};
const model={asset:{version:'2.0',generator:'Explicit Lee Perry-Smith test preparation; MikkTSpace',copyright:'Lee Perry-Smith / Infinite Realities, CC-BY-3.0; via three.js'},buffers:[{byteLength:data.length}],bufferViews:views,accessors,
 images:[{uri:'Map-COL.jpg',mimeType:'image/jpeg'},{uri:'Infinite-Level_02_Tangent_SmoothUV.jpg',mimeType:'image/jpeg'}],textures:[{source:0},{source:1}],
 materials:[{pbrMetallicRoughness:{baseColorFactor:[1,1,1,1],metallicFactor:0,roughnessFactor:.6,baseColorTexture:{index:0}},normalTexture:{index:1}}],
 meshes:[{primitives:[{attributes,material:0}]}],nodes:[{mesh:0}],scenes:[{nodes:[0]}],scene:0};
let json=Buffer.from(JSON.stringify(model));json=Buffer.concat([json,Buffer.alloc((4-json.length%4)%4,32)]);
const header=Buffer.alloc(20);header.writeUInt32LE(0x46546c67,0);header.writeUInt32LE(2,4);header.writeUInt32LE(28+json.length+data.length,8);header.writeUInt32LE(json.length,12);header.writeUInt32LE(0x4e4f534a,16);
const bh=Buffer.alloc(8);bh.writeUInt32LE(data.length,0);bh.writeUInt32LE(0x004e4942,4);
fs.writeFileSync(path.join(root,'head-prepared.glb'),Buffer.concat([header,json,bh,data]));
console.log(`Prepared head: ${indices.length/3} triangles, ${positions.length/3} expanded vertices, MikkTSpace tangents, original JPEG color/normal maps`);

'use strict';
/* Decode the ORIGINAL NASA Z-2 Draco geometry. This generates intermediate
   visual mesh arrays only; it never creates synthetic terrain or NASA science. */
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const [src,decoderPath,out]=process.argv.slice(2);
if(!src||!decoderPath||!out)throw Error('Usage: node scripts/decode_nasa_z2.cjs source.glb decoder.js output_dir');
const payload=fs.readFileSync(src);
const expected='4199762c27f8e730030a7bf9f1a453c203457e84c33b36247c0237a74f9a0c2a';
const found=crypto.createHash('sha256').update(payload).digest('hex');
if(found!==expected)throw Error('NASA Z-2 original SHA256 does not match inspected source: '+found);
fs.mkdirSync(out,{recursive:true});
let factory=require(path.resolve(decoderPath));
if(typeof factory!=='function'){
 // Three.js 0.180 includes a browser-global decoder without CommonJS export.
 // Evaluate the pinned local decoder source in an isolated Node VM only.
 const vm=require('node:vm');
 const scope={module:{exports:{}},exports:{},console,process,Buffer,
   WebAssembly,TextDecoder,TextEncoder,setTimeout,clearTimeout};
 vm.runInNewContext(fs.readFileSync(decoderPath,'utf8')+
   '\n;module.exports = DracoDecoderModule;',scope,{timeout:30000});
 factory=scope.module.exports;
}
if(typeof factory!=='function')throw Error('Local Three.js Draco decoder does not expose a factory');
(async()=>{
 const m=await factory(),length=payload.readUInt32LE(12);
 const gltf=JSON.parse(payload.subarray(20,20+length).toString());
 const off=20+length+8,prim=gltf.meshes[0].primitives[0];
 const ext=prim.extensions.KHR_draco_mesh_compression;
 const view=gltf.bufferViews[ext.bufferView];
 const bytes=payload.subarray(off+view.byteOffset,off+view.byteOffset+view.byteLength);
 const decoder=new m.Decoder(),input=new m.DecoderBuffer();
 input.Init(new Int8Array(bytes),bytes.length);
 const mesh=new m.Mesh(),status=decoder.DecodeBufferToMesh(input,mesh);
 if(!status.ok())throw Error('NASA Draco mesh is invalid: '+status.error_msg());
 for(const [name,id] of Object.entries(ext.attributes)){
  const attribute=decoder.GetAttributeByUniqueId(mesh,id);
  const size=mesh.num_points()*attribute.num_components();
  const arr=new Float32Array(size),ptr=m._malloc(arr.byteLength);
  decoder.GetAttributeDataArrayForAllPoints(mesh,attribute,m.DT_FLOAT32,arr.byteLength,ptr);
  arr.set(m.HEAPF32.subarray(ptr/4,ptr/4+size));m._free(ptr);
  const filename=name==='POSITION'?'z2_positions.f32':name==='NORMAL'?'z2_normals.f32':'z2_uv.f32';
  fs.writeFileSync(path.join(out,filename),Buffer.from(arr.buffer));
 }
 const faces=new Uint32Array(mesh.num_faces()*3),idx=new m.DracoInt32Array();
 for(let i=0;i<mesh.num_faces();i++){
  decoder.GetFaceFromMesh(mesh,i,idx);
  for(let j=0;j<3;j++)faces[i*3+j]=idx.GetValue(j);
 }
 fs.writeFileSync(path.join(out,'z2_faces.u32'),Buffer.from(faces.buffer));
 console.log('NASA Z-2 original geometry:',mesh.num_points(),'vertices',mesh.num_faces(),'triangles');
 m.destroy(idx);m.destroy(mesh);m.destroy(input);m.destroy(decoder);
})().catch(e=>{console.error(e);process.exitCode=1});

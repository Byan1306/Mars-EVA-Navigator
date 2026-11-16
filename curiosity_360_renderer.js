/**
 * NASA cylindrical panorama 360° viewer using WebGL2.
 * Horizontal 360°, never a reconstructed 3D Mars surface or spherical 360x180 image.
 * Gracefully falls back to static <img> when CORS/WebGL unavailable.
 */
(function(root){
'use strict';
const VERT=[
 '#version 300 es','out vec2 vUV;',
 'void main(){',
 'vec2 p=vec2(float((gl_VertexID<<1)&2),float(gl_VertexID&2));',
 'vUV=p;gl_Position=vec4(p*2.0-1.0,0.0,1.0);',
 '}'
].join('\n');
const FRAG=[
 '#version 300 es','precision highp float;',
 'in vec2 vUV;out vec4 outColor;',
 'uniform sampler2D tex;',
 'uniform float yaw,pitch,aspect,halfFovTan,verticalFov;',
 'const float PI=3.141592653589793;',
 'void main(){',
 'vec2 q=2.0*vUV-1.0;',
 'vec3 ray=normalize(vec3(q.x*aspect*halfFovTan,-q.y*halfFovTan,-1.0));',
 'float c=cos(pitch),s=sin(pitch);',
 'ray=vec3(ray.x,ray.y*c-ray.z*s,ray.y*s+ray.z*c);',
 'float phi=atan(ray.x,-ray.z)+yaw;',
 'float theta=atan(ray.y,length(ray.xz));',
 'float u=fract(0.5+phi/(2.0*PI));',
 'float v=0.5-theta/verticalFov;',
 'if(v<0.0||v>1.0){outColor=vec4(0.055,0.066,0.08,1.0);return;}',
 'outColor=vec4(texture(tex,vec2(u,v)).rgb,1.0);',
 '}'
].join('\n');
function shader(gl,type,code){
  const item=gl.createShader(type);gl.shaderSource(item,code);gl.compileShader(item);
  if(!gl.getShaderParameter(item,gl.COMPILE_STATUS)){
    const message=gl.getShaderInfoLog(item);gl.deleteShader(item);throw Error('Shader: '+message);
  }
  return item;
}
class Cylindrical360 {
  constructor(canvas){
    this.canvas=canvas;this.gl=null;this.program=null;this.texture=null;
    this.yaw=0;this.pitch=0;this.fov=75;this.verticalFov=Math.PI/2;
    this.active=false;this.dragging=false;this.request=0;this.pointerStart=null;
    canvas.addEventListener('pointerdown',e=>{
      if(!this.active)return;
      this.dragging=true;
      this.pointerStart={x:e.clientX,y:e.clientY,yaw:this.yaw,pitch:this.pitch};
      canvas.setPointerCapture(e.pointerId);e.preventDefault();
    });
    canvas.addEventListener('pointermove',e=>{
      if(!this.active||!this.dragging||!this.pointerStart)return;
      const a=this.pointerStart;
      this.yaw=a.yaw-(e.clientX-a.x)*0.004;
      this.pitch=Math.max(-.36,Math.min(.36,a.pitch+(e.clientY-a.y)*0.002));
      this.draw();
    });
    for(const type of ['pointerup','pointercancel'])canvas.addEventListener(type,()=>{this.dragging=false;});
    canvas.addEventListener('wheel',e=>{
      if(!this.active)return;
      this.fov=Math.max(38,Math.min(105,this.fov+Math.sign(e.deltaY)*5));
      this.draw();e.preventDefault();
    },{passive:false});
  }
  setup(){
    if(this.gl)return;
    const gl=this.canvas.getContext('webgl2',{alpha:false,antialias:false,preserveDrawingBuffer:false});
    if(!gl)throw Error('WebGL2 no disponible.');
    const program=gl.createProgram(),vertex=shader(gl,gl.VERTEX_SHADER,VERT),frag=shader(gl,gl.FRAGMENT_SHADER,FRAG);
    gl.attachShader(program,vertex);gl.attachShader(program,frag);gl.linkProgram(program);
    gl.deleteShader(vertex);gl.deleteShader(frag);
    if(!gl.getProgramParameter(program,gl.LINK_STATUS))throw Error('Error de enlace de proyección cilíndrica.');
    const vao=gl.createVertexArray();gl.bindVertexArray(vao);
    this.gl=gl;this.program=program;this.vao=vao;
    this.uniforms=Object.fromEntries(['tex','yaw','pitch','aspect','halfFovTan','verticalFov'].map(k=>[k,gl.getUniformLocation(program,k)]));
    this.texture=gl.createTexture();
  }
  load(url){
    this.disable();
    const request=++this.request;
    if(!/^https:\/\//.test(url))return Promise.reject(Error('La imagen no utiliza HTTPS.'));
    return new Promise((resolve,reject)=>{
      const img=new Image();img.crossOrigin='anonymous';
      img.onload=()=>{
        if(request!==this.request){resolve(false);return;}
        try{
          if(img.naturalWidth < img.naturalHeight*2.5) throw Error('La imagen no tiene formato panorámico cilíndrico adecuado.');
          this.setup();
          const gl=this.gl,max=gl.getParameter(gl.MAX_TEXTURE_SIZE);
          let source=img;
          if(img.naturalWidth>max||img.naturalHeight>max){
            const ratio=Math.min(max/img.naturalWidth,max/img.naturalHeight);
            const buffer=document.createElement('canvas');
            buffer.width=Math.floor(img.naturalWidth*ratio);buffer.height=Math.floor(img.naturalHeight*ratio);
            buffer.getContext('2d').drawImage(img,0,0,buffer.width,buffer.height);source=buffer;
          }
          gl.activeTexture(gl.TEXTURE0);gl.bindTexture(gl.TEXTURE_2D,this.texture);
          gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL,true);
          gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_S,gl.REPEAT);
          gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_T,gl.CLAMP_TO_EDGE);
          gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,gl.LINEAR);
          gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MAG_FILTER,gl.LINEAR);
          gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,gl.RGBA,gl.UNSIGNED_BYTE,source);
          this.verticalFov=Math.max(.6,Math.min(2.4,2*Math.PI*img.naturalHeight/img.naturalWidth));
          this.active=true;this.canvas.hidden=false;this.fov=75;this.pitch=0;this.yaw=0;
          this.draw();resolve(true);
        }catch(error){this.disable();reject(error);}
      };
      img.onerror=()=>reject(Error('El servidor de imágenes no permite WebGL/CORS o no responde.'));
      img.src=url;
    });
  }
  draw(){
    if(!this.active||!this.gl)return;
    const gl=this.gl;
    const width=this.canvas.clientWidth||this.canvas.parentElement.clientWidth;
    const height=this.canvas.clientHeight||this.canvas.parentElement.clientHeight;
    if(!width||!height)return;
    const dpr=Math.min(2,window.devicePixelRatio||1);
    const w=Math.round(width*dpr),h=Math.round(height*dpr);
    if(this.canvas.width!==w||this.canvas.height!==h){this.canvas.width=w;this.canvas.height=h;}
    gl.viewport(0,0,w,h);gl.useProgram(this.program);gl.bindVertexArray(this.vao);
    gl.activeTexture(gl.TEXTURE0);gl.bindTexture(gl.TEXTURE_2D,this.texture);
    gl.uniform1i(this.uniforms.tex,0);gl.uniform1f(this.uniforms.yaw,this.yaw);
    gl.uniform1f(this.uniforms.pitch,this.pitch);gl.uniform1f(this.uniforms.aspect,w/h);
    gl.uniform1f(this.uniforms.halfFovTan,Math.tan(this.fov*Math.PI/360));
    gl.uniform1f(this.uniforms.verticalFov,this.verticalFov);
    gl.drawArrays(gl.TRIANGLES,0,3);
  }
  disable(){this.request++;this.active=false;this.dragging=false;this.canvas.hidden=true;}
}
root.CuriosityPano360=Cylindrical360;
})(typeof window!=='undefined'?window:globalThis);

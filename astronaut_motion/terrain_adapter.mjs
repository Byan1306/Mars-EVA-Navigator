/** Read-only terrain adapter: unknown DEM heights always return null. */
import {groundNormal} from './math.mjs';
export function createTerrainSampler(sampleGround,{epsilon=.45}={}){
 if(typeof sampleGround!=='function')throw new TypeError('sampleGround must be a function');
 const height=(x,z)=>{const v=sampleGround(x,z);return typeof v==='number'&&Number.isFinite(v)?v:null};
 return {height,normal:(x,z)=>groundNormal(height,x,z,epsilon)};
}

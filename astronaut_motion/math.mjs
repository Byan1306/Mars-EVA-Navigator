/** Motion Genesis V5: +Y up, -Z forward; metres and radians. Pure IK math. */
export const clamp=(v,a,b)=>Math.min(b,Math.max(a,v));
export const smoothstep=t=>{const x=clamp(t,0,1);return x*x*(3-2*x)};
export const lerp=(a,b,t)=>a+(b-a)*t;
export function solveLegIK(dy,dz,upper=.41,lower=.36){
 if(![dy,dz,upper,lower].every(Number.isFinite)||upper<=0||lower<=0)return null;
 const requested=Math.hypot(dy,dz),maxReach=upper+lower-.003;
 const minReach=Math.abs(upper-lower)+.015;
 const d=clamp(requested,minReach,maxReach);
 const inclination=Math.atan2(-dz,-dy);
 const beta=Math.acos(clamp((upper*upper+lower*lower-d*d)/(2*upper*lower),-1,1));
 const alpha=Math.acos(clamp((upper*upper+d*d-lower*lower)/(2*upper*d),-1,1));
 return {hip:inclination+alpha,shin:-(Math.PI-beta),flexion:Math.PI-beta,
 reach:d,unreachable:requested>maxReach+.002||requested<minReach-.002};
}
export function groundNormal(sample,x,z,epsilon=.45){
 if(!Number.isFinite(epsilon)||epsilon<=0)return null;
 const e=sample(x+epsilon,z),w=sample(x-epsilon,z);
 const n=sample(x,z-epsilon),s=sample(x,z+epsilon);
 if(![e,w,n,s].every(Number.isFinite))return null;
 const nx=-(e-w)/(2*epsilon),ny=1,nz=-(s-n)/(2*epsilon);
 const inv=1/Math.hypot(nx,ny,nz);return [nx*inv,ny*inv,nz*inv];
}
export function raisedFoot(t,h){return Math.max(0,Math.sin(Math.PI*clamp(t,0,1)))*Math.max(0,h)}
export function advancePhase(phase,travel,step=.72){
 if(![phase,travel,step].every(Number.isFinite)||step<=0)return 0;
 return (phase+Math.max(0,travel)/step*Math.PI*2)%(Math.PI*2);
}

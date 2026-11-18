/** One-second browser-measured frame and IK counters. Not native GPU benchmarks. */
export function createMotionMetrics(){
 let n=0,t=0,ms=0,ik=0,slip=0;
 let result={fps:0,frameMs:0,ikSolvesPerSecond:0,footSlipCorrections:0};
 return {
  tick(dt,solves=0,corrections=0){
   if(!Number.isFinite(dt)||dt<=0)return result;
   n++;t+=dt;ms+=dt*1000;ik+=solves;slip+=corrections;
   if(t>=1){result={fps:Math.round(n/t),frameMs:+(ms/n).toFixed(2),
    ikSolvesPerSecond:Math.round(ik/t),footSlipCorrections:slip};
    n=0;t=0;ms=0;ik=0;slip=0;}
   return result;
  },
  read(){return {...result}},
  reset(){n=0;t=0;ms=0;ik=0;slip=0;result={fps:0,frameMs:0,ikSolvesPerSecond:0,footSlipCorrections:0}}
 };
}

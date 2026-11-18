/** Low-cost IK update profiles. Off-screen IK is disabled separately. */
export const MOTION_QUALITY=Object.freeze({
 low:Object.freeze({ikHz:20,normalHz:10,normalDistance:.8,footHeight:.095}),
 balanced:Object.freeze({ikHz:30,normalHz:15,normalDistance:.45,footHeight:.125}),
 high:Object.freeze({ikHz:60,normalHz:30,normalDistance:.25,footHeight:.135})
});
export function motionQuality(name){return MOTION_QUALITY[name]||MOTION_QUALITY.balanced}

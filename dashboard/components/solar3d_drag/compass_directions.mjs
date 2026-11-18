// Cardinal directions in the Three.js scene are derived from ENU:
// Python X=Leste, Y=Norte, Z=altura; Three X=Leste, Y=altura, Z=-Norte.
// Never rotate cardinal bearings with the camera or the module azimuth.
export const CARDINAL_DIRECTIONS = Object.freeze([
  Object.freeze({letter:"N", name:"Norte", azimuth:0, x:0, z:-1}),
  Object.freeze({letter:"L", name:"Leste", azimuth:90, x:1, z:0}),
  Object.freeze({letter:"S", name:"Sul", azimuth:180, x:0, z:1}),
  Object.freeze({letter:"O", name:"Oeste", azimuth:270, x:-1, z:0}),
]);

/** Geographic azimuth is measured clockwise from true north.
 * Three.js: X=east, Y=up, Z=north, with a right-handed coordinate system.
 */
export function sunVector(
  azimuthDeg: number,
  elevationDeg: number,
  radius = 35
): [number, number, number] {
  const azimuth = azimuthDeg * Math.PI / 180;
  const elevation = elevationDeg * Math.PI / 180;
  const horizontal = Math.cos(elevation) * radius;
  return [
    Math.sin(azimuth) * horizontal,
    Math.sin(elevation) * radius,
    Math.cos(azimuth) * horizontal,
  ];
}

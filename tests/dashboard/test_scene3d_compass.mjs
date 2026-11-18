import test from "node:test";
import assert from "node:assert/strict";
import {CARDINAL_DIRECTIONS} from
  "../../dashboard/components/solar3d_drag/compass_directions.mjs";

test("roses are four unique geographic cardinal directions", () => {
  assert.equal(CARDINAL_DIRECTIONS.length,4);
  assert.deepEqual(CARDINAL_DIRECTIONS.map(x=>x.letter), ["N","L","S","O"]);
  assert.deepEqual(CARDINAL_DIRECTIONS.map(x=>x.azimuth), [0,90,180,270]);
  assert.deepEqual(CARDINAL_DIRECTIONS.map(x=>x.name),
                   ["Norte","Leste","Sul","Oeste"]);
});
test("Three.js world X east, negative Z north, invariant to camera angle", () => {
  const vectors=Object.fromEntries(CARDINAL_DIRECTIONS.map(x=>[x.letter,[x.x,x.z]]));
  assert.deepEqual(vectors.N,[0,-1]);
  assert.deepEqual(vectors.S,[0,1]);
  assert.deepEqual(vectors.L,[1,0]);
  assert.deepEqual(vectors.O,[-1,0]);
  for(const dir of CARDINAL_DIRECTIONS) {
    const radians=dir.azimuth*Math.PI/180;
    assert.ok(Math.abs(dir.x-Math.sin(radians))<1e-12);
    assert.ok(Math.abs(dir.z+Math.cos(radians))<1e-12);
  }
});

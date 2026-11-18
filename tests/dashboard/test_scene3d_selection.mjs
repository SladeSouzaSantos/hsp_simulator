import {test} from "node:test";
import assert from "node:assert/strict";
import {updateSelection,applyDropPositions} from
  "../../dashboard/components/solar3d_drag/selection_logic.mjs";

const scene = {
  module: {length_m: 2, width_m: 1, bottom_height_m: .15, tilt_deg: 15,
           azimuth_deg: 0, count: 3, columns: 1, gap_m: .15},
  groups: [{id:"mppt-1",name:"MPPT 1"},{id:"mppt-2",name:"MPPT 2"}],
  panels: [
    {id:"pv-1", mppt_id:"mppt-1", x_m:0,y_m:0,bottom_height_m:.15},
    {id:"pv-2", mppt_id:"mppt-1", x_m:1,y_m:0,bottom_height_m:.8},
    {id:"pv-3", mppt_id:"mppt-2", x_m:2,y_m:0,bottom_height_m:.15},
  ],
  obstacles: [{id:"obs-1",x_m:0,y_m:3,width_m:2,depth_m:.5,height_m:3}],
};
test("Ctrl clicks form and toggle arbitrary multi-selection", () => {
  const first=updateSelection([],"panel:pv-1",scene);
  const second=updateSelection(first,"panel:pv-3",scene,{ctrl:true});
  assert.deepEqual(second,["panel:pv-1","panel:pv-3"]);
  assert.deepEqual(updateSelection(second,"panel:pv-1",scene,{ctrl:true}),
                   ["panel:pv-3"]);
});
test("Shift selects exactly the MPPT, regardless of other groups",()=>{
  assert.deepEqual(updateSelection([],"panel:pv-2",scene,{shift:true}),
                   ["panel:pv-1","panel:pv-2"]);
  assert.deepEqual(updateSelection([],"panel:pv-3",scene,{groupMode:true}),
                   ["panel:pv-3"]);
});
test("Drag XY affects selected panels/obstacles; not z, MPPT or dimensions",()=>{
  const moved=applyDropPositions(scene,{
    "panel:pv-1":{x_m:5.1254,y_m:-7},
    "panel:pv-2":{x_m:6.1254,y_m:-7},
    "obstacle:obs-1":{x_m:1,y_m:4},
  });
  assert.equal(moved.panels[0].x_m,5.125);
  assert.equal(moved.panels[1].y_m,-7);
  assert.equal(moved.panels[1].bottom_height_m,.8);
  assert.equal(moved.panels[1].mppt_id,"mppt-1");
  assert.equal(moved.obstacles[0].height_m,3);
  assert.equal(moved.obstacles[0].y_m,4);
  assert.equal(scene.panels[0].x_m,0);
  assert.equal(moved.module.tilt_deg,15);
});
test("Cannot mutate geometry by sending keys outside X/Y",()=>{
  const moved=applyDropPositions(scene,{
    "panel:pv-1":{x_m:2,y_m:4,bottom_height_m:120,mppt_id:"mppt-2"},
    "obstacle:obs-1":{x_m:2,y_m:4,height_m:999},
    "panel:unrecognized":{x_m:4,y_m:4}
  });
  assert.equal(moved.panels[0].bottom_height_m,.15);
  assert.equal(moved.panels[0].mppt_id,"mppt-1");
  assert.equal(moved.obstacles[0].height_m,3);
  assert.equal(moved.panels.length,3);
});

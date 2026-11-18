import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import {updateSelection, applyDropPositions} from "./selection_logic.mjs";
import {CARDINAL_DIRECTIONS} from "./compass_directions.mjs";

// A viewport Streamlit Component, not st.components.v1.html: this sends
// edited positions back to Python, so HSP uses exactly the visible scene.
const canvasHost = document.getElementById("viewport");
const statusEl = document.getElementById("status");
const groupMode = document.getElementById("group-mode");
const scene = new THREE.Scene();
scene.background = new THREE.Color("#f5f9fc");
const camera = new THREE.PerspectiveCamera(42, 1, 0.05, 5000);
camera.position.set(8, 11, 15);
const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
canvasHost.appendChild(renderer.domElement);
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.minDistance = 1.5;
controls.maxDistance = 500;
controls.maxPolarAngle = Math.PI / 2 - 0.025;
controls.target.set(0, 0.7, 0);
controls.update();
scene.add(new THREE.AmbientLight(0xffffff, 2.0));
const sunLight = new THREE.DirectionalLight(0xffffff, 2);
sunLight.position.set(0, 12, -8);
scene.add(sunLight);
const grid = new THREE.GridHelper(60, 60, 0x6e8f9f, 0xcad9e3);
grid.position.y = -0.015;
scene.add(grid);
const axis = new THREE.AxesHelper(2.5);
axis.position.y = 0.008;
scene.add(axis);
// Geographic compass is static in world coordinates and is not draggable.
const compass = makeCompass();
scene.add(compass);

const raycaster = new THREE.Raycaster();
const pointer = new THREE.Vector2();
const groundPlane = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);
const coords = new THREE.Vector3();
const colors = ["#136ca1", "#2b9348", "#d17a00", "#763eb5",
                "#c44d73", "#008b8b", "#7b644a", "#9a4b1e"];
let editableScene = null;
let lastServerScene = "";
let selections = new Set();
let objects = new Map();
let pickMeshes = [];
let dynamicGroup = new THREE.Group();
let lastDrag = null;
let revision = 0;
let initial = true;
scene.add(dynamicGroup);

function post(type, other = {}) {
  window.parent.postMessage({isStreamlitMessage: true, type: "streamlit:" + type, ...other}, "*");
}
function resize() {
  const w = Math.max(320, canvasHost.clientWidth);
  const h = Math.max(440, canvasHost.clientHeight);
  renderer.setSize(w, h, false);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
  post("setFrameHeight", {height: document.body.scrollHeight + 2});
}
new ResizeObserver(resize).observe(canvasHost);
function animate() {
  requestAnimationFrame(animate);
  controls.update();
  renderer.render(scene, camera);
}
animate();
function pos2d(event) {
  const rect = renderer.domElement.getBoundingClientRect();
  pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
  pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
  raycaster.setFromCamera(pointer, camera);
}
function groundIntersection(event) {
  pos2d(event);
  return raycaster.ray.intersectPlane(groundPlane, coords) ? coords.clone() : null;
}
function clamp(v) { return Math.min(1000, Math.max(-1000, Math.round(v * 1000) / 1000)); }
function normalizedGeometry(module) {
  const a = module.azimuth_deg * Math.PI / 180;
  const b = module.tilt_deg * Math.PI / 180;
  return {
    along: new THREE.Vector3(-Math.sin(a)*Math.cos(b), Math.sin(b), Math.cos(a)*Math.cos(b)),
    across: new THREE.Vector3(Math.cos(a), 0, Math.sin(a)),
    midElevation: module.length_m * Math.sin(b) / 2,
  };
}
function polygonGeometry(corners) {
  const vertices = [0, 1, 2, 0, 2, 3].flatMap(idx => corners[idx].toArray());
  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.Float32BufferAttribute(vertices, 3));
  geo.computeVertexNormals();
  return geo;
}
function panelObject(panel, m, tint) {
  const {along, across, midElevation} = normalizedGeometry(m);
  const s = m.length_m / 2;
  const w = m.width_m / 2;
  const corners = [[-s,-w], [-s,w], [s,w], [s,-w]]
    .map(([a,b]) => along.clone().multiplyScalar(a).addScaledVector(across,b));
  const root = new THREE.Group();
  root.position.set(panel.x_m, panel.bottom_height_m + midElevation, -panel.y_m);
  const mesh = new THREE.Mesh(
    polygonGeometry(corners),
    new THREE.MeshStandardMaterial({
      color: tint, metalness: 0.2, roughness: 0.6,
      side: THREE.DoubleSide, transparent: true, opacity: 0.96,
    })
  );
  const lines = new THREE.LineLoop(
    new THREE.BufferGeometry().setFromPoints(corners),
    new THREE.LineBasicMaterial({color: 0x163c5b})
  );
  root.add(mesh, lines);
  mesh.userData.key = "panel:" + panel.id;
  mesh.userData.kind = "panel";
  dynamicGroup.add(root);
  return {root, mesh, lines, tint};
}
function obstacleObject(obstacle) {
  const root = new THREE.Group();
  root.position.set(obstacle.x_m, 0, -obstacle.y_m);
  const mesh = new THREE.Mesh(
    new THREE.BoxGeometry(obstacle.width_m, obstacle.height_m, obstacle.depth_m),
    new THREE.MeshStandardMaterial({
      color: "#8997a2", opacity: 0.82, transparent: true,
      metalness: 0.0, roughness: 0.85,
    })
  );
  mesh.position.y = obstacle.height_m / 2;
  mesh.userData.key = "obstacle:" + obstacle.id;
  mesh.userData.kind = "obstacle";
  const edges = new THREE.LineSegments(
    new THREE.EdgesGeometry(mesh.geometry),
    new THREE.LineBasicMaterial({color: 0x465662})
  );
  edges.position.copy(mesh.position);
  root.add(mesh, edges);
  dynamicGroup.add(root);
  return {root, mesh, edges, tint: "#8997a2"};
}
function hull2d(raw) {
  const pts = raw.map(p => [p[0],p[1]]).sort((a,b) => a[0]-b[0] || a[1]-b[1]);
  const cross=(o,a,b) => (a[0]-o[0])*(b[1]-o[1])-(a[1]-o[1])*(b[0]-o[0]);
  const lo=[], hi=[];
  for(const p of pts){while(lo.length>1 && cross(lo.at(-2),lo.at(-1),p)<=0)lo.pop();lo.push(p)}
  for(const p of [...pts].reverse()){while(hi.length>1 && cross(hi.at(-2),hi.at(-1),p)<=0)hi.pop();hi.push(p)}
  return lo.slice(0,-1).concat(hi.slice(0,-1));
}
function drawSunAndShadows(sun, obstacles, panels) {
  if (!sun || sun.elevation_deg <= 0) return;
  const er = sun.elevation_deg * Math.PI/180;
  const ar = sun.azimuth_deg * Math.PI/180;
  const dir = new THREE.Vector3(Math.cos(er)*Math.sin(ar), Math.sin(er),
                                -Math.cos(er)*Math.cos(ar));
  const arrow = new THREE.ArrowHelper(dir, new THREE.Vector3(0, 0.7, 0),
                                       5, 0xe8a11a, 0.6, 0.3);
  dynamicGroup.add(arrow);
  for(const ob of obstacles) {
    const xVals=[ob.x_m-ob.width_m/2, ob.x_m+ob.width_m/2];
    const yVals=[ob.y_m-ob.depth_m/2, ob.y_m+ob.depth_m/2];
    const shift = Math.min(ob.height_m/Math.max(Math.tan(er),0.001), 25);
    const east = shift*Math.sin(ar), north=shift*Math.cos(ar);
    const points=[];
    for (const x of xVals) for(const y of yVals) {
      points.push([x,y], [x-east,y-north]);
    }
    const hull=hull2d(points);
    if(hull.length<3) continue;
    const vertices=hull.map(([x,y])=>new THREE.Vector3(x,0.025,-y));
    const geometry=polygonGeometryFromFan(vertices);
    const mesh=new THREE.Mesh(geometry,new THREE.MeshBasicMaterial({
      color: 0x4b5b67, transparent: true, opacity: 0.2,
      depthWrite: false, side: THREE.DoubleSide
    }));
    dynamicGroup.add(mesh);
  }
}
function polygonGeometryFromFan(vertices) {
  const coords=[];
  for(let i=1;i<vertices.length-1;i++) coords.push(...vertices[0].toArray(),
      ...vertices[i].toArray(), ...vertices[i+1].toArray());
  const g=new THREE.BufferGeometry();
  g.setAttribute("position",new THREE.Float32BufferAttribute(coords,3));
  g.computeVertexNormals();
  return g;
}
function makeCompassLabel(letter, north) {
  const canvas = document.createElement("canvas");
  canvas.width = 128;
  canvas.height = 128;
  const ctx = canvas.getContext("2d");
  ctx.beginPath();
  ctx.arc(64, 64, 56, 0, Math.PI * 2);
  ctx.fillStyle = "#ffffff";
  ctx.fill();
  ctx.lineWidth = 8;
  ctx.strokeStyle = north ? "#bf2b31" : "#214b66";
  ctx.stroke();
  ctx.fillStyle = north ? "#bf2b31" : "#214b66";
  ctx.font = "bold 72px system-ui, sans-serif";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(letter, 64, 68);
  const texture = new THREE.CanvasTexture(canvas);
  const material = new THREE.SpriteMaterial({
    map: texture, depthTest: false, depthWrite: false, transparent: true,
  });
  const sprite = new THREE.Sprite(material);
  sprite.scale.set(0.85, 0.85, 1);
  sprite.renderOrder = 30;
  return sprite;
}
function makeCompass() {
  const rose = new THREE.Group();
  rose.name = "Rosa dos ventos (N/S/L/O geográficos)";
  const ring = new THREE.Mesh(
    new THREE.RingGeometry(1.17, 1.22, 64).rotateX(-Math.PI/2),
    new THREE.MeshBasicMaterial({color: 0x214b66,
      side: THREE.DoubleSide, depthWrite: false}),
  );
  ring.position.y = 0.05;
  rose.add(ring);
  for(const direction of CARDINAL_DIRECTIONS) {
    const isNorth = direction.letter === "N";
    const arrow = new THREE.ArrowHelper(
      new THREE.Vector3(direction.x, 0, direction.z),
      new THREE.Vector3(0, 0.08, 0),
      1.06, isNorth ? 0xbf2b31 : 0x214b66, 0.24, 0.15,
    );
    rose.add(arrow);
    const label = makeCompassLabel(direction.letter, isNorth);
    label.name = direction.name;
    label.position.set(direction.x * 1.62, 0.6, direction.z * 1.62);
    rose.add(label);
  }
  return rose;
}
function placeCompassNearScene() {
  const bounds = new THREE.Box3();
  for(const entry of objects.values()) bounds.expandByObject(entry.root);
  if(!bounds.isEmpty()) {
    // Outside the panel/obstacle footprint; does not obstruct drag picking.
    compass.position.set(bounds.min.x - 2.7, 0, bounds.max.z + 2.7);
  }
}

function releaseGroup(group) {
  group.traverse(o => {
    if(o.geometry) o.geometry.dispose();
    if(o.material) {
      if(Array.isArray(o.material)) o.material.forEach(m=>m.dispose());
      else o.material.dispose();
    }
  });
}
function renderObjects(sun, fractions) {
  releaseGroup(dynamicGroup);
  scene.remove(dynamicGroup);
  dynamicGroup = new THREE.Group();
  scene.add(dynamicGroup);
  objects = new Map();
  pickMeshes = [];
  const m = editableScene.module;
  editableScene.panels.forEach((p,index) => {
    const color=colors[Math.max(0,editableScene.groups.findIndex(g=>g.id===p.mppt_id)) % colors.length];
    const entry=panelObject(p,m, (fractions && fractions[index] > 0.15) ? "#d79921" : color);
    objects.set("panel:"+p.id,entry);
    pickMeshes.push(entry.mesh);
  });
  editableScene.obstacles.forEach(ob => {
    const entry=obstacleObject(ob);
    objects.set("obstacle:"+ob.id,entry);
    pickMeshes.push(entry.mesh);
  });
  drawSunAndShadows(sun, editableScene.obstacles, editableScene.panels);
  placeCompassNearScene();
  for(const key of [...selections]) if(!objects.has(key))selections.delete(key);
  updateHighlight();
  if(initial) {
    const points=[...objects.values()].map(o=>o.root.position);
    points.push(compass.position.clone());
    if(points.length) {
      const box=new THREE.Box3().setFromPoints(points);
      const center=box.getCenter(new THREE.Vector3());
      const sz=box.getSize(new THREE.Vector3());
      controls.target.set(center.x, Math.max(0.5,center.y),center.z);
      const radius=Math.max(7,sz.length()*0.7+7);
      camera.position.set(center.x+radius, center.y+radius*1.1, center.z+radius*1.4);
      controls.update();
    }
    initial=false;
  }
}
function updateHighlight() {
  for(const [key,entry] of objects){
    const selected=selections.has(key);
    entry.mesh.material.color.set(selected ? "#ffb703" : entry.tint);
    if(entry.lines)entry.lines.material.color.set(selected ? "#d04d13" : "#163c5b");
    if(entry.edges)entry.edges.material.color.set(selected ? "#d04d13" : "#465662");
  }
  if(!editableScene) return;
  const names=[...selections].map(key => {
    const [kind,id]=key.split(":");
    if(kind==="panel"){
      const p=editableScene.panels.find(x=>x.id===id);
      const label=editableScene.groups.find(g=>g.id===p?.mppt_id)?.name||"MPPT";
      return (p?.id||id)+" ("+label+")";
    }
    return id;
  });
  statusEl.textContent=names.length
    ? "Selecionados: "+names.join(", ")+" · arraste para mover no plano horizontal (altura não muda)."
    : "Selecione uma placa ou obstáculo. Ctrl adiciona/remove da seleção; Shift seleciona todas as placas do mesmo MPPT.";
}
function publish() {
  revision += 1;
  post("setComponentValue", {
    value: {
      revision,
      scene: editableScene,
      selection: [...selections],
    }
  });
}
function selectHit(key, event) {
  selections = new Set(updateSelection([...selections],key,editableScene,{
    ctrl:event.ctrlKey, meta:event.metaKey, shift:event.shiftKey,
    groupMode:groupMode.checked,
  }));
  updateHighlight();
}
renderer.domElement.addEventListener("pointerdown", event => {
  if(event.button !== 0 || !editableScene) return;
  pos2d(event);
  const hits = raycaster.intersectObjects(pickMeshes, false);
  if (!hits.length) {
    if(event.ctrlKey || event.metaKey) {
      selections.clear();
      updateHighlight();
    }
    return; // Pass empty-space gestures to OrbitControls.
  }
  event.preventDefault();
  event.stopImmediatePropagation();
  selectHit(hits[0].object.userData.key, event);
  const start=groundIntersection(event);
  if(!start) return;
  const initialPositions=new Map();
  for(const key of selections) {
    const entry=objects.get(key);
    if(entry) initialPositions.set(key, entry.root.position.clone());
  }
  lastDrag={id:event.pointerId,start, initialPositions, moved:false};
  controls.enabled=false;
  renderer.domElement.setPointerCapture(event.pointerId);
}, true);
renderer.domElement.addEventListener("pointermove", event => {
  if(!lastDrag || lastDrag.id !== event.pointerId) return;
  event.preventDefault();
  event.stopImmediatePropagation();
  const current=groundIntersection(event);
  if(!current)return;
  const delta=current.sub(lastDrag.start);
  delta.y=0;
  if(delta.lengthSq()>0.000004) lastDrag.moved=true;
  for(const [key,start] of lastDrag.initialPositions){
    const entry=objects.get(key);
    if(!entry) continue;
    entry.root.position.x=clamp(start.x+delta.x);
    entry.root.position.z=clamp(start.z+delta.z);
  }
}, true);
function finishDrag(event) {
  if(!lastDrag || event.pointerId !== lastDrag.id)return;
  event.preventDefault();
  event.stopImmediatePropagation();
  const moved={};
  for(const key of lastDrag.initialPositions.keys()){
    const entry=objects.get(key);
    if(!entry)continue;
    moved[key]={x_m:clamp(entry.root.position.x),
                y_m:clamp(-entry.root.position.z)};
  }
  editableScene=applyDropPositions(editableScene,moved);
  lastDrag=null;
  controls.enabled=true;
  if(renderer.domElement.hasPointerCapture(event.pointerId))
    renderer.domElement.releasePointerCapture(event.pointerId);
  updateHighlight();
  // Persist only at pointer-up, never during movement (avoids Streamlit reruns).
  publish();
}
renderer.domElement.addEventListener("pointerup",finishDrag,true);
renderer.domElement.addEventListener("pointercancel",finishDrag,true);
function handleStreamlitRender(payload) {
  if(payload?.type !== "streamlit:render") return;
  const args=payload.args||{};
  if (!args.scene || !args.scene.module) return;
  const next=JSON.stringify(args.scene);
  const sun=JSON.stringify(args.sun||{});
  const fractions=JSON.stringify(args.fractions||[]);
  const combined=next+"|"+sun+"|"+fractions;
  if(combined !== lastServerScene){
    editableScene=JSON.parse(next);
    lastServerScene=combined;
    renderObjects(args.sun,args.fractions);
  }
  resize();
}
window.addEventListener("message", event => {
  if(event.source === window.parent) handleStreamlitRender(event.data);
});
// index.html already sends streamlit:componentReady, even if JS/WebGL
// fails to initialize. Reconsume the latest render message captured
// before the bundled editor was ready to receive it.
const boot = window.__hsp3dBoot;
if(boot){
  boot.loaded = true;
  document.getElementById("error").style.display = "none";
  if(boot.pending) {
    handleStreamlitRender(boot.pending);
    boot.pending = null;
  }
}
window.addEventListener("keydown", event => {
  if(event.key==="Escape"){
    selections.clear();
    updateHighlight();
  }
});
resize();
// The Streamlit v1 handshake is sent once, synchronously from index.html.

/** Metres in a local tangent plane: east=X, north=Z, elevation=Y in Three.js. */
import { defaultElectricalDesign, parseElectricalDesign } from "./electrical";
import type { ElectricalDesign } from "./electrical";
export type SceneKind = "building" | "obstacle" | "panel";
export type Position = { east: number; north: number; elevation: number };
export type SceneObject = {
  id: string;
  name: string;
  kind: SceneKind;
  position: Position; // center of the geometry, NOT its bottom edge
  width: number;      // east-west before rotation
  depth: number;      // north-south before rotation
  height: number;     // vertical extent for solids; thickness for modules
  azimuth: number;    // 0=N, 90=E
  tilt: number;       // panel inclination, degrees
};
export type SolarSample = {
  local_time: string;
  utc_time: string;
  azimuth_deg: number;
  elevation_deg: number;
  apparent_elevation_deg: number;
};
export type SolarDay = {
  latitude: number;
  longitude: number;
  local_date: string;
  timezone: string;
  samples: SolarSample[];
  visual_only: boolean;
};

const panel = (id: string, east: number, north: number): SceneObject => ({
  id, name: "Módulo " + id, kind: "panel",
  position: { east, north, elevation: 3.48 },
  width: 1.134, depth: 2.278, height: 0.045, azimuth: 0, tilt: 12,
});

export const INITIAL_OBJECTS: SceneObject[] = [
  { id: "roof-1", name: "Edificação / laje", kind: "building",
    position: { east: 0, north: 0, elevation: 1.5 }, width: 9, depth: 8,
    height: 3, azimuth: 0, tilt: 0 },
  { id: "wall-1", name: "Muro a leste", kind: "obstacle",
    position: { east: 6.5, north: 0, elevation: 2.1 }, width: 0.22, depth: 9,
    height: 4.2, azimuth: 0, tilt: 0 },
  ...[-2.4, -1.1, 0.2].flatMap((east, row) =>
    [-1.45, 1.45].map((north, column) => panel(
      "M" + String(row * 2 + column + 1).padStart(2, "0"), east, north
    ))
  ),
];

export type SolarProject = {
  schema_version: 2;
  latitude: number;
  longitude: number;
  timezone: string;
  objects: SceneObject[];
  electrical: ElectricalDesign;
};

const finite = (value: unknown): value is number =>
  typeof value === "number" && Number.isFinite(value);

export function parseProject(raw: unknown): SolarProject {
  if (!raw || typeof raw !== "object") throw new Error("Projeto inválido.");
  const data = raw as Record<string, unknown>;
  if ((data.schema_version !== 1 && data.schema_version !== 2) ||
      !finite(data.latitude) || !finite(data.longitude) ||
      Math.abs(data.latitude) > 90 || Math.abs(data.longitude) > 180 ||
      typeof data.timezone !== "string" || data.timezone.length > 128 ||
      !Array.isArray(data.objects) || data.objects.length > 250) {
    throw new Error("Esquema de projeto não suportado.");
  }
  const ids = new Set<string>();
  for (const item of data.objects) {
    if (!item || typeof item !== "object") throw new Error("Objeto inválido.");
    const obj = item as SceneObject;
    if (typeof obj.id !== "string" || !obj.id || ids.has(obj.id) ||
        typeof obj.name !== "string" || obj.name.length > 120 ||
        !["building", "obstacle", "panel"].includes(obj.kind) ||
        !obj.position || ![obj.position.east, obj.position.north, obj.position.elevation,
          obj.width, obj.depth, obj.height, obj.azimuth, obj.tilt].every(finite) ||
        obj.width <= 0 || obj.depth <= 0 || obj.height <= 0 ||
        obj.width > 1000 || obj.depth > 1000 || obj.height > 1000 ||
        Math.abs(obj.position.east) > 10000 || Math.abs(obj.position.north) > 10000 ||
        Math.abs(obj.position.elevation) > 10000 ||
        obj.tilt < 0 || obj.tilt > 90 || obj.azimuth < 0 || obj.azimuth >= 360) {
      throw new Error("Geometria inválida no arquivo.");
    }
    ids.add(obj.id);
  }
  // v1 files predate the electrical topology. Migrate without silently
  // connecting any module; the user must explicitly approve wiring.
  const objects = data.objects as SceneObject[];
  const electrical = data.schema_version === 1
    ? defaultElectricalDesign(objects, false)
    : parseElectricalDesign(data.electrical);
  return {
    schema_version: 2,
    latitude: data.latitude as number,
    longitude: data.longitude as number,
    timezone: data.timezone as string,
    objects,
    electrical,
  };
}

export function makeObject(kind: SceneKind, index: number): SceneObject {
  const id = kind + "-" + crypto.randomUUID();
  if (kind === "panel") return {
    ...panel(id, 0, -index % 7), name: "Novo módulo",
  };
  return {
    id,
    kind,
    name: kind === "building" ? "Nova edificação" : "Novo obstáculo",
    position: { east: kind === "building" ? -5 : 5, north: 0, elevation: 1.5 },
    width: kind === "building" ? 6 : 0.25,
    depth: kind === "building" ? 5 : 5,
    height: 3, azimuth: 0, tilt: 0,
  };
}

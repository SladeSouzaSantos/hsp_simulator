import { describe, expect, it } from "vitest";
import { INITIAL_OBJECTS, parseProject } from "./model";
import { defaultElectricalDesign } from "./electrical";

describe("Solar3D project schema v2", () => {
  const base = {
    latitude: -5.9252, longitude: -35.205,
    timezone: "America/Fortaleza", objects: INITIAL_OBJECTS,
  };
  it("imports old schema v1 without assigning wiring", () => {
    const project = parseProject({ ...base, schema_version: 1 });
    expect(project.schema_version).toBe(3);
    expect(project.electrical.strings).toEqual([]);
    expect(project.meshes).toEqual([]);
    expect(Object.keys(project.electrical.module_model_ids)).toHaveLength(6);
  });
  it("roundtrips v2 electrical topology and exact string order", () => {
    const electrical = defaultElectricalDesign(INITIAL_OBJECTS, true);
    const source = { ...base, schema_version: 2, electrical };
    const project = parseProject(JSON.parse(JSON.stringify(source)));
    expect(project).toEqual({ ...source, schema_version: 3, meshes: [] });
    expect(project.electrical.strings[0].module_ids).toEqual(["M01", "M02", "M03"]);
  });
  it("rejects v2 without electrical content", () => {
    expect(() => parseProject({ ...base, schema_version: 2 })).toThrow();
  });
});

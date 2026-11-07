import { describe, expect, it } from "vitest";
import { sunVector } from "./solarMath";
import { parseProject, INITIAL_OBJECTS } from "./model";

describe("geographic 3D solar convention", () => {
  it("points north at azimuth 0", () => {
    const [x, y, z] = sunVector(0, 0, 10);
    expect(x).toBeCloseTo(0);
    expect(y).toBeCloseTo(0);
    expect(z).toBeCloseTo(10);
  });
  it("points east at azimuth 90", () => {
    const [x, , z] = sunVector(90, 0, 10);
    expect(x).toBeCloseTo(10);
    expect(z).toBeCloseTo(0);
  });
  it("points up at elevation 90", () => {
    const [, y] = sunVector(142, 90, 10);
    expect(y).toBeCloseTo(10);
  });
  it("puts night sun below horizon", () => {
    const [, y] = sunVector(30, -4);
    expect(y).toBeLessThan(0);
  });
});

describe("scene schema", () => {
  it("accepts a clean versioned project", () => {
    const p = parseProject({ schema_version: 1, latitude: -5.9,
      longitude: -35.2, timezone: "America/Fortaleza", objects: INITIAL_OBJECTS });
    expect(p.objects.length).toBeGreaterThan(1);
  });
  it("rejects invalid geometry", () => {
    expect(() => parseProject({ schema_version: 1, latitude: -5.9,
      longitude: -35.2, timezone: "America/Fortaleza",
      objects: [{ ...INITIAL_OBJECTS[0], width: -1 }] })).toThrow();
  });
});

import { describe, expect, it } from "vitest";
import { parseMeshes } from "./meshModel";

describe("F3.1 mesh object geometry", () => {
  const mesh = { id: "roof", name: "roof",
    vertices: [[0, 2, 0], [2, 2, 0], [0, 2, 2]],
    triangles: [[0, 1, 2]] };
  it("accepts a valid triangular obstacle", () => {
    expect(parseMeshes([mesh])).toHaveLength(1);
  });
  it("rejects invalid faces, coordinates and degenerate triangles", () => {
    expect(() => parseMeshes([{ ...mesh, triangles: [[0, 1, 3]] }])).toThrow();
    expect(() => parseMeshes([{ ...mesh, vertices: [[0, 2, 0], [1, 2, 0], [2, 2, 0]] }])).toThrow();
    expect(() => parseMeshes([{ ...mesh, vertices: [[0, 2, NaN]] }])).toThrow();
  });
});

/** Opaque triangular obstruction in local metric X=East, Y=up, Z=North. */
export type MeshObstacle = {
  id: string;
  name: string;
  vertices: [number, number, number][];
  triangles: [number, number, number][];
};

export function parseMeshes(raw: unknown): MeshObstacle[] {
  if (!Array.isArray(raw) || raw.length > 20) throw new Error("Quantidade de malhas inválida.");
  const meshes: MeshObstacle[] = [];
  const ids = new Set<string>();
  for (const item of raw) {
    if (!item || typeof item !== "object") throw new Error("Malha inválida.");
    const m = item as MeshObstacle;
    if (typeof m.id !== "string" || !m.id || m.id.length > 120 || ids.has(m.id) ||
        typeof m.name !== "string" || m.name.length > 120 ||
        !Array.isArray(m.vertices) || !Array.isArray(m.triangles) ||
        m.vertices.length < 3 || m.vertices.length > 500 ||
        m.triangles.length < 1 || m.triangles.length > 1000) {
      throw new Error("Malha com identificador ou tamanho inválido.");
    }
    const validVertex = (xyz: unknown): xyz is [number, number, number] =>
      Array.isArray(xyz) && xyz.length === 3 && xyz.every(
        (v) => typeof v === "number" && Number.isFinite(v) && Math.abs(v) <= 10000);
    if (!m.vertices.every(validVertex) ||
        !m.triangles.every((face) => Array.isArray(face) && face.length === 3 &&
          face.every((i) => Number.isInteger(i) && i >= 0 && i < m.vertices.length))) {
      throw new Error("Coordenadas ou índices de triângulos inválidos.");
    }
    // Reject zero-area triangles; F3 backend performs the same physical check.
    for (const [i, j, k] of m.triangles) {
      const a = m.vertices[i], b = m.vertices[j], c = m.vertices[k];
      const u = b.map((n, t) => n - a[t]);
      const v = c.map((n, t) => n - a[t]);
      const cross = [u[1] * v[2] - u[2] * v[1],
        u[2] * v[0] - u[0] * v[2],
        u[0] * v[1] - u[1] * v[0]];
      if (Math.hypot(...cross) <= 1e-8) throw new Error("Triângulo de área nula.");
    }
    ids.add(m.id);
    meshes.push(m);
  }
  return meshes;
}

export function sampleRoof(): MeshObstacle {
  const id = "roof-mesh-" + crypto.randomUUID();
  // Simple two-slope roof, independent of the default building.
  return {
    id, name: "Cobertura inclinada (malha triangular)",
    vertices: [
      [7, 3.4, -2], [15, 3.4, -2],
      [7, 5.1, 0], [15, 5.1, 0],
      [7, 3.4, 2], [15, 3.4, 2],
    ],
    triangles: [[0, 1, 3], [0, 3, 2], [2, 3, 5], [2, 5, 4]],
  };
}

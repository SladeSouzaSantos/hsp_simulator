import { describe, expect, it } from "vitest";
import { activeShading } from "./shadingModel";
import type { ShadingDayResult } from "./shadingModel";
import type { SolarSample } from "./model";

const sample: SolarSample = {
  local_time: "2026-11-07T12:00:00-03:00",
  utc_time: "2026-11-07T15:00:00+00:00",
  azimuth_deg: 12,
  elevation_deg: 50,
  apparent_elevation_deg: 50,
};

const result: ShadingDayResult = {
  geometry_only: true,
  schema_version: 1,
  model: "ray_oriented_boxes_front_sampling_v1",
  quantity: "fraction_of_direct_front_area",
  local_date: "2026-11-07",
  timezone: "America/Fortaleza",
  sampling: { rows: 2, columns: 2, cells_per_module: 4 },
  solar_samples_utc: [sample.utc_time],
  modules: [{ id: "P1", name: "Panel", direct_eligible_intervals: 1,
    shaded_direct_intervals: 1, mean_blocked_fraction_direct_eligible: 0.5,
    frames: [{ blocked_fraction: 0.5, blocked_cells: [0, 0, 1, 1] }] }],
  limitations: [],
};

describe("F3 solar/shade synchronization", () => {
  it("returns the exact module frame for the solar timestamp", () => {
    expect(activeShading(result, sample, 0, "P1")?.blocked_fraction).toBe(0.5);
  });
  it("rejects stale dates and timestamps", () => {
    expect(activeShading(result, { ...sample, utc_time: "changed" }, 0, "P1")).toBe(null);
  });
  it("rejects unmatched module IDs and missing data", () => {
    expect(activeShading(result, sample, 0, "missing")).toBe(null);
    expect(activeShading(null, sample, 0, "P1")).toBe(null);
  });
});

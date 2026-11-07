import { describe, expect, it } from "vitest";
import { INITIAL_OBJECTS } from "./model";
import { assignPanelToString, defaultElectricalDesign,
  deleteModuleFromDesign, parseElectricalDesign, registerModule } from "./electrical";

describe("F4 topology model", () => {
  it("builds clearly unverified sample equipment and two strings", () => {
    const d = defaultElectricalDesign(INITIAL_OBJECTS, true);
    expect(d.inverter.verified_datasheet).toBe(false);
    expect(d.module_catalog[0].verified_datasheet).toBe(false);
    expect(d.strings.map((s) => s.module_ids.length)).toEqual([3, 3]);
    expect(d.inverter.mppts.map((m) => m.id)).toEqual(["MPPT1", "MPPT2"]);
  });
  it("moves a panel atomically from one string to another", () => {
    const initial = defaultElectricalDesign(INITIAL_OBJECTS, true);
    const next = assignPanelToString(initial, "S2", "M01", INITIAL_OBJECTS);
    expect(next.strings[0].module_ids).not.toContain("M01");
    expect(next.strings[1].module_ids).toContain("M01");
    expect(initial.strings[0].module_ids).toContain("M01");
    expect(assignPanelToString(next, "S2", "M01", INITIAL_OBJECTS)
      .strings[1].module_ids).not.toContain("M01");
  });
  it("rejects wiring non-panels or a nonexistent string", () => {
    const d = defaultElectricalDesign(INITIAL_OBJECTS, true);
    expect(assignPanelToString(d, "S1", "roof-1", INITIAL_OBJECTS)).toBe(d);
    expect(assignPanelToString(d, "NONE", "M01", INITIAL_OBJECTS)).toBe(d);
  });
  it("removes stale mappings and wires for deleted module", () => {
    const d = deleteModuleFromDesign(defaultElectricalDesign(INITIAL_OBJECTS, true), "M01");
    expect(d.module_model_ids.M01).toBeUndefined();
    expect(d.strings[0].module_ids).not.toContain("M01");
  });
  it("registers newly added module without silently wiring it", () => {
    const d = defaultElectricalDesign(INITIAL_OBJECTS, true);
    const next = registerModule(d, "P-NEW");
    expect(next.module_model_ids["P-NEW"]).toBe("DEMO-550");
    expect(next.strings.flatMap((s) => s.module_ids)).not.toContain("P-NEW");
  });
  it("imports valid electrical JSON and rejects malformed specification", () => {
    const d = defaultElectricalDesign(INITIAL_OBJECTS, false);
    expect(parseElectricalDesign(JSON.parse(JSON.stringify(d)))).toEqual(d);
    expect(() => parseElectricalDesign({ ...d, strings: [{ id: "S", module_ids: 2 }] })).toThrow();
    expect(() => parseElectricalDesign({ ...d, module_catalog: [] })).toThrow();
  });
});

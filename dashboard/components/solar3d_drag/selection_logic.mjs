// Pure, browser-independent editor operations. MPPT is geometry-only.
export function updateSelection(currentKeys, targetKey, scene, options = {}) {
  const selected = new Set(currentKeys);
  const [kind, id] = targetKey.split(":");
  const panel = kind === "panel" ? scene.panels.find(p => p.id === id) : null;
  const wholeGroup = Boolean(panel && (options.shift || options.groupMode));
  const chosen = wholeGroup
    ? scene.panels.filter(p => p.mppt_id === panel.mppt_id)
        .map(p => "panel:" + p.id)
    : [targetKey];
  if (options.ctrl || options.meta) {
    const already = chosen.every(k => selected.has(k));
    for (const key of chosen) already ? selected.delete(key) : selected.add(key);
  } else if (!selected.has(targetKey) || wholeGroup) {
    return chosen;
  }
  return [...selected];
}

export function applyDropPositions(scene, moved) {
  // Position updates are X/Y only. Height, dimensions, group and tilt
  // can only be modified through Streamlit numeric/editor controls.
  const clone = JSON.parse(JSON.stringify(scene));
  const clamp = v => Math.max(-1000, Math.min(1000, Math.round(v*1000)/1000));
  for (const [key, location] of Object.entries(moved)) {
    const [kind, id] = key.split(":");
    const items = kind === "panel" ? clone.panels
      : kind === "obstacle" ? clone.obstacles : [];
    const item = items.find(p => p.id === id);
    if (item && Number.isFinite(location.x_m) && Number.isFinite(location.y_m)) {
      item.x_m = clamp(location.x_m);
      item.y_m = clamp(location.y_m);
    }
  }
  return clone;
}

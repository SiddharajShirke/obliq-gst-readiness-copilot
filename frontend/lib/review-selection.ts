export function selectAllVisible(
  current: Set<string>,
  visibleEligibleIds: string[],
  checked: boolean,
): Set<string> {
  const next = new Set(current);
  for (const id of visibleEligibleIds) {
    if (checked) next.add(id);
    else next.delete(id);
  }
  return next;
}

export function trimSelectionToVisible(
  current: Set<string>,
  visibleEligibleIds: string[],
): Set<string> {
  const visible = new Set(visibleEligibleIds);
  return new Set([...current].filter(id => visible.has(id)));
}

export function selectionState(
  current: Set<string>,
  visibleEligibleIds: string[],
): {checked: boolean; indeterminate: boolean; selectedVisibleCount: number} {
  const selectedVisibleCount = visibleEligibleIds.filter(id => current.has(id)).length;
  return {
    checked: visibleEligibleIds.length > 0 && selectedVisibleCount === visibleEligibleIds.length,
    indeterminate: selectedVisibleCount > 0 && selectedVisibleCount < visibleEligibleIds.length,
    selectedVisibleCount,
  };
}

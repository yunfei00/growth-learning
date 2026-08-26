type Identified = { id: string };

export const ACTIVE_FAMILY_KEY = "growth-learning:active-family-id";

export function activeChildKey(familyId: string): string {
  return `growth-learning:active-child:${familyId}`;
}

export function selectRemembered<T extends Identified>(
  items: T[],
  rememberedId: string | null,
): T | null {
  if (items.length === 0) return null;
  return items.find((item) => item.id === rememberedId) ?? items.at(0) ?? null;
}

export async function loadFamilyChildren<T extends Identified>(
  familyId: string,
  rememberedChildId: string | null,
  loader: (selectedFamilyId: string) => Promise<T[]>,
): Promise<{ children: T[]; activeChild: T | null }> {
  const children = await loader(familyId);
  return { children, activeChild: selectRemembered(children, rememberedChildId) };
}

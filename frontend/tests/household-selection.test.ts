import assert from "node:assert/strict";
import test from "node:test";

import {
  ACTIVE_FAMILY_KEY,
  activeChildKey,
  loadFamilyChildren,
  selectRemembered,
} from "../src/lib/household-selection.ts";

test("active child persistence is scoped by family", () => {
  assert.equal(ACTIVE_FAMILY_KEY, "growth-learning:active-family-id");
  assert.equal(activeChildKey("family-a"), "growth-learning:active-child:family-a");
  assert.notEqual(activeChildKey("family-a"), activeChildKey("family-b"));
});

test("switching family reloads only that family's children", async () => {
  const loadedFamilyIds: string[] = [];
  const result = await loadFamilyChildren("family-b", "child-b2", async (familyId) => {
    loadedFamilyIds.push(familyId);
    return [{ id: "child-b1" }, { id: "child-b2" }];
  });
  assert.deepEqual(loadedFamilyIds, ["family-b"]);
  assert.equal(result.activeChild?.id, "child-b2");
});

test("remembered selection wins and an unavailable selection falls back safely", () => {
  const households = [{ id: "family-a" }, { id: "family-b" }];
  assert.equal(selectRemembered(households, "family-b")?.id, "family-b");
  assert.equal(selectRemembered(households, "gone")?.id, "family-a");
  assert.equal(selectRemembered([], "family-a"), null);
});

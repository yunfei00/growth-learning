import assert from "node:assert/strict";
import test from "node:test";

import { resolveAppHeaderMode } from "../src/lib/header-mode.ts";

test("system admin routes use only the dedicated admin header", () => {
  assert.equal(
    resolveAppHeaderMode({
      pathname: "/admin/users",
      authenticated: true,
      systemAdmin: true,
      childMode: true,
    }),
    "admin",
  );
});

test("normal parent and child routes keep their existing header modes", () => {
  assert.equal(
    resolveAppHeaderMode({
      pathname: "/home",
      authenticated: true,
      systemAdmin: true,
      childMode: false,
    }),
    "parent",
  );
  assert.equal(
    resolveAppHeaderMode({
      pathname: "/kids",
      authenticated: true,
      systemAdmin: false,
      childMode: true,
    }),
    "child",
  );
});

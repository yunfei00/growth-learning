import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import test from "node:test";

import { resolveStaticEnglishVisual } from "../src/lib/english-visual-display.ts";
import { withAppBasePath } from "../src/lib/public-assets.ts";

const component = readFileSync(
  new URL("../src/components/english-visual.tsx", import.meta.url),
  "utf8",
);

test("public assets use the configured application basePath exactly once", () => {
  assert.equal(withAppBasePath("/english/visuals/dog.svg", ""), "/english/visuals/dog.svg");
  assert.equal(
    withAppBasePath("/english/visuals/dog.svg", "/growth"),
    "/growth/english/visuals/dog.svg",
  );
  assert.equal(
    withAppBasePath("/growth/english/visuals/dog.svg", "/growth"),
    "/growth/english/visuals/dog.svg",
  );
  assert.equal(withAppBasePath("https://cdn.example/dog.svg", "/growth"), "https://cdn.example/dog.svg");
});

test("all project-curated English static visuals exist", () => {
  for (const word of ["cat", "dog", "apple", "ball", "sun", "moon"]) {
    const path = new URL(`../public/english/visuals/${word}.svg`, import.meta.url);
    assert.equal(existsSync(path), true, `${word}.svg should exist`);
    assert.match(readFileSync(path, "utf8"), /<svg/);
  }
});

test("a failed static image becomes its symbol instead of a broken image", () => {
  const visual = { image_url: "/english/visuals/dog.svg", visual_key: "🐶" };
  assert.deepEqual(resolveStaticEnglishVisual(visual, false, "/growth"), {
    kind: "image",
    src: "/growth/english/visuals/dog.svg",
  });
  assert.deepEqual(resolveStaticEnglishVisual(visual, true, "/growth"), {
    kind: "fallback",
    symbol: "🐶",
  });
  assert.deepEqual(
    resolveStaticEnglishVisual({ image_url: "/missing.svg", visual_key: null }, true),
    { kind: "fallback", symbol: "🔊" },
  );
});

test("EnglishVisualCard switches rendering on a real image error", () => {
  assert.match(component, /onError=\{\(\) => setFailedImageUrl\(visual\.image_url\)\}/);
  assert.match(component, /data-visual-fallback="true"/);
  assert.match(component, /resolveStaticEnglishVisual/);
});

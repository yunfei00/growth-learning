import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const home = readFileSync(new URL("../src/app/home/page.tsx", import.meta.url), "utf8");
const learn = readFileSync(new URL("../src/app/learn/page.tsx", import.meta.url), "utf8");

const SUBJECT_ROUTES = [
  "/learn/characters",
  "/learn/pinyin",
  "/learn/math",
  "/learn/english",
  "/read",
  "/science",
];

test("parent home exposes all six real subject destinations", () => {
  for (const route of SUBJECT_ROUTES) assert.match(home, new RegExp(route.replaceAll("/", "\\/")));
  assert.match(home, /getCharacterMasterySummary/);
  assert.match(home, /getPinyinOverview/);
  assert.match(home, /getMathOverview/);
  assert.match(home, /getEnglishOverview/);
  assert.match(home, /getReadingSummary/);
  assert.match(home, /listScienceRecommendations/);
  assert.match(home, /learning-grid/);
});

test("Today remains subject-specific and chooses the first unfinished task", () => {
  assert.match(home, /getPinyinToday/);
  assert.match(home, /getMathToday/);
  assert.match(home, /getEnglishToday/);
  assert.match(home, /parent-today-subject-grid/);
  assert.match(home, /todayStartHref/);
  assert.match(home, /今天完成啦/);
  assert.doesNotMatch(home, /className="button button-primary today-start" href="\/learn\/characters"/);
});

test("one failed subject does not blank the other dashboard cards", () => {
  assert.match(home, /Promise\.allSettled/);
  assert.match(home, /subjectErrors/);
  assert.match(learn, /Promise\.allSettled/);
  assert.match(learn, /setCharacters\(null\)/);
  assert.match(learn, /setPinyin\(null\)/);
  assert.match(learn, /setMath\(null\)/);
  assert.match(learn, /setEnglish\(null\)/);
});

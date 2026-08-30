import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const admin = readFileSync(new URL("../src/app/admin/courses/page.tsx", import.meta.url), "utf8");
const browser = readFileSync(new URL("../src/app/courses/page.tsx", import.meta.url), "utf8");
const family = readFileSync(new URL("../src/app/settings/family/page.tsx", import.meta.url), "utf8");
const api = readFileSync(new URL("../src/lib/api/client.ts", import.meta.url), "utf8");
const styles = readFileSync(new URL("../src/app/globals.css", import.meta.url), "utf8");

test("admin curriculum center navigates grade, semester, subject, and release layers", () => {
  assert.match(admin, /课程内容中心/);
  assert.match(admin, /const GRADES = \[0, 1, 2, 3, 4, 5, 6, 7, 8, 9\]/);
  assert.match(admin, /semester_1/);
  assert.match(admin, /semester_2/);
  for (const subject of ["语文", "数学", "英语", "科学"]) assert.match(admin, new RegExp(subject));
  assert.match(admin, /尚未创建/);
  assert.match(admin, /创建 Draft/);
});

test("builder keeps the formal hierarchy and canonical knowledge picker", () => {
  assert.match(admin, /Course → Unit → Lesson → Activity → Canonical KnowledgePoint/);
  assert.match(admin, /addCurriculumUnit/);
  assert.match(admin, /addCurriculumLesson/);
  assert.match(admin, /addCurriculumActivity/);
  assert.match(admin, /addCurriculumKnowledgePoint/);
  assert.match(admin, /listAdminKnowledge/);
  assert.match(admin, /moveCurriculumNode/);
  assert.match(admin, /status: "archived"/);
});

test("workflow exposes validation, preview, export, immutable review, and new version", () => {
  assert.match(admin, /validateCurriculumRelease/);
  assert.match(admin, /previewCurriculumRelease/);
  assert.match(admin, /Draft Preview · 无学习写入/);
  assert.match(admin, /exportCurriculumRelease/);
  assert.match(admin, /transitionCurriculumRelease/);
  assert.match(admin, /送审/);
  assert.match(admin, /审核通过/);
  assert.match(admin, /创建新版本/);
  assert.match(admin, /孩子 Evidence 未复制/);
});

test("parent browser recommends but does not lock the child's grade", () => {
  assert.match(browser, /activeChild\.current_grade_level/);
  assert.match(browser, /Array\.from\(\{ length: 9 \}/);
  assert.match(browser, /semester_1/);
  assert.match(browser, /semester_2/);
  assert.match(browser, /course\.curriculum_version/);
  assert.match(api, /grade_level/);
  assert.match(api, /education_stage/);
});

test("family admin can explicitly set grade and school year without birthday inference", () => {
  assert.match(family, /当前年级/);
  assert.match(family, /学年（可选）/);
  assert.match(family, /current_grade_level/);
  assert.match(family, /school_year/);
  assert.match(family, /不根据生日自动推断/);
});

test("curriculum content center remains responsive", () => {
  assert.match(styles, /\.curriculum-grade-tabs/);
  assert.match(styles, /\.curriculum-subject-grid/);
  assert.match(styles, /\.curriculum-builder-panel/);
  assert.match(styles, /@media \(max-width: 760px\)/);
});

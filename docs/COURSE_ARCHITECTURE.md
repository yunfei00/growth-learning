# Reusable Course Architecture and Chinese Catalog

## Canonical knowledge boundary

`KnowledgePoint` remains the only system knowledge identity. A course never creates a
`CourseCharacter`, mastery table, or parallel answer record. The reusable path is:

```text
Course → CourseUnit → LearningActivity → ActivityKnowledgePoint → KnowledgePoint
```

Activity mappings have an explicit `primary`, `review`, `optional`, or `prerequisite` role and
stable order. The same `KnowledgePoint(山)` can therefore appear in system, family, teacher, and
textbook-reference courses without duplicating its UUID.

Course progress is the fraction of completed activities. Knowledge summaries are separately read
from `ChildKnowledgeState`; completing an activity creates canonical `LearningRecord` exposure and
never writes `mastery_level = stable`.

## Course ownership and authorization

- `system`: managed by System Admin; it does not grant access to household data.
- `family` / `textbook_reference`: owned by a family and administered only by Family Admin.
- `teacher`: owned by one `TeacherProfile`; visibility to a child additionally requires an active
  `TeacherChildRelation` confirmed by Family Admin.
- Companion may accompany an active activity, but cannot create, archive, enroll, reorder, pause,
  copy, or otherwise administer a course path.

Copying a sibling path copies enrollment choices, order, version, and path settings only. It never
copies `ChildKnowledgeState`, `LearningRecord`, `AssessmentItem`, review schedules, literacy
estimates, stories, reading/science history, growth events, or teacher observations.

## Daily-plan precedence

The deterministic selection order is:

```text
authorization/safety
→ explicit teacher assignments (independent task source)
→ due review capacity and backlog
→ priority unintroduced points
→ dynamic new-character capacity
→ active course path/order
→ fallback canonical order
```

Review V1 decides the number of new characters. Courses only order the eligible candidates. When
the dynamic recommendation is zero, the course selector is not queried and cannot force new work.

## Catalog v2 provenance

- Catalog version: `growth-chinese-v2-unihan-2026`
- Size: 1,200 simplified Chinese characters
- Sources: Growth Learning project-owned 200-character starter catalog plus Unicode Unihan
  `kHanyuPinlu`, `kMandarin`, `kGB0`, and simplified-variant properties
- Upstream: <https://www.unicode.org/Public/UNIDATA/Unihan.zip>
- License: `Unicode-3.0`; the required notice is vendored at
  `backend/data/UNICODE_LICENSE.txt`
- Selection: original starter order first; remaining simplified GB0 characters ordered by
  descending `kHanyuPinlu` occurrence total, then code point for deterministic ties

The ordering and the four stages (起步 100、基础 300、进阶 500、扩展 1000+) are Growth Learning
project curriculum, not an official educational standard or textbook list. Optional meanings,
radicals, strokes, and examples remain `NULL`/empty when the imported source does not provide a
reliable value.

`CatalogRelease` records provenance and `CharacterCatalogEntry` records the exact membership/order
for a version. Import is an idempotent upsert by unique character/canonical key and verifies that
every pre-existing KnowledgePoint UUID remains unchanged before creating release membership.

Historical `AssessmentSessionPlan` and `LiteracyEstimate` rows retain both `catalog_size` and
`catalog_version`; an old estimate remains `/ 200`. StoryVersion coverage/snapshots and science
knowledge links are immutable and are never recalculated during import.

## Operations

Production deployment runs, after Alembic and before app replacement:

```bash
python -m app.cli.characters import-chinese-catalog
```

The command reports created, updated, skipped, preserved, catalog version/size, system-course seed,
and errors. Repeating it must report zero created rows. The admin UI provides the same controlled
operation and shows current provenance; no public physical-delete endpoint is provided.

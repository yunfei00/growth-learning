# Phase 16 Multi-subject Foundation

Phase 16 only establishes reusable infrastructure. It does not seed fake math, English, pinyin,
or science curriculum into production, and it does not claim domain mastery algorithms that have
not been designed and validated.

## Subject and knowledge taxonomy

`KnowledgePoint` is the stable identity shared by curriculum, learning evidence, assessments, and
future projections. Every point has one explicit `subject` and a compatible `type`:

| Subject | Supported knowledge types |
| --- | --- |
| `chinese` | `chinese_character`, `pinyin_initial`, `pinyin_final`, `pinyin_tone`, `pinyin_syllable` |
| `math` | `math_skill` |
| `english` | `english_letter`, `english_word`, `english_phonics` |
| `science` | `science_concept` |

The database enforces this matrix. Existing Chinese-character rows are updated in place to
`subject=chinese`; their UUIDs and all catalog, course, story, science, learning, assessment, and
mastery foreign keys remain unchanged. `canonical_key` remains globally unique and stable.

## Evidence model

`LearningSession` and `LearningRecord` remain the append-only presentation/practice record. Phase
16 adds generic activity evidence such as `guided_practice`, `independent_practice`, `reviewed`,
and `applied`. `AssessmentSession.assessment_kind` identifies recognition, practice, listening,
oral, or math checks. `AssessmentItem` keeps the four existing outcomes while adding an optional
`skill_dimension` and structured `evidence_metadata` for domain-specific facts.

An activity executor registry maps explicitly supported course activity types to evidence. An
unsupported activity may be displayed, but cannot silently invent a `LearningRecord`. Repeating a
completed course activity returns its existing progress/session and does not append duplicate
evidence.

## Mastery policy boundary

`MasteryPolicyRegistry` is keyed by `KnowledgePoint.type`. Only `chinese_character` is registered,
using policy key `chinese-character-v1` and the unchanged deterministic Mastery V1 calculation.
`ChildKnowledgeState` now stores `policy_key`, generic `state_code`, and `dimensions_json` alongside
legacy-compatible character fields.

For pinyin, math, English, and science, evidence is saved but mastery projection is reported as
`unavailable`. The system does not create a fake state row, does not create a review schedule, and
does not convert “algorithm unavailable” into “unlearned”. New policies must be explicitly
implemented, versioned, tested, and registered.

## Character-only product boundaries

The 1,200-character catalog denominator, literacy estimates, character review, character
achievements, character growth milestones, story known-character snapshots, and the Chinese
growth tree select `KnowledgeType.chinese_character` explicitly. Adding 30 math/English/pinyin
knowledge points therefore leaves `/ 1200` character estimates and known-character counts
unchanged.

## Course and administration boundary

Courses support `chinese`, `math`, `english`, and `science`. Every activity mapping must reference
an active knowledge point from the course's exact subject. `/courses`, teacher course lists, and
System Admin course lists accept a subject filter. Empty subjects return an honest empty list.

System Admin may search and inspect canonical knowledge metadata and aggregate evidence counts at
`/admin/knowledge`; this does not grant access to a family's sessions, answers, stories, media, or
notes. Chinese characters continue to use the specialized character maintenance endpoint so their
required pinyin and child-facing content cannot be bypassed.

## Safe rollout and rollback

Migration `20260827_0016` is additive in production: it backfills existing rows, adds columns, and
widens checks without deleting or replacing knowledge/evidence rows. Before deployment, back up
PostgreSQL and MinIO and record row counts. After migration, verify the revision, subject backfill,
unchanged Chinese UUIDs/counts, evidence counts, and current catalog size. Application rollback is
safe while retaining the migrated schema; database downgrade is only for an empty/test database
because generic Phase 16 rows cannot fit Phase 15 constraints.

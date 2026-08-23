# Parent / Child Experience

Phase 11 adds two explicit presentation modes over the same canonical household and evidence data.
Parent mode keeps planning, settings, metrics, reports, teacher collaboration, and child switching.
Child mode keeps one active child fixed until an adult exits it and presents only Today, saved stories,
safe science entry points, the growth tree, and evidence-backed achievements.

## Unified Today projection

`GET /api/v1/children/{child_id}/experience/today` composes existing Phase 5–10 data. It does not
create learning or assessment evidence and does not replace subsystem workflows:

- teacher assignments that are due soon;
- an in-progress or due adaptive review;
- dynamic new-character capacity and course order;
- the existing daily reading task and resumable reading session;
- an in-progress science session, otherwise an optional enabled experiment entry.

The response carries stable source IDs and canonical URLs so refresh and sign-in resume the same
underlying session. Existing `DailyLearningPlan`, `AssessmentSession`, `ReadingSession`,
`ExperimentSession`, and `TeacherAssignmentProgress` remain the sources of truth.

## Growth tree projection

The projection version is `growth-tree-v1`. Chinese leaf language maps the canonical mastery levels:

| Canonical state | Child-facing wording |
| --- | --- |
| `unlearned` | 等待种下 |
| `introduced` | 种下种子 |
| `recognizing` | 正在发芽 |
| `proficient` | 长出新叶 |
| `stable` | 已经很熟悉 |

Course activity completion is displayed separately from character familiarity. Completing a course
activity never writes `stable` and never bypasses `LearningRecord` / `AssessmentItem`. The Chinese
tree queries summaries by Course and Unit, avoiding a full 1,200-character detail payload. Reading
and science branches use completed `ReadingSession` and `ExperimentSession` counts.

## Deterministic achievements

Definitions are versioned as `achievement-v1` and rebuilt from source evidence. Unlocking uses a
unique `(child_id, achievement_definition_id)` constraint and stores the rule threshold, observed
count, source ID, source type, and immutable evidence snapshot.

| Key | Evidence |
| --- | --- |
| `first_learning` | first LearningRecord |
| `learning_10_characters` | 10 distinct learned KnowledgePoints |
| `stable_10_characters` / `stable_50_characters` | canonical stable states |
| `first_review` | first completed daily review session |
| `learning_7_days` | LearningRecords on 7 dates |
| `first_independent_story` / `stories_10` | completed ReadingSessions |
| `first_science` / `science_5` | completed ExperimentSessions |
| `first_science_question` | question_asked ExperimentEvidence |
| `first_teacher_task` | completed TeacherAssignmentProgress |

The rebuild CLI is `python -m app.cli.experience rebuild-achievements`. It is safe to repeat and is
part of `gl-update` after migrations and existing source projectors.

## Positive-only family encouragement

Stars are optional presentation encouragement, not money, scores, ranking, or mastery evidence.
`stars-v1` awards a bounded positive transaction for a completed review, reading, science session,
teacher assignment, or evidence-backed achievement. It never awards per answer. The database rejects
non-positive ledger entries and the unique source/rule constraint makes rebuild idempotent. Balance is
always calculated from the append-only ledger; no mutable balance field exists.

Family Admin may enable/disable display and define plain-text offline goals. Companion can view but
cannot change settings. Disabling stars preserves history. There are no negative rewards, marketplace,
competition, leaderboard, streak punishment, or sibling comparison.

## Unified character learning experience

Every learnable character entry now opens the same `/learn/characters/{knowledge_point_id}` page.
The entry supplies a small, refresh-safe context (`source`, `returnTo`, sequence type, and at most one
plan/session/activity ID); it never serializes the 1,200 UUID catalog into the URL. Explicit `returnTo`
wins, browser history is the fallback, and the literacy home is the final safe fallback.

The current `CatalogRelease` and `CharacterCatalogEntry.order_index` are the sole authority for the
system path's global index, ten-character group, previous character, and next character. Groups remain
a directory and progress aid only: navigation crosses 10/11 and 90/91 without returning to the course
page. Today, mastery lists, learning-history sessions, assessment sessions, and course activities each
resolve their own deterministic sequence on the server.

The child learning page keeps one large character on the left and explanation, words, sentence, and
parent tip on the right. Browser speech synthesis is a progressive enhancement: character, word, and
sentence audio controls stop their click event and never create evidence or navigate. AI explanation,
free practice, and repeat viewing remain auxiliary and never change mastery.

`CharacterLearningHistoryPage` is intentionally different from mastery. It is rooted at
`LearningSession -> LearningRecord`; an assessment-only `ChildKnowledgeState` is therefore absent.
Sessions and repeated records remain visible as an append-oriented learning timeline. Assessment
evidence stays in test history.

On a suitably provisioned host, `scripts/server-build-deploy.sh` builds both revision-labelled
application images locally and then hands the archive to the standard migration/health-gated deploy
flow. Small hosts can continue using the CI release archive through `server-deploy.sh`.

## Authorization and privacy

All child projections call the existing household authorization guard. Cross-family users, unrelated
teachers, and System Admin receive no implicit access. Companion retains existing household read and
accompaniment access but cannot administer rewards. Child mode does not expose family members, child
switching, private notes/media, exports, teacher administration, account controls, or system metrics.

## Responsive and accessibility checklist

- 390 px: single-column task/cards and a compact one-row child header, with no page overflow.
- 768 px: one-row child identity/navigation/parent-mode exit and two-column cards where space allows.
- 1280 px: centered content, a 64 px one-row child header, and up to four summary cards.
- All interactive controls have at least a 44 px target and visible keyboard focus.
- Emoji decoration is `aria-hidden`; data-bearing stars have an accessible label.
- Loading, empty, error/retry, and success states use text and not color alone.
- `prefers-reduced-motion` disables movement; child pages use readable contrast and restrained motion.

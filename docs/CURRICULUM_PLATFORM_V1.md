# Curriculum Platform V1

Curriculum Platform V1 adds a versioned path over canonical knowledge. It does not create a second
mastery engine and does not copy commercial textbook content.

## Identity and release

`curriculum_key` is the stable course identity, for example
`gl:grade1:math:semester1`. `release_version` is an immutable content version such as `2026-v1`.
Every formal `Course` points to exactly one `CurriculumRelease`; every new
`ChildCourseEnrollment` pins that Release ID.

```text
draft → in_review → reviewed → published → archived
                          └──── create new version → draft
```

Only Draft structure is editable. Published structure is read-only. Archived releases stop new
enrollments while existing history remains readable.

## Portable JSON V1

```json
{
  "schema_version": "gl-curriculum-v1",
  "curriculum_version": "2026-v1",
  "course": {
    "curriculum_key": "gl:grade1:math:semester1",
    "release_version": "2026-v1",
    "education_stage": "primary",
    "grade_level": 1,
    "semester": "semester_1",
    "subject": "math",
    "title": "一年级上 · 数学",
    "source_type": "project_curated",
    "source_name": "Growth Learning",
    "license": "project_owned"
  },
  "units": [
    {
      "title": "Unit 1",
      "lessons": [
        {
          "title": "Lesson 1",
          "activities": [
            {
              "title": "数量观察",
              "activity_type": "knowledge_learning",
              "knowledge_points": [
                {"canonical_key": "math:number:recognize-1", "role": "primary"}
              ]
            }
          ]
        }
      ]
    }
  ]
}
```

Exports contain structure, canonical references, provenance, and metadata only. They never contain
Child, Family, LearningRecord, Assessment, Mastery, Review, photos, or question response content.
Imports reject unknown canonical keys and never create KnowledgePoints automatically.

## CLI

```bash
python -m app.cli.curriculum list
python -m app.cli.curriculum validate --release-id RELEASE_UUID
python -m app.cli.curriculum export --release-id RELEASE_UUID --output curriculum.json
python -m app.cli.curriculum import curriculum.json --dry-run
python -m app.cli.curriculum import curriculum.json --actor-email admin@example.com
```

Dry-run reports `will_create`, `will_update`, `errors`, and `warnings` without a commit. A repeated
identical import returns `idempotent=true`; different content under an existing identity/version is
rejected and must use a new release version.

## Explicitly out of scope

- Grade 1 official course production content
- commercial textbook/PDF/workbook copying
- automatic release migration for children
- payments, memberships, course marketplace, rankings
- third-party analytics

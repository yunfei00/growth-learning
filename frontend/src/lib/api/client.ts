const DEFAULT_API_PORT = "8000";
const REQUEST_TIMEOUT_MS = 8_000;

export type User = {
  id: string;
  email: string;
  display_name: string;
  is_active: boolean;
  account_status: "active" | "suspended" | "disabled";
  system_role: "user" | "admin";
  registration_source: "legacy" | "platform_invitation" | "admin_created";
  last_login_at: string | null;
  created_at: string;
  updated_at: string;
};

export type AccountMetadata = {
  id: string;
  email: string;
  display_name: string;
  account_status: "active" | "suspended" | "disabled";
  created_at: string;
  last_login_at: string | null;
};

export type AdminUser = {
  id: string;
  email: string;
  display_name: string;
  account_status: "active" | "suspended" | "disabled";
  system_role: "user" | "admin";
  registration_source: "legacy" | "platform_invitation" | "admin_created";
  registered_via_invitation_id: string | null;
  created_at: string;
  updated_at: string;
  last_login_at: string | null;
  family_count: number;
};

export type AdminUserPage = {
  items: AdminUser[];
  page: number;
  page_size: number;
  total: number;
  pages: number;
};

export type PlatformInvitation = {
  id: string;
  purpose: "create_account";
  status: "active" | "used" | "expired" | "revoked" | "exhausted";
  code_hint: string;
  created_by_user_id: string;
  created_by_display_name: string;
  created_at: string;
  updated_at: string;
  expires_at: string;
  max_uses: number;
  used_count: number;
  email_constraint: string | null;
  revoked_at: string | null;
  last_used_at: string | null;
};

export type CreatedPlatformInvitation = PlatformInvitation & {
  invitation_code: string;
};

export type PlatformInvitationPage = {
  items: PlatformInvitation[];
  page: number;
  page_size: number;
  total: number;
  pages: number;
};

export type AdminOverview = {
  users: number;
  families: number;
  children: number;
  characters: number;
  science_experiments: number;
};

export type CharacterStatus = "active" | "archived";

export type ChineseCharacter = {
  id: string;
  character: string;
  pinyin: string;
  stroke_count: number | null;
  radical: string | null;
  frequency_rank: number | null;
  difficulty_level: number | null;
  simple_meaning: string | null;
  example_sentence: string | null;
  parent_tip: string | null;
  common_words: string[];
  tags: string[];
  is_enabled: boolean;
  status: CharacterStatus;
  source_type: string;
  source_reference: string | null;
  created_at: string;
  updated_at: string;
};

export type CharacterPage = {
  items: ChineseCharacter[];
  page: number;
  page_size: number;
  total: number;
  pages: number;
};

export type CharacterInput = {
  character: string;
  pinyin: string;
  stroke_count?: number | null;
  radical?: string | null;
  simple_meaning?: string | null;
  example_sentence?: string | null;
  parent_tip?: string | null;
  common_words: string[];
  tags: string[];
  is_enabled: boolean;
};

export type ImportReport = {
  created: number;
  updated: number;
  skipped: number;
  errors: string[];
};

export type Subject = "chinese" | "math" | "english" | "science";

export type KnowledgeType =
  | "chinese_character"
  | "pinyin_initial"
  | "pinyin_final"
  | "pinyin_tone"
  | "pinyin_syllable"
  | "math_skill"
  | "english_letter"
  | "english_word"
  | "english_phonics"
  | "science_concept";

export type AdminKnowledgePoint = {
  id: string;
  subject: Subject;
  type: KnowledgeType;
  status: "active" | "archived";
  title: string;
  canonical_key: string;
  source_type: string;
  source_reference: string | null;
  mastery_policy_key: string | null;
  mastery_projection_status: "configured" | "unavailable";
  learning_evidence_count: number;
  assessment_evidence_count: number;
  child_state_count: number;
  created_at: string;
  updated_at: string;
};

export type AdminKnowledgePage = {
  items: AdminKnowledgePoint[];
  page: number;
  page_size: number;
  total: number;
  pages: number;
};

export type PinyinKind = "initial" | "final" | "tone" | "whole";
export type PinyinState = "unlearned" | "introduced" | "practicing" | "proficient" | "stable";
export type PinyinDimension = "recognition" | "listening" | "tone" | "blending" | "pronunciation";

export type PinyinItem = {
  knowledge_point_id: string;
  symbol: string;
  kind: PinyinKind;
  subcategory: string;
  display_text: string;
  example_text: string | null;
  order_index: number;
  status: "active" | "archived";
  audio_status: "curated" | "tts_fallback" | "missing";
  state_code: PinyinState;
  learned: boolean;
};

export type PinyinItemPage = {
  items: PinyinItem[];
  page: number;
  page_size: number;
  total: number;
  pages: number;
};

export type PinyinNavigationItem = {
  knowledge_point_id: string;
  display_text: string;
};

export type PinyinItemDetail = PinyinItem & {
  canonical_key: string;
  pronunciation_cue: string | null;
  example_pinyin: string | null;
  description: string | null;
  parent_tip: string | null;
  audio_key: string | null;
  catalog_version: string;
  metadata: Record<string, string | number | boolean>;
  audio: {
    mode: "curated" | "tts_fallback" | "missing";
    audio_url: string | null;
    speech_text: string | null;
  };
  position: number;
  total: number;
  previous: PinyinNavigationItem | null;
  next: PinyinNavigationItem | null;
  confusing: PinyinNavigationItem[];
  listening_options: PinyinNavigationItem[];
  policy_key: string;
  dimensions: Record<string, unknown>;
};

export type PinyinOverview = {
  child_id: string;
  catalog_version: string;
  total: number;
  learned: number;
  stable: number;
  groups: Array<{
    kind: PinyinKind;
    label: string;
    total: number;
    learned: number;
    stable: number;
  }>;
  blending_state: PinyinState;
  blending_attempts: number;
};

export type PinyinToday = {
  plan_id: string;
  child_id: string;
  plan_date: string;
  new_items: PinyinItem[];
  review_items: PinyinItem[];
  completed_count: number;
  target_count: number;
  status: "pending" | "in_progress" | "completed";
};

export type PinyinPractice = {
  id: string;
  practice_key: string;
  initial_knowledge_point_id: string;
  final_knowledge_point_id: string;
  initial: string;
  underlying_final: string;
  display_final: string;
  display_syllable: string;
  pronunciation_cue: string;
  order_index: number;
  metadata: Record<string, string | number | boolean>;
};

export type PinyinHistory = {
  child_id: string;
  items: Array<{
    session_id: string;
    source: string;
    actor_display_name: string;
    occurred_at: string;
    evidence: Array<{
      evidence_id: string;
      evidence_type: "learning" | "assessment";
      knowledge_point_id: string;
      display_text: string;
      dimension: string | null;
      outcome: string;
      occurred_at: string;
    }>;
  }>;
};

export type MathState = "unlearned" | "introduced" | "practicing" | "proficient" | "stable";
export type MathMode = "practice" | "assessment";
export type MathDimension = "understanding" | "independent" | "transfer";

export type MathSkill = {
  knowledge_point_id: string;
  canonical_key: string;
  domain: string;
  skill_code: string;
  title: string;
  difficulty_level: number;
  order_index: number;
  status: "active" | "archived";
  representation_types: string[];
  template_count: number;
  state_code: MathState;
  learned: boolean;
};

export type MathSkillPage = {
  items: MathSkill[];
  page: number;
  page_size: number;
  total: number;
  pages: number;
};

export type MathTemplate = {
  id: string;
  template_key: string;
  representation_type: string;
  difficulty: number;
  generator_version: string;
  status: "active" | "archived";
};

export type MathSkillDetail = MathSkill & {
  child_instruction: string;
  parent_tip: string;
  recommended_age_min: number | null;
  recommended_age_max: number | null;
  generator_key: string | null;
  settings: Record<string, unknown>;
  catalog_version: string;
  templates: MathTemplate[];
  prerequisites: Array<{ knowledge_point_id: string; title: string }>;
  position: number;
  total: number;
  previous: { knowledge_point_id: string; title: string } | null;
  next: { knowledge_point_id: string; title: string } | null;
  policy_key: string;
  dimensions: Record<string, unknown>;
  mastery_explanation: string[];
  common_difficulties: string[];
  last_learning_at: string | null;
  last_assessed_at: string | null;
  next_review_at: string | null;
};

export type MathOverview = {
  child_id: string;
  catalog_version: string;
  total: number;
  learned: number;
  stable: number;
  groups: Array<{
    domain: string;
    label: string;
    total: number;
    learned: number;
    proficient: number;
    stable: number;
    state_code: MathState;
  }>;
};

export type MathToday = {
  plan_id: string;
  child_id: string;
  plan_date: string;
  items: Array<MathSkill & { item_kind: "new" | "review"; problem_count: number; completed: boolean }>;
  completed_count: number;
  target_count: number;
  status: "pending" | "in_progress" | "completed";
  estimated_minutes: number;
};

export type MathProblem = {
  attempt_id: string;
  template_key: string;
  generator_version: string;
  seed: number;
  representation_type: string;
  render_payload: {
    kind: string;
    instruction: string;
    representation_type: string;
    visual: Record<string, unknown>;
    options: Array<Record<string, unknown> & { value: unknown; label: string }>;
  };
  answered: boolean;
};

export type MathSession = {
  session_id: string;
  child_id: string;
  knowledge_point_id: string;
  skill_title: string;
  mode: MathMode;
  dimension: MathDimension;
  problems: MathProblem[];
  completed_count: number;
  total_count: number;
  completed: boolean;
};

export type MathAttemptResult = {
  attempt_id: string;
  outcome: AssessmentOutcome;
  first_answer_correct: boolean;
  attempt_count: number;
  hint_used: boolean;
  feedback: string;
  session_completed: boolean;
  mastery_state: MathState | null;
};

export type MathHistory = {
  child_id: string;
  items: Array<{
    session_id: string;
    mode: MathMode | "offline";
    actor_display_name: string;
    occurred_at: string;
    skills: Array<{
      knowledge_point_id: string;
      title: string;
      domain: string;
      problem_count: number;
      correct: number;
      hinted_correct: number;
      uncertain: number;
      incorrect: number;
      representations: string[];
    }>;
  }>;
};

export type FamilyRole = "admin" | "companion";

export type Family = {
  id: string;
  name: string;
  current_role: FamilyRole;
  created_at: string;
  updated_at: string;
};

export type ChildGender = "male" | "female" | "other";

export type Child = {
  id: string;
  family_id: string;
  display_name: string;
  nickname: string | null;
  birth_date: string;
  gender: ChildGender | null;
  avatar_key: string | null;
  is_archived: boolean;
  archived_at: string | null;
  created_at: string;
  updated_at: string;
};

export type AdultChildRelation =
  | "father"
  | "mother"
  | "grandfather"
  | "grandmother"
  | "guardian"
  | "other";

export type FamilyMember = {
  id: string;
  role: FamilyRole;
  user: { id: string; email: string; display_name: string };
  relations: Array<{
    id: string;
    child_id: string;
    relation: AdultChildRelation;
    created_at: string;
    updated_at: string;
  }>;
  created_at: string;
  updated_at: string;
};

export type FamilyInvitationStatus = "active" | "expired" | "revoked" | "used";

export type FamilyInvitation = {
  id: string;
  family_id: string;
  family_name: string;
  code_hint: string;
  status: FamilyInvitationStatus;
  role_to_grant: FamilyRole;
  email_constraint: string | null;
  created_by_user_id: string;
  created_by_display_name: string;
  expires_at: string;
  used_count: number;
  revoked_at: string | null;
  accepted_by_user_id: string | null;
  accepted_at: string | null;
  created_at: string;
  updated_at: string;
};

export type FamilyInvitationCreated = FamilyInvitation & { invitation_code: string };

export type FamilyInvitationAcceptance = {
  family_id: string;
  family_name: string;
  membership_id: string;
  role: FamilyRole;
  already_member: boolean;
};

export type FamilyActivity = {
  id: string;
  kind: "learning" | "reading" | "science" | "growth";
  child_id: string;
  child_name: string;
  actor_user_id: string | null;
  actor_display_name: string | null;
  title: string;
  occurred_at: string;
};

export type HealthResponse = {
  status: "ok";
  version: string;
  revision: string;
};

export type MasteryLevel =
  | "unlearned"
  | "introduced"
  | "recognizing"
  | "proficient"
  | "stable";

export type CharacterMasterySummary = {
  total_enabled: number;
  unlearned: number;
  introduced: number;
  recognizing: number;
  proficient: number;
  stable: number;
  priority: number;
  learning_records: number;
  assessment_items: number;
};

export type CharacterMasteryState = {
  knowledge_point_id: string;
  character: string;
  pinyin: string;
  common_words: string[];
  simple_meaning: string | null;
  example_sentence: string | null;
  parent_tip: string | null;
  mastery_level: MasteryLevel;
  mastery_score: number;
  first_introduced_at: string | null;
  last_learning_at: string | null;
  last_assessed_at: string | null;
  correct_count: number;
  hinted_correct_count: number;
  uncertain_count: number;
  incorrect_count: number;
  consecutive_correct: number;
  consecutive_incorrect: number;
  average_response_time_ms: number | null;
  is_priority: boolean;
  algorithm_version: string;
};

export type CharacterMasteryPage = {
  items: CharacterMasteryState[];
  page: number;
  page_size: number;
  total: number;
  pages: number;
};

export type CharacterRecommendation = {
  id: string;
  character: string;
  pinyin: string;
  common_words: string[];
  simple_meaning: string | null;
  example_sentence: string | null;
  mastery_level: MasteryLevel;
  is_priority: boolean;
};

export type TimelineItem = {
  id: string;
  evidence_type: "learning" | "assessment";
  value: string;
  occurred_at: string;
  response_time_ms: number | null;
};

export type CharacterMasteryDetail = {
  state: CharacterMasteryState;
  timeline: TimelineItem[];
};

export type CharacterLearningHistoryRecord = {
  record_id: string;
  knowledge_point_id: string;
  character: string;
  pinyin: string;
  activity_type: string;
  source: string;
  learned_at: string;
  mastery_level: MasteryLevel;
  is_priority: boolean;
};

export type CharacterLearningHistorySession = {
  session_id: string;
  source: string;
  status: "in_progress" | "completed" | "abandoned";
  started_at: string;
  completed_at: string | null;
  records: CharacterLearningHistoryRecord[];
};

export type CharacterLearningHistoryPage = {
  items: CharacterLearningHistorySession[];
  page: number;
  page_size: number;
  total_sessions: number;
  total_records: number;
  pages: number;
  distinct_characters: number;
  this_week_first_learned: number;
};

export type CharacterNavigationSequence =
  | "system_path"
  | "today"
  | "mastery"
  | "learning_session"
  | "assessment_session"
  | "course_activity";

export type CharacterNavigationOptions = {
  sequence: CharacterNavigationSequence;
  contextId?: string;
  itemKind?: "new" | "review";
  masteryLevel?: MasteryLevel;
  priority?: boolean;
  sortBy?: "learning_time" | "recent_review" | "character";
  sortOrder?: "asc" | "desc";
};

export type CharacterNavigation = {
  sequence: CharacterNavigationSequence;
  position: number;
  total: number;
  group: number | null;
  group_size: number | null;
  previous: { knowledge_point_id: string; character: string } | null;
  next: { knowledge_point_id: string; character: string } | null;
};

export type CharacterAIAssistance = {
  simple_explanation: string;
  words: string[];
  example_sentence: string;
  parent_tip: string;
  provider: string;
  model: string;
  mastery_directly_modified: false;
};

export type EvidenceSession = {
  id: string;
  child_id: string;
  status: "in_progress" | "completed" | "abandoned";
  source: string;
  item_count: number;
  started_at: string;
  completed_at: string | null;
  created_at: string;
};

export type LearningSettings = {
  max_new_characters_per_day: number;
  daily_review_capacity: number;
  weekly_assessment_enabled: boolean;
  monthly_assessment_enabled: boolean;
  timezone: string;
};

export type DailyPlanItem = {
  knowledge_point_id: string;
  character: string;
  pinyin: string;
  common_words: string[];
  simple_meaning: string | null;
  example_sentence: string | null;
  item_kind: "new" | "review";
  status: "pending" | "completed";
  position: number;
  selection_reason: string;
};

export type DailyPlan = {
  id: string;
  child_id: string;
  plan_date: string;
  timezone: string;
  recommended_new_count: number;
  review_count: number;
  due_count: number;
  estimated_backlog_days: number;
  recommendation_reason: string;
  new_completed_count: number;
  review_completed_count: number;
  status: "pending" | "in_progress" | "completed";
  recent_independent_correct_rate: number | null;
  weekly_status: string;
  monthly_status: string;
  literacy_status: string;
  literacy_estimate: number | null;
  literacy_catalog_size: number;
  items: DailyPlanItem[];
  reading: DailyReadingTask;
};

export type DailyReadingTask = {
  status: "needs_story" | "pending" | "in_progress" | "completed";
  target_count: number;
  story_version_id: string | null;
  reading_session_id: string | null;
  title: string | null;
};

export type AssessmentSource =
  | "quick_test"
  | "daily_review"
  | "weekly_check"
  | "monthly_assessment";

export type AssessmentOutcome = "correct" | "hinted_correct" | "uncertain" | "incorrect";

export type AssessmentTarget = {
  knowledge_point_id: string;
  character: string;
  pinyin: string;
  position: number;
  sampling_class: string;
  outcome: AssessmentOutcome | null;
  response_time_ms: number | null;
};

export type PlannedAssessment = {
  id: string;
  child_id: string;
  source: AssessmentSource;
  status: "in_progress" | "completed" | "abandoned";
  sampling_method: string;
  sampling_version: string;
  eligible_catalog_size: number;
  catalog_version: string;
  started_at: string;
  completed_at: string | null;
  total_items: number;
  completed_items: number;
  targets: AssessmentTarget[];
};

export type AssessmentHistoryEntry = {
  id: string;
  source: AssessmentSource;
  status: "in_progress" | "completed" | "abandoned";
  started_at: string;
  completed_at: string | null;
  item_count: number;
  correct: number;
  hinted_correct: number;
  uncertain: number;
  incorrect: number;
};

export type LiteracyEstimate = {
  id: string | null;
  assessment_session_id: string | null;
  catalog_size: number;
  catalog_version: string;
  sample_size: number;
  known_count: number;
  unknown_count: number;
  sampling_method: string | null;
  sampling_version: string | null;
  estimate: number | null;
  lower_bound: number | null;
  upper_bound: number | null;
  is_sufficient: boolean;
  estimation_version: string;
  limitation: string;
  created_at: string | null;
};

export type StoryDifficulty = "beginner" | "normal" | "challenge";

export type StoryTarget = {
  knowledge_point_id: string;
  character: string;
  mastery_level: MasteryLevel;
  is_priority: boolean;
};

export type ReadingContext = {
  child_id: string;
  age_band: string;
  provider_configured: boolean;
  provider: string;
  model: string;
  recommended_difficulty: StoryDifficulty | null;
  strong_known_count: number;
  usable_recognizing_count: number;
  automatic_targets: StoryTarget[];
  safe_themes: string[];
  catalog_size: number;
  catalog_limitation: string;
  feasibility_message: string | null;
};

export type ReadingQuestion = {
  id: string;
  position: number;
  question: string;
  options: string[];
};

export type CharacterGlossary = {
  knowledge_point_id: string;
  character: string;
  pinyin: string;
  simple_meaning: string | null;
  common_words: string[];
};

export type StoryVersion = {
  id: string;
  story_id: string;
  source_experiment_session_id: string | null;
  version_number: number;
  title: string;
  paragraphs: string[];
  summary: string | null;
  theme: string;
  custom_theme: string | null;
  difficulty: StoryDifficulty;
  requested_known_coverage: number;
  actual_strong_known_coverage: number;
  actual_usable_known_coverage: number;
  actual_target_coverage: number;
  actual_unexpected_coverage: number;
  unique_known_coverage: number;
  total_han_occurrences: number;
  unique_han_count: number;
  unexpected_characters: string[];
  target_characters: string[];
  snapshot_at: string;
  coverage_policy_version: string;
  analyzer_version: string;
  prompt_version: string;
  provider: string;
  model: string;
  questions: ReadingQuestion[];
  glossary: CharacterGlossary[];
  created_at: string;
};

export type StoryGenerationResult = {
  generation_run_id: string;
  status: "succeeded";
  attempt_count: number;
  version: StoryVersion;
};

export type StoryListItem = {
  story_id: string;
  story_version_id: string;
  title: string;
  theme: string;
  difficulty: StoryDifficulty;
  actual_known_coverage: number;
  target_characters: string[];
  generated_at: string;
  reading_status: "in_progress" | "completed" | "abandoned" | null;
  reading_mode: "independent" | "with_help" | null;
  comprehension_answered: number;
  comprehension_total: number;
};

export type StoryPage = {
  items: StoryListItem[];
  page: number;
  page_size: number;
  total: number;
  pages: number;
};

export type ReadingAnswer = {
  question_id: string;
  selected_option_index: number;
  outcome: "correct" | "with_help" | "partial" | "incorrect";
  answered_at: string;
};

export type ReadingSession = {
  id: string;
  child_id: string;
  story_version_id: string;
  reading_mode: "independent" | "with_help";
  status: "in_progress" | "completed" | "abandoned";
  started_at: string;
  completed_at: string | null;
  duration_seconds: number | null;
  parent_note: string | null;
  answers: ReadingAnswer[];
  story_exposure_count: number;
};

export type ReadingSummary = {
  stories_read_this_week: number;
  independent_this_week: number;
  with_help_this_week: number;
  comprehension_correct: number;
  comprehension_answered: number;
  comprehension_message: string;
  target_exposure_count: number;
};

export type ScienceDifficulty = "intro" | "explore" | "advanced";
export type ScienceExperimentStatus = "draft" | "enabled" | "archived";

export type ExperimentMaterial = {
  id: string;
  canonical_key: string;
  name: string;
  aliases: string[];
  description: string | null;
  unit: string | null;
  category: string | null;
  safety_note: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type MaterialRequirement = {
  id: string;
  material: ExperimentMaterial;
  quantity_text: string | null;
  is_required: boolean;
  substitution_notes: string | null;
  position: number;
};

export type ScienceExperiment = {
  id: string;
  canonical_key: string;
  title: string;
  description: string;
  age_min: number;
  age_max: number | null;
  difficulty: ScienceDifficulty;
  estimated_duration_minutes: number;
  guiding_question: string;
  expected_phenomenon: string;
  child_friendly_explanation: string;
  parent_scientific_explanation: string;
  safety_notes: string[];
  common_failure_reasons: string[];
  follow_up_questions: string[];
  likely_child_questions: string[];
  steps: string[];
  status: ScienceExperimentStatus;
  source_type: "system" | "family";
  content_version: number;
  requirements: MaterialRequirement[];
  related_knowledge_points: Array<{
    knowledge_point_id: string;
    title: string;
    character: string | null;
    exposure_enabled: boolean;
  }>;
  created_at: string;
  updated_at: string;
};

export type ScienceExperimentPage = {
  items: ScienceExperiment[];
  page: number;
  page_size: number;
  total: number;
  pages: number;
};

export type FamilyMaterial = {
  material: ExperimentMaterial;
  is_owned: boolean;
  quantity_text: string | null;
  note: string | null;
  updated_at: string | null;
};

export type ScienceRecommendation = {
  experiment: ScienceExperiment;
  ready_at_home: boolean;
  owned_required_materials: string[];
  missing_required_materials: string[];
  optional_substitutions: string[];
  reasons: string[];
  recently_completed: boolean;
};

export type ExperimentEvidence = {
  id: string;
  evidence_type: "prediction" | "observation" | "child_summary" | "question_asked" | "child_original_words" | "parent_explanation";
  original_text: string;
  capability_tags: string[];
  recorder_user_id: string;
  captured_at: string;
};

export type ExperimentMedia = {
  id: string;
  media_kind: "image" | "video" | "audio";
  mime_type: string;
  size_bytes: number;
  original_filename: string;
  uploader_user_id: string;
  created_at: string;
  content_url: string;
};

export type ExperimentSession = {
  id: string;
  child_id: string;
  experiment_id: string;
  experiment_version_id: string;
  experiment_snapshot: Record<string, unknown>;
  accompanying_user_id: string;
  status: "planned" | "in_progress" | "completed" | "abandoned";
  current_step: "question" | "prediction" | "materials" | "experiment" | "observation" | "explanation" | "follow_up" | "summary" | "complete";
  local_date: string;
  timezone: string;
  started_at: string | null;
  completed_at: string | null;
  parent_note: string | null;
  evidence: ExperimentEvidence[];
  media: ExperimentMedia[];
  science_exposure_count: number;
  created_at: string;
  updated_at: string;
};

export type ExperimentSessionPage = {
  items: ExperimentSession[];
  page: number;
  page_size: number;
  total: number;
  pages: number;
};

export type ExperimentGrowthCard = {
  session_id: string;
  title: string;
  completed_at: string;
  accompanying_user: string;
  prediction: string[];
  observation: string[];
  child_original_words: string[];
  child_summary: string[];
  questions_asked: string[];
  media: ExperimentMedia[];
  scientific_explanation: string;
  follow_up_questions: string[];
  related_characters: string[];
  capability_tags: string[];
};

export type ExperimentAIParentTip = {
  parent_tip: string;
  provider: string;
  model: string;
  learning_records_modified: false;
};

export type GrowthCategory =
  | "learning"
  | "assessment"
  | "reading"
  | "science"
  | "family"
  | "original_words"
  | "achievement"
  | "report";

export type GrowthMedia = {
  id: string;
  media_kind: "image" | "video" | "audio";
  mime_type: string;
  size_bytes: number;
  original_filename: string;
  created_at: string;
  content_url: string;
};

export type GrowthEvent = {
  id: string;
  child_id: string;
  event_type: string;
  category: GrowthCategory;
  occurred_at: string;
  title: string;
  body: string;
  source_type: "system" | "parent" | "companion" | "teacher";
  actor_user_id: string | null;
  actor_display_name: string | null;
  source_entity_type: string | null;
  source_entity_id: string | null;
  source_url: string | null;
  evidence_snapshot: Record<string, unknown>;
  policy_version: string;
  archived_at: string | null;
  media: GrowthMedia[];
};

export type GrowthEventPage = {
  items: GrowthEvent[];
  page: number;
  page_size: number;
  total: number;
  pages: number;
};

export type GrowthReport = {
  id: string;
  report_id: string;
  version_number: number;
  period_type: "monthly" | "yearly" | "custom";
  period_start: string;
  period_end: string;
  generated_at: string;
  source_cutoff_at: string;
  policy_version: string;
  metrics: Record<string, unknown>;
  sections: Record<string, unknown>;
  selected_event_ids: string[];
  ai_narrative: string | null;
  ai_provider: string | null;
  ai_model: string | null;
  ai_prompt_version: string | null;
};

export type GrowthReportSummary = {
  id: string;
  period_type: "monthly" | "yearly" | "custom";
  period_start: string;
  period_end: string;
  latest_version: number;
  generated_at: string;
};

export type GrowthBook = {
  id: string;
  growth_book_id: string;
  version_number: number;
  edition_type: "yearly" | "age_year";
  edition_key: string;
  title: string;
  selected_event_ids: string[];
  selected_media: Array<Record<string, string>>;
  snapshot: Record<string, unknown>;
  parent_message: string | null;
  message_author_user_id: string | null;
  message_recorded_at: string | null;
  created_at: string;
};

export type GrowthBookSummary = {
  id: string;
  edition_type: "yearly" | "age_year";
  edition_key: string;
  latest_version: number;
  title: string;
  created_at: string;
};

export type ExportJob = {
  id: string;
  family_id: string;
  child_id: string | null;
  requested_by_user_id: string;
  status: "pending" | "processing" | "completed" | "failed" | "expired";
  schema_version: string;
  size_bytes: number | null;
  checksum_sha256: string | null;
  failure_reason: string | null;
  completed_at: string | null;
  expires_at: string | null;
  created_at: string;
  updated_at: string;
  download_url: string | null;
};

type ErrorPayload = {
  detail?: string | Array<{ msg?: string }>;
};

export class ApiClientError extends Error {
  constructor(
    message: string,
    public readonly status?: number,
    public readonly response?: ErrorPayload | null,
  ) {
    super(message);
    this.name = "ApiClientError";
  }
}

export function createClientKey(): string {
  const runtimeCrypto = globalThis.crypto;
  if (typeof runtimeCrypto?.randomUUID === "function") {
    return runtimeCrypto.randomUUID();
  }

  const bytes = new Uint8Array(16);
  if (typeof runtimeCrypto?.getRandomValues === "function") {
    runtimeCrypto.getRandomValues(bytes);
  } else {
    for (let index = 0; index < bytes.length; index += 1) {
      bytes[index] = Math.floor(Math.random() * 256);
    }
  }
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = Array.from(bytes, (value) => value.toString(16).padStart(2, "0"));
  return `${hex.slice(0, 4).join("")}-${hex.slice(4, 6).join("")}-${hex.slice(6, 8).join("")}-${hex.slice(8, 10).join("")}-${hex.slice(10).join("")}`;
}

export function getApiBaseUrl(): string {
  const configuredBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();
  if (configuredBaseUrl) {
    return configuredBaseUrl.replace(/\/$/, "");
  }

  const apiUrl = new URL(window.location.origin);
  apiUrl.port = process.env.NEXT_PUBLIC_API_PORT?.trim() || DEFAULT_API_PORT;
  return apiUrl.origin;
}

function errorMessage(payload: ErrorPayload | null, fallback: string): string {
  if (typeof payload?.detail === "string") {
    return payload.detail;
  }
  if (Array.isArray(payload?.detail)) {
    const messages = payload.detail.flatMap((item) => (item.msg ? [item.msg] : []));
    if (messages.length > 0) {
      return messages.join("；");
    }
  }
  return fallback;
}

async function request<T>(
  path: string,
  init?: RequestInit,
  timeoutMs = REQUEST_TIMEOUT_MS,
): Promise<T> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), timeoutMs);
  const hasJsonBody = init?.body !== undefined && !(init.body instanceof FormData);

  try {
    const response = await fetch(`${getApiBaseUrl()}${path}`, {
      ...init,
      cache: init?.cache ?? "no-store",
      credentials: "include",
      headers: {
        Accept: "application/json",
        ...(hasJsonBody ? { "Content-Type": "application/json" } : {}),
        ...init?.headers,
      },
      signal: controller.signal,
    });

    if (!response.ok) {
      const payload = (await response.json().catch(() => null)) as ErrorPayload | null;
      if (response.status === 401) {
        window.dispatchEvent(new Event("growth-learning:unauthorized"));
      }
      throw new ApiClientError(
        errorMessage(payload, `请求失败（HTTP ${response.status}）`),
        response.status,
        payload,
      );
    }

    if (response.status === 204) {
      return undefined as T;
    }
    return (await response.json()) as T;
  } catch (error) {
    if (error instanceof ApiClientError) {
      throw error;
    }
    throw new ApiClientError(
      error instanceof DOMException && error.name === "AbortError"
        ? "请求超时，请稍后重试"
        : "无法连接服务，请检查网络后重试",
    );
  } finally {
    window.clearTimeout(timeout);
  }
}

function jsonBody(value: unknown): string {
  return JSON.stringify(value);
}

export function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>("/health");
}

export function registerAccount(payload: {
  invitation_code: string;
  display_name: string;
  email: string;
  password: string;
}): Promise<User> {
  return request<User>("/api/v1/auth/register", {
    method: "POST",
    body: jsonBody(payload),
  });
}

export function loginAccount(payload: { email: string; password: string }): Promise<User> {
  return request<User>("/api/v1/auth/login", {
    method: "POST",
    body: jsonBody(payload),
  });
}

export function logoutAccount(): Promise<void> {
  return request<void>("/api/v1/auth/logout", { method: "POST" });
}

export function getCurrentUser(): Promise<User> {
  return request<User>("/api/v1/auth/me");
}

export function getAccountMetadata(): Promise<AccountMetadata> {
  return request<AccountMetadata>("/api/v1/auth/account");
}

export function changeAccountPassword(payload: {
  current_password: string;
  new_password: string;
  confirm_password: string;
}): Promise<User> {
  return request<User>("/api/v1/auth/change-password", {
    method: "POST",
    body: jsonBody(payload),
  });
}

export function logoutAllDevices(): Promise<void> {
  return request<void>("/api/v1/auth/logout-all", { method: "POST" });
}

export function listFamilies(): Promise<Family[]> {
  return request<Family[]>("/api/v1/families");
}

export function createFamily(name: string): Promise<Family> {
  return request<Family>("/api/v1/families", {
    method: "POST",
    body: jsonBody({ name }),
  });
}

export function updateFamily(familyId: string, name: string): Promise<Family> {
  return request<Family>(`/api/v1/families/${familyId}`, {
    method: "PATCH",
    body: jsonBody({ name }),
  });
}

export function listChildren(familyId: string, includeArchived = false): Promise<Child[]> {
  return request<Child[]>(
    `/api/v1/families/${familyId}/children${includeArchived ? "?include_archived=true" : ""}`,
  );
}

export function createChild(
  familyId: string,
  payload: {
    display_name: string;
    nickname?: string | null;
    birth_date: string;
    gender?: ChildGender | null;
  },
): Promise<Child> {
  return request<Child>(`/api/v1/families/${familyId}/children`, {
    method: "POST",
    body: jsonBody(payload),
  });
}

export function updateChild(
  childId: string,
  payload: Partial<{
    display_name: string;
    nickname: string | null;
    birth_date: string;
    gender: ChildGender | null;
  }>,
): Promise<Child> {
  return request<Child>(`/api/v1/children/${childId}`, {
    method: "PATCH",
    body: jsonBody(payload),
  });
}

export function archiveChild(childId: string): Promise<Child> {
  return request<Child>(`/api/v1/children/${childId}/archive`, { method: "POST" });
}

export function restoreChild(childId: string): Promise<Child> {
  return request<Child>(`/api/v1/children/${childId}/restore`, { method: "POST" });
}

export function listFamilyMembers(familyId: string): Promise<FamilyMember[]> {
  return request<FamilyMember[]>(`/api/v1/families/${familyId}/members`);
}

export function updateFamilyMemberRole(
  familyId: string,
  memberId: string,
  role: FamilyRole,
): Promise<FamilyMember> {
  return request<FamilyMember>(`/api/v1/families/${familyId}/members/${memberId}`, {
    method: "PATCH",
    body: jsonBody({ role }),
  });
}

export function removeFamilyMember(familyId: string, memberId: string): Promise<void> {
  return request<void>(`/api/v1/families/${familyId}/members/${memberId}`, {
    method: "DELETE",
  });
}

export function setAdultChildRelation(
  familyId: string,
  memberId: string,
  childId: string,
  relation: AdultChildRelation,
): Promise<FamilyMember["relations"][number]> {
  return request(`/api/v1/families/${familyId}/members/${memberId}/relations/${childId}`, {
    method: "PUT",
    body: jsonBody({ relation }),
  });
}

export function createFamilyInvitation(
  familyId: string,
  payload: { email_constraint?: string | null; role_to_grant: FamilyRole; expires_at: string },
): Promise<FamilyInvitationCreated> {
  return request<FamilyInvitationCreated>(`/api/v1/families/${familyId}/invitations`, {
    method: "POST",
    body: jsonBody(payload),
  });
}

export function listFamilyInvitations(familyId: string): Promise<FamilyInvitation[]> {
  return request<FamilyInvitation[]>(`/api/v1/families/${familyId}/invitations`);
}

export function revokeFamilyInvitation(
  familyId: string,
  invitationId: string,
): Promise<FamilyInvitation> {
  return request<FamilyInvitation>(
    `/api/v1/families/${familyId}/invitations/${invitationId}/revoke`,
    { method: "POST" },
  );
}

export function listPendingFamilyInvitations(): Promise<FamilyInvitation[]> {
  return request<FamilyInvitation[]>("/api/v1/family-invitations/pending");
}

export function acceptFamilyInvitation(code: string): Promise<FamilyInvitationAcceptance> {
  return request<FamilyInvitationAcceptance>("/api/v1/family-invitations/accept", {
    method: "POST",
    body: jsonBody({ invitation_code: code }),
  });
}

export function acceptPendingFamilyInvitation(
  invitationId: string,
): Promise<FamilyInvitationAcceptance> {
  return request<FamilyInvitationAcceptance>(`/api/v1/family-invitations/${invitationId}/accept`, {
    method: "POST",
  });
}

export function listFamilyActivity(familyId: string): Promise<FamilyActivity[]> {
  return request<FamilyActivity[]>(`/api/v1/families/${familyId}/activity`);
}

export function getAdminOverview(): Promise<AdminOverview> {
  return request<AdminOverview>("/api/v1/admin/overview");
}

export function listAdminUsers(filters: {
  search?: string;
  accountStatus?: string;
  page?: number;
  pageSize?: number;
}): Promise<AdminUserPage> {
  const query = new URLSearchParams();
  if (filters.search) query.set("search", filters.search);
  if (filters.accountStatus) query.set("account_status", filters.accountStatus);
  query.set("page", String(filters.page ?? 1));
  query.set("page_size", String(filters.pageSize ?? 20));
  return request<AdminUserPage>(`/api/v1/admin/users?${query.toString()}`);
}

export function updateAdminUserStatus(
  userId: string,
  accountStatus: AdminUser["account_status"],
): Promise<AdminUser> {
  return request<AdminUser>(`/api/v1/admin/users/${userId}/status`, {
    method: "PATCH",
    body: jsonBody({ account_status: accountStatus }),
  });
}

export function createPlatformInvitation(payload: {
  expires_at: string;
  max_uses: number;
  email_constraint: string | null;
}): Promise<CreatedPlatformInvitation> {
  return request<CreatedPlatformInvitation>("/api/v1/admin/invitations", {
    method: "POST",
    body: jsonBody({ purpose: "create_account", ...payload }),
  });
}

export function listPlatformInvitations(
  page = 1,
  pageSize = 20,
): Promise<PlatformInvitationPage> {
  return request<PlatformInvitationPage>(
    `/api/v1/admin/invitations?page=${page}&page_size=${pageSize}`,
  );
}

export function revokePlatformInvitation(id: string): Promise<PlatformInvitation> {
  return request<PlatformInvitation>(`/api/v1/admin/invitations/${id}/revoke`, {
    method: "POST",
  });
}

export function listAdminCharacters(filters: {
  search?: string;
  enabled?: boolean;
  page?: number;
  pageSize?: number;
}): Promise<CharacterPage> {
  const query = new URLSearchParams();
  if (filters.search) query.set("search", filters.search);
  if (filters.enabled !== undefined) query.set("enabled", String(filters.enabled));
  query.set("page", String(filters.page ?? 1));
  query.set("page_size", String(filters.pageSize ?? 20));
  return request<CharacterPage>(`/api/v1/admin/characters?${query.toString()}`);
}

export function createAdminCharacter(payload: CharacterInput): Promise<ChineseCharacter> {
  return request<ChineseCharacter>("/api/v1/admin/characters", {
    method: "POST",
    body: jsonBody(payload),
  });
}

export function updateAdminCharacter(
  id: string,
  payload: Partial<CharacterInput> & { status?: CharacterStatus },
): Promise<ChineseCharacter> {
  return request<ChineseCharacter>(`/api/v1/admin/characters/${id}`, {
    method: "PATCH",
    body: jsonBody(payload),
  });
}

export function importStarterCharacters(): Promise<ImportReport> {
  return request<ImportReport>("/api/v1/admin/characters/import-starter", {
    method: "POST",
  });
}

export function listAdminKnowledge(filters: {
  subject?: Subject | "";
  type?: KnowledgeType | "";
  status?: "active" | "archived" | "";
  search?: string;
  page?: number;
  pageSize?: number;
}): Promise<AdminKnowledgePage> {
  const query = new URLSearchParams();
  if (filters.subject) query.set("subject", filters.subject);
  if (filters.type) query.set("type", filters.type);
  if (filters.status) query.set("status", filters.status);
  if (filters.search) query.set("search", filters.search);
  query.set("page", String(filters.page ?? 1));
  query.set("page_size", String(filters.pageSize ?? 20));
  return request<AdminKnowledgePage>(`/api/v1/admin/knowledge?${query.toString()}`);
}

export function getAdminKnowledge(id: string): Promise<AdminKnowledgePoint> {
  return request<AdminKnowledgePoint>(`/api/v1/admin/knowledge/${id}`);
}

export function createAdminKnowledge(payload: {
  subject: Subject;
  type: KnowledgeType;
  title: string;
  canonical_key: string;
  source_type?: string;
  source_reference?: string | null;
}): Promise<AdminKnowledgePoint> {
  return request<AdminKnowledgePoint>("/api/v1/admin/knowledge", {
    method: "POST",
    body: jsonBody(payload),
  });
}

export function listAdminPinyin(filters: {
  kind?: PinyinKind | "";
  status?: "active" | "archived" | "";
  search?: string;
  page?: number;
  pageSize?: number;
}): Promise<PinyinItemPage> {
  const query = new URLSearchParams({
    page: String(filters.page ?? 1),
    page_size: String(filters.pageSize ?? 50),
  });
  if (filters.kind) query.set("kind", filters.kind);
  if (filters.status) query.set("status", filters.status);
  if (filters.search) query.set("search", filters.search);
  return request<PinyinItemPage>(`/api/v1/admin/pinyin?${query.toString()}`);
}

export function getAdminPinyin(id: string): Promise<PinyinItemDetail> {
  return request<PinyinItemDetail>(`/api/v1/admin/pinyin/${id}`);
}

export function updateAdminPinyin(
  id: string,
  payload: Partial<{
    status: "active" | "archived";
    pronunciation_cue: string | null;
    example_text: string | null;
    example_pinyin: string | null;
    description: string | null;
    parent_tip: string | null;
    audio_key: string | null;
  }>,
): Promise<PinyinItemDetail> {
  return request<PinyinItemDetail>(`/api/v1/admin/pinyin/${id}`, {
    method: "PATCH",
    body: jsonBody(payload),
  });
}

export function importPinyinFoundation(): Promise<{
  created: number;
  updated: number;
  skipped: number;
  relations_created: number;
  practices_created: number;
  catalog_version: string;
  catalog_size: number;
  course_created: boolean;
  errors: string[];
}> {
  return request("/api/v1/admin/pinyin/import-foundation", { method: "POST" });
}

export function listChildPinyinItems(
  childId: string,
  kind?: PinyinKind,
): Promise<PinyinItemPage> {
  const query = new URLSearchParams({ page: "1", page_size: "100" });
  if (kind) query.set("kind", kind);
  return request<PinyinItemPage>(
    `/api/v1/children/${childId}/pinyin/items?${query.toString()}`,
  );
}

export function getPinyinOverview(childId: string): Promise<PinyinOverview> {
  return request<PinyinOverview>(`/api/v1/children/${childId}/pinyin/overview`);
}

export function getPinyinToday(childId: string): Promise<PinyinToday | null> {
  return request<PinyinToday | null>(`/api/v1/children/${childId}/pinyin/today`);
}

export function getPinyinItemDetail(
  childId: string,
  knowledgePointId: string,
): Promise<PinyinItemDetail> {
  return request<PinyinItemDetail>(
    `/api/v1/children/${childId}/pinyin/items/${knowledgePointId}`,
  );
}

export function getPinyinPractices(): Promise<{ items: PinyinPractice[]; total: number }> {
  return request<{ items: PinyinPractice[]; total: number }>("/api/v1/pinyin/practices");
}

export function getPinyinHistory(childId: string): Promise<PinyinHistory> {
  return request<PinyinHistory>(`/api/v1/children/${childId}/pinyin/history`);
}

export function recordPinyinLearning(
  childId: string,
  knowledgePointId: string,
  activityType: "introduced" | "reviewed" = "introduced",
): Promise<EvidenceSession> {
  return request<EvidenceSession>(`/api/v1/children/${childId}/learning-sessions`, {
    method: "POST",
    body: jsonBody({
      status: "completed",
      source: "pinyin_learning",
      items: [{ knowledge_point_id: knowledgePointId, activity_type: activityType }],
    }),
  });
}

export function recordPinyinAssessment(
  childId: string,
  payload: {
    knowledgePointId: string;
    outcome: AssessmentOutcome;
    dimension: PinyinDimension;
    assessmentKind: "recognition" | "practice_check" | "listening_check" | "oral_check";
    responseTimeMs?: number;
    metadata?: Record<string, string | number | boolean>;
  },
): Promise<EvidenceSession> {
  return request<EvidenceSession>(`/api/v1/children/${childId}/assessment-sessions`, {
    method: "POST",
    body: jsonBody({
      status: "completed",
      source: `pinyin_${payload.dimension}`,
      assessment_kind: payload.assessmentKind,
      items: [
        {
          knowledge_point_id: payload.knowledgePointId,
          outcome: payload.outcome,
          response_time_ms: payload.responseTimeMs,
          hint_used: payload.outcome === "hinted_correct",
          skill_dimension: payload.dimension,
          evidence_metadata: payload.metadata ?? {},
        },
      ],
    }),
  });
}

export function listChildMathSkills(childId: string, domain?: string): Promise<MathSkillPage> {
  const query = new URLSearchParams({ page: "1", page_size: "100" });
  if (domain) query.set("domain", domain);
  return request<MathSkillPage>(`/api/v1/children/${childId}/math/skills?${query}`);
}

export function getMathOverview(childId: string): Promise<MathOverview> {
  return request<MathOverview>(`/api/v1/children/${childId}/math/overview`);
}

export function getMathToday(childId: string): Promise<MathToday | null> {
  return request<MathToday | null>(`/api/v1/children/${childId}/math/today`);
}

export function getMathSkillDetail(childId: string, knowledgePointId: string): Promise<MathSkillDetail> {
  return request<MathSkillDetail>(`/api/v1/children/${childId}/math/skills/${knowledgePointId}`);
}

export function getMathHistory(childId: string): Promise<MathHistory> {
  return request<MathHistory>(`/api/v1/children/${childId}/math/history`);
}

export function startMathSession(
  childId: string,
  payload: {
    knowledgePointId: string;
    mode: MathMode;
    problemCount: number;
    dimension: MathDimension;
    seed?: number;
  },
): Promise<MathSession> {
  return request<MathSession>(`/api/v1/children/${childId}/math/sessions`, {
    method: "POST",
    body: jsonBody({
      knowledge_point_id: payload.knowledgePointId,
      mode: payload.mode,
      problem_count: payload.problemCount,
      dimension: payload.dimension,
      seed: payload.seed,
    }),
  });
}

export function answerMathAttempt(
  childId: string,
  sessionId: string,
  attemptId: string,
  payload: { submittedAnswer: unknown; hintUsed: boolean; responseTimeMs?: number },
): Promise<MathAttemptResult> {
  return request<MathAttemptResult>(
    `/api/v1/children/${childId}/math/sessions/${sessionId}/attempts/${attemptId}/answer`,
    {
      method: "POST",
      body: jsonBody({
        submitted_answer: payload.submittedAnswer,
        hint_used: payload.hintUsed,
        response_time_ms: payload.responseTimeMs,
      }),
    },
  );
}

export function recordMathOfflineObservation(
  childId: string,
  knowledgePointId: string,
  outcome: "correct" | "hinted_correct" | "uncertain",
): Promise<{ assessment_item_id: string; outcome: string; mastery_state: MathState }> {
  return request(`/api/v1/children/${childId}/math/skills/${knowledgePointId}/offline-observations`, {
    method: "POST",
    body: jsonBody({ outcome }),
  });
}

export function listAdminMath(filters: {
  domain?: string;
  status?: "active" | "archived" | "";
  search?: string;
  pageSize?: number;
} = {}): Promise<MathSkillPage> {
  const query = new URLSearchParams({ page: "1", page_size: String(filters.pageSize ?? 100) });
  if (filters.domain) query.set("domain", filters.domain);
  if (filters.status) query.set("status", filters.status);
  if (filters.search) query.set("search", filters.search);
  return request<MathSkillPage>(`/api/v1/admin/math?${query}`);
}

export function getAdminMath(id: string): Promise<MathSkillDetail> {
  return request<MathSkillDetail>(`/api/v1/admin/math/${id}`);
}

export function updateAdminMath(
  id: string,
  payload: Partial<Pick<MathSkillDetail, "status" | "title" | "child_instruction" | "parent_tip" | "recommended_age_min" | "recommended_age_max">>,
): Promise<MathSkillDetail> {
  return request<MathSkillDetail>(`/api/v1/admin/math/${id}`, {
    method: "PATCH",
    body: jsonBody(payload),
  });
}

export function importMathFoundation(): Promise<{
  created: number;
  updated: number;
  skipped: number;
  relations_created: number;
  templates_created: number;
  catalog_version: string;
  catalog_size: number;
  template_count: number;
  course_created: boolean;
  errors: string[];
}> {
  return request("/api/v1/admin/math/import-foundation", { method: "POST" });
}

export function getCharacterMasterySummary(childId: string): Promise<CharacterMasterySummary> {
  return request<CharacterMasterySummary>(`/api/v1/children/${childId}/characters/summary`);
}

export function listCharacterMastery(
  childId: string,
  filters: {
    search?: string;
    masteryLevel?: MasteryLevel;
    priority?: boolean;
    sortBy?: "learning_time" | "recent_review" | "character";
    sortOrder?: "asc" | "desc";
    page?: number;
    pageSize?: number;
  },
): Promise<CharacterMasteryPage> {
  const query = new URLSearchParams();
  if (filters.search) query.set("search", filters.search);
  if (filters.masteryLevel) query.set("mastery_level", filters.masteryLevel);
  if (filters.priority !== undefined) query.set("priority", String(filters.priority));
  if (filters.sortBy) query.set("sort_by", filters.sortBy);
  if (filters.sortOrder) query.set("sort_order", filters.sortOrder);
  query.set("page", String(filters.page ?? 1));
  query.set("page_size", String(filters.pageSize ?? 20));
  return request<CharacterMasteryPage>(
    `/api/v1/children/${childId}/characters?${query.toString()}`,
  );
}

export function getCharacterMasteryDetail(
  childId: string,
  knowledgePointId: string,
): Promise<CharacterMasteryDetail> {
  return request<CharacterMasteryDetail>(
    `/api/v1/children/${childId}/characters/${knowledgePointId}`,
  );
}

export function getCharacterLearningHistory(
  childId: string,
  filters: {
    search?: string;
    learnedFrom?: string;
    learnedTo?: string;
    page?: number;
    pageSize?: number;
  } = {},
): Promise<CharacterLearningHistoryPage> {
  const query = new URLSearchParams({
    page: String(filters.page ?? 1),
    page_size: String(filters.pageSize ?? 10),
  });
  if (filters.search) query.set("search", filters.search);
  if (filters.learnedFrom) query.set("learned_from", filters.learnedFrom);
  if (filters.learnedTo) query.set("learned_to", filters.learnedTo);
  return request<CharacterLearningHistoryPage>(
    `/api/v1/children/${childId}/character-learning-history?${query.toString()}`,
  );
}

export function getCharacterNavigation(
  childId: string,
  knowledgePointId: string,
  options: CharacterNavigationOptions,
): Promise<CharacterNavigation> {
  const query = new URLSearchParams({ sequence: options.sequence });
  if (options.contextId) query.set("context_id", options.contextId);
  if (options.itemKind) query.set("item_kind", options.itemKind);
  if (options.masteryLevel) query.set("mastery_level", options.masteryLevel);
  if (options.priority !== undefined) query.set("priority", String(options.priority));
  if (options.sortBy) query.set("sort_by", options.sortBy);
  if (options.sortOrder) query.set("sort_order", options.sortOrder);
  return request<CharacterNavigation>(
    `/api/v1/children/${childId}/characters/${knowledgePointId}/navigation?${query.toString()}`,
  );
}

export function generateCharacterAIAssistance(
  childId: string,
  knowledgePointId: string,
): Promise<CharacterAIAssistance> {
  return request<CharacterAIAssistance>(
    `/api/v1/children/${childId}/characters/${knowledgePointId}/ai-assistance`,
    { method: "POST" },
    45_000,
  );
}

export function getCharacterRecommendations(
  childId: string,
  mode: "new" | "assessment",
  limit = 5,
): Promise<CharacterRecommendation[]> {
  return request<CharacterRecommendation[]>(
    `/api/v1/children/${childId}/characters/recommendations?mode=${mode}&limit=${limit}`,
  );
}

export function createLearningSession(
  childId: string,
  knowledgePointIds: string[],
  source = "parent_assisted",
): Promise<EvidenceSession> {
  return request<EvidenceSession>(`/api/v1/children/${childId}/learning-sessions`, {
    method: "POST",
    body: jsonBody({
      status: "completed",
      source,
      items: knowledgePointIds.map((knowledge_point_id) => ({
        knowledge_point_id,
        activity_type: "introduced",
      })),
    }),
  });
}

export function createAssessmentSession(
  childId: string,
  items: Array<{
    knowledge_point_id: string;
    outcome: "correct" | "hinted_correct" | "uncertain" | "incorrect";
    response_time_ms: number;
    hint_used?: boolean;
  }>,
): Promise<EvidenceSession> {
  return request<EvidenceSession>(`/api/v1/children/${childId}/assessment-sessions`, {
    method: "POST",
    body: jsonBody({ status: "completed", source: "quick_recognition", items }),
  });
}

export function updateCharacterPriority(
  childId: string,
  knowledgePointId: string,
  isPriority: boolean,
): Promise<CharacterMasteryState> {
  return request<CharacterMasteryState>(
    `/api/v1/children/${childId}/characters/${knowledgePointId}/priority`,
    { method: "PATCH", body: jsonBody({ is_priority: isPriority }) },
  );
}

export function getLearningSettings(childId: string): Promise<LearningSettings> {
  return request<LearningSettings>(`/api/v1/children/${childId}/learning-settings`);
}

export function updateLearningSettings(
  childId: string,
  payload: Partial<LearningSettings>,
): Promise<LearningSettings> {
  return request<LearningSettings>(`/api/v1/children/${childId}/learning-settings`, {
    method: "PATCH",
    body: jsonBody(payload),
  });
}

export function getTodayPlan(childId: string): Promise<DailyPlan> {
  return request<DailyPlan>(`/api/v1/children/${childId}/today`);
}

export function startPlannedAssessment(
  childId: string,
  source: "daily_review" | "weekly_check" | "monthly_assessment",
): Promise<PlannedAssessment> {
  const route = {
    daily_review: "reviews",
    weekly_check: "weekly-check",
    monthly_assessment: "monthly-assessment",
  }[source];
  return request<PlannedAssessment>(`/api/v1/children/${childId}/${route}/start`, {
    method: "POST",
  });
}

export function getPlannedAssessment(
  childId: string,
  sessionId: string,
): Promise<PlannedAssessment> {
  return request<PlannedAssessment>(
    `/api/v1/children/${childId}/planned-assessments/${sessionId}`,
  );
}

export function submitPlannedAssessment(
  childId: string,
  sessionId: string,
  payload: {
    items: Array<{
      knowledge_point_id: string;
      outcome: AssessmentOutcome;
      response_time_ms: number;
      hint_used?: boolean;
    }>;
    complete?: boolean;
  },
): Promise<PlannedAssessment> {
  return request<PlannedAssessment>(
    `/api/v1/children/${childId}/planned-assessments/${sessionId}/items`,
    { method: "POST", body: jsonBody(payload) },
  );
}

export function getAssessmentHistory(childId: string): Promise<AssessmentHistoryEntry[]> {
  return request<AssessmentHistoryEntry[]>(`/api/v1/children/${childId}/assessment-history`);
}

export function getLiteracyEstimate(childId: string): Promise<LiteracyEstimate> {
  return request<LiteracyEstimate>(`/api/v1/children/${childId}/literacy-estimate`);
}

export function getReadingContext(childId: string): Promise<ReadingContext> {
  return request<ReadingContext>(`/api/v1/children/${childId}/reading-context`);
}

export function generateStory(
  childId: string,
  payload: {
    difficulty: StoryDifficulty;
    theme: string;
    custom_theme?: string | null;
    target_knowledge_point_ids?: string[];
    request_key?: string;
    story_id?: string;
  },
): Promise<StoryGenerationResult> {
  return request<StoryGenerationResult>(
    `/api/v1/children/${childId}/stories/generate`,
    { method: "POST", body: jsonBody(payload) },
    90_000,
  );
}

export function listStories(
  childId: string,
  filters: { page?: number; search?: string; difficulty?: StoryDifficulty } = {},
): Promise<StoryPage> {
  const query = new URLSearchParams({ page: String(filters.page ?? 1), page_size: "12" });
  if (filters.search) query.set("search", filters.search);
  if (filters.difficulty) query.set("difficulty", filters.difficulty);
  return request<StoryPage>(`/api/v1/children/${childId}/stories?${query}`);
}

export function getStoryVersion(childId: string, versionId: string): Promise<StoryVersion> {
  return request<StoryVersion>(`/api/v1/children/${childId}/story-versions/${versionId}`);
}

export function startReading(
  childId: string,
  versionId: string,
  readingMode: "independent" | "with_help",
): Promise<ReadingSession> {
  return request<ReadingSession>(
    `/api/v1/children/${childId}/story-versions/${versionId}/reading/start`,
    { method: "POST", body: jsonBody({ reading_mode: readingMode }) },
  );
}

export function submitReadingAnswers(
  childId: string,
  sessionId: string,
  answers: Array<{
    question_id: string;
    selected_option_index: number;
    outcome: "correct" | "with_help" | "partial" | "incorrect";
  }>,
): Promise<ReadingSession> {
  return request<ReadingSession>(
    `/api/v1/children/${childId}/reading-sessions/${sessionId}/answers`,
    { method: "POST", body: jsonBody({ answers }) },
  );
}

export function completeReading(
  childId: string,
  sessionId: string,
  payload: { duration_seconds?: number; parent_note?: string | null },
): Promise<ReadingSession> {
  return request<ReadingSession>(
    `/api/v1/children/${childId}/reading-sessions/${sessionId}/complete`,
    { method: "POST", body: jsonBody(payload) },
  );
}

export function getReadingSummary(childId: string): Promise<ReadingSummary> {
  return request<ReadingSummary>(`/api/v1/children/${childId}/reading-summary`);
}

export function listScienceExperiments(filters: {
  search?: string;
  difficulty?: ScienceDifficulty;
  page?: number;
  pageSize?: number;
} = {}): Promise<ScienceExperimentPage> {
  const query = new URLSearchParams({
    page: String(filters.page ?? 1),
    page_size: String(filters.pageSize ?? 20),
  });
  if (filters.search) query.set("search", filters.search);
  if (filters.difficulty) query.set("difficulty", filters.difficulty);
  return request<ScienceExperimentPage>(`/api/v1/science/experiments?${query}`);
}

export function getScienceExperiment(id: string): Promise<ScienceExperiment> {
  return request<ScienceExperiment>(`/api/v1/science/experiments/${id}`);
}

export function listScienceRecommendations(childId: string): Promise<ScienceRecommendation[]> {
  return request<ScienceRecommendation[]>(`/api/v1/children/${childId}/science/recommendations`);
}

export function getFamilyMaterials(familyId: string): Promise<FamilyMaterial[]> {
  return request<FamilyMaterial[]>(`/api/v1/families/${familyId}/science/materials`);
}

export function updateFamilyMaterials(
  familyId: string,
  items: Array<{ material_id: string; is_owned: boolean; quantity_text?: string | null; note?: string | null }>,
): Promise<FamilyMaterial[]> {
  return request<FamilyMaterial[]>(`/api/v1/families/${familyId}/science/materials`, {
    method: "PUT",
    body: jsonBody({ items }),
  });
}

export function startExperimentSession(
  childId: string,
  experimentId: string,
  requestKey = createClientKey(),
): Promise<ExperimentSession> {
  return request<ExperimentSession>(`/api/v1/children/${childId}/experiment-sessions`, {
    method: "POST",
    body: jsonBody({
      experiment_id: experimentId,
      timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "Asia/Shanghai",
      request_key: requestKey,
      start_immediately: true,
    }),
  });
}

export function listExperimentSessions(childId: string): Promise<ExperimentSessionPage> {
  return request<ExperimentSessionPage>(`/api/v1/children/${childId}/experiment-sessions`);
}

export function getExperimentSession(childId: string, sessionId: string): Promise<ExperimentSession> {
  return request<ExperimentSession>(`/api/v1/children/${childId}/experiment-sessions/${sessionId}`);
}

export function updateExperimentSession(
  childId: string,
  sessionId: string,
  payload: { action?: "start" | "advance" | "abandon"; current_step?: ExperimentSession["current_step"]; parent_note?: string | null },
): Promise<ExperimentSession> {
  return request<ExperimentSession>(`/api/v1/children/${childId}/experiment-sessions/${sessionId}`, {
    method: "PATCH",
    body: jsonBody(payload),
  });
}

export function addExperimentEvidence(
  childId: string,
  sessionId: string,
  items: Array<{ evidence_type: ExperimentEvidence["evidence_type"]; original_text: string; capability_tags: string[]; client_key?: string }>,
): Promise<ExperimentEvidence[]> {
  return request<ExperimentEvidence[]>(`/api/v1/children/${childId}/experiment-sessions/${sessionId}/evidence`, {
    method: "POST",
    body: jsonBody({ items }),
  });
}

export function updateExperimentEvidence(
  childId: string,
  sessionId: string,
  evidenceId: string,
  payload: { original_text?: string; capability_tags?: string[] },
): Promise<ExperimentEvidence> {
  return request<ExperimentEvidence>(
    `/api/v1/children/${childId}/experiment-sessions/${sessionId}/evidence/${evidenceId}`,
    { method: "PATCH", body: jsonBody(payload) },
  );
}

export function uploadExperimentMedia(childId: string, sessionId: string, file: File): Promise<ExperimentSession> {
  const body = new FormData();
  body.set("file", file);
  return request<ExperimentSession>(`/api/v1/children/${childId}/experiment-sessions/${sessionId}/media`, {
    method: "POST",
    body,
  }, 120_000);
}

export function replaceExperimentMedia(
  childId: string,
  sessionId: string,
  mediaId: string,
  file: File,
): Promise<ExperimentSession> {
  const body = new FormData();
  body.set("file", file);
  return request<ExperimentSession>(
    `/api/v1/children/${childId}/experiment-sessions/${sessionId}/media/${mediaId}`,
    { method: "PUT", body },
    120_000,
  );
}

export function deleteExperimentMedia(
  childId: string,
  sessionId: string,
  mediaId: string,
): Promise<void> {
  return request<void>(
    `/api/v1/children/${childId}/experiment-sessions/${sessionId}/media/${mediaId}`,
    { method: "DELETE" },
  );
}

export function completeExperiment(childId: string, sessionId: string, parentNote?: string): Promise<ExperimentSession> {
  return request<ExperimentSession>(`/api/v1/children/${childId}/experiment-sessions/${sessionId}/complete`, {
    method: "POST",
    body: jsonBody({ parent_note: parentNote || null }),
  });
}

export function getExperimentGrowthCard(childId: string, sessionId: string): Promise<ExperimentGrowthCard> {
  return request<ExperimentGrowthCard>(`/api/v1/children/${childId}/experiment-sessions/${sessionId}/growth-card`);
}

export function generateExperimentAIParentTip(
  childId: string,
  sessionId: string,
): Promise<ExperimentAIParentTip> {
  return request<ExperimentAIParentTip>(
    `/api/v1/children/${childId}/experiment-sessions/${sessionId}/ai-parent-tip`,
    { method: "POST" },
    45_000,
  );
}

export function generateExperimentStory(
  childId: string,
  sessionId: string,
  difficulty: StoryDifficulty = "normal",
): Promise<StoryGenerationResult> {
  return request<StoryGenerationResult>(`/api/v1/children/${childId}/experiment-sessions/${sessionId}/generate-story`, {
    method: "POST",
    body: jsonBody({ difficulty, request_key: createClientKey() }),
  }, 120_000);
}

export function listAdminScienceExperiments(filters: {
  search?: string;
  status?: ScienceExperimentStatus;
  difficulty?: ScienceDifficulty;
  page?: number;
} = {}): Promise<ScienceExperimentPage> {
  const query = new URLSearchParams({ page: String(filters.page ?? 1), page_size: "20" });
  if (filters.search) query.set("search", filters.search);
  if (filters.status) query.set("status", filters.status);
  if (filters.difficulty) query.set("difficulty", filters.difficulty);
  return request<ScienceExperimentPage>(`/api/v1/admin/science/experiments?${query}`);
}

export function updateAdminScienceExperiment(id: string, payload: Partial<ScienceExperiment>): Promise<ScienceExperiment> {
  return request<ScienceExperiment>(`/api/v1/admin/science/experiments/${id}`, {
    method: "PATCH",
    body: jsonBody(payload),
  });
}

export function importStarterScience(): Promise<{ created: number; updated: number; skipped: number; materials_created: number; errors: string[] }> {
  return request("/api/v1/admin/science/import-starter", { method: "POST" });
}

export function listGrowthEvents(
  childId: string,
  filters: { category?: GrowthCategory; year?: number; month?: number } = {},
): Promise<GrowthEventPage> {
  const query = new URLSearchParams({ page: "1", page_size: "100" });
  if (filters.category) query.set("category", filters.category);
  if (filters.year) query.set("year", String(filters.year));
  if (filters.month) query.set("month", String(filters.month));
  return request<GrowthEventPage>(`/api/v1/children/${childId}/growth/events?${query}`);
}

export function getRecentGrowth(childId: string): Promise<GrowthEvent[]> {
  return request<GrowthEvent[]>(`/api/v1/children/${childId}/growth/recent`);
}

export function createGrowthEvent(
  childId: string,
  payload: {
    occurred_at: string;
    title?: string | null;
    text: string;
    event_type: "manual_growth_note" | "family_observation";
    category: "family" | "learning" | "reading" | "science";
  },
): Promise<GrowthEvent> {
  return request<GrowthEvent>(`/api/v1/children/${childId}/growth/events`, {
    method: "POST",
    body: jsonBody(payload),
  });
}

export function uploadGrowthMedia(
  childId: string,
  eventId: string,
  file: File,
): Promise<GrowthEvent> {
  const body = new FormData();
  body.set("file", file);
  return request<GrowthEvent>(
    `/api/v1/children/${childId}/growth/events/${eventId}/media`,
    { method: "POST", body },
    120_000,
  );
}

export function generateGrowthReport(
  childId: string,
  payload: {
    period_type: "monthly" | "yearly" | "custom";
    period_start: string;
    period_end: string;
    include_ai_narrative?: boolean;
  },
): Promise<GrowthReport> {
  return request<GrowthReport>(`/api/v1/children/${childId}/growth/reports`, {
    method: "POST",
    body: jsonBody(payload),
  });
}

export function listGrowthReports(childId: string): Promise<GrowthReportSummary[]> {
  return request<GrowthReportSummary[]>(`/api/v1/children/${childId}/growth/reports`);
}

export function getGrowthReport(childId: string, reportId: string): Promise<GrowthReport> {
  return request<GrowthReport>(`/api/v1/children/${childId}/growth/reports/${reportId}`);
}

export function createGrowthBook(
  childId: string,
  payload: {
    edition_type: "yearly" | "age_year";
    edition_key: string;
    title: string;
    selected_event_ids: string[];
    selected_media: Array<Record<string, string>>;
    parent_message?: string | null;
  },
): Promise<GrowthBook> {
  return request<GrowthBook>(`/api/v1/children/${childId}/growth/books`, {
    method: "POST",
    body: jsonBody(payload),
  });
}

export function listGrowthBooks(childId: string): Promise<GrowthBookSummary[]> {
  return request<GrowthBookSummary[]>(`/api/v1/children/${childId}/growth/books`);
}

export function getGrowthBook(childId: string, bookId: string): Promise<GrowthBook> {
  return request<GrowthBook>(`/api/v1/children/${childId}/growth/books/${bookId}`);
}

export function requestFamilyExport(familyId: string, childId?: string): Promise<ExportJob> {
  return request<ExportJob>(`/api/v1/families/${familyId}/exports`, {
    method: "POST",
    body: jsonBody({ child_id: childId || null }),
  }, 120_000);
}

export async function downloadFamilyExport(job: ExportJob): Promise<void> {
  if (!job.download_url) throw new ApiClientError("导出文件尚不可下载");
  const response = await fetch(`${getApiBaseUrl()}${job.download_url}`, {
    credentials: "include",
    cache: "no-store",
  });
  if (!response.ok) throw new ApiClientError("导出文件下载失败", response.status);
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = `growth-learning-export-${job.id}.zip`;
  link.click();
  URL.revokeObjectURL(url);
}

export type TeacherProfile = {
  id: string;
  display_name: string;
  organization_name: string | null;
  short_bio: string | null;
  teacher_code: string;
  status: "active" | "disabled";
  created_at: string;
  updated_at: string;
};

export type TeacherPublicProfile = Pick<
  TeacherProfile,
  "id" | "display_name" | "organization_name" | "short_bio"
>;

export type TeacherClassroom = {
  id: string;
  name: string;
  description: string | null;
  class_code: string;
  status: "active" | "archived";
  student_count: number;
  created_at: string;
  updated_at: string;
};

export type TeacherAssignmentType =
  | "character_learning"
  | "character_review"
  | "recognition_check"
  | "reading"
  | "freeform_instruction";

export type AssignmentCharacter = {
  knowledge_point_id: string;
  character: string;
  pinyin: string;
  position: number;
};

export type TeacherTask = {
  assignment_id: string;
  teacher: TeacherPublicProfile;
  classroom_name: string | null;
  title: string;
  instructions: string;
  assignment_type: TeacherAssignmentType;
  due_at: string | null;
  progress_status: "pending" | "in_progress" | "completed" | "overdue";
  completed_item_count: number;
  total_item_count: number;
  characters: AssignmentCharacter[];
};

export type TeacherTaskProgress = TeacherTask & {
  learning_session_id: string | null;
  assessment_session_id: string | null;
  reading_session_id: string | null;
  started_at: string | null;
  completed_at: string | null;
  completed_learning_point_ids: string[];
  assessment_outcomes: Record<string, string>;
};

export type TeacherAssignment = {
  id: string;
  teacher: TeacherPublicProfile;
  classroom_id: string | null;
  classroom_name: string | null;
  title: string;
  instructions: string;
  assignment_type: TeacherAssignmentType;
  due_at: string | null;
  status: "draft" | "published" | "closed" | "archived";
  published_at: string | null;
  characters: AssignmentCharacter[];
  targets: Array<{
    child_id: string;
    child_name: string;
    progress_status: "pending" | "in_progress" | "completed" | "overdue";
    completed_item_count: number;
    total_item_count: number;
  }>;
  created_at: string;
  updated_at: string;
};

export type TeacherObservation = {
  id: string;
  teacher: TeacherPublicProfile;
  child_id: string;
  category: "recognition" | "reading" | "expression" | "learning_habit" | "participation" | "other";
  original_text: string;
  occurred_at: string;
  classroom_id: string | null;
  assignment_id: string | null;
  knowledge_point_ids: string[];
  created_at: string;
};

export type TeacherStudent = {
  child_id: string;
  display_name: string;
  nickname: string | null;
  age_band: string;
  assignments: TeacherTask[];
  relevant_mastery: Array<{
    knowledge_point_id: string;
    character: string;
    pinyin: string;
    mastery_level: MasteryLevel;
    mastery_score: number;
    is_priority: boolean;
  }>;
  observations: TeacherObservation[];
};

export type TeacherDashboard = {
  profile: TeacherProfile;
  classrooms: TeacherClassroom[];
  students: TeacherStudent[];
  assignments: TeacherAssignment[];
  pending_review_count: number;
  recent_completed_count: number;
};

export type ParentTeacherCollaboration = {
  relations: Array<{
    id: string;
    child_id: string;
    teacher: TeacherPublicProfile;
    status: "active" | "revoked";
    authorized_at: string;
    revoked_at: string | null;
    permission_version: string;
  }>;
  classrooms: Array<{
    id: string;
    classroom_id: string;
    classroom_name: string;
    teacher: TeacherPublicProfile;
    status: "active" | "left";
    joined_at: string;
    left_at: string | null;
  }>;
  assignments: TeacherTask[];
  observations: TeacherObservation[];
};

export type AssignmentAnalytics = {
  assignment_id: string;
  total: number;
  pending: number;
  in_progress: number;
  completed: number;
  overdue: number;
  outcome_counts: Record<string, number>;
  character_outcomes: Record<string, Record<string, number>>;
  common_errors: string[];
  ranking_enabled: false;
};

export function getTeacherProfile(): Promise<TeacherProfile> {
  return request<TeacherProfile>("/api/v1/teacher/profile");
}

export function enableTeacherMode(payload: {
  display_name: string;
  organization_name?: string | null;
  short_bio?: string | null;
}): Promise<TeacherProfile> {
  return request<TeacherProfile>("/api/v1/teacher/profile", {
    method: "POST",
    body: jsonBody(payload),
  });
}

export function rotateTeacherCode(): Promise<TeacherProfile> {
  return request<TeacherProfile>("/api/v1/teacher/profile/rotate-code", { method: "POST" });
}

export function getTeacherDashboard(): Promise<TeacherDashboard> {
  return request<TeacherDashboard>("/api/v1/teacher/dashboard");
}

export function createTeacherClassroom(payload: {
  name: string;
  description?: string | null;
}): Promise<TeacherClassroom> {
  return request<TeacherClassroom>("/api/v1/teacher/classrooms", {
    method: "POST",
    body: jsonBody(payload),
  });
}

export function resolveTeacherConnection(code: string): Promise<{
  kind: "teacher" | "classroom";
  teacher: TeacherPublicProfile;
  classroom: TeacherClassroom | null;
}> {
  return request(`/api/v1/teacher/connections/resolve?code=${encodeURIComponent(code)}`);
}

export function connectChildTeacher(childId: string, code: string): Promise<unknown> {
  return request(`/api/v1/children/${childId}/teacher-connections`, {
    method: "POST",
    body: jsonBody({ code }),
  });
}

export function revokeChildTeacher(
  childId: string,
  relationId: string,
): Promise<unknown> {
  return request(`/api/v1/children/${childId}/teacher-connections/${relationId}/revoke`, {
    method: "POST",
  });
}

export function leaveTeacherClassroom(childId: string, membershipId: string): Promise<void> {
  return request(`/api/v1/children/${childId}/teacher-classrooms/${membershipId}/leave`, {
    method: "POST",
  });
}

export function getParentTeacherCollaboration(
  childId: string,
): Promise<ParentTeacherCollaboration> {
  return request(`/api/v1/children/${childId}/teacher-collaboration`);
}

export function createTeacherAssignment(payload: {
  classroom_id?: string | null;
  title: string;
  instructions: string;
  assignment_type: TeacherAssignmentType;
  due_at?: string | null;
  target_child_ids: string[];
  knowledge_point_ids: string[];
}): Promise<TeacherAssignment> {
  return request<TeacherAssignment>("/api/v1/teacher/assignments", {
    method: "POST",
    body: jsonBody(payload),
  });
}

export function publishTeacherAssignment(assignmentId: string): Promise<TeacherAssignment> {
  return request<TeacherAssignment>(`/api/v1/teacher/assignments/${assignmentId}/publish`, {
    method: "POST",
  });
}

export function getTeacherAssignment(assignmentId: string): Promise<TeacherAssignment> {
  return request<TeacherAssignment>(`/api/v1/teacher/assignments/${assignmentId}`);
}

export function getTeacherAssignmentAnalytics(
  assignmentId: string,
): Promise<AssignmentAnalytics> {
  return request(`/api/v1/teacher/assignments/${assignmentId}/analytics`);
}

export function getTeacherStudent(childId: string): Promise<TeacherStudent> {
  return request(`/api/v1/teacher/students/${childId}`);
}

export function addTeacherObservation(
  childId: string,
  payload: {
    category: TeacherObservation["category"];
    original_text: string;
    occurred_at: string;
    classroom_id?: string | null;
    assignment_id?: string | null;
    knowledge_point_ids?: string[];
  },
): Promise<TeacherObservation> {
  return request(`/api/v1/teacher/students/${childId}/observations`, {
    method: "POST",
    body: jsonBody(payload),
  });
}

export function getChildTeacherTasks(childId: string): Promise<TeacherTask[]> {
  return request(`/api/v1/children/${childId}/teacher-tasks`);
}

export function startTeacherTask(
  childId: string,
  assignmentId: string,
): Promise<TeacherTaskProgress> {
  return request(`/api/v1/children/${childId}/teacher-tasks/${assignmentId}/start`, {
    method: "POST",
  });
}

export function submitTeacherTask(
  childId: string,
  assignmentId: string,
  payload: {
    learning_point_ids?: string[];
    assessment_items?: Array<{
      knowledge_point_id: string;
      outcome: "correct" | "hinted_correct" | "uncertain" | "incorrect";
      response_time_ms?: number | null;
    }>;
    reading_session_id?: string | null;
    complete?: boolean;
  },
): Promise<TeacherTaskProgress> {
  return request(`/api/v1/children/${childId}/teacher-tasks/${assignmentId}/progress`, {
    method: "POST",
    body: jsonBody(payload),
  });
}

export function listEnabledCharacters(search = ""): Promise<CharacterPage> {
  const query = new URLSearchParams({ page: "1", page_size: "100" });
  if (search) query.set("search", search);
  return request<CharacterPage>(`/api/v1/characters?${query}`);
}

export type CoursePoint = {
  knowledge_point_id: string;
  title: string;
  subject: Subject;
  knowledge_type: KnowledgeType;
  character: string | null;
  pinyin: string | null;
  role: "primary" | "review" | "optional" | "prerequisite";
  order_index: number;
  mastery_level: MasteryLevel | null;
  mastery_policy_key: string | null;
  projection_status: "configured" | "unavailable";
};

export type CourseActivity = {
  id: string;
  title: string;
  activity_type:
    | "knowledge_learning"
    | "guided_practice"
    | "independent_practice"
    | "knowledge_review"
    | "knowledge_check"
    | "listening"
    | "speaking"
    | "character_learning"
    | "character_review"
    | "recognition_check"
    | "reading"
    | "science_reference"
    | "offline_instruction";
  instructions: string | null;
  order_index: number;
  status: "draft" | "enabled" | "archived";
  progress_status: "pending" | "in_progress" | "completed";
  points: CoursePoint[];
};

export type CourseUnit = {
  id: string;
  title: string;
  description: string | null;
  order_index: number;
  status: "draft" | "enabled" | "archived";
  activity_count: number;
  completed_activities: number;
  introduced_count: number;
  stable_count: number;
  unlearned_count: number;
  projection_unavailable_count: number;
  activities: CourseActivity[];
};

export type Course = {
  id: string;
  subject: Subject;
  title: string;
  description: string | null;
  source_type: "system" | "family" | "teacher" | "textbook_reference";
  status: "draft" | "enabled" | "archived";
  version: number;
  recommended_age_min: number | null;
  recommended_age_max: number | null;
  reference_metadata: Record<string, string>;
  enrollment_id: string | null;
  enrollment_status: "planned" | "active" | "paused" | "completed" | "archived" | null;
  path_order: number | null;
  activity_count: number;
  completed_activities: number;
  progress_percent: number;
  introduced_count: number;
  stable_count: number;
  unlearned_count: number;
  projection_unavailable_count: number;
  units: CourseUnit[];
  created_at: string;
  updated_at: string;
};

export type CourseInput = {
  subject?: Subject;
  title: string;
  description?: string | null;
  source_type: "system" | "family" | "teacher" | "textbook_reference";
  reference_metadata?: Record<string, string>;
  units: Array<{
    title: string;
    description?: string | null;
    activities: Array<{
      title: string;
      activity_type: CourseActivity["activity_type"];
      instructions?: string | null;
      knowledge_points: Array<{
        knowledge_point_id: string;
        role: CoursePoint["role"];
      }>;
    }>;
  }>;
};

export type CourseEnrollment = {
  id: string;
  child_id: string;
  course_id: string;
  course_title: string;
  course_version: number;
  status: "planned" | "active" | "paused" | "completed" | "archived";
  path_order: number;
  started_at: string | null;
  completed_at: string | null;
  progress_percent: number;
};

export type CatalogRelease = {
  catalog_version: string;
  item_count: number;
  source_type: string;
  source_name: string;
  source_reference: string | null;
  license: string | null;
  imported_at: string;
  is_current: boolean;
  metadata: Record<string, string>;
};

export type ChildTodayTask = {
  subject: Subject;
  kind: "new" | "review" | "pinyin" | "math" | "reading" | "science" | "teacher";
  title: string;
  description: string;
  status: "pending" | "in_progress" | "completed" | "needs_story" | "optional";
  count: number;
  cta_label: string;
  href: string;
  source_type: string;
  source_id: string | null;
  urgent: boolean;
};

export type ChildToday = {
  child_id: string;
  plan_date: string;
  tasks: ChildTodayTask[];
  continue_task: ChildTodayTask | null;
  completed_count: number;
  total_count: number;
  star_balance: number;
  newly_unlocked_achievements: number;
};

export type GrowthTreeUnit = {
  id: string;
  title: string;
  total: number;
  course_completed_activities: number;
  course_activity_count: number;
  touched: number;
  growing: number;
  familiar: number;
};

export type GrowthTreeCourse = {
  id: string;
  title: string;
  source_type: string;
  course_progress_percent: number;
  total: number;
  touched: number;
  growing: number;
  familiar: number;
  units: GrowthTreeUnit[];
};

export type GrowthTree = {
  child_id: string;
  projection_version: string;
  mastery_mapping: Record<MasteryLevel, string>;
  chinese: GrowthTreeCourse[];
  reading: { completed: number; independent: number | null; questions: number | null };
  science: { completed: number; independent: number | null; questions: number | null };
};

export type ChildAchievement = {
  id: string;
  key: string;
  title: string;
  description: string;
  icon: string;
  rule_version: string;
  evidence_source_type: string;
  evidence_source_id: string | null;
  evidence_snapshot: Record<string, string | number>;
  unlocked_at: string;
};

export type StarLedgerEntry = {
  id: string;
  amount: number;
  reason_type: string;
  source_type: string;
  source_id: string;
  rule_version: string;
  occurred_at: string;
};

export type RewardGoal = {
  id: string;
  title: string;
  required_stars: number;
  is_active: boolean;
};

export type AchievementSummary = {
  child_id: string;
  stars_enabled: boolean;
  star_balance: number;
  achievements: ChildAchievement[];
  recent_ledger: StarLedgerEntry[];
  next_reward_goal: RewardGoal | null;
};

export type RewardSettings = {
  family_id: string;
  stars_enabled: boolean;
  goals: RewardGoal[];
};

export function listCourses(childId: string, subject?: Subject): Promise<Course[]> {
  const query = new URLSearchParams({ child_id: childId });
  if (subject) query.set("subject", subject);
  return request<Course[]>(`/api/v1/courses?${query.toString()}`);
}

export function getCourse(courseId: string, childId: string): Promise<Course> {
  return request<Course>(
    `/api/v1/courses/${courseId}?child_id=${encodeURIComponent(childId)}`,
  );
}

export function createFamilyCourse(familyId: string, payload: CourseInput): Promise<Course> {
  return request<Course>(`/api/v1/families/${familyId}/courses`, {
    method: "POST",
    body: jsonBody(payload),
  });
}

export function createTeacherCourse(payload: CourseInput): Promise<Course> {
  return request<Course>("/api/v1/teacher/courses", {
    method: "POST",
    body: jsonBody(payload),
  });
}

export function listTeacherCourses(subject?: Subject): Promise<Course[]> {
  return request<Course[]>(`/api/v1/teacher/courses${subject ? `?subject=${subject}` : ""}`);
}

export function enrollCourse(
  childId: string,
  courseId: string,
  pathOrder = 0,
): Promise<CourseEnrollment> {
  return request<CourseEnrollment>(`/api/v1/children/${childId}/course-enrollments`, {
    method: "POST",
    body: jsonBody({ course_id: courseId, path_order: pathOrder, status: "active" }),
  });
}

export function updateCourseEnrollment(
  childId: string,
  enrollmentId: string,
  status: CourseEnrollment["status"],
): Promise<CourseEnrollment> {
  return request<CourseEnrollment>(
    `/api/v1/children/${childId}/course-enrollments/${enrollmentId}`,
    { method: "PATCH", body: jsonBody({ status }) },
  );
}

export function copyCoursePath(sourceChildId: string, targetChildId: string): Promise<{
  copied_enrollments: number;
  mastery_copied: false;
  history_copied: false;
}> {
  return request(`/api/v1/children/${sourceChildId}/course-path/copy`, {
    method: "POST",
    body: jsonBody({ target_child_id: targetChildId }),
  });
}

export function completeCourseActivity(
  childId: string,
  activityId: string,
): Promise<{
  activity_id: string;
  progress_status: "completed";
  learning_session_id: string;
  learning_records_created: number;
  mastery_directly_modified: false;
}> {
  return request(`/api/v1/children/${childId}/course-activities/${activityId}/complete`, {
    method: "POST",
  });
}

export function getAdminCatalog(): Promise<CatalogRelease> {
  return request<CatalogRelease>("/api/v1/admin/catalog");
}

export function importChineseCatalog(): Promise<{
  created: number;
  updated: number;
  skipped: number;
  preserved: number;
  catalog_version: string;
  catalog_size: number;
  course_created: boolean;
  errors: string[];
}> {
  return request("/api/v1/admin/catalog/import", { method: "POST" });
}

export function listAdminCourses(subject?: Subject): Promise<Course[]> {
  return request<Course[]>(`/api/v1/admin/courses${subject ? `?subject=${subject}` : ""}`);
}

export function createAdminCourse(payload: CourseInput): Promise<Course> {
  return request<Course>("/api/v1/admin/courses", {
    method: "POST",
    body: jsonBody(payload),
  });
}

export function getChildToday(childId: string): Promise<ChildToday> {
  return request<ChildToday>(`/api/v1/children/${childId}/experience/today`);
}

export function getGrowthTree(childId: string): Promise<GrowthTree> {
  return request<GrowthTree>(`/api/v1/children/${childId}/growth-tree`);
}

export function getAchievements(childId: string): Promise<AchievementSummary> {
  return request<AchievementSummary>(`/api/v1/children/${childId}/achievements`);
}

export function getRewardSettings(familyId: string): Promise<RewardSettings> {
  return request<RewardSettings>(`/api/v1/families/${familyId}/reward-settings`);
}

export function updateRewardSettings(
  familyId: string,
  starsEnabled: boolean,
): Promise<RewardSettings> {
  return request<RewardSettings>(`/api/v1/families/${familyId}/reward-settings`, {
    method: "PATCH",
    body: jsonBody({ stars_enabled: starsEnabled }),
  });
}

export function createRewardGoal(
  familyId: string,
  title: string,
  requiredStars: number,
): Promise<RewardGoal> {
  return request<RewardGoal>(`/api/v1/families/${familyId}/reward-goals`, {
    method: "POST",
    body: jsonBody({ title, required_stars: requiredStars }),
  });
}

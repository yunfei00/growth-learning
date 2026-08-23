export type CharacterLearningSource =
  | "today"
  | "system_path"
  | "mastery"
  | "records"
  | "review"
  | "course"
  | "direct";

export type CharacterLearningSequence =
  | "system_path"
  | "today"
  | "mastery"
  | "learning_session"
  | "assessment_session"
  | "course_activity";

export type CharacterLearningContext = {
  source?: CharacterLearningSource;
  returnTo?: string;
  sequence?: CharacterLearningSequence;
  contextId?: string;
  itemKind?: "new" | "review";
  masteryLevel?: "unlearned" | "introduced" | "recognizing" | "proficient" | "stable";
  priority?: boolean;
  sortBy?: "learning_time" | "recent_review" | "character";
  sortOrder?: "asc" | "desc";
};

const SOURCES = new Set<CharacterLearningSource>([
  "today",
  "system_path",
  "mastery",
  "records",
  "review",
  "course",
  "direct",
]);

const SEQUENCES = new Set<CharacterLearningSequence>([
  "system_path",
  "today",
  "mastery",
  "learning_session",
  "assessment_session",
  "course_activity",
]);

export function normalizeCharacterReturnTo(value?: string | null): string | null {
  if (!value || !value.startsWith("/") || value.startsWith("//")) return null;
  return value;
}

export function buildCharacterLearningHref(
  knowledgePointId: string,
  context: CharacterLearningContext = {},
): string {
  const query = new URLSearchParams();
  if (context.source) query.set("source", context.source);
  const returnTo = normalizeCharacterReturnTo(context.returnTo);
  if (returnTo) query.set("returnTo", returnTo);
  if (context.sequence) query.set("sequence", context.sequence);
  if (context.contextId) query.set("contextId", context.contextId);
  if (context.itemKind) query.set("itemKind", context.itemKind);
  if (context.masteryLevel) query.set("masteryLevel", context.masteryLevel);
  if (context.priority !== undefined) query.set("priority", String(context.priority));
  if (context.sortBy) query.set("sortBy", context.sortBy);
  if (context.sortOrder) query.set("sortOrder", context.sortOrder);
  const encoded = query.toString();
  return `/learn/characters/${knowledgePointId}${encoded ? `?${encoded}` : ""}`;
}

export function parseCharacterLearningContext(
  query: URLSearchParams,
): Required<Pick<CharacterLearningContext, "source" | "sequence">> & CharacterLearningContext {
  const sourceValue = query.get("source") as CharacterLearningSource | null;
  const sequenceValue = query.get("sequence") as CharacterLearningSequence | null;
  const itemKind = query.get("itemKind");
  const masteryLevel = query.get("masteryLevel");
  const sortBy = query.get("sortBy");
  const sortOrder = query.get("sortOrder");
  return {
    source: sourceValue && SOURCES.has(sourceValue) ? sourceValue : "direct",
    sequence: sequenceValue && SEQUENCES.has(sequenceValue) ? sequenceValue : "system_path",
    returnTo: normalizeCharacterReturnTo(query.get("returnTo")) ?? undefined,
    contextId: query.get("contextId") ?? undefined,
    itemKind: itemKind === "new" || itemKind === "review" ? itemKind : undefined,
    masteryLevel:
      masteryLevel === "unlearned" ||
      masteryLevel === "introduced" ||
      masteryLevel === "recognizing" ||
      masteryLevel === "proficient" ||
      masteryLevel === "stable"
        ? masteryLevel
        : undefined,
    priority: query.has("priority") ? query.get("priority") === "true" : undefined,
    sortBy:
      sortBy === "learning_time" || sortBy === "recent_review" || sortBy === "character"
        ? sortBy
        : undefined,
    sortOrder: sortOrder === "asc" || sortOrder === "desc" ? sortOrder : undefined,
  };
}

export function characterReturnLabel(source: CharacterLearningSource): string {
  return {
    today: "返回今日任务",
    system_path: "返回系统汉字学习路径",
    mastery: "返回掌握状态列表",
    records: "返回识字记录",
    review: "返回测试历史",
    course: "返回课程学习路径",
    direct: "返回识字学习",
  }[source];
}

export function resolveCharacterReturnAction(
  returnTo: string | null | undefined,
  hasBrowserHistory: boolean,
): { kind: "url"; value: string } | { kind: "history" } {
  const normalized = normalizeCharacterReturnTo(returnTo);
  if (normalized) return { kind: "url", value: normalized };
  if (hasBrowserHistory) return { kind: "history" };
  return { kind: "url", value: "/learn/characters" };
}

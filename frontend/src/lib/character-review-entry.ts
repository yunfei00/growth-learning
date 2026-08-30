import type { DailyPlan, LearningSettings } from "@/lib/api/client";

type ReviewPlan = Pick<DailyPlan, "review_count" | "review_completed_count">;
type ReviewSettings = Pick<
  LearningSettings,
  "character_review_mode" | "speech_review_feature_enabled"
>;

export type DailyReviewEntry = {
  hasTask: boolean;
  completed: boolean;
  speechEnabled: boolean;
  title: string;
  buttonLabel: string;
};

export function getDailyReviewEntry(
  plan: ReviewPlan,
  settings: ReviewSettings | null,
): DailyReviewEntry {
  const hasTask = plan.review_count > 0;
  const completed = hasTask && plan.review_completed_count >= plan.review_count;
  const speechEnabled = Boolean(
    settings?.speech_review_feature_enabled && settings.character_review_mode === "speech_auto",
  );
  return {
    hasTask,
    completed,
    speechEnabled,
    title: speechEnabled ? "🎙️ 儿童朗读复习" : "每日复习",
    buttonLabel: completed
      ? speechEnabled
        ? "查看已完成朗读复习"
        : "查看已完成复习"
      : speechEnabled
        ? "开始朗读复习"
        : "开始 / 继续复习",
  };
}

export function getCompletedReviewDetailAction(plan: ReviewPlan | null): {
  href: string | null;
  label: string;
} {
  if (!plan) return { href: null, label: "正在确认今日复习…" };
  if (plan.review_count === 0) return { href: null, label: "今日暂无复习任务" };
  if (plan.review_completed_count >= plan.review_count) {
    return { href: null, label: "今日复习已完成" };
  }
  return { href: "/learn/characters?view=session", label: "回到今日复习" };
}


"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { useActiveChild } from "@/components/active-child-provider";
import { ChildSwitcher } from "@/components/child-switcher";
import { ProtectedPage } from "@/components/protected-page";
import {
  ApiClientError,
  type ReadingContext,
  type ReadingSummary,
  type StoryDifficulty,
  type StoryPage,
  generateStory,
  getReadingContext,
  getReadingSummary,
  listStories,
} from "@/lib/api/client";

const DIFFICULTIES: Array<{
  value: StoryDifficulty;
  label: string;
  coverage: string;
}> = [
  { value: "beginner", label: "初级", coverage: "目标约 95% 已掌握字" },
  { value: "normal", label: "正常", coverage: "目标约 90% 已掌握字" },
  { value: "challenge", label: "挑战", coverage: "目标约 80% 已掌握字" },
];

const THEME_LABELS: Record<string, string> = {
  animals: "动物",
  dinosaurs: "恐龙",
  vehicles: "汽车",
  space: "太空",
  nature: "自然",
  family_life: "家庭生活",
  science: "科学探索",
};

const DIFFICULTY_LABELS: Record<StoryDifficulty, string> = {
  beginner: "初级",
  normal: "正常",
  challenge: "挑战",
};

function messageFrom(error: unknown, fallback: string) {
  return error instanceof ApiClientError ? error.message : fallback;
}

function ReadingLibrary() {
  const router = useRouter();
  const { status, family, children, activeChild, setActiveChildId } = useActiveChild();
  const [context, setContext] = useState<ReadingContext | null>(null);
  const [stories, setStories] = useState<StoryPage | null>(null);
  const [summary, setSummary] = useState<ReadingSummary | null>(null);
  const [difficulty, setDifficulty] = useState<StoryDifficulty>("beginner");
  const [theme, setTheme] = useState("animals");
  const [customTheme, setCustomTheme] = useState("");
  const [manualTargets, setManualTargets] = useState(false);
  const [selectedTargets, setSelectedTargets] = useState<string[]>([]);
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    if (!activeChild) return;
    try {
      const [contextValue, storiesValue, summaryValue] = await Promise.all([
        getReadingContext(activeChild.id),
        listStories(activeChild.id),
        getReadingSummary(activeChild.id),
      ]);
      setContext(contextValue);
      setStories(storiesValue);
      setSummary(summaryValue);
      setDifficulty(contextValue.recommended_difficulty ?? "beginner");
      setSelectedTargets(
        contextValue.automatic_targets.slice(0, 3).map((target) => target.knowledge_point_id),
      );
      setError("");
    } catch (requestError) {
      setError(messageFrom(requestError, "暂时无法加载故事书"));
    }
  }, [activeChild]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  if (status !== "ready" || !family || !activeChild) {
    return (
      <section className="center-state section-shell">
        <span className="loading-spinner" aria-hidden="true" />
        <p>正在加载孩子的故事书…</p>
      </section>
    );
  }

  const canGenerate = family.current_role === "admin";
  const toggleTarget = (id: string) => {
    setSelectedTargets((current) => {
      if (current.includes(id)) return current.filter((item) => item !== id);
      return current.length < 5 ? [...current, id] : current;
    });
  };
  const handleGenerate = async () => {
    if (!context?.provider_configured || !canGenerate) return;
    if (manualTargets && selectedTargets.length < 2) {
      setError("请至少选择 2 个目标字");
      return;
    }
    setIsGenerating(true);
    setError("");
    try {
      const result = await generateStory(activeChild.id, {
        difficulty,
        theme,
        custom_theme: customTheme.trim() || undefined,
        target_knowledge_point_ids: manualTargets ? selectedTargets : undefined,
        request_key: crypto.randomUUID(),
      });
      router.push(`/read/${result.version.id}`);
    } catch (requestError) {
      setError(messageFrom(requestError, "故事没有生成成功，请调整难度后重试"));
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <section className="reading-hub section-shell">
      <div className="dashboard-toolbar">
        <div>
          <p className="eyebrow">Mastery-aware reading</p>
          <h1>我的故事书</h1>
          <p className="role-note">每篇故事都保存生成当时的识字掌握快照与实际覆盖率。</p>
        </div>
        <ChildSwitcher
          activeChildId={activeChild.id}
          childOptions={children}
          onChange={(id) => {
            setContext(null);
            setStories(null);
            setActiveChildId(id);
          }}
        />
      </div>

      {error ? <p className="form-message form-error">{error}</p> : null}

      <div className="reading-summary-grid">
        <article><span>本周阅读</span><strong>{summary?.stories_read_this_week ?? 0} 篇</strong></article>
        <article><span>独立完成</span><strong>{summary?.independent_this_week ?? 0} 篇</strong></article>
        <article><span>需要陪伴</span><strong>{summary?.with_help_this_week ?? 0} 篇</strong></article>
        <article><span>阅读理解</span><strong className="summary-copy">{summary?.comprehension_message ?? "数据不足"}</strong></article>
      </div>

      <section className="story-generator-panel">
        <div className="section-title-row">
          <div><p className="eyebrow">今日阅读</p><h2>生成适合当前识字水平的故事</h2></div>
          <span>强掌握 {context?.strong_known_count ?? 0} 字 · 可用识别 {context?.usable_recognizing_count ?? 0} 字</span>
        </div>

        {context && !context.provider_configured ? (
          <div className="provider-disabled">
            <strong>AI 服务尚未配置</strong>
            <p>故事书、阅读历史和全部本地能力可用；配置服务器 AI Provider 后即可生成新故事。</p>
          </div>
        ) : null}
        {context?.feasibility_message ? <p className="form-message form-error">{context.feasibility_message}</p> : null}

        <div className="story-form-grid">
          <label>
            安全主题
            <select value={theme} onChange={(event) => setTheme(event.target.value)}>
              {(context?.safe_themes ?? Object.keys(THEME_LABELS)).map((value) => (
                <option key={value} value={value}>{THEME_LABELS[value] ?? value}</option>
              ))}
            </select>
          </label>
          <label>
            补充主题（可选）
            <input
              maxLength={80}
              onChange={(event) => setCustomTheme(event.target.value)}
              placeholder="例如：会种树的小熊"
              value={customTheme}
            />
          </label>
        </div>

        <div className="difficulty-options" role="radiogroup" aria-label="故事难度">
          {DIFFICULTIES.map((item) => (
            <button
              aria-pressed={difficulty === item.value}
              className={difficulty === item.value ? "selected" : ""}
              key={item.value}
              onClick={() => setDifficulty(item.value)}
              type="button"
            >
              <strong>{item.label}</strong><span>{item.coverage}</span>
            </button>
          ))}
        </div>

        <div className="target-selector">
          <div>
            <strong>目标字</strong>
            <label className="inline-toggle">
              <input checked={manualTargets} onChange={(event) => setManualTargets(event.target.checked)} type="checkbox" />
              家长手动选择
            </label>
          </div>
          <div className="target-character-row">
            {context?.automatic_targets.map((target) => (
              <button
                aria-pressed={selectedTargets.includes(target.knowledge_point_id)}
                className={selectedTargets.includes(target.knowledge_point_id) ? "selected" : ""}
                disabled={!manualTargets}
                key={target.knowledge_point_id}
                onClick={() => toggleTarget(target.knowledge_point_id)}
                type="button"
              >
                {target.character}<small>{target.mastery_level}</small>
              </button>
            ))}
          </div>
          <p>自动选择优先考虑重点、待巩固和近期较弱字符；每篇保留 2～5 个目标字。</p>
        </div>

        <button
          className="button button-primary"
          disabled={!context?.provider_configured || !canGenerate || isGenerating || Boolean(context?.feasibility_message)}
          onClick={() => void handleGenerate()}
          type="button"
        >
          {isGenerating ? "正在生成并校验实际覆盖率…" : canGenerate ? "生成故事" : "陪伴成员可阅读，家庭管理员可生成"}
        </button>
        <p className="catalog-note">{context?.catalog_limitation}</p>
      </section>

      <section className="storybook-section">
        <div className="section-title-row"><div><p className="eyebrow">Archive</p><h2>按时间保存的真实版本</h2></div><span>{stories?.total ?? 0} 个版本</span></div>
        {stories && stories.items.length > 0 ? (
          <div className="storybook-grid">
            {stories.items.map((story) => (
              <Link className="story-card" href={`/read/${story.story_version_id}`} key={story.story_version_id}>
                <div><span>{THEME_LABELS[story.theme] ?? story.theme}</span><span>{DIFFICULTY_LABELS[story.difficulty]}</span></div>
                <h3>{story.title}</h3>
                <p>实际已知字覆盖率 {(story.actual_known_coverage * 100).toFixed(1)}%</p>
                <p>目标字：{story.target_characters.join("、")}</p>
                <small>{new Date(story.generated_at).toLocaleDateString("zh-CN")} · {story.reading_status === "completed" ? "已读完" : story.reading_status === "in_progress" ? "继续阅读" : "尚未阅读"} · 理解题 {story.comprehension_answered}/{story.comprehension_total}</small>
              </Link>
            ))}
          </div>
        ) : (
          <div className="empty-storybook"><strong>故事书还是空的</strong><p>具备足够字符掌握证据并配置 AI 服务后，可以生成第一篇故事。</p></div>
        )}
      </section>
    </section>
  );
}

export default function ReadPage() {
  return <ProtectedPage><ReadingLibrary /></ProtectedPage>;
}

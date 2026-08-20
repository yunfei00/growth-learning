"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { useActiveChild } from "@/components/active-child-provider";
import { ProtectedPage } from "@/components/protected-page";
import { ApiClientError, type StoryPage, listStories } from "@/lib/api/client";

const DIFFICULTY = { beginner: "轻松读", normal: "认真读", challenge: "一起挑战" } as const;

function ChildStoriesContent() {
  const { status, activeChild } = useActiveChild();
  const [stories, setStories] = useState<StoryPage | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    if (!activeChild) return;
    try {
      setStories(await listStories(activeChild.id));
      setError("");
    } catch (requestError) {
      setError(
        requestError instanceof ApiClientError ? requestError.message : "故事书暂时打不开",
      );
    }
  }, [activeChild]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  if (status !== "ready" || !activeChild) {
    return <section className="child-state"><span className="loading-spinner" /><p>正在打开故事书…</p></section>;
  }

  return (
    <section className="child-page child-library-page">
      <header className="child-page-heading">
        <span aria-hidden="true">📚</span>
        <div><p>选一个喜欢的故事，慢慢读</p><h1>我的故事书</h1></div>
      </header>
      {error ? <div className="child-error" role="alert"><span>🌦️</span><div><strong>故事书休息了一会儿</strong><p>{error}</p></div><button onClick={() => void load()} type="button">重新尝试</button></div> : null}
      {!stories ? (
        <div className="child-state compact"><span className="loading-spinner" /><p>正在找故事…</p></div>
      ) : stories.items.length === 0 ? (
        <div className="child-empty"><span aria-hidden="true">🌙</span><strong>故事正在准备中</strong><p>请让爸爸妈妈先为你准备一个适合的故事。</p></div>
      ) : (
        <div className="child-story-grid">
          {stories.items.map((story) => (
            <Link className="child-story-card" href={`/read/${story.story_version_id}`} key={story.story_version_id}>
              <span aria-hidden="true">{story.theme === "science" ? "🚀" : story.theme === "nature" ? "🌿" : "📖"}</span>
              <div><small>{DIFFICULTY[story.difficulty]}</small><h2>{story.title}</h2><p>{story.target_characters.length ? `会遇见：${story.target_characters.join("、")}` : "一起发现故事里的新朋友"}</p></div>
              <strong>{story.reading_status === "in_progress" ? "继续读 →" : story.reading_status === "completed" ? "再读一次 →" : "开始读 →"}</strong>
            </Link>
          ))}
        </div>
      )}
      <p className="child-kind-note">这里没有生成和难度设置；故事由家长准备，阅读时可以随时停下来再继续。</p>
    </section>
  );
}

export default function ChildStoriesPage() {
  return <ProtectedPage><ChildStoriesContent /></ProtectedPage>;
}

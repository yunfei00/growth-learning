"use client";

import { useCallback, useEffect, useState } from "react";

import { useActiveChild } from "@/components/active-child-provider";
import { ProtectedPage } from "@/components/protected-page";
import { ApiClientError, type GrowthTree, getGrowthTree } from "@/lib/api/client";

function ChildGrowthTreeContent() {
  const { status, activeChild } = useActiveChild();
  const [tree, setTree] = useState<GrowthTree | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    if (!activeChild) return;
    try {
      setTree(await getGrowthTree(activeChild.id));
      setError("");
    } catch (requestError) {
      setError(
        requestError instanceof ApiClientError ? requestError.message : "成长树暂时没有加载成功",
      );
    }
  }, [activeChild]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  if (status !== "ready" || !activeChild) {
    return <section className="child-state"><span className="loading-spinner" /><p>正在数成长树的新叶子…</p></section>;
  }

  return (
    <section className="child-page growth-tree-page">
      <header className="growth-tree-hero">
        <div className="growth-tree-crown" aria-hidden="true">🌳</div>
        <div><p>每片叶子都来自真实的学习</p><h1>我的成长树</h1></div>
      </header>
      {error ? <div className="child-error" role="alert"><span>🌦️</span><div><strong>成长树在休息</strong><p>{error}</p></div><button onClick={() => void load()} type="button">重新尝试</button></div> : null}
      {!tree ? (
        <div className="child-state compact"><span className="loading-spinner" /><p>正在慢慢展开树枝…</p></div>
      ) : (
        <>
          <section className="tree-domain chinese-tree">
            <div className="tree-domain-title"><span aria-hidden="true">字</span><div><p>种下种子，慢慢长成新叶</p><h2>我的识字树</h2></div></div>
            {tree.chinese.length === 0 ? (
              <div className="child-empty"><span aria-hidden="true">🪴</span><strong>还没有选择学习课程</strong><p>请让爸爸妈妈在家长模式里选择一条学习路径。</p></div>
            ) : (
              <div className="tree-course-list">
                {tree.chinese.map((course) => (
                  <details className="tree-course-branch" key={course.id}>
                    <summary>
                      <span className="branch-icon" aria-hidden="true">🌿</span>
                      <span><strong>{course.title}</strong><small>已接触 {course.touched} · 已经很熟悉 {course.familiar}</small></span>
                      <span className="branch-progress" aria-label={`课程活动完成 ${course.course_progress_percent}%`}><i style={{ width: `${course.course_progress_percent}%` }} /></span>
                    </summary>
                    <div className="tree-unit-list">
                      {course.units.map((unit) => (
                        <article key={unit.id}>
                          <div><strong>{unit.title}</strong><small>课程活动 {unit.course_completed_activities}/{unit.course_activity_count}</small></div>
                          <div className="leaf-stats"><span>🌱 种下 {unit.touched}</span><span>🌿 继续成长 {unit.growing}</span><span>🍃 很熟悉 {unit.familiar}</span></div>
                        </article>
                      ))}
                    </div>
                  </details>
                ))}
              </div>
            )}
            <p className="tree-truth-note">课程活动完成和汉字熟悉程度是两件不同的事；新叶子只来自真实学习和认字记录。</p>
          </section>
          <div className="cross-domain-trees">
            <section className="tree-domain"><div className="tree-domain-title"><span aria-hidden="true">📖</span><div><p>故事里的成长</p><h2>阅读树</h2></div></div><strong>读过 {tree.reading.completed} 个故事</strong><p>自己读完 {tree.reading.independent ?? 0} 个</p></section>
            <section className="tree-domain"><div className="tree-domain-title"><span aria-hidden="true">🔬</span><div><p>好奇心的成长</p><h2>科学树</h2></div></div><strong>完成 {tree.science.completed} 次实验</strong><p>提出过 {tree.science.questions ?? 0} 个问题</p></section>
          </div>
        </>
      )}
    </section>
  );
}

export default function ChildGrowthTreePage() {
  return <ProtectedPage><ChildGrowthTreeContent /></ProtectedPage>;
}

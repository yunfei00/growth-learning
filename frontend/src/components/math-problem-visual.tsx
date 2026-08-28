import type { MathProblem } from "@/lib/api/client";

type Payload = MathProblem["render_payload"];
type Option = Payload["options"][number];

function Shape({ shape, label }: { shape: string; label?: string }) {
  const sizeClass = shape.includes("small") ? "size-small" : shape.includes("large") ? "size-large" : "";
  if (shape.includes("circle")) {
    return <svg aria-label={label ?? "圆形"} className={`math-svg-shape ${sizeClass}`} role="img" viewBox="0 0 100 100"><circle cx="50" cy="50" fill="currentColor" r="38" /></svg>;
  }
  if (shape.includes("triangle")) {
    return <svg aria-label={label ?? "三角形"} className={`math-svg-shape ${sizeClass}`} role="img" viewBox="0 0 100 100"><polygon fill="currentColor" points="50,10 92,88 8,88" /></svg>;
  }
  if (shape.includes("rectangle")) {
    return <svg aria-label={label ?? "长方形"} className="math-svg-shape" role="img" viewBox="0 0 120 100"><rect fill="currentColor" height="58" rx="7" width="100" x="10" y="21" /></svg>;
  }
  if (shape.includes("sphere")) {
    return <svg aria-label={label ?? "球体"} className="math-svg-shape" role="img" viewBox="0 0 100 100"><defs><radialGradient id="sphere"><stop offset="0" stopColor="#fff" /><stop offset="0.3" stopColor="currentColor" /></radialGradient></defs><circle cx="50" cy="50" fill="url(#sphere)" r="38" /></svg>;
  }
  if (shape.includes("cube")) {
    return <svg aria-label={label ?? "正方体"} className="math-svg-shape" role="img" viewBox="0 0 100 100"><path d="M22 32 50 16l28 16v36L50 84 22 68Z" fill="none" stroke="currentColor" strokeWidth="7" /><path d="m22 32 28 16 28-16M50 48v36" fill="none" stroke="currentColor" strokeWidth="6" /></svg>;
  }
  return <svg aria-label={label ?? "正方形"} className={`math-svg-shape ${sizeClass}`} role="img" viewBox="0 0 100 100"><rect fill="currentColor" height="72" rx="6" width="72" x="14" y="14" /></svg>;
}

function Dots({ count, representation = "dots", layout = "cluster" }: { count: number; representation?: string; layout?: string }) {
  if (representation === "ten_frame") {
    return <div aria-label={`十格框中有${count}个点`} className="math-ten-frame" role="img">{Array.from({ length: 10 }, (_, index) => <span className={index < count ? "filled" : ""} key={index} />)}</div>;
  }
  return <div aria-label={`${count}个${representation === "objects" ? "积木" : "圆点"}`} className={`math-dot-group representation-${representation} layout-${layout}`} role="img">{Array.from({ length: count }, (_, index) => <span key={index} />)}</div>;
}

export function MathOptionVisual({ option }: { option: Option }) {
  const shape = typeof option.shape === "string" ? option.shape : null;
  const token = typeof option.token === "object" && option.token ? option.token as Record<string, unknown> : null;
  if (shape) return <Shape label={option.label} shape={shape} />;
  if (token) return <Shape label={String(token.label)} shape={String(token.shape)} />;
  if (typeof option.count === "number") return <Dots count={option.count} />;
  return <strong>{option.label}</strong>;
}

export function MathProblemVisual({ payload }: { payload: Payload }) {
  const visual = payload.visual;
  const representation = payload.representation_type;
  if (typeof visual.count === "number") return <Dots count={visual.count} layout={String(visual.layout ?? "cluster")} representation={representation} />;
  if (visual.empty_meaning === true) return <div aria-label="一个也没有，用数字0表示" className="math-zero-meaning" role="img"><span>一个也没有</span><strong>0</strong></div>;
  if (typeof visual.numeral === "number") return <div className="math-big-numeral">{visual.numeral}</div>;
  if (payload.kind === "pattern_choice" && Array.isArray(visual.sequence)) return <div className="math-pattern-sequence">{visual.sequence.map((token, index) => { const value = token as Record<string, unknown>; return <Shape key={index} label={String(value.label)} shape={String(value.shape)} />; })}<span>?</span></div>;
  if (Array.isArray(visual.sequence)) return <div aria-label="数字序列" className="math-number-sequence">{visual.sequence.map((value, index) => <span className={value === null ? "missing" : ""} key={index}>{value === null ? "?" : String(value)}</span>)}</div>;
  if (typeof visual.left_count === "number" && typeof visual.right_count === "number") return <div className="math-compare-groups"><Dots count={visual.left_count} representation={representation} /><span>和</span><Dots count={visual.right_count} representation={representation} /></div>;
  if (Array.isArray(visual.groups)) return <div className="math-composition-groups">{visual.groups.map((count, index) => <Dots count={Number(count)} key={index} representation={representation} />)}</div>;
  if (typeof visual.first_count === "number") return <div className="math-operation-stage"><Dots count={visual.first_count} representation={representation} /><span>再来</span><Dots count={Number(visual.second_count)} representation={representation} />{typeof visual.story === "string" ? <p>{visual.story}</p> : null}{representation === "equation" ? <strong>{String(visual.equation)}</strong> : null}</div>;
  if (typeof visual.start_count === "number") return <div className="math-operation-stage"><Dots count={visual.start_count} representation={representation} /><span>拿走 {String(visual.removed_count)} 个</span>{typeof visual.story === "string" ? <p>{visual.story}</p> : null}{representation === "equation" ? <strong>{String(visual.equation)}</strong> : null}</div>;
  if (payload.kind === "shape_choice") return <div className="math-shape-prompt">仔细看看每个图形的边和角</div>;
  if (payload.kind === "spatial_choice") return <div aria-label="蓝色圆形和黄色正方形的位置图" className={`math-spatial-scene relation-${String(visual.relation)} answer-${String(visual.answer_object)}`} role="img"><span aria-label="蓝色圆形" className="object-a" /><span aria-label="黄色正方形" className="object-b" /><span className="scene-box" /></div>;
  if (payload.kind === "measurement_compare") return <div className={`math-measurement-scene kind-${String(visual.comparison)}`}><span style={{ "--math-value": Number(visual.left_value) } as CSSProperties} /><span style={{ "--math-value": Number(visual.right_value) } as CSSProperties} /></div>;
  if (payload.kind === "classification_choice") return <div className="math-shape-prompt"><Shape shape="circle" /><small>找一找相同或不同的图形</small></div>;
  return <div className="math-shape-prompt">看一看，再想一想</div>;
}
import type { CSSProperties } from "react";

import type { CSSProperties, ReactNode } from "react";

import type { MathProblem } from "@/lib/api/client";

type Payload = MathProblem["render_payload"];
type Option = Payload["options"][number];
type Token = {
  key: string;
  shape: string;
  color: string;
  size: string;
  label: string;
  value?: number;
};

type SelectableProps = {
  correctValue?: unknown;
  disabled?: boolean;
  onSelect?: (value: unknown) => void;
  revealCorrect?: boolean;
  selectedValue?: unknown;
};

const TOKEN_COLORS: Record<string, string> = {
  blue: "#397ca6",
  green: "#4f8d5f",
  orange: "#d3833e",
  purple: "#7866a9",
  red: "#c65b4d",
  teal: "#31877f",
  yellow: "#e1af43",
};

function sameAnswer(left: unknown, right: unknown): boolean {
  return JSON.stringify(left) === JSON.stringify(right);
}

export function mathAnswerStateClass(
  value: unknown,
  { correctValue, revealCorrect, selectedValue }: SelectableProps,
): string {
  if (!revealCorrect) return sameAnswer(value, selectedValue) ? "selected" : "";
  if (sameAnswer(value, correctValue)) return "correct-answer";
  if (sameAnswer(value, selectedValue)) return "incorrect-answer";
  return "";
}

function tokenFrom(value: unknown, fallbackLabel = "图形"): Token {
  const token = typeof value === "object" && value ? (value as Record<string, unknown>) : {};
  return {
    key: String(token.key ?? token.shape ?? fallbackLabel),
    shape: String(token.shape ?? "square"),
    color: String(token.color ?? "blue"),
    size: String(token.size ?? "medium"),
    label: String(token.label ?? fallbackLabel),
    value: typeof token.value === "number" ? token.value : undefined,
  };
}

export function MathVisualToken({ token: tokenValue }: { token: unknown }) {
  const token = tokenFrom(tokenValue);
  const style = { color: TOKEN_COLORS[token.color] ?? token.color } as CSSProperties;
  const className = `math-visual-token shape-${token.shape} size-${token.size}`;
  if (token.shape === "line" || token.shape === "bar") {
    return <span aria-label={token.label} className={className} role="img" style={{ ...style, "--math-token-value": token.value ?? 4 } as CSSProperties} />;
  }
  if (token.shape === "check") return <span aria-label={token.label} className={`${className} math-symbol-token`} role="img">✓</span>;
  if (token.shape === "not_equal") return <span aria-label={token.label} className={`${className} math-symbol-token`} role="img">≠</span>;
  if (token.shape === "circle" || token.shape === "sphere") {
    return <svg aria-label={token.label} className={className} role="img" style={style} viewBox="0 0 100 100">{token.shape === "sphere" ? <><defs><radialGradient id={`sphere-${token.key}`}><stop offset="0" stopColor="#fff" /><stop offset="0.35" stopColor="currentColor" /></radialGradient></defs><circle cx="50" cy="50" fill={`url(#sphere-${token.key})`} r="38" /></> : <circle cx="50" cy="50" fill="currentColor" r="38" />}</svg>;
  }
  if (token.shape === "triangle") return <svg aria-label={token.label} className={className} role="img" style={style} viewBox="0 0 100 100"><polygon fill="currentColor" points="50,10 92,88 8,88" /></svg>;
  if (token.shape === "rectangle") return <svg aria-label={token.label} className={className} role="img" style={style} viewBox="0 0 120 100"><rect fill="currentColor" height="58" rx="7" width="100" x="10" y="21" /></svg>;
  if (token.shape === "cube") return <svg aria-label={token.label} className={className} role="img" style={style} viewBox="0 0 100 100"><path d="M22 32 50 16l28 16v36L50 84 22 68Z" fill="none" stroke="currentColor" strokeWidth="7" /><path d="m22 32 28 16 28-16M50 48v36" fill="none" stroke="currentColor" strokeWidth="6" /></svg>;
  return <svg aria-label={token.label} className={className} role="img" style={style} viewBox="0 0 100 100"><rect fill="currentColor" height="72" rx="6" width="72" x="14" y="14" /></svg>;
}

function EmptyContainer() {
  return <div aria-label="空盘子，一个也没有" className="math-empty-container" role="img"><span>空盘子</span><strong>0</strong></div>;
}

function Dots({ count, representation = "dots", layout = "cluster" }: { count: number; representation?: string; layout?: string }) {
  if (count === 0) return <EmptyContainer />;
  if (representation === "ten_frame") return <div aria-label={`十格框中有${count}个点`} className="math-ten-frame" role="img">{Array.from({ length: 10 }, (_, index) => <span className={index < count ? "filled" : ""} key={index} />)}</div>;
  return <div aria-label={`${count}个${representation === "objects" ? "积木" : "圆点"}`} className={`math-dot-group representation-${representation} layout-${layout}`} role="img">{Array.from({ length: count }, (_, index) => <span key={index} />)}</div>;
}

export function MathOptionVisual({ option }: { option: Option }) {
  const token = typeof option.token === "object" && option.token ? option.token : null;
  if (token) return <MathVisualToken token={token} />;
  if (typeof option.count === "number") return <Dots count={option.count} />;
  return <strong>{option.label}</strong>;
}

function SelectableVisual({ ariaLabel, children, className, value, ...props }: SelectableProps & { ariaLabel: string; children: ReactNode; className: string; value: unknown }) {
  return <button aria-label={ariaLabel} aria-pressed={sameAnswer(value, props.selectedValue)} className={`${className} ${mathAnswerStateClass(value, props)}`} disabled={props.disabled} onClick={() => props.onSelect?.(value)} type="button">{children}</button>;
}

export function usesDirectVisualAnswers(payload: Payload): boolean {
  if (payload.kind === "spatial_choice" || payload.kind === "measurement_compare") return true;
  return payload.kind === "compare_groups" && !payload.options.some((option) => option.value === "equal");
}

export function MathProblemVisual({ payload, ...selectable }: { payload: Payload } & SelectableProps) {
  const visual = payload.visual;
  const representation = payload.representation_type;
  if (visual.empty_meaning === true) return <div aria-label="一个也没有，用数字0表示" className="math-zero-meaning" role="img"><EmptyContainer /><strong>0</strong></div>;
  if (typeof visual.count === "number") return <Dots count={visual.count} layout={String(visual.layout ?? "cluster")} representation={representation} />;
  if (typeof visual.numeral === "number") return <div className="math-big-numeral">{visual.numeral}</div>;
  if (payload.kind === "classification_choice" && visual.prompt_token) return <div aria-label="要配对的图形" className="math-classification-prompt"><MathVisualToken token={visual.prompt_token} /></div>;
  if (payload.kind === "pattern_choice" && Array.isArray(visual.sequence)) return <div className="math-pattern-sequence">{visual.sequence.map((token, index) => <MathVisualToken key={`${String((token as Record<string, unknown>).key)}-${index}`} token={token} />)}<span>?</span></div>;
  if (Array.isArray(visual.sequence)) return <div aria-label="数字序列" className="math-number-sequence">{visual.sequence.map((value, index) => <span className={value === null ? "missing" : ""} key={index}>{value === null ? "?" : String(value)}</span>)}</div>;
  if (typeof visual.left_count === "number" && typeof visual.right_count === "number") {
    const direct = usesDirectVisualAnswers(payload);
    return <div className={`math-compare-scene ${direct ? "is-selectable" : ""}`}>
      {direct ? <SelectableVisual ariaLabel={`左侧${visual.left_count}个`} className="math-compare-side side-left" value="left" {...selectable}><Dots count={visual.left_count} representation={representation} /></SelectableVisual> : <div className="math-compare-side side-left"><Dots count={visual.left_count} representation={representation} /></div>}
      <span aria-hidden="true" className="math-compare-divider" />
      {direct ? <SelectableVisual ariaLabel={`右侧${visual.right_count}个`} className="math-compare-side side-right" value="right" {...selectable}><Dots count={visual.right_count} representation={representation} /></SelectableVisual> : <div className="math-compare-side side-right"><Dots count={visual.right_count} representation={representation} /></div>}
    </div>;
  }
  if (Array.isArray(visual.groups)) return <div className="math-composition-groups">{visual.groups.map((count, index) => <Dots count={Number(count)} key={index} representation={representation} />)}</div>;
  if (typeof visual.first_count === "number") return <div className="math-operation-stage"><Dots count={visual.first_count} representation={representation} /><span>＋</span><Dots count={Number(visual.second_count)} representation={representation} />{typeof visual.story === "string" ? <p>{visual.story}</p> : null}{representation === "equation" ? <strong>{String(visual.equation)}</strong> : null}</div>;
  if (typeof visual.start_count === "number") return <div className="math-operation-stage"><Dots count={visual.start_count} representation={representation} /><span>拿走 {String(visual.removed_count)} 个</span>{typeof visual.story === "string" ? <p>{visual.story}</p> : null}{representation === "equation" ? <strong>{String(visual.equation)}</strong> : null}</div>;
  if (payload.kind === "spatial_choice" && Array.isArray(visual.objects)) return <div aria-label="空间位置场景" className={`math-spatial-scene relation-${String(visual.relation)} answer-${String(visual.answer_object)}`} role="group">{(visual.objects as unknown[]).map((tokenValue) => { const token = tokenFrom(tokenValue); return <SelectableVisual ariaLabel={token.label} className={`math-spatial-object object-${token.key}`} key={token.key} value={token.key} {...selectable}><MathVisualToken token={token} /></SelectableVisual>; })}<span aria-hidden="true" className="scene-box" /><span aria-hidden="true" className="spatial-divider" /></div>;
  if (payload.kind === "measurement_compare" && Array.isArray(visual.objects)) return <div className={`math-measurement-scene kind-${String(visual.comparison)}`}>{(visual.objects as unknown[]).map((tokenValue) => { const token = tokenFrom(tokenValue); return <SelectableVisual ariaLabel={token.label} className={`math-measurement-object object-${token.key}`} key={token.key} value={token.key} {...selectable}><MathVisualToken token={token} /></SelectableVisual>; })}</div>;
  if (payload.kind === "classification_choice" || payload.kind === "shape_choice") return <div aria-hidden="true" className="math-visual-cue">看一看</div>;
  return <div className="math-visual-cue">看一看，再想一想</div>;
}

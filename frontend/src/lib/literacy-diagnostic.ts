export type DiagnosticOutcome = "correct" | "uncertain" | "incorrect";

export type DiagnosticTargetLike = {
  outcome: DiagnosticOutcome | null;
};

export function nextDiagnosticTarget<T extends DiagnosticTargetLike>(targets: T[]): T | null {
  return targets.find((target) => target.outcome === null) ?? null;
}

export function diagnosticCounts(targets: DiagnosticTargetLike[]): {
  correct: number;
  uncertain: number;
  incorrect: number;
  completed: number;
} {
  const counts = { correct: 0, uncertain: 0, incorrect: 0, completed: 0 };
  for (const target of targets) {
    if (!target.outcome) continue;
    counts[target.outcome] += 1;
    counts.completed += 1;
  }
  return counts;
}

export function shouldOfferDiagnosticBreak(
  completed: number,
  total: number,
  segmentSize = 30,
): boolean {
  return completed > 0 && completed < total && completed % segmentSize === 0;
}

export function diagnosticSegmentNumber(
  completed: number,
  total: number,
  segmentSize = 30,
): number {
  const totalSegments = Math.max(1, Math.ceil(total / segmentSize));
  return Math.min(totalSegments, Math.max(1, Math.floor(completed / segmentSize) + 1));
}

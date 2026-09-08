export const MATH_DIRECT_PRAISES = [
  "太棒了！",
  "答对啦，真不错！",
  "你看得很仔细！",
  "做得真好！",
  "真厉害，你找到了！",
  "对啦，就是这样！",
  "很棒，你越来越熟练啦！",
  "太好了，继续加油！",
] as const;

export const MATH_HINTED_PRAISES = [
  "找到了，真棒！",
  "对啦，你又想明白了一步！",
  "很好，你没有放弃！",
  "提示一下你就会了，真不错！",
  "答对啦，继续试一试！",
  "太好了，你自己找到了答案！",
] as const;

const QUANTITY_RETRY_HINTS = [
  "没关系，再看一看。可以一个一个指着数。",
  "别着急，从第一个开始，一个一个数过去。",
  "试着用小手点着数，每一个只数一次。",
  "再数一遍，最后数到的数字就是一共有几个。",
] as const;

const GENERIC_RETRY_HINTS = [
  "没关系，再看一看，慢慢来。",
  "可以换一种方法再试一次。",
  "别着急，仔细看看题目里的线索。",
  "再想一想，你可以做到的。",
] as const;

function pick<T extends readonly string[]>(values: T, turn: number): T[number] {
  const safeTurn = Number.isFinite(turn) ? Math.max(0, Math.floor(turn)) : 0;
  return values[safeTurn % values.length];
}

export function mathPraise(hintUsed: boolean, turn: number): string {
  return hintUsed
    ? pick(MATH_HINTED_PRAISES, turn)
    : pick(MATH_DIRECT_PRAISES, turn);
}

export function mathRetryHint(domain: string, turn: number): string {
  return pick(domain === "quantity" ? QUANTITY_RETRY_HINTS : GENERIC_RETRY_HINTS, turn);
}

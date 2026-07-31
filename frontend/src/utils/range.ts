export const RANKS = '23456789TJQKA';

const DISPLAY_RANKS = [...RANKS].reverse();

export function generate13x13Matrix(): string[][] {
  return DISPLAY_RANKS.map((rowRank, rowIndex) =>
    DISPLAY_RANKS.map((columnRank, columnIndex) => {
      if (rowIndex === columnIndex) {
        return `${rowRank}${rowRank}`;
      }

      const highRank = rowIndex < columnIndex ? rowRank : columnRank;
      const lowRank = rowIndex < columnIndex ? columnRank : rowRank;
      return `${highRank}${lowRank}${rowIndex < columnIndex ? 's' : 'o'}`;
    }),
  );
}

function expandPlus(token: string): string[] {
  const base = token.slice(0, -1);
  const firstRankIndex = RANKS.indexOf(base[0]);
  const secondRankIndex = RANKS.indexOf(base[1]);

  if (firstRankIndex < 0 || secondRankIndex < 0) {
    return [];
  }

  if (base.length === 2 && firstRankIndex === secondRankIndex) {
    return RANKS.slice(firstRankIndex).split('').map((rank) => `${rank}${rank}`);
  }

  const suitedness = base[2];
  if ((suitedness !== 's' && suitedness !== 'o') || secondRankIndex >= firstRankIndex) {
    return [];
  }

  return RANKS.slice(secondRankIndex, firstRankIndex)
    .split('')
    .map((rank) => `${base[0]}${rank}${suitedness}`);
}

function expandDash(token: string): string[] {
  const [start, end, ...rest] = token.split('-');
  if (!start || !end || rest.length > 0) {
    return [];
  }

  const startFirst = RANKS.indexOf(start[0]);
  const startSecond = RANKS.indexOf(start[1]);
  const endFirst = RANKS.indexOf(end[0]);
  const endSecond = RANKS.indexOf(end[1]);

  if ([startFirst, startSecond, endFirst, endSecond].some((index) => index < 0)) {
    return [];
  }

  const isPairRange = start.length === 2 && end.length === 2
    && startFirst === startSecond && endFirst === endSecond;
  if (isPairRange) {
    const step = startFirst <= endFirst ? 1 : -1;
    const hands: string[] = [];
    for (let index = startFirst; ; index += step) {
      hands.push(`${RANKS[index]}${RANKS[index]}`);
      if (index === endFirst) break;
    }
    return hands;
  }

  const sameFirstRank = start[0] === end[0];
  const sameSuitedness = start[2] === end[2]
    && (start[2] === 's' || start[2] === 'o');
  if (!sameFirstRank || !sameSuitedness) {
    return [];
  }

  const step = startSecond <= endSecond ? 1 : -1;
  const hands: string[] = [];
  for (let index = startSecond; ; index += step) {
    if (index >= startFirst) return [];
    hands.push(`${start[0]}${RANKS[index]}${start[2]}`);
    if (index === endSecond) break;
  }
  return hands;
}

export function expandRangeStr(rangeStr?: string): Set<string> {
  if (!rangeStr?.trim()) {
    return new Set();
  }

  const expanded = new Set<string>();
  for (const rawToken of rangeStr.split(',')) {
    const token = rawToken.trim().replace(/\s+/g, '');
    if (!token) continue;

    const hands = token.endsWith('+')
      ? expandPlus(token)
      : token.includes('-')
        ? expandDash(token)
        : [token];
    hands.forEach((hand) => expanded.add(hand));
  }

  return expanded;
}

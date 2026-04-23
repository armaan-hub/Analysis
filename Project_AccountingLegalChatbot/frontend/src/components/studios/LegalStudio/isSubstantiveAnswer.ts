export interface SourceLike {
  filename?: string;
  source?: string;
}

const NON_ANSWER_PHRASES = [
  "i don't know",
  "i couldn't find",
  "no information available",
  "not found in",
  "i don't have",
  "cannot find",
  "no relevant",
];

export function isSubstantiveAnswer(content: string, sources: SourceLike[] | undefined): boolean {
  if (!content?.trim()) return false;
  if (!sources?.length) return false;
  const lower = content.toLowerCase();
  return !NON_ANSWER_PHRASES.some(p => lower.includes(p));
}

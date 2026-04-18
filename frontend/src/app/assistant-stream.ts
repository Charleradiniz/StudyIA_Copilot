const STREAM_INTERVAL_MS = 16;
const MIN_STREAM_UPDATES = 6;
const MAX_STREAM_UPDATES = 18;
const MIN_CHARS_PER_UPDATE = 24;
const IMMEDIATE_RENDER_THRESHOLD = 3600;

export type AssistantStreamPlan = {
  immediate: boolean;
  intervalMs: number;
  charsPerUpdate: number;
};

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

export function buildAssistantStreamPlan(
  fullText: string,
  options?: { prefersReducedMotion?: boolean },
): AssistantStreamPlan {
  const textLength = fullText.trim().length;
  const prefersReducedMotion = options?.prefersReducedMotion ?? false;

  if (textLength === 0 || prefersReducedMotion || textLength >= IMMEDIATE_RENDER_THRESHOLD) {
    return {
      immediate: true,
      intervalMs: 0,
      charsPerUpdate: textLength,
    };
  }

  const targetUpdates = clamp(
    Math.ceil(textLength / 180),
    MIN_STREAM_UPDATES,
    MAX_STREAM_UPDATES,
  );
  const charsPerUpdate = Math.max(
    MIN_CHARS_PER_UPDATE,
    Math.ceil(textLength / targetUpdates),
  );

  return {
    immediate: charsPerUpdate >= textLength,
    intervalMs: STREAM_INTERVAL_MS,
    charsPerUpdate,
  };
}

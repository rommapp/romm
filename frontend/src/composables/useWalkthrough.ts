import { useLocalStorage } from "@vueuse/core";
import { nextTick, ref, watch, computed, type Ref } from "vue";
import { FRONTEND_RESOURCES_PATH } from "@/utils";

// Types
export interface Walkthrough {
  id: number;
  url: string;
  title?: string | null;
  author?: string | null;
  source: string;
  format: "html" | "text" | "pdf";
  file_path?: string | null;
  content: string;
}

interface WalkthroughProgress {
  lines?: number;
  scroll?: number;
  percent?: number;
}

interface UseWalkthroughOptions {
  openPanels: Ref<number[]>;
}

// Constants
const CONFIG = {
  SCROLL_THRESHOLD: 200,
  LINE_CHUNK: 400,
  MAX_PROGRESS_PERCENT: 100,
  COMPLETION_THRESHOLD: 99,
} as const;

// Utility functions
/**
 * Splits walkthrough content into lines and caches the result
 */
function getWalkthroughLines(
  walkthrough: Walkthrough,
  cache: Map<number, string[]>,
): string[] {
  if (cache.has(walkthrough.id)) {
    return cache.get(walkthrough.id)!;
  }

  const lines = walkthrough.content ? walkthrough.content.split(/\r?\n/) : [];
  cache.set(walkthrough.id, lines);
  return lines;
}

/**
 * Calculates the number of lines to show based on current progress
 */
function calculateVisibleLineCount(
  walkthrough: Walkthrough,
  savedProgress: WalkthroughProgress | undefined,
  currentVisible: number | undefined,
  totalLines: number,
): number {
  const savedLines = savedProgress?.lines;
  const fallback = Math.min(totalLines, CONFIG.LINE_CHUNK);

  return currentVisible ?? savedLines ?? fallback;
}

/**
 * Builds PDF URL from walkthrough file path
 */
function buildPdfUrl(walkthrough: Walkthrough): string {
  return walkthrough.file_path
    ? `${FRONTEND_RESOURCES_PATH}/${walkthrough.file_path}`
    : "";
}

/**
 * Enhanced walkthrough composable with better organization and type safety
 */
export function useWalkthrough({ openPanels }: UseWalkthroughOptions) {
  // Reactive state
  const visibleLines = ref<Record<number, number>>({});

  // Non-reactive state
  const contentRefs = new Map<number, HTMLElement>();
  const lineCache = new Map<number, string[]>();

  // Persistent storage
  const storedProgress = useLocalStorage<Record<number, WalkthroughProgress>>(
    "walkthrough.progress",
    {},
  );

  // Computed values
  const progressData = computed(() => storedProgress.value);

  // Core functionality
  /**
   * Gets visible text lines for a walkthrough
   */
  function getVisibleText(walkthrough: Walkthrough): string[] {
    const lines = getWalkthroughLines(walkthrough, lineCache);
    const savedProgress = progressData.value[walkthrough.id];
    const currentVisible = visibleLines.value[walkthrough.id];

    const lineCount = calculateVisibleLineCount(
      walkthrough,
      savedProgress,
      currentVisible,
      lines.length,
    );

    visibleLines.value[walkthrough.id] = lineCount;
    return lines.slice(0, lineCount);
  }

  /**
   * Checks if more content can be shown
   */
  function canShowMore(walkthrough: Walkthrough): boolean {
    const totalLines = getWalkthroughLines(walkthrough, lineCache).length;
    const currentVisible =
      visibleLines.value[walkthrough.id] ?? CONFIG.LINE_CHUNK;

    return currentVisible < totalLines;
  }

  /**
   * Shows more content by incrementing visible lines
   */
  function showMore(walkthrough: Walkthrough): void {
    const totalLines = getWalkthroughLines(walkthrough, lineCache).length;
    const currentVisible =
      visibleLines.value[walkthrough.id] ?? CONFIG.LINE_CHUNK;
    const nextVisible = Math.min(
      currentVisible + CONFIG.LINE_CHUNK,
      totalLines,
    );

    visibleLines.value[walkthrough.id] = nextVisible;
  }

  /**
   * Shows all content at once
   */
  function showAll(walkthrough: Walkthrough): void {
    const totalLines = getWalkthroughLines(walkthrough, lineCache).length;
    visibleLines.value[walkthrough.id] = totalLines;
  }

  /**
   * Gets PDF URL for the walkthrough
   */
  function getPdfUrl(walkthrough: Walkthrough): string {
    return buildPdfUrl(walkthrough);
  }

  // Progress tracking
  /**
   * Calculates progress percentage for a walkthrough
   */
  function getProgressPercent(walkthrough: Walkthrough): number {
    if (walkthrough.format === "text") {
      const totalLines =
        getWalkthroughLines(walkthrough, lineCache).length || 1;
      const currentVisible = visibleLines.value[walkthrough.id] ?? 0;
      return Math.min(
        CONFIG.MAX_PROGRESS_PERCENT,
        Math.round((currentVisible / totalLines) * CONFIG.MAX_PROGRESS_PERCENT),
      );
    }

    // For HTML and PDF formats, use stored percentage
    return progressData.value[walkthrough.id]?.percent ?? 0;
  }

  /**
   * Gets formatted progress label
   */
  function getProgressLabel(walkthrough: Walkthrough): string {
    const percent = getProgressPercent(walkthrough);
    return percent >= CONFIG.COMPLETION_THRESHOLD
      ? "Completed"
      : `${percent}% read`;
  }

  /**
   * Updates stored progress for a walkthrough
   */
  function updateProgress(
    walkthroughId: number,
    updates: Partial<WalkthroughProgress>,
  ): void {
    storedProgress.value = {
      ...storedProgress.value,
      [walkthroughId]: {
        ...storedProgress.value[walkthroughId],
        ...updates,
      },
    };
  }

  // Event handlers
  /**
   * Handles scroll events for text walkthroughs
   */
  function handleScroll(walkthrough: Walkthrough, event: Event): void {
    const target = event.target as HTMLElement;
    if (!target) return;

    const { scrollHeight, scrollTop, clientHeight } = target;
    const distanceToBottom = scrollHeight - (scrollTop + clientHeight);

    // Load more content if near bottom
    if (
      distanceToBottom < CONFIG.SCROLL_THRESHOLD &&
      canShowMore(walkthrough)
    ) {
      showMore(walkthrough);
    }

    // Update progress
    updateProgress(walkthrough.id, {
      lines: visibleLines.value[walkthrough.id] ?? CONFIG.LINE_CHUNK,
      scroll: scrollTop,
      percent: getProgressPercent(walkthrough),
    });
  }

  /**
   * Stores HTML scroll progress
   */
  function storeHtmlProgress(walkthrough: Walkthrough, event: Event): void {
    const target = event.target as HTMLElement;
    if (!target) return;

    const { scrollHeight, scrollTop, clientHeight } = target;
    const percent = Math.min(
      CONFIG.MAX_PROGRESS_PERCENT,
      Math.round(
        ((scrollTop + clientHeight) / scrollHeight) *
          CONFIG.MAX_PROGRESS_PERCENT,
      ),
    );

    updateProgress(walkthrough.id, {
      percent,
      scroll: scrollTop,
    });
  }

  // Element reference management
  /**
   * Sets or removes content element reference
   */
  function setContentRef(id: number, element: HTMLElement | null): void {
    if (element) {
      contentRefs.set(id, element);
    } else {
      contentRefs.delete(id);
    }
  }

  // Watchers
  watch(
    () => openPanels.value.slice(),
    async (panelIds) => {
      await nextTick();

      panelIds.forEach((id) => {
        const savedProgress = progressData.value[id];
        const element = contentRefs.get(id);

        if (savedProgress?.scroll != null && element) {
          element.scrollTop = savedProgress.scroll;
        }
      });
    },
  );

  // Public API
  return {
    getVisibleText,
    canShowMore,
    showMore,
    showAll,
    getPdfUrl,
    getProgressLabel,
    handleScroll,
    storeHtmlProgress,
    setContentRef,
    openPanels,
  };
}

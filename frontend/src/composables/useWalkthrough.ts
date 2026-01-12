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
  openPanels?: Ref<number[]>;
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
 * Reformats text by preserving paragraph breaks but removing arbitrary line breaks
 */
function getWalkthroughLines(
  walkthrough: Walkthrough,
  cache: Map<number, string[]>,
): string[] {
  if (cache.has(walkthrough.id)) {
    return cache.get(walkthrough.id)!;
  }

  if (!walkthrough.content) {
    const emptyLines: string[] = [];
    cache.set(walkthrough.id, emptyLines);
    return emptyLines;
  }

  let lines: string[];

  if (walkthrough.format === "text") {
    // For text files, reformat to improve readability
    // Split into paragraphs (double line breaks)
    const paragraphs = walkthrough.content.split(/\r?\n\s*\r?\n/);

    lines = paragraphs
      .map((paragraph) => {
        // Within each paragraph, replace single line breaks with spaces
        // but preserve the paragraph structure
        return paragraph.replace(/\r?\n/g, " ").trim();
      })
      .filter((paragraph) => paragraph.length > 0); // Remove empty paragraphs
  } else {
    // For HTML and other formats, keep original line splitting
    lines = walkthrough.content.split(/\r?\n/);
  }

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
 * Enhanced walkthrough composable with better organization and type safety
 */
export function useWalkthrough({
  openPanels = ref<number[]>([]),
}: UseWalkthroughOptions) {
  const visibleLines = ref<Record<number, number>>({});
  const contentRefs = new Map<number, HTMLElement>();
  const lineCache = new Map<number, string[]>();
  const storedProgress = useLocalStorage<Record<number, WalkthroughProgress>>(
    "walkthrough.progress",
    {},
  );
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

  function getPdfUrl(walkthrough: Walkthrough): string {
    return walkthrough.file_path
      ? `${FRONTEND_RESOURCES_PATH}/${walkthrough.file_path}`
      : "";
  }

  // Progress tracking
  function getProgressPercent(walkthrough: Walkthrough): number {
    const storedProgress = progressData.value[walkthrough.id];
    if (storedProgress?.percent !== undefined) {
      return storedProgress.percent;
    }

    if (walkthrough.format === "text") {
      const totalLines =
        getWalkthroughLines(walkthrough, lineCache).length || 1;
      // Use stored lines progress or current visible lines, fallback to 0
      const savedLines = storedProgress?.lines ?? 0;
      const currentVisible = visibleLines.value[walkthrough.id] ?? savedLines;
      return Math.min(
        CONFIG.MAX_PROGRESS_PERCENT,
        Math.round((currentVisible / totalLines) * CONFIG.MAX_PROGRESS_PERCENT),
      );
    }

    // For HTML and PDF formats without stored data, return 0
    return 0;
  }

  const getProgressDisplay = (walkthrough: Walkthrough) => {
    const percent = getProgressPercent(walkthrough);

    return {
      text: percent >= CONFIG.COMPLETION_THRESHOLD ? "Completed" : percent,
      value: percent,
      color:
        percent === 0
          ? "grey"
          : percent < 50
            ? "orange"
            : percent < 100
              ? "blue"
              : "success",
    };
  };

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

  return {
    getVisibleText,
    getPdfUrl,
    getProgressDisplay,
    handleScroll,
    storeHtmlProgress,
    setContentRef,
    openPanels,
  };
}

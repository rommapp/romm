import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { effectScope, ref } from "vue";
import {
  popEscapable,
  pushEscapable,
  type EscapableEntry,
} from "@/lib/overlays/RDialog/escapeStack";
import { RESULT_ID_ATTR, useResultsTransition } from "./index";

const reduced = ref(false);
vi.mock("@/composables/useReducedMotion", () => ({
  useReducedMotion: () => ({ enabled: reduced }),
}));
vi.mock("@/composables/useViewTransition", async () => {
  const { ref: vueRef } = await import("vue");
  return { pendingMorphName: vueRef(null) };
});

interface FakeTransition {
  update: () => Promise<void>;
  finish: () => void;
}

let transitions: FakeTransition[] = [];

function stubViewTransitions() {
  const start = vi.fn((update: () => Promise<void>) => {
    let finish!: () => void;
    const finished = new Promise<void>((r) => {
      finish = r;
    });
    let rejectReady!: (reason: unknown) => void;
    const ready = new Promise<void>((_, reject) => {
      rejectReady = reject;
    });
    const done = update();
    transitions.push({ update, finish });
    return {
      finished,
      updateCallbackDone: done,
      ready,
      // As in the browser: skipping before the transition is ready rejects it.
      skipTransition: () => {
        rejectReady(new DOMException("Skipped", "AbortError"));
        finish();
      },
    };
  });
  Object.defineProperty(document, "startViewTransition", {
    value: start,
    configurable: true,
  });
  return start;
}

function card(id: number, top: number): HTMLElement {
  const el = document.createElement("div");
  el.setAttribute(RESULT_ID_ATTR, String(id));
  el.getBoundingClientRect = () => new DOMRect(0, top, 100, 100);
  return el;
}

function scroller(...cards: HTMLElement[]): HTMLElement {
  const root = document.createElement("div");
  root.getBoundingClientRect = () => new DOMRect(0, 0, 1280, 1000);
  root.append(...cards);
  document.body.append(root);
  return root;
}

describe("useResultsTransition", () => {
  beforeEach(() => {
    transitions = [];
    reduced.value = false;
    vi.stubGlobal("innerHeight", 1000);
  });

  afterEach(async () => {
    for (const t of transitions) t.finish();
    await new Promise((r) => setTimeout(r, 0));
    document.body.innerHTML = "";
    delete (document as { startViewTransition?: unknown }).startViewTransition;
    document.documentElement.className = "";
  });

  it("swaps directly without view transition support", async () => {
    const root = scroller(card(1, 200));
    const apply = vi.fn();
    const { run } = useResultsTransition({
      container: () => root,
      visibleTop: () => 100,
      visibleBottom: () => 1000,
      kind: () => "cards",
    });

    await run(apply);

    expect(apply).toHaveBeenCalledOnce();
  });

  it("swaps directly under reduced motion", async () => {
    const start = stubViewTransitions();
    reduced.value = true;
    const root = scroller(card(1, 200));
    const apply = vi.fn();
    const { run } = useResultsTransition({
      container: () => root,
      visibleTop: () => 100,
      visibleBottom: () => 1000,
      kind: () => "cards",
    });

    await run(apply);

    expect(apply).toHaveBeenCalledOnce();
    expect(start).not.toHaveBeenCalled();
  });

  it("names visible cards in both states and only kept ones after", async () => {
    stubViewTransitions();
    const kept = card(1, 200);
    const dropped = card(2, 400);
    const hidden = card(3, 50);
    const root = scroller(kept, dropped, hidden);
    const names: string[] = [];
    const { run } = useResultsTransition({
      container: () => root,
      visibleTop: () => 100,
      visibleBottom: () => 1000,
      kind: () => "cards",
    });

    await run(() => {
      names.push(
        kept.style.viewTransitionName,
        dropped.style.viewTransitionName,
      );
      dropped.remove();
      root.append(card(4, 600));
    });

    // Cleared before the swap so the old elements don't keep stale names.
    expect(names).toEqual(["", ""]);
    expect(kept.style.viewTransitionName).toBe("r-result-1");
    expect(hidden.style.viewTransitionName).toBe("");
    expect(
      root.querySelector<HTMLElement>(`[${RESULT_ID_ATTR}="4"]`)!.style
        .viewTransitionName,
    ).toBe("");
    expect(document.documentElement.classList).toContain("r-results-vt");
  });

  it("names arriving rows and delays them past the leaving ones", async () => {
    stubViewTransitions();
    const root = scroller(card(1, 200));
    const { run } = useResultsTransition({
      container: () => root,
      visibleTop: () => 100,
      visibleBottom: () => 1000,
      kind: () => "rows",
    });

    await run(() => {
      root.append(card(4, 400));
      root.append(card(5, 600));
    });

    expect(
      root.querySelector<HTMLElement>(`[${RESULT_ID_ATTR}="4"]`)!.style
        .viewTransitionName,
    ).toBe("r-result-4");
    expect(document.documentElement.classList).toContain("r-results-vt--rows");
    const css = document.head.textContent ?? "";
    expect(css).toContain(
      "html.r-results-vt::view-transition-new(r-result-4):only-child{animation-delay:100ms}",
    );
    expect(css).toContain(
      "view-transition-new(r-result-5):only-child{animation-delay:128ms}",
    );
  });

  it("leaves arriving cards unnamed so their mount fade plays", async () => {
    stubViewTransitions();
    const root = scroller(card(1, 200));
    const { run } = useResultsTransition({
      container: () => root,
      visibleTop: () => 100,
      visibleBottom: () => 1000,
      kind: () => "cards",
    });

    await run(() => root.append(card(4, 400)));

    expect(
      root.querySelector<HTMLElement>(`[${RESULT_ID_ATTR}="4"]`)!.style
        .viewTransitionName,
    ).toBe("");
    expect(document.documentElement.classList).not.toContain(
      "r-results-vt--rows",
    );
  });

  it("keeps a newer swap's names when an older one finishes late", async () => {
    stubViewTransitions();
    const kept = card(1, 200);
    const root = scroller(kept);
    const { run } = useResultsTransition({
      container: () => root,
      visibleTop: () => 100,
      visibleBottom: () => 1000,
      kind: () => "rows",
    });

    await run(() => {});
    await run(() => {});
    transitions[0]!.finish();
    await new Promise((r) => setTimeout(r, 0));

    expect(kept.style.viewTransitionName).toBe("r-result-1");
    expect(document.documentElement.classList).toContain("r-results-vt");
    expect(document.documentElement.classList).toContain("r-results-vt--rows");
  });

  it("skips the animation when the swap changed nothing", async () => {
    stubViewTransitions();
    const kept = card(1, 200);
    const root = scroller(kept);
    const { run } = useResultsTransition({
      container: () => root,
      visibleTop: () => 100,
      visibleBottom: () => 1000,
      kind: () => "cards",
    });

    await run(() => false);

    expect(kept.style.viewTransitionName).toBe("");
    expect(document.documentElement.classList).not.toContain("r-results-vt");
  });

  it("leaves cards under the bottom chrome unnamed", async () => {
    stubViewTransitions();
    const above = card(1, 200);
    const underNav = card(2, 850);
    const root = scroller(above, underNav);
    const { run } = useResultsTransition({
      container: () => root,
      visibleTop: () => 100,
      visibleBottom: () => 900,
      kind: () => "cards",
    });

    await run(() => {});

    expect(above.style.viewTransitionName).toBe("r-result-1");
    expect(underNav.style.viewTransitionName).toBe("");
  });

  describe("with an overlay", () => {
    const overlay: EscapableEntry = { close: () => {}, persistent: false };
    afterEach(() => popEscapable(overlay));

    it("swaps directly while one is open", async () => {
      const start = stubViewTransitions();
      const root = scroller(card(1, 200));
      const apply = vi.fn();
      const { run } = useResultsTransition({
        container: () => root,
        visibleTop: () => 100,
        visibleBottom: () => 1000,
        kind: () => "cards",
      });
      pushEscapable(overlay);

      await run(apply);

      expect(apply).toHaveBeenCalledOnce();
      expect(start).not.toHaveBeenCalled();
    });

    it("ends a running animation when one opens", async () => {
      stubViewTransitions();
      const kept = card(1, 200);
      const root = scroller(kept);
      const scope = effectScope();
      const { run } = scope.run(() =>
        useResultsTransition({
          container: () => root,
          visibleTop: () => 100,
          visibleBottom: () => 1000,
          kind: () => "cards",
        }),
      )!;
      await run(() => {});
      expect(kept.style.viewTransitionName).toBe("r-result-1");

      pushEscapable(overlay);

      expect(kept.style.viewTransitionName).toBe("");
      expect(document.documentElement.classList).not.toContain("r-results-vt");
      scope.stop();
    });
  });

  it("clears every name and the root class once finished", async () => {
    stubViewTransitions();
    const kept = card(1, 200);
    const root = scroller(kept);
    const { run } = useResultsTransition({
      container: () => root,
      visibleTop: () => 100,
      visibleBottom: () => 1000,
      kind: () => "rows",
    });

    await run(() => root.append(card(4, 400)));
    transitions[0]!.finish();
    await new Promise((r) => setTimeout(r, 0));

    expect(kept.style.viewTransitionName).toBe("");
    expect(document.documentElement.classList).not.toContain("r-results-vt");
    expect(document.documentElement.classList).not.toContain(
      "r-results-vt--rows",
    );
    expect(document.head.textContent).not.toContain("view-transition-new");
  });
});

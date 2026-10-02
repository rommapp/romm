import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { effectScope, nextTick, ref } from "vue";
import { useDebouncedSearch } from "./index";

describe("useDebouncedSearch", () => {
  let scope: ReturnType<typeof effectScope>;

  beforeEach(() => {
    vi.useFakeTimers();
    scope = effectScope();
  });

  afterEach(() => {
    scope.stop();
    vi.useRealTimers();
  });

  function setup(initial: string | null) {
    const term = ref<string | null>(initial);
    const search = scope.run(() => useDebouncedSearch(term))!;
    return { term, ...search };
  }

  it("writes the trimmed term once typing settles", () => {
    const { term, input, setSearch } = setup(null);

    setSearch("mar");
    setSearch(" mario ");
    expect(input.value).toBe(" mario ");
    expect(term.value).toBeNull();

    vi.advanceTimersByTime(300);
    expect(term.value).toBe("mario");
  });

  it("clears the term when the box is emptied", () => {
    const { term, setSearch } = setup("mario");

    setSearch("  ");
    vi.advanceTimersByTime(300);
    expect(term.value).toBeNull();
  });

  it("shows a term set by navigation in the box", async () => {
    const { term, input } = setup("mario");

    term.value = "zelda";
    await nextTick();
    expect(input.value).toBe("zelda");

    term.value = null;
    await nextTick();
    expect(input.value).toBe("");
  });

  it("drops a pending keystroke when navigation sets the term first", async () => {
    const { term, input, setSearch } = setup(null);

    setSearch("mario");
    term.value = "zelda";
    await nextTick();
    vi.advanceTimersByTime(300);

    expect(term.value).toBe("zelda");
    expect(input.value).toBe("zelda");
  });

  it("commits straight away on flush, dropping the pending keystroke", () => {
    const { term, setSearch, flush } = setup(null);

    setSearch(" mario ");
    expect(flush()).toBe(true);
    expect(term.value).toBe("mario");

    term.value = "zelda";
    vi.advanceTimersByTime(300);
    expect(term.value).toBe("zelda");
  });

  it("reports an unchanged term on flush", () => {
    const { setSearch, flush } = setup("mario");

    setSearch("mario ");
    expect(flush()).toBe(false);
  });

  it("keeps what the user typed when the term it settled on echoes back", async () => {
    const { term, input, setSearch } = setup(null);

    setSearch("mario ");
    vi.advanceTimersByTime(300);
    await nextTick();

    expect(term.value).toBe("mario");
    expect(input.value).toBe("mario ");
  });
});

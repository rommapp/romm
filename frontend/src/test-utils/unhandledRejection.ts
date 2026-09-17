import { expect, vi } from "vitest";

// Any listener masks the unhandled signal, so this only observes, and only for
// the duration of `run`.
export async function expectNoUnhandledRejection(run: () => Promise<void>) {
  const unhandled = vi.fn();
  process.on("unhandledRejection", unhandled);
  try {
    await run();
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(unhandled).not.toHaveBeenCalled();
  } finally {
    process.off("unhandledRejection", unhandled);
  }
}

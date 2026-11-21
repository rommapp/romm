import type { ConsoleCreatePayload } from "@/__generated__";

export type ConsoleKind = ConsoleCreatePayload["console"];

/** The i18n key of each console's name, keyed by the client it registers as. */
export const CONSOLE_TITLES: Record<ConsoleKind, string> = {
  ps3: "settings.console-ps3",
  ps4: "settings.console-ps4",
};

/** The console a device client names, or null when it names none. */
export function consoleKindOf(
  client: string | null | undefined,
): ConsoleKind | null {
  return client && Object.hasOwn(CONSOLE_TITLES, client)
    ? (client as ConsoleKind)
    : null;
}

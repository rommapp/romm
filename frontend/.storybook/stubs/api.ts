// Storybook-only: every `@/services/api` import resolves here so stories
// never construct axios or touch the backend.
import {
  AUTOSAVE_SLOT,
  SAVE_SLOT_MAX_LENGTH,
  UNLOAD_SAVE_MAX_BYTES,
} from "@/services/saveSlot";

export { AUTOSAVE_SLOT, SAVE_SLOT_MAX_LENGTH, UNLOAD_SAVE_MAX_BYTES };

const empty = { data: {} as Record<string, never> };

function deadCall(): Promise<{ data: Record<string, never> }> {
  return Promise.resolve(empty);
}

function noopUse(): number {
  return 0;
}

const interceptors = {
  request: { use: noopUse, eject() {} },
  response: { use: noopUse, eject() {} },
};

const client = new Proxy(
  { interceptors, defaults: { adapter: undefined } },
  {
    get(target, prop) {
      if (prop in target) return target[prop as keyof typeof target];
      if (prop === "then") return undefined;
      return deadCall;
    },
  },
);

export default client;
export const saveApi = client;
export const romApi = client;

export function refetchCSRFToken(): Promise<{ data: Record<string, never> }> {
  return deadCall();
}

export function keepaliveHeaders(): Record<string, string> {
  return {};
}

export function isCsrfFailure(_error?: unknown): boolean {
  return false;
}

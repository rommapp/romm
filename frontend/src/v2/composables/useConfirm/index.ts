// useConfirm — open the global ConfirmDialog and await the user's choice.
//
//   const confirm = useConfirm();
//   const ok = await confirm({
//     title: "Delete library?",
//     body: "This removes 5 platforms and 1820 ROMs.",
//     confirmText: "Delete library",
//     tone: "danger",
//     requireTyped: "DELETE",
//   });
//   if (!ok) return;
//
// The composable internally emits `showConfirm` and listens for the matching
// `confirmResolved` event scoped by id. Always resolves — never rejects —
// so consumers can `if (!ok) return;` without try/catch noise.
import type { Emitter } from "mitt";
import { inject } from "vue";
import type { Events } from "@/types/emitter";

export interface ConfirmOptions {
  title: string;
  body?: string;
  confirmText?: string;
  cancelText?: string;
  tone?: "warning" | "danger";
  /** When set, the confirm button stays disabled until the user types this
   *  exact value into the input. Use for filesystem-affecting actions. */
  requireTyped?: string;
}

let nextId = 1;

export function useConfirm() {
  const emitter = inject<Emitter<Events>>("emitter");

  return function confirm(opts: ConfirmOptions): Promise<boolean> {
    return new Promise<boolean>((resolve) => {
      if (!emitter) {
        resolve(false);
        return;
      }
      const id = nextId++;
      const handler = (payload: { id: number; confirmed: boolean }) => {
        if (payload.id !== id) return;
        emitter.off("confirmResolved", handler);
        resolve(payload.confirmed);
      };
      emitter.on("confirmResolved", handler);
      emitter.emit("showConfirm", { id, ...opts });
    });
  };
}

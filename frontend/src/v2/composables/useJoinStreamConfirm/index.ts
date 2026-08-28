// Shared join-confirm flow for a multiplayer streaming session: the game
// details page (an existing session on the ROM being viewed, via
// useGameActions) and the Home page's live-sessions row (LiveSessionCard)
// both route through this so the dialog copy and the post-confirm
// navigation stay in one place.
import { useI18n } from "vue-i18n";
import { useRouter } from "vue-router";
import { useConfirm } from "@/v2/composables/useConfirm";

export interface JoinStreamTarget {
  romId: number;
  romName: string;
  hostUsername: string | null;
}

export function useJoinStreamConfirm() {
  const { t } = useI18n();
  const router = useRouter();
  const confirm = useConfirm();

  async function joinStream(target: JoinStreamTarget): Promise<void> {
    const ok = await confirm({
      title: target.hostUsername
        ? t("rom.confirm-join-title-of", { user: target.hostUsername })
        : t("rom.confirm-join-title"),
      body: t("rom.confirm-join-body", { name: target.romName }),
      confirmText: t("rom.join-session"),
    });
    if (!ok) return;
    void router.push(`/rom/${target.romId}/stream?join=1`);
  }

  return { joinStream };
}

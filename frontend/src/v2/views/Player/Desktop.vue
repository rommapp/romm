<script setup lang="ts">
// Desktop: admin view onto a streaming container's desktop with no game
// running. This is where an operator configures the emulator inside the
// container that will run it (BIOS, controllers, paths), which persists
// because the container's config directory is a bind mount.
//
// It claims the same container key under the same lock as a game session,
// so opening a desktop blocks players and a running game blocks the admin.
// Nothing here belongs to a ROM: no cover art, no save states, no resume.
import { RAlert, RBtn, RSpinner } from "@v2/lib";
import { useEventListener, useIntervalFn } from "@vueuse/core";
import { isAxiosError } from "axios";
import { computed, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import { onBeforeRouteLeave, useRoute, useRouter } from "vue-router";
import { ROUTES } from "@/plugins/router";
import streamingApi from "@/services/api/streaming";
import { type SessionTermination, useStreamingStore } from "@/stores/streaming";
import StreamStage from "@/v2/components/Player/StreamStage.vue";
import { useConfirm } from "@/v2/composables/useConfirm";
import { usePageTitle } from "@/v2/composables/usePageTitle";
import { useSocketEvent } from "@/v2/composables/useSocketEvent";

const { t } = useI18n();
const route = useRoute();
const router = useRouter();
const confirm = useConfirm();
const streamingStore = useStreamingStore();

const containerKey = computed(() => String(route.query.container ?? ""));

const stage = ref<InstanceType<typeof StreamStage> | null>(null);
const state = ref<"loading" | "running" | "error" | "exited">("loading");
const errorMessage = ref("");
const endedReason = ref("");
const containerHost = ref("");
const label = ref("");
// The platform the backend filed the session under, which the release route
// keys on. Whatever it reports, not something this view can derive.
const platform = ref("");
const isExiting = ref(false);
// Whether the container is still claimed. Tracked apart from `state`, which
// describes the view: a release that failed leaves an "error" screen over a
// claim that is very much still standing.
const holdsClaim = ref(false);
// The stamp the claim answered with, which every release and heartbeat sends
// back so a claim that replaced this one is never the one they reach.
const claimedAt = ref("");

usePageTitle(() => t("play.desktop-title"));

async function openDesktop(): Promise<void> {
  if (!containerKey.value) {
    state.value = "error";
    errorMessage.value = t("play.desktop-error-no-container");
    return;
  }
  try {
    const { data } = await streamingApi.claimDesktop(containerKey.value);
    containerHost.value = data.host;
    label.value = data.label;
    platform.value = data.platform;
    claimedAt.value = data.claimed_at;
    holdsClaim.value = true;
    state.value = "running";
  } catch (err: unknown) {
    state.value = "error";
    const status = isAxiosError(err) ? err.response?.status : undefined;
    const detail: unknown = isAxiosError(err)
      ? err.response?.data?.detail
      : undefined;
    if (status === 409) {
      const busy = detail as {
        draining?: boolean;
        rom_name?: string | null;
      } | null;
      // A drain marker is nobody's claim: the container comes free on its own
      // once the previous session has finished saving.
      if (busy?.draining)
        errorMessage.value = t("play.stream-occupied-draining");
      else if (busy?.rom_name)
        errorMessage.value = t("play.desktop-error-occupied-by", {
          rom: busy.rom_name,
        });
      else errorMessage.value = t("play.desktop-error-occupied");
    } else if (status === 404)
      errorMessage.value = t("play.desktop-error-no-container");
    else errorMessage.value = t("play.desktop-error-server");
  }
}

// Releasing names the container explicitly: the platform alone is ambiguous
// once a pool serves it.
// Returns whether the container is actually free: a release that failed leaves
// the claim standing, and saying "exited" over it hides a container nobody can
// take until it times out.
async function release(): Promise<boolean> {
  if (!holdsClaim.value) return true;
  try {
    await streamingApi.releaseSession(
      platform.value,
      undefined,
      containerKey.value,
      undefined,
      claimedAt.value,
    );
    holdsClaim.value = false;
    state.value = "exited";
    return true;
  } catch (err) {
    console.warn("[streaming] Could not release the desktop session:", err);
    state.value = "error";
    errorMessage.value = t("play.desktop-error-release");
    return false;
  }
}

// The backend counts a session whose liveness stamp goes stale as abandoned
// and lets the next claimant tear the container down, so a desktop has to beat
// like the player does: configuring an emulator takes far longer than the
// stale window, and nothing else here touches the claim.
const HEARTBEAT_MS = 30_000;

// Dropping the claim keeps a later exit from releasing the next holder, and the
// notice is the only sign the desktop was taken away rather than broken.
function noteSessionEnded(notice?: SessionTermination | null): void {
  holdsClaim.value = false;
  state.value = "error";
  errorMessage.value = notice?.ended_by
    ? t("play.session-ended-by", { user: notice.ended_by })
    : t("play.session-ended");
  endedReason.value = notice?.reason ?? "";
}

useIntervalFn(async () => {
  if (!holdsClaim.value) return;
  const status = await streamingStore.heartbeatSession(
    platform.value,
    containerKey.value,
    claimedAt.value,
  );
  if (status?.status !== "ended") return;
  noteSessionEnded(status.termination);
}, HEARTBEAT_MS);

// Pushed when someone else ends this claim, sooner than the next heartbeat.
// The user's room carries all their claims, so only this container's is ours.
useSocketEvent<SessionTermination>("streaming:session-ended", (notice) => {
  if (!holdsClaim.value || notice.container !== containerKey.value) return;
  noteSessionEnded(notice);
});

function backToAdministration(): void {
  router.push({ name: ROUTES.ADMINISTRATION, query: { tab: "streaming" } });
}

// Returns whether the session is done with and the view may be left. The
// confirmation is awaited, so the flag keeps a second press (or a back nav
// arriving mid-dialog) from stacking a second dialog behind the first.
async function confirmAndRelease(): Promise<boolean> {
  if (isExiting.value) return false;
  isExiting.value = true;
  try {
    await stage.value?.leaveFullscreen();
    const ok = await confirm({
      title: t("play.desktop-exit-title"),
      body: t("play.desktop-exit-body"),
      confirmText: t("play.desktop-exit-confirm"),
    });
    if (!ok) {
      stage.value?.focusStream();
      return false;
    }
    return await release();
  } finally {
    isExiting.value = false;
  }
}

async function handleExit(): Promise<void> {
  if (await confirmAndRelease()) backToAdministration();
}

// Every way out of a live session funnels through the same confirmation, so
// a stray back press cannot drop the container mid-configuration.
onBeforeRouteLeave(async () => {
  if (!holdsClaim.value) return true;
  return confirmAndRelease();
});

// The tab closing takes the session's only owner with it, so hand the claim
// back on a path that survives the page going away.
function onPageHide(): void {
  // The claim, not the view state, says whether the container is still held:
  // an exit whose release failed shows an error and still holds it.
  if (!holdsClaim.value) return;
  holdsClaim.value = false;
  state.value = "exited";
  streamingApi.releaseSessionKeepalive(
    platform.value,
    containerKey.value,
    claimedAt.value,
  );
}

useEventListener(window, "pagehide", onPageHide);

onMounted(() => {
  void openDesktop();
});
</script>

<template>
  <section class="r-v2-desktop">
    <RAlert
      v-if="state === 'error'"
      type="error"
      variant="translucent"
      class="r-v2-desktop__error"
    >
      {{ errorMessage }}
      <div v-if="endedReason" class="r-v2-desktop__ended-reason">
        <span class="r-v2-desktop__ended-reason-label">
          {{ t("play.session-ended-reason-label") }}
        </span>
        <span>{{ endedReason }}</span>
      </div>
      <template #append>
        <RBtn variant="text" @click="backToAdministration">
          {{ t("play.desktop-back") }}
        </RBtn>
      </template>
    </RAlert>

    <RSpinner
      v-else-if="state === 'loading'"
      class="r-v2-desktop__spinner"
      :size="40"
      :aria-label="t('common.loading')"
    />

    <StreamStage
      v-else
      ref="stage"
      :src="containerHost"
      :frame-title="t('play.desktop-frame-title')"
      :active="state === 'running'"
    >
      <template #bar="{ isFullscreen, toggleFullscreen }">
        <span class="r-v2-desktop__bar-title">{{ label }}</span>
        <span class="r-v2-desktop__bar-subtitle">
          {{ t("play.desktop-subtitle") }}
        </span>

        <span class="r-v2-desktop__bar-spacer" />

        <RBtn
          :icon="isFullscreen ? 'mdi-fullscreen-exit' : 'mdi-fullscreen'"
          variant="text"
          density="compact"
          :tooltip="
            isFullscreen
              ? t('play.stream-exit-fullscreen')
              : t('play.stream-fullscreen')
          "
          @click="toggleFullscreen"
        />
        <RBtn
          icon="mdi-stop"
          variant="text"
          density="compact"
          color="error"
          :tooltip="t('play.desktop-exit')"
          @click="handleExit"
        />
      </template>
    </StreamStage>
  </section>
</template>

<style scoped>
.r-v2-desktop {
  min-height: 100%;
}

.r-v2-desktop__error {
  margin: 24px auto;
  max-width: 560px;
}

.r-v2-desktop__ended-reason {
  display: flex;
  flex-direction: column;
  gap: 3px;
  margin-top: 8px;
  overflow-wrap: anywhere;
}

.r-v2-desktop__ended-reason-label {
  font-size: var(--r-font-size-xs);
  font-weight: var(--r-font-weight-bold);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.r-v2-desktop__spinner {
  display: block;
  margin: 64px auto;
}

.r-v2-desktop__bar-title {
  font-size: var(--r-font-size-sm);
  font-weight: var(--r-font-weight-semibold);
}
.r-v2-desktop__bar-subtitle {
  font-size: var(--r-font-size-xs);
  color: var(--r-color-fg-muted);
}
.r-v2-desktop__bar-spacer {
  flex: 1;
}
</style>

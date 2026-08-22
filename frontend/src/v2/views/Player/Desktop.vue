<script setup lang="ts">
// Desktop: admin view onto a streaming container's desktop with no game
// running. This is where an operator configures the emulator inside the
// container that will run it (BIOS, controllers, paths), which persists
// because the container's config directory is a bind mount.
//
// It claims the same container key under the same lock as a game session,
// so opening a desktop blocks players and a running game blocks the admin.
// Nothing here belongs to a ROM: no cover art, no save states, no resume.
import { RAlert, RBtn } from "@v2/lib";
import { isAxiosError } from "axios";
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import { onBeforeRouteLeave, useRoute, useRouter } from "vue-router";
import { ROUTES } from "@/plugins/router";
import streamingApi from "@/services/api/streaming";
import StreamStage from "@/v2/components/Player/StreamStage.vue";
import { useConfirm } from "@/v2/composables/useConfirm";
import { usePageTitle } from "@/v2/composables/usePageTitle";

const { t } = useI18n();
const route = useRoute();
const router = useRouter();
const confirm = useConfirm();

const containerKey = computed(() => String(route.query.container ?? ""));

const stage = ref<InstanceType<typeof StreamStage> | null>(null);
const state = ref<"loading" | "running" | "error" | "exited">("loading");
const errorMessage = ref("");
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
    holdsClaim.value = true;
    state.value = "running";
  } catch (err: unknown) {
    state.value = "error";
    const status = isAxiosError(err) ? err.response?.status : undefined;
    if (status === 409) errorMessage.value = t("play.desktop-error-occupied");
    else if (status === 404)
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
  streamingApi.releaseSessionKeepalive(platform.value, containerKey.value);
}

onMounted(() => {
  window.addEventListener("pagehide", onPageHide);
  void openDesktop();
});

onBeforeUnmount(() => {
  window.removeEventListener("pagehide", onPageHide);
});
</script>

<template>
  <section class="r-v2-desktop">
    <RAlert
      v-if="state === 'error'"
      type="error"
      variant="translucent"
      class="r-v2-desktop__error"
      :text="errorMessage"
    >
      <template #append>
        <RBtn variant="text" @click="backToAdministration">
          {{ t("play.desktop-back") }}
        </RBtn>
      </template>
    </RAlert>

    <div
      v-else-if="state === 'loading'"
      class="r-v2-desktop__spinner"
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

.r-v2-desktop__spinner {
  width: 40px;
  height: 40px;
  margin: 64px auto;
  border-radius: 50%;
  border: 2px solid var(--r-color-surface-hover);
  border-top-color: var(--r-color-brand-primary);
  animation: r-v2-desktop-spin 0.8s linear infinite;
}

@keyframes r-v2-desktop-spin {
  to {
    transform: rotate(360deg);
  }
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

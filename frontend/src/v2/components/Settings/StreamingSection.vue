<script setup lang="ts">
// StreamingSection, the operator's view of the streaming fleet, one row
// per configured container. A container serves many platforms but hosts a
// single session, so the container is the unit that matters here, which is
// what `GET /streaming/containers` reports.
//
// Each row shows what the container is running and offers the two actions
// an admin needs: open its desktop to configure the emulator inside it, and
// end whatever session is holding it.
import { RBtn, REmptyState, RIcon, RSpinner } from "@v2/lib";
import { computed, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useRouter } from "vue-router";
import { ROUTES } from "@/plugins/router";
import streamingApi, {
  type AdminStreamingContainer,
} from "@/services/api/streaming";
import { formatTimestamp } from "@/utils";
import SettingsSection from "@/v2/components/Settings/SettingsSection.vue";
import { useConfirm } from "@/v2/composables/useConfirm";
import { useSnackbar } from "@/v2/composables/useSnackbar";

defineOptions({ inheritAttrs: false });

const { t, locale } = useI18n();
const router = useRouter();
const confirm = useConfirm();
const snackbar = useSnackbar();

const loading = ref(true);
const enabled = ref(false);
// A failed listing is not a configuration answer: without this the panel
// reports streaming as disabled over what was a 403 or a server error.
const loadFailed = ref(false);
const containers = ref<AdminStreamingContainer[]>([]);
const releasing = ref<string | null>(null);

const emptyState = computed<{ icon: string; title: string } | null>(() => {
  if (loadFailed.value) {
    return {
      icon: "mdi-alert-circle-outline",
      title: t("settings.streaming-load-failed"),
    };
  }
  if (!enabled.value) {
    return { icon: "mdi-monitor-off", title: t("settings.streaming-disabled") };
  }
  if (containers.value.length === 0) {
    return {
      icon: "mdi-monitor-dashboard",
      title: t("settings.streaming-none"),
    };
  }
  return null;
});

async function load(): Promise<void> {
  loading.value = true;
  loadFailed.value = false;
  try {
    const { data } = await streamingApi.adminListContainers();
    enabled.value = data.enabled;
    containers.value = data.containers;
  } catch (err) {
    console.warn("[streaming] Could not load containers:", err);
    loadFailed.value = true;
    snackbar.error(t("settings.streaming-load-failed"));
  } finally {
    loading.value = false;
  }
}

function openDesktop(container: AdminStreamingContainer): void {
  router.push({
    name: ROUTES.STREAM_DESKTOP,
    query: { container: container.container },
  });
}

async function release(container: AdminStreamingContainer): Promise<void> {
  const session = container.session;
  if (!session) return;
  const ok = await confirm({
    title: t("settings.streaming-release-title"),
    body: t("settings.streaming-release-body", {
      container: container.label ?? container.container,
    }),
    confirmText: t("settings.streaming-release-confirm"),
    tone: "danger",
  });
  if (!ok) return;

  releasing.value = container.container;
  try {
    // A reason is what marks this as an admin force-release, which the
    // displaced player is shown when their session disappears.
    await streamingApi.releaseSession(
      session.platform ?? "",
      t("settings.streaming-release-reason"),
      container.container,
    );
    snackbar.success(t("settings.streaming-released"));
    await load();
  } catch (err) {
    console.warn("[streaming] Could not release session:", err);
    snackbar.error(t("settings.streaming-release-failed"));
  } finally {
    releasing.value = null;
  }
}

function sessionState(container: AdminStreamingContainer): string {
  const session = container.session;
  if (!session) return t("settings.streaming-idle");
  return [
    session.desktop
      ? t("settings.streaming-desktop-session")
      : (session.rom_name ?? t("settings.streaming-unknown-game")),
    session.claimed_at &&
      t("settings.streaming-since", {
        time: formatTimestamp(session.claimed_at, locale.value),
      }),
    session.username && t("settings.streaming-by", { user: session.username }),
  ]
    .filter(Boolean)
    .join(" ");
}

onMounted(load);
</script>

<template>
  <SettingsSection
    :title="t('settings.streaming')"
    icon="mdi-monitor-dashboard"
  >
    <template #header-actions>
      <RBtn
        icon="mdi-refresh"
        variant="text"
        density="compact"
        :tooltip="t('settings.streaming-refresh')"
        :disabled="loading"
        @click="load"
      />
    </template>

    <div v-if="loading" class="r-v2-streaming__loading">
      <RSpinner />
    </div>

    <REmptyState v-else-if="emptyState" size="small" v-bind="emptyState" />

    <template v-else>
      <div
        v-for="container in containers"
        :key="container.container || container.host || ''"
        class="r-v2-streaming__row"
      >
        <RIcon
          :icon="container.session ? 'mdi-play-circle' : 'mdi-monitor'"
          size="18"
          class="r-v2-streaming__icon"
          :class="{ 'r-v2-streaming__icon--busy': !!container.session }"
        />

        <div class="r-v2-streaming__info">
          <span class="r-v2-streaming__name">
            {{ container.label ?? container.host }}
          </span>
          <span class="r-v2-streaming__meta">
            {{ container.host }}
            <template v-if="container.platforms.length">
              {{ container.platforms.join(", ") }}
            </template>
          </span>
          <span
            v-if="!container.configured"
            class="r-v2-streaming__warning"
            role="alert"
          >
            {{ t("settings.streaming-unusable") }}
          </span>
          <span v-else class="r-v2-streaming__state">
            {{ sessionState(container) }}
          </span>
        </div>

        <div class="r-v2-streaming__actions">
          <RBtn
            v-if="container.supports_desktop"
            variant="outlined"
            density="compact"
            prepend-icon="mdi-desktop-classic"
            :disabled="!container.configured || !!container.session"
            @click="openDesktop(container)"
          >
            {{ t("settings.streaming-open-desktop") }}
          </RBtn>
          <RBtn
            variant="text"
            density="compact"
            color="error"
            prepend-icon="mdi-stop"
            :disabled="!container.session"
            :loading="releasing === container.container"
            @click="release(container)"
          >
            {{ t("settings.streaming-release") }}
          </RBtn>
        </div>
      </div>
    </template>
  </SettingsSection>
</template>

<style scoped>
.r-v2-streaming__loading {
  padding: 16px;
  color: var(--r-color-fg-muted);
}

.r-v2-streaming__row {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  border-bottom: 1px solid var(--r-color-border);
}
.r-v2-streaming__row:last-child {
  border-bottom: none;
}

.r-v2-streaming__icon {
  color: var(--r-color-fg-muted);
}
.r-v2-streaming__icon--busy {
  color: var(--r-color-brand-primary);
}

.r-v2-streaming__info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.r-v2-streaming__name {
  font-size: var(--r-font-size-sm);
  font-weight: var(--r-font-weight-semibold);
}

.r-v2-streaming__meta,
.r-v2-streaming__state {
  font-size: var(--r-font-size-xs);
  color: var(--r-color-fg-muted);
}
.r-v2-streaming__meta {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.r-v2-streaming__actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
}

/* On a phone the actions drop under the details instead of squeezing them out. */
html[data-bp~="xs"] .r-v2-streaming__actions {
  grid-column: 2 / -1;
}

.r-v2-streaming__warning {
  font-size: var(--r-font-size-xs);
  color: var(--r-color-danger-fg);
}
</style>

<script setup lang="ts">
// NewVersionBanner — checks the GitHub releases API for a newer version
// than the running build (heartbeat.SYSTEM.VERSION) and surfaces a
// bottom-center sticky panel with Dismiss / "See what's new" actions.
//
// Mirrors the v1 NewVersionDialog logic so the dismissal state carries
// across UI versions (shared `ui.dismissedVersion` localStorage key):
//   * skip when VERSION isn't valid semver (e.g. "development")
//   * skip when the latest tag matches the dismissed tag
//   * skip when the release is younger than 2 hours (avoids flashing the
//     banner during a rolling release that hasn't fully published)
//
// Visual: same canvas-bg-deep + blur + lg radius vocabulary as
// UploadProgressToast. Positioned bottom-center so it never collides
// with the upload toast (bottom-right).
import { RBtn, RIcon } from "@v2/lib";
import { useLocalStorage } from "@vueuse/core";
import semver from "semver";
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import storeHeartbeat from "@/stores/heartbeat";

defineOptions({ inheritAttrs: false });

const { t } = useI18n();
const heartbeat = storeHeartbeat();
const { VERSION } = heartbeat.value.SYSTEM;

const latestVersion = ref(VERSION);
const dismissed = ref(VERSION === "development");
const dismissedVersion = useLocalStorage("ui.dismissedVersion", "");

const visible = computed(
  () =>
    semver.valid(VERSION) &&
    !dismissed.value &&
    semver.valid(latestVersion.value) &&
    semver.gt(latestVersion.value, VERSION),
);

function onDismiss() {
  dismissedVersion.value = latestVersion.value;
  dismissed.value = true;
}

function onOpenRelease() {
  window.open(
    `https://github.com/rommapp/romm/releases/tag/${latestVersion.value}`,
    "_blank",
    "noopener,noreferrer",
  );
}

async function fetchLatestVersion() {
  try {
    const response = await fetch(
      "https://api.github.com/repos/rommapp/romm/releases/latest",
    );
    const json = await response.json();
    latestVersion.value = json.tag_name;

    const publishedAt = new Date(json.published_at);
    dismissed.value =
      !semver.valid(VERSION) ||
      json.tag_name === dismissedVersion.value ||
      publishedAt.getTime() + 2 * 60 * 60 * 1000 > Date.now();
  } catch (error) {
    console.error("Failed to fetch latest version from GitHub", error);
  }

  document.removeEventListener("network-quiesced", fetchLatestVersion);
}

onMounted(() => {
  document.addEventListener("network-quiesced", fetchLatestVersion);
});
onBeforeUnmount(() => {
  document.removeEventListener("network-quiesced", fetchLatestVersion);
});
</script>

<template>
  <transition name="r-v2-new-version">
    <div v-if="visible" class="r-v2-new-version" role="status">
      <div class="r-v2-new-version__head">
        <RIcon
          icon="mdi-rocket-launch-outline"
          size="18"
          class="r-v2-new-version__icon"
        />
        <span class="r-v2-new-version__text">
          {{ t("common.new-version-available") }}
          <span class="r-v2-new-version__tag">{{ latestVersion }}</span>
        </span>
      </div>
      <div class="r-v2-new-version__actions">
        <RBtn
          size="small"
          variant="translucent"
          color="primary"
          prepend-icon="mdi-open-in-new"
          @click="onOpenRelease"
        >
          {{ t("common.whats-new") }}
        </RBtn>
        <RBtn
          size="small"
          variant="text"
          class="r-v2-new-version__dismiss"
          @click="onDismiss"
        >
          {{ t("common.dismiss") }}
        </RBtn>
      </div>
    </div>
  </transition>
</template>

<style scoped>
.r-v2-new-version {
  position: fixed;
  left: 50%;
  bottom: 16px;
  transform: translateX(-50%);
  z-index: 8800;
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 8px 8px 8px 14px;
  background: var(--r-color-toast-bg);
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-lg);
  backdrop-filter: blur(18px);
  -webkit-backdrop-filter: blur(18px);
  box-shadow:
    0 18px 36px color-mix(in srgb, black 50%, transparent),
    0 4px 10px color-mix(in srgb, black 30%, transparent);
  max-width: calc(100vw - 32px);
}

.r-v2-new-version__head {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.r-v2-new-version__icon {
  color: var(--r-color-brand-primary);
  flex-shrink: 0;
}

.r-v2-new-version__text {
  font-size: 13px;
  color: var(--r-color-fg);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.r-v2-new-version__tag {
  margin-left: 6px;
  font-weight: var(--r-font-weight-semibold);
  color: var(--r-color-brand-primary);
  font-variant-numeric: tabular-nums;
}

.r-v2-new-version__actions {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}
/* Extra breathing room before the dismiss link so it reads as a
   secondary, "I'm done here" affordance rather than a sibling action
   of the primary CTA. */
.r-v2-new-version__dismiss {
  margin-left: 8px;
  color: var(--r-color-fg-muted);
}

/* Slide + fade in/out from the bottom. */
.r-v2-new-version-enter-from,
.r-v2-new-version-leave-to {
  opacity: 0;
  transform: translate(-50%, 12px);
}
.r-v2-new-version-enter-active,
.r-v2-new-version-leave-active {
  transition:
    opacity var(--r-motion-med) var(--r-motion-ease-out),
    transform var(--r-motion-med) var(--r-motion-ease-out);
}

/* On narrow viewports, stack the actions under the message and let the
   panel take the full safe width. */
html[data-bp~="xs"] .r-v2-new-version {
  left: 12px;
  right: 12px;
  bottom: 12px;
  transform: none;
  flex-direction: column;
  align-items: stretch;
  gap: 8px;
  padding: 12px;
}
html[data-bp~="xs"] .r-v2-new-version-enter-from,
html[data-bp~="xs"] .r-v2-new-version-leave-to {
  transform: translateY(12px);
}
html[data-bp~="xs"] .r-v2-new-version__actions {
  justify-content: flex-end;
}
</style>

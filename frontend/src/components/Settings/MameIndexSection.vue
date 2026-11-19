<script setup lang="ts">
// The MAME machine index: what is loaded, and the three ways to load one
// (MAME's latest release, a URL, or an uploaded listxml).
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import type { MameIndexStatus } from "@/__generated__";
import SettingsSection from "@/components/Settings/SettingsSection.vue";
import { useSnackbar } from "@/composables/useSnackbar";
import { RBtn, RTextField } from "@/lib";
import mameApi from "@/services/api/mame";
import { errorMessage } from "@/utils/errorMessage";

const POLL_MS = 3000;

const { t } = useI18n();
const snackbar = useSnackbar();

const status = ref<MameIndexStatus | null>(null);
const url = ref("");
const busy = ref(false);
const fileInput = ref<HTMLInputElement | null>(null);
let pollTimer: ReturnType<typeof setTimeout> | undefined;

const updating = computed(() => busy.value || !!status.value?.updating);

async function refresh() {
  clearTimeout(pollTimer);
  try {
    status.value = await mameApi.getIndexStatus();
  } catch {
    status.value = null;
  }
  if (status.value?.updating) pollTimer = setTimeout(refresh, POLL_MS);
}

async function run(action: () => Promise<unknown>) {
  busy.value = true;
  try {
    await action();
    snackbar.success(t("settings.mame-index-queued"), {
      icon: "mdi-check-bold",
    });
  } catch (err) {
    snackbar.error(
      t("settings.mame-index-failed", { detail: errorMessage(err) }),
      { icon: "mdi-close-circle" },
    );
  } finally {
    busy.value = false;
    await refresh();
  }
}

function updateLatest() {
  void run(() => mameApi.updateIndex());
}

function updateFromUrl() {
  const target = url.value.trim();
  if (target) void run(() => mameApi.updateIndex(target));
}

function onFile(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  input.value = "";
  if (file) void run(() => mameApi.uploadIndex(file));
}

onMounted(refresh);
onBeforeUnmount(() => clearTimeout(pollTimer));
</script>

<template>
  <SettingsSection
    :title="t('settings.mame-index-title')"
    icon="mdi-gamepad-variant-outline"
  >
    <div class="r-mame">
      <p class="r-mame__status" data-testid="mame-index-status">
        <template v-if="updating">{{ t("settings.mame-index-updating") }}</template>
        <template v-else-if="status?.info">
          {{
            t("settings.mame-index-loaded", {
              build: status.info.build,
              sets: status.info.sets.toLocaleString(),
              date: new Date(status.info.updated_at).toLocaleString(),
            })
          }}
        </template>
        <template v-else>{{ t("settings.mame-index-none") }}</template>
      </p>
      <p class="r-mame__hint">{{ t("settings.mame-index-hint") }}</p>

      <div class="r-mame__actions">
        <RBtn
          variant="flat"
          size="small"
          prepend-icon="mdi-download"
          :loading="updating"
          :disabled="updating"
          @click="updateLatest"
        >
          {{ t("settings.mame-index-update-latest") }}
        </RBtn>
        <RBtn
          variant="translucent"
          size="small"
          prepend-icon="mdi-upload"
          :disabled="updating"
          @click="fileInput?.click()"
        >
          {{ t("settings.mame-index-upload") }}
        </RBtn>
        <input
          ref="fileInput"
          type="file"
          accept=".xml,.zip"
          hidden
          @change="onFile"
        />
      </div>

      <div class="r-mame__url">
        <RTextField
          v-model="url"
          :label="t('settings.mame-index-url')"
          placeholder="https://github.com/mamedev/mame/releases/download/mame0289/mame0289lx.zip"
          density="compact"
          hide-details
          :disabled="updating"
          @keyup.enter="updateFromUrl"
        />
        <RBtn
          variant="translucent"
          size="small"
          prepend-icon="mdi-link-variant"
          :disabled="updating || !url.trim()"
          @click="updateFromUrl"
        >
          {{ t("settings.mame-index-update-url") }}
        </RBtn>
      </div>
    </div>
  </SettingsSection>
</template>

<style scoped>
.r-mame {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px;
}
.r-mame__status {
  margin: 0;
  font-weight: 600;
}
.r-mame__hint {
  margin: 0;
  opacity: 0.75;
  font-size: 0.875rem;
}
.r-mame__actions,
.r-mame__url {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}
.r-mame__url > :first-child {
  flex: 1 1 280px;
}
</style>

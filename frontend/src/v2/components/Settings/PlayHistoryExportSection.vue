<script setup lang="ts">
// Backloggd has no API to sync against, so this is a point-in-time snapshot:
// re-exporting is how you catch it up.
import { RBtn } from "@v2/lib";
import { ref } from "vue";
import { useI18n } from "vue-i18n";
import exportApi from "@/services/api/export";
import SettingsSection from "@/v2/components/Settings/SettingsSection.vue";
import { useSnackbar } from "@/v2/composables/useSnackbar";
import { downloadBlob, filenameFromResponse } from "@/v2/utils/download";

const { t } = useI18n();
const snackbar = useSnackbar();

const exporting = ref(false);

async function exportBackloggd() {
  exporting.value = true;
  try {
    const response = await exportApi.exportBackloggdCsv();
    downloadBlob(
      response.data,
      filenameFromResponse(
        response.headers["content-disposition"],
        "romm-backloggd.csv",
      ),
    );
  } catch (err) {
    console.error(err);
    snackbar.error(t("settings.play-history-export-failed"), {
      icon: "mdi-close-circle",
    });
  } finally {
    exporting.value = false;
  }
}
</script>

<template>
  <SettingsSection
    :title="t('settings.play-history')"
    icon="mdi-book-clock-outline"
  >
    <div class="r-v2-play-history__body">
      <p class="r-v2-play-history__desc">
        {{ t("settings.play-history-export-desc") }}
      </p>
      <RBtn
        variant="flat"
        color="primary"
        :loading="exporting"
        prepend-icon="mdi-file-delimited-outline"
        @click="exportBackloggd"
      >
        {{ t("settings.play-history-export-backloggd") }}
      </RBtn>
    </div>
  </SettingsSection>
</template>

<style scoped>
.r-v2-play-history__body {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 14px;
  padding: 14px 16px;
}

.r-v2-play-history__desc {
  margin: 0;
  font-size: 13px;
  line-height: 1.5;
  color: var(--r-color-fg-secondary);
}
</style>

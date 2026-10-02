<script setup lang="ts">
// ConfigFileAlerts: the config.yml status alerts (not mounted, unparsable,
// read-only) shown above every settings page that edits that file.
import { RAlert } from "@v2/lib";
import { storeToRefs } from "pinia";
import { useI18n } from "vue-i18n";
import storeConfig from "@/stores/config";

const { t } = useI18n();
const { config } = storeToRefs(storeConfig());
</script>

<template>
  <RAlert v-if="!config.CONFIG_FILE_MOUNTED" type="error">
    <template #title>
      {{ t("settings.config-file-not-mounted-title") }}
    </template>
    {{ t("settings.config-file-not-mounted-desc") }}
  </RAlert>
  <RAlert
    v-if="config.CONFIG_FILE_MOUNTED && config.CONFIG_FILE_PARSE_ERROR"
    type="error"
  >
    <template #title>
      {{ t("settings.config-file-parse-error-title") }}
    </template>
    {{
      t("settings.config-file-parse-error-desc", {
        error: config.CONFIG_FILE_PARSE_ERROR,
      })
    }}
  </RAlert>
  <RAlert
    v-if="config.CONFIG_FILE_MOUNTED && !config.CONFIG_FILE_WRITABLE"
    type="warning"
  >
    <template #title>
      {{ t("settings.config-file-not-writable-title") }}
    </template>
    {{ t("settings.config-file-not-writable-desc") }}
  </RAlert>
</template>

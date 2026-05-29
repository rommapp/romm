<script setup lang="ts">
import { useI18n } from "vue-i18n";
import RSection from "@/components/common/RSection.vue";
import { useUiVersion } from "@/composables/useUiVersion";

const { t } = useI18n();
const uiVersion = useUiVersion();

function setVersion(value: unknown) {
  if (value === "v1" || value === "v2") {
    uiVersion.value = value;
  }
}
</script>

<template>
  <RSection
    icon="mdi-new-box"
    :title="t('settings.ui-version', 'UI version')"
    class="ma-2"
  >
    <template #content>
      <div class="pa-4">
        <div class="text-body-2 text-medium-emphasis mb-4">
          {{
            t(
              "settings.ui-version-desc",
              "Preview the new RomM UI (beta). Switching is instant and you can flip back at any time.",
            )
          }}
        </div>
        <v-btn-toggle
          :model-value="uiVersion"
          color="primary"
          variant="outlined"
          divided
          mandatory
          @update:model-value="setVersion"
        >
          <v-btn value="v1" prepend-icon="mdi-star-outline">
            {{ t("settings.ui-version-classic", "Classic UI") }}
          </v-btn>
          <v-btn value="v2" prepend-icon="mdi-star-four-points">
            {{ t("settings.ui-version-new", "New UI (beta)") }}
          </v-btn>
        </v-btn-toggle>
      </div>
    </template>
  </RSection>
</template>

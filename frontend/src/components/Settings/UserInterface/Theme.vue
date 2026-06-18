<script setup lang="ts">
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import ThemeOption from "@/components/Settings/UserInterface/ThemeOption.vue";
import RSection from "@/components/common/RSection.vue";
import { useUISettings } from "@/composables/useUISettings";

const { t } = useI18n();
const { theme: selectedTheme } = useUISettings();
const themeOptions = computed(() => [
  {
    name: "dark",
    icon: "mdi-moon-waning-crescent",
  },
  {
    name: "light",
    icon: "mdi-white-balance-sunny",
  },
  {
    name: "auto",
    icon: "mdi-theme-light-dark",
  },
]);
</script>
<template>
  <RSection icon="mdi-brush-variant" :title="t('settings.theme')" class="ma-2">
    <template #content>
      <v-item-group v-model="selectedTheme" mandatory>
        <v-row no-gutters>
          <v-col
            v-for="themeOption in themeOptions"
            :key="themeOption.name"
            cols="4"
            sm="3"
            md="2"
            class="pa-2"
          >
            <ThemeOption
              :key="themeOption.name"
              :text="themeOption.name"
              :icon="themeOption.icon"
            />
          </v-col>
        </v-row>
      </v-item-group>
    </template>
  </RSection>
</template>

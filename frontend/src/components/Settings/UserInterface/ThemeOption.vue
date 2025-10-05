<script setup lang="ts">
import { useI18n } from "vue-i18n";
import { useDisplay } from "vuetify";

const { t } = useI18n();
const { xs } = useDisplay();
withDefaults(defineProps<{ text: string; icon: string }>(), {
  text: "",
  icon: "",
});
</script>
<template>
  <v-item v-slot="{ isSelected, toggle }">
    <v-card
      :color="isSelected ? 'primary' : 'romm-gray'"
      class="d-flex align-center"
      height="50"
      variant="outlined"
      @click="toggle"
    >
      <div class="text-subtitle-2 flex-grow-1 text-center text-capitalize">
        <v-icon>
          {{ icon }}
        </v-icon>
        <span v-if="!xs" class="ml-2">{{ t(`settings.theme-${text}`) }}</span>
      </div>
    </v-card>
  </v-item>
</template>

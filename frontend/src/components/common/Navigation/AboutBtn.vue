<script setup lang="ts">
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { inject } from "vue";
import { useI18n } from "vue-i18n";

// Props
withDefaults(
  defineProps<{
    block?: boolean;
    height?: string;
    rounded?: boolean;
    withTag?: boolean;
  }>(),
  {
    block: false,
    height: "",
    rounded: false,
    withTag: false,
  },
);
const { t } = useI18n();
const emitter = inject<Emitter<Events>>("emitter");
</script>
<template>
  <v-btn
    icon
    :block="block"
    variant="flat"
    color="background"
    :height="height"
    :class="{ rounded: rounded }"
    class="bg-background custom-btn"
    @click="emitter?.emit('showAboutDialog')"
  >
    <div class="icon-container">
      <v-icon>mdi-help-circle-outline</v-icon>
      <v-expand-transition>
        <span v-if="withTag" class="text-caption">{{ t("common.about") }}</span>
      </v-expand-transition>
    </div>
  </v-btn>
</template>

<style scoped>
.custom-btn {
  display: flex;
  align-items: center;
  justify-content: center;
}

.icon-container {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.icon-container span {
  text-align: center;
}
</style>

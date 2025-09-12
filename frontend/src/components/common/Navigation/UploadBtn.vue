<script setup lang="ts">
import type { Emitter } from "mitt";
import { inject } from "vue";
import { useI18n } from "vue-i18n";
import storeAuth from "@/stores/auth";
import type { Events } from "@/types/emitter";

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
const auth = storeAuth();
</script>
<template>
  <v-btn
    v-if="auth.scopes.includes('roms.write')"
    icon
    :block="block"
    variant="flat"
    color="background"
    :height="height"
    :class="{ rounded: rounded }"
    class="bg-background d-flex align-center justify-center"
    @click="emitter?.emit('showUploadRomDialog', null)"
  >
    <div class="d-flex flex-column align-center">
      <v-icon>mdi-cloud-upload-outline</v-icon>
      <v-expand-transition>
        <span v-if="withTag" class="text-caption text-center">{{
          t("common.upload")
        }}</span>
      </v-expand-transition>
    </div>
  </v-btn>
</template>

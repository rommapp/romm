<script setup lang="ts">
import storeAuth from "@/stores/auth";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { inject, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useNavigation } from "@/composables/useNavigation";

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
const auth = storeAuth();

const uploadBtnRef = ref<HTMLElement>();

useNavigation(uploadBtnRef, "upload-btn", {
  priority: 6,
  action: () => emitter?.emit("showUploadRomDialog", null),
});
</script>
<template>
  <v-btn
    v-if="auth.scopes.includes('roms.write')"
    ref="uploadBtnRef"
    icon
    :block="block"
    variant="flat"
    color="background"
    :height="height"
    :class="{ rounded: rounded }"
    class="bg-background d-flex align-center justify-center"
    @click="emitter?.emit('showUploadRomDialog', null)"
    v-navigation="{ id: 'upload-btn', priority: 6 }"
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

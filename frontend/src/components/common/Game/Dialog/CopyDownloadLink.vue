<script setup lang="ts">
import type { Emitter } from "mitt";
import { inject, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useDisplay } from "vuetify";
import RDialog from "@/components/common/RDialog.vue";
import type { Events } from "@/types/emitter";

const { t } = useI18n();
const { lgAndUp } = useDisplay();
const show = ref(false);
const link = ref("");
const emitter = inject<Emitter<Events>>("emitter");
emitter?.on("showCopyDownloadLinkDialog", (downloadLink) => {
  show.value = true;
  link.value = downloadLink;
});

function closeDialog() {
  show.value = false;
  link.value = "";
}
</script>

<template>
  <RDialog
    v-model="show"
    icon="mdi-content-copy"
    :width="lgAndUp ? '60vw' : '95vw'"
    @close="closeDialog"
  >
    <template #content>
      <v-row class="justify-center pa-2" no-gutters>
        <v-list-item>{{ t("rom.cant-copy-link") }}:</v-list-item>
      </v-row>
      <v-row class="text-center pa-2" no-gutters>
        <v-list-item rounded class="bg-toplayer">
          {{ link }}
        </v-list-item>
      </v-row>
    </template>
  </RDialog>
</template>

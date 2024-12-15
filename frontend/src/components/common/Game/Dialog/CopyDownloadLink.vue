<script setup lang="ts">
import RDialog from "@/components/common/RDialog.vue";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { inject, ref } from "vue";
import { useDisplay } from "vuetify";
import { useI18n } from "vue-i18n";

// Props
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
  <r-dialog
    @close="closeDialog"
    v-model="show"
    icon="mdi-content-copy"
    :width="lgAndUp ? '60vw' : '95vw'"
  >
    <template #content>
      <v-row class="justify-center text-center pa-2" no-gutters>
        <v-list-item>{{ t("rom.cant-copy-link") }}:</v-list-item>
      </v-row>
      <v-row class="justify-center text-center pa-2 mb-3" no-gutters>
        <v-list-item class="bg-terciary">{{ link }}</v-list-item>
      </v-row>
    </template></r-dialog
  >
</template>

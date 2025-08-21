<script setup lang="ts">
import { ref } from "vue";
import { useI18n } from "vue-i18n";
import RDialog from "@/components/common/RDialog.vue";

const { t } = useI18n();
const show = ref(false);

function clearIndexDB() {
  window.indexedDB.deleteDatabase("/data/saves");
  window.indexedDB.deleteDatabase("EmulatorJS-roms");
  window.indexedDB.deleteDatabase("EmulatorJS-core");
  window.indexedDB.deleteDatabase("EmulatorJS-states");

  closeDialog();
}

function closeDialog() {
  show.value = false;
}
</script>

<template>
  <v-btn
    class="text-romm-red mt-6"
    block
    variant="flat"
    prepend-icon="mdi-database-remove"
    @click="show = true"
    >{{ t("play.clear-cache") }}
  </v-btn>
  <r-dialog v-model="show" @close="closeDialog" icon="mdi-database-remove">
    <template #header>
      <v-row class="ml-2">
        {{ t("play.clear-cache") }}
      </v-row>
    </template>
    <template #content>
      <div class="text-h6 text-center pa-4">
        {{ t("play.clear-cache-title") }}
      </div>
      <div class="text-body-1 text-center px-4 pb-4">
        <strong>{{ t("play.clear-cache-warning") }}</strong>
        <br />
        {{ t("play.clear-cache-description") }}
      </div>
    </template>
    <template #append>
      <v-row class="justify-center pa-2" no-gutters>
        <v-btn-group divided density="compact">
          <v-btn class="bg-toplayer" @click="closeDialog">
            {{ t("common.cancel") }}
          </v-btn>
          <v-btn class="bg-toplayer text-romm-red" @click="clearIndexDB">
            {{ t("common.confirm") }}
          </v-btn>
        </v-btn-group>
      </v-row>
    </template>
  </r-dialog>
</template>

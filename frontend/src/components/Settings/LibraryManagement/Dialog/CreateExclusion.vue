<script setup lang="ts">
import RDialog from "@/components/common/RDialog.vue";
import configApi from "@/services/api/config";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import storeConfig from "@/stores/config";
import { inject, ref } from "vue";
import { useDisplay } from "vuetify";
import { useI18n } from "vue-i18n";

// Props
const { t } = useI18n();
const { mdAndUp, smAndDown } = useDisplay();
const show = ref(false);
const emitter = inject<Emitter<Events>>("emitter");
const configStore = storeConfig();
const exclusionValue = ref();
const exclusionType = ref();
const exclusionIcon = ref();
const exclusionTitle = ref();
emitter?.on("showCreateExclusionDialog", ({ type, icon, title }) => {
  exclusionType.value = type;
  exclusionIcon.value = icon;
  exclusionTitle.value = title;
  show.value = true;
});

// Functions
function addExclusion() {
  if (configStore.isExclusionType(exclusionType.value)) {
    configApi.addExclusion({
      exclusionValue: exclusionValue.value,
      exclusionType: exclusionType.value,
    });
    configStore.addExclusion(exclusionType.value, exclusionValue.value);
    closeDialog();
  } else {
    console.error(`Invalid exclusion type '${exclusionType.value}'`);
  }
}

function closeDialog() {
  show.value = false;
  exclusionValue.value = "";
}
</script>
<template>
  <r-dialog
    @close="closeDialog"
    v-model="show"
    icon="mdi-cancel"
    :width="mdAndUp ? '45vw' : '95vw'"
  >
    <template #content>
      <v-row v-if="smAndDown" no-gutters>
        <v-col class="mt-2 py-2 text-center">
          <v-icon :icon="exclusionIcon" />
          <span class="ml-2">{{ exclusionTitle }}</span>
        </v-col>
      </v-row>
      <v-row class="align-center py-2 px-4" no-gutters>
        <v-col v-if="mdAndUp" class="text-center" cols="2">
          <div>
            <v-icon :icon="exclusionIcon" />
          </div>
          <div class="mt-2">
            <span class="ml-2">{{ exclusionTitle }}</span>
          </div>
        </v-col>
        <v-col>
          <v-text-field
            v-model="exclusionValue"
            class="py-2"
            :class="{ 'ml-4': mdAndUp }"
            variant="outlined"
            required
            hide-details
            @keyup.enter="addExclusion"
          />
        </v-col>
      </v-row>
    </template>
    <template #append>
      <v-row class="justify-center mb-2" no-gutters>
        <v-btn-group divided density="compact">
          <v-btn class="bg-terciary" @click="closeDialog">
            {{ t("common.cancel") }}
          </v-btn>
          <v-btn
            class="bg-terciary text-romm-green"
            :disabled="exclusionValue == ''"
            :variant="exclusionValue == '' ? 'plain' : 'flat'"
            @click="addExclusion"
          >
            {{ t("common.confirm") }}
          </v-btn>
        </v-btn-group>
      </v-row>
    </template>
  </r-dialog>
</template>

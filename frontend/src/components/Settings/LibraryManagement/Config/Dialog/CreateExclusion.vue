<script setup lang="ts">
import type { Emitter } from "mitt";
import { inject, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useDisplay } from "vuetify";
import RDialog from "@/components/common/RDialog.vue";
import configApi from "@/services/api/config";
import storeConfig from "@/stores/config";
import type { Events } from "@/types/emitter";

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
  <RDialog
    v-model="show"
    icon="mdi-plus-circle"
    :width="mdAndUp ? '45vw' : '95vw'"
    @close="closeDialog"
  >
    <template #header>
      <v-row class="align-center" no-gutters>
        <v-col cols="10">
          <v-icon icon="mdi-cancel" class="ml-5" />
          <v-icon icon="mdi-menu-right" class="ml-1 text-romm-gray" />
          <v-icon :icon="exclusionIcon" class="ml-1 text-primary" />
        </v-col>
      </v-row>
    </template>
    <template #content>
      <v-row class="px-4 pt-4 align-center" no-gutters>
        <v-col cols="12">
          <v-card-text class="pa-0">
            <p class="text-sm text-romm-gray mb-3">
              Add a new exclusion for {{ exclusionTitle }}
            </p>
            <v-text-field
              v-model="exclusionValue"
              label="Exclusion value"
              placeholder="e.g., *.tmp or test_file.rom"
              variant="outlined"
              required
              hide-details
              autofocus
              @keyup.enter="addExclusion"
            >
              <template #prepend-inner>
                <v-icon :icon="exclusionIcon" class="mr-2" />
              </template>
            </v-text-field>
          </v-card-text>
        </v-col>
      </v-row>
    </template>
    <template #footer>
      <v-row class="justify-center my-2" no-gutters>
        <v-btn-group divided density="compact">
          <v-btn class="bg-toplayer" @click="closeDialog">
            {{ t("common.cancel") }}
          </v-btn>
          <v-btn
            class="bg-toplayer text-romm-green"
            :disabled="exclusionValue == ''"
            :variant="exclusionValue == '' ? 'plain' : 'flat'"
            @click="addExclusion"
          >
            {{ t("common.confirm") }}
          </v-btn>
        </v-btn-group>
      </v-row>
    </template>
  </RDialog>
</template>

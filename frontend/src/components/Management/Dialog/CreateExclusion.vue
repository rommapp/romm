<script setup lang="ts">
import RDialog from "@/components/common/RDialog.vue";
import configApi from "@/services/api/config";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { inject, ref } from "vue";
import { useDisplay } from "vuetify";

// Props
const { mdAndUp, smAndDown } = useDisplay();
const show = ref(false);
const emitter = inject<Emitter<Events>>("emitter");
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
  configApi.addExclusion({
    exclusionValue: exclusionValue.value,
    exclusionType: exclusionType.value,
  });
  configStore.addExclusion(exclusionValue, exclusionType);
  closeDialog();
}

function closeDialog() {
  show.value = false;
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
  </r-dialog>
</template>

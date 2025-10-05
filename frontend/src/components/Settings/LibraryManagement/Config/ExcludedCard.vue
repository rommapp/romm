<script setup lang="ts">
import type { Emitter } from "mitt";
import { inject } from "vue";
import { useI18n } from "vue-i18n";
import configApi from "@/services/api/config";
import storeConfig from "@/stores/config";
import type { Events } from "@/types/emitter";

const { t } = useI18n();
const emitter = inject<Emitter<Events>>("emitter");
const props = defineProps<{
  set: string[];
  editable: boolean;
  title: string;
  type: string;
  icon: string;
}>();
const configStore = storeConfig();

function removeExclusion(exclusionValue: string) {
  if (configStore.isExclusionType(props.type)) {
    configApi.deleteExclusion({
      exclusionValue: exclusionValue,
      exclusionType: props.type,
    });
    configStore.removeExclusion(exclusionValue, props.type);
  } else {
    console.error(`Invalid exclusion type '${props.type}'`);
  }
}
</script>
<template>
  <v-card color="toplayer" class="ma-2">
    <v-card-title class="text-body-2 align-center justify-center">
      <v-icon class="mr-2"> {{ icon }} </v-icon>{{ title }}
    </v-card-title>
    <v-divider />
    <v-card-text class="pa-2">
      <v-chip
        v-for="exclusionValue in set"
        :key="exclusionValue"
        label
        class="ma-1"
      >
        <span>{{ exclusionValue }}</span>
        <v-slide-x-reverse-transition>
          <v-btn
            v-if="editable"
            variant="text"
            rounded="0"
            size="x-small"
            icon="mdi-delete"
            class="text-romm-red ml-1"
            @click="removeExclusion(exclusionValue)"
          />
        </v-slide-x-reverse-transition>
      </v-chip>
      <v-expand-transition>
        <v-btn
          v-if="editable"
          rounded="1"
          prepend-icon="mdi-plus"
          variant="outlined"
          class="text-primary ml-1"
          @click="
            emitter?.emit('showCreateExclusionDialog', {
              type: type,
              icon: icon,
              title: title,
            })
          "
        >
          {{ t("common.add") }}
        </v-btn>
      </v-expand-transition>
    </v-card-text>
  </v-card>
</template>

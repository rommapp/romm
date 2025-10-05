<script setup lang="ts">
import { ref } from "vue";
import { useI18n } from "vue-i18n";
import { useDisplay } from "vuetify";
import Saves from "@/components/Details/Saves.vue";
import States from "@/components/Details/States.vue";
import type { DetailedRom } from "@/stores/roms";

const { t } = useI18n();
defineProps<{ rom: DetailedRom }>();
const tab = ref<"saves" | "states">("saves");
const { mdAndDown } = useDisplay();
</script>
<template>
  <v-row no-gutters>
    <v-col cols="12" lg="2">
      <v-tabs
        v-model="tab"
        :direction="mdAndDown ? 'horizontal' : 'vertical'"
        :align-tabs="mdAndDown ? 'center' : 'start'"
        slider-color="secondary"
        class="mr-4 mt-2"
        selected-class="bg-toplayer"
      >
        <v-tab
          prepend-icon="mdi-content-save"
          class="rounded text-caption"
          value="saves"
        >
          {{ t("common.saves") }}
        </v-tab>
        <v-tab
          prepend-icon="mdi-file"
          class="rounded text-caption"
          value="states"
        >
          {{ t("common.states") }}
        </v-tab>
      </v-tabs>
    </v-col>
    <v-col>
      <v-tabs-window v-model="tab">
        <v-tabs-window-item value="saves">
          <Saves :rom="rom" />
        </v-tabs-window-item>
        <v-tabs-window-item value="states">
          <States :rom="rom" />
        </v-tabs-window-item>
      </v-tabs-window>
    </v-col>
  </v-row>
</template>

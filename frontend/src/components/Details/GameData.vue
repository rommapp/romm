<script setup lang="ts">
import Saves from "@/components/Details/Saves.vue";
import States from "@/components/Details/States.vue";
import type { DetailedRom } from "@/stores/roms";
import { ref } from "vue";
import { useDisplay } from "vuetify";

// Props
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
          >Saves</v-tab
        >
        <v-tab
          prepend-icon="mdi-file"
          class="rounded text-caption"
          value="states"
          >States</v-tab
        >
      </v-tabs>
    </v-col>
    <v-col>
      <v-tabs-window v-model="tab">
        <v-tabs-window-item value="saves">
          <saves :rom="rom" />
        </v-tabs-window-item>
        <v-tabs-window-item value="states">
          <states :rom="rom" />
        </v-tabs-window-item>
      </v-tabs-window>
    </v-col>
  </v-row>
</template>

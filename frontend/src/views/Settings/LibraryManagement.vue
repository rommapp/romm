<script setup lang="ts">
import Excluded from "@/components/Settings/LibraryManagement/Config/Excluded.vue";
import PlatformBinding from "@/components/Settings/LibraryManagement/Config/PlatformBinding.vue";
import PlatformVersions from "@/components/Settings/LibraryManagement/Config/PlatformVersions.vue";
import MissingGames from "@/components/Settings/LibraryManagement/MissingGames/MissingGames.vue";
import romApi from "@/services/api/rom";
import { ref, onMounted } from "vue";
import { useDisplay } from "vuetify";

const tab = ref<"config" | "missing">("config");
const { mdAndDown } = useDisplay();

const missingGames = ref([]);
const missingGamesLoading = ref(false);

async function fetchMissingGames() {
  missingGamesLoading.value = true;
  await romApi
    .getRoms({
      filter: {
        missing: true,
      },
      limit: 10000,
    })
    .then((response) => {
      missingGames.value = response.data.items;
    })
    .catch((error) => {
      console.error("Error fetching missing games:", error);
    })
    .finally(() => {
      missingGamesLoading.value = false;
    });
}

onMounted(() => {
  fetchMissingGames();
});
</script>

<template>
  <v-row no-gutters class="pa-2">
    <v-col cols="12">
      <v-tabs
        v-model="tab"
        align-tabs="start"
        slider-color="secondary"
        selected-class="bg-toplayer"
      >
        <v-tab prepend-icon="mdi-cog" class="rounded" value="config"
          >Config</v-tab
        >
        <v-tab
          prepend-icon="mdi-folder-question"
          class="rounded"
          value="missing"
          >Missing games</v-tab
        >
      </v-tabs>
    </v-col>
    <v-col>
      <v-tabs-window v-model="tab">
        <v-tabs-window-item value="config">
          <platform-binding class="mt-2" />
          <platform-versions class="mt-4" />
          <excluded class="mt-4" />
        </v-tabs-window-item>
        <v-tabs-window-item value="missing">
          <missing-games
            class="mt-2"
            :missing-games="missingGames"
            :loading="missingGamesLoading"
          />
        </v-tabs-window-item>
      </v-tabs-window>
    </v-col>
  </v-row>
</template>

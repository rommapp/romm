<script setup lang="ts">
import { ref, inject, onMounted, watch } from "vue";
import { useRouter } from "vue-router";

import AdminMenu from "@/components/Game/AdminMenu/Base.vue";
import romApi from "@/services/api/rom";
import storeAuth from "@/stores/auth";
import storeDownload from "@/stores/download";
import storeRoms from "@/stores/roms";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import {
  formatBytes,
  languageToEmoji,
  platformSlugEJSCoreMap,
  regionToEmoji,
} from "@/utils";
import { useTheme } from "vuetify";
const theme = useTheme();

const HEADERS = [
  {
    title: "",
    align: "start",
    sortable: false,
    key: "path_cover_s",
  },
  {
    title: "Name",
    align: "start",
    sortable: true,
    key: "name",
  },
  {
    title: "File",
    align: "start",
    sortable: true,
    key: "file_name",
  },
  {
    title: "Size",
    align: "start",
    sortable: true,
    key: "file_size_bytes",
  },
  {
    title: "Reg",
    align: "start",
    sortable: true,
    key: "regions",
  },
  {
    title: "Lang",
    align: "start",
    sortable: true,
    key: "languages",
  },
  {
    title: "Rev",
    align: "start",
    sortable: true,
    key: "revision",
  },
  { title: "", align: "end", key: "actions", sortable: false },
] as const;

const PER_PAGE_OPTIONS = [
  { value: 25, title: "25" },
  { value: 50, title: "50" },
  { value: 100, title: "100" },
] as const;
const emitter = inject<Emitter<Events>>("emitter");
emitter?.on("updateDataTablePages", updateDataTablePages);

// Props
const router = useRouter();
const downloadStore = storeDownload();
const romsStore = storeRoms();
const auth = storeAuth();
const page = ref(1);
const romsPerPage = ref(10);
const pageCount = ref(0);

// Functions
function rowClick(_: Event, row: any) {
  router.push({ name: "rom", params: { rom: row.item.id } });
}

function updateDataTablePages() {
  pageCount.value = Math.ceil(
    romsStore.filteredRoms.length / romsPerPage.value
  );
}

watch(romsPerPage, async () => {
  updateDataTablePages();
});

onMounted(() => {
  updateDataTablePages();
});
</script>

<template>
  <v-data-table
    :items-per-page="romsPerPage"
    :items-per-page-options="PER_PAGE_OPTIONS"
    items-per-page-text=""
    :fixed-footer="false"
    :headers="HEADERS"
    :item-value="(item) => item.id"
    :items="romsStore.filteredRoms"
    @click:row="rowClick"
    show-select
    v-model="romsStore._selectedIDs"
    v-model:page="page"
  >
    <template v-slot:item.path_cover_s="{ item }">
      <v-avatar :rounded="0">
        <v-progress-linear
          color="romm-accent-1"
          :active="downloadStore.value.includes(item.id)"
          :indeterminate="true"
          absolute
        />
        <img
          :src="
            !item.igdb_id && !item.has_cover
              ? `/assets/default/cover/small_${theme.global.name.value}_unmatched.png`
              : !item.has_cover
              ? `/assets/default/cover/small_${theme.global.name.value}_missing_cover.png`
              : `/assets/romm/resources/${item.path_cover_s}`
          "
          min-height="150"
        />
      </v-avatar>
    </template>
    <template v-slot:item.name="{ item }">
      <span>
        {{ item.name }}
      </span>
    </template>
    <template v-slot:item.file_name="{ item }">
      <span>
        {{ item.file_name }}
      </span>
    </template>
    <template v-slot:item.file_size_bytes="{ item }">
      <span>
        {{ formatBytes(item.file_size_bytes) }}
      </span>
    </template>
    <template v-slot:item.regions="{ item }">
      <span class="px-1" v-for="region in item.regions">
        {{ regionToEmoji(region) }}
      </span>
    </template>
    <template v-slot:item.languages="{ item }">
      <span class="px-1" v-for="language in item.languages">
        {{ languageToEmoji(language) }}
      </span>
    </template>
    <template v-slot:item.actions="{ item }">
      <v-btn
        class="ma-1 bg-terciary"
        rounded="0"
        @click.stop="romApi.downloadRom({ rom: item })"
        :disabled="downloadStore.value.includes(item.id)"
        download
        size="small"
        variant="text"
      >
        <v-icon>mdi-download</v-icon>
      </v-btn>
      <v-btn
        v-if="item.platform_slug.toLowerCase() in platformSlugEJSCoreMap"
        size="small"
        variant="text"
        :href="`/play/${item.id}`"
        class="my-1 bg-terciary"
        rounded="0"
      >
        <v-icon>mdi-play</v-icon>
      </v-btn>
      <v-menu location="bottom">
        <template v-slot:activator="{ props }">
          <v-btn
            rounded="0"
            :disabled="!auth.scopes.includes('roms.write')"
            v-bind="props"
            size="small"
            variant="text"
            class="ma-1 bg-terciary"
            ><v-icon>mdi-dots-vertical</v-icon></v-btn
          >
        </template>
        <admin-menu :rom="item" />
      </v-menu>
    </template>

    <template v-slot:bottom>
      <v-divider class="border-opacity-25" />
      <v-row no-gutters class="pt-2 px-6 align-center">
        <v-col cols="11" class="px-6">
          <v-pagination
            class="mr-6"
            rounded="0"
            :show-first-last-page="true"
            active-color="romm-accent-1"
            v-model="page"
            :length="pageCount"
          ></v-pagination>
        </v-col>
        <v-col>
          <v-select
            label="Roms per page"
            density="compact"
            variant="outlined"
            :items="[10, 25, 50]"
            v-model="romsPerPage"
            hide-details
          />
        </v-col>
      </v-row>
    </template>
  </v-data-table>
</template>

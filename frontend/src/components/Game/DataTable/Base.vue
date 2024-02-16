<script setup lang="ts">
import { ref } from "vue";
import { useRouter } from "vue-router";
import { VDataTable } from "vuetify/labs/VDataTable";

import AdminMenu from "@/components/Game/AdminMenu/Base.vue";
import romApi from "@/services/api/rom";
import storeAuth from "@/stores/auth";
import storeDownload from "@/stores/download";
import storeRoms from "@/stores/roms";
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
  { value: -1, title: "$vuetify.dataFooter.itemsPerPageAll" },
] as const;

// Props
const router = useRouter();
const downloadStore = storeDownload();
const romsStore = storeRoms();
const auth = storeAuth();
const romsPerPage = ref(-1);

// Functions
function rowClick(_: Event, row: any) {
  router.push({ name: "rom", params: { rom: row.item.raw.id } });
}
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
  >
    <template v-slot:item.path_cover_s="{ item }">
      <v-avatar :rounded="0">
        <v-progress-linear
          color="romm-accent-1"
          :active="downloadStore.value.includes(item.raw.id)"
          :indeterminate="true"
          absolute
        />
        <v-img
          :src="
            !item.raw.igdb_id && !item.raw.has_cover
              ? `/assets/default/cover/small_${theme.global.name.value}_unmatched.png`
              : !item.raw.has_cover
              ? `/assets/default/cover/small_${theme.global.name.value}_missing_cover.png`
              : `/assets/romm/resources/${item.raw.path_cover_s}`
          "
          :lazy-src="
            !item.raw.igdb_id && !item.raw.has_cover
              ? `/assets/default/cover/small_${theme.global.name.value}_unmatched.png`
              : !item.raw.has_cover
              ? `/assets/default/cover/small_${theme.global.name.value}_missing_cover.png`
              : `/assets/romm/resources/${item.raw.path_cover_s}`
          "
          min-height="150"
        />
      </v-avatar>
    </template>
    <template v-slot:item.file_size_bytes="{ item }">
      <span>
        {{ formatBytes(item.raw.file_size_bytes) }}
      </span>
    </template>
    <template v-slot:item.regions="{ item }">
      <span class="px-1" v-for="region in item.raw.regions">
        {{ regionToEmoji(region) }}
      </span>
    </template>
    <template v-slot:item.languages="{ item }">
      <span class="px-1" v-for="language in item.raw.languages">
        {{ languageToEmoji(language) }}
      </span>
    </template>
    <template v-slot:item.actions="{ item }">
      <v-btn
        class="ma-1 bg-terciary"
        rounded="0"
        @click.stop="romApi.downloadRom({ rom: item.raw })"
        :disabled="downloadStore.value.includes(item.raw.id)"
        download
        size="small"
        variant="text"
      >
        <v-icon>mdi-download</v-icon>
      </v-btn>
      <v-btn
        v-if="item.raw.platform_slug.toLowerCase() in platformSlugEJSCoreMap"
        size="small"
        variant="text"
        :href="`/play/${item.raw.id}`"
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
        <admin-menu :rom="item.raw" />
      </v-menu>
    </template>
  </v-data-table>
</template>

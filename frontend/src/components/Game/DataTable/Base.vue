<script setup lang="ts">
import AdminMenu from "@/components/Game/AdminMenu/Base.vue";
import romApi from "@/services/api/rom";
import storeAuth from "@/stores/auth";
import storeDownload from "@/stores/download";
import storeRoms from "@/stores/roms";
import type { Events } from "@/types/emitter";
import {
  formatBytes,
  isEmulationSupported,
  languageToEmoji,
  regionToEmoji,
} from "@/utils";
import type { Emitter } from "mitt";
import { inject, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
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

const PER_PAGE_OPTIONS = [10, 25, 50, 100];
const emitter = inject<Emitter<Events>>("emitter");
emitter?.on("updateDataTablePages", updateDataTablePages);

// Props
const router = useRouter();
const downloadStore = storeDownload();
const romsStore = storeRoms();
const auth = storeAuth();
const page = ref(1);
const storedRomsPerPage = parseInt(localStorage.getItem("romsPerPage") ?? "");
const romsPerPage = ref(isNaN(storedRomsPerPage) ? 25 : storedRomsPerPage);
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
  localStorage.setItem("romsPerPage", romsPerPage.value.toString());
  updateDataTablePages();
});

onMounted(() => {
  updateDataTablePages();
});
</script>

<template>
  <v-data-table
    @click:row="rowClick"
    :items-per-page="romsPerPage"
    :items-per-page-options="PER_PAGE_OPTIONS"
    :item-value="(item) => item.id"
    :items="romsStore.filteredRoms"
    :headers="HEADERS"
    v-model="romsStore._selectedIDs"
    v-model:page="page"
    show-select
    hover
  >
    <template #item.path_cover_s="{ item }">
      <v-avatar :rounded="0" size="45"
        ><v-img
          :src="
            !item.igdb_id && !item.moby_id && !item.has_cover
              ? `/assets/default/cover/small_${theme.global.name.value}_unmatched.png`
              : `/assets/romm/resources/${item.path_cover_s}`
          "
        ></v-img
      ></v-avatar>
    </template>
    <template #item.name="{ item }">
      <span>
        {{ item.name }}
      </span>
    </template>
    <template #item.file_name="{ item }">
      <span>
        {{ item.file_name }}
      </span>
    </template>
    <template #item.file_size_bytes="{ item }">
      <span>
        {{ formatBytes(item.file_size_bytes) }}
      </span>
    </template>
    <template #item.regions="{ item }">
      <span class="px-1" v-for="region in item.regions">
        {{ regionToEmoji(region) }}
      </span>
    </template>
    <template #item.languages="{ item }">
      <span class="px-1" v-for="language in item.languages">
        {{ languageToEmoji(language) }}
      </span>
    </template>
    <template #item.actions="{ item }">
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
        v-if="isEmulationSupported(item.platform_slug)"
        size="small"
        variant="text"
        :href="`/play/${item.id}`"
        class="my-1 bg-terciary"
        rounded="0"
      >
        <v-icon>mdi-play</v-icon>
      </v-btn>
      <v-menu location="bottom">
        <template #activator="{ props }">
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

    <template #bottom>
      <v-divider class="border-opacity-25" />
      <v-row no-gutters class="pt-2 align-center">
        <v-col cols="11" class="px-6">
          <v-pagination
            rounded="0"
            :show-first-last-page="true"
            active-color="romm-accent-1"
            v-model="page"
            :length="pageCount"
          ></v-pagination>
        </v-col>
        <v-col cols="5" sm="2" xl="1">
          <v-select
            class="pa-2"
            label="Roms per page"
            density="compact"
            variant="outlined"
            :items="PER_PAGE_OPTIONS"
            v-model="romsPerPage"
            hide-details
          />
        </v-col>
      </v-row>
    </template>
  </v-data-table>
</template>
<style scoped>
.custom-data-table .v-data-table__tr .v-data-table__tr--clickable {
  background-color: #f5f5f5 !important; /* Change to desired hover color */
  color: #333 !important; /* Change text color on hover */
  border: 1px solid #ddd !important; /* Add border on hover */
}
</style>

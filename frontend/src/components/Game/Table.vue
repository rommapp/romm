<script setup lang="ts">
import AdminMenu from "@/components/Game/AdminMenu.vue";
import RAvatar from "@/components/Game/Avatar.vue";
import romApi from "@/services/api/rom";
import storeAuth from "@/stores/auth";
import storeDownload from "@/stores/download";
import storeRoms, { type SimpleRom } from "@/stores/roms";
import type { Events } from "@/types/emitter";
import {
  formatBytes,
  isEmulationSupported,
  languageToEmoji,
  regionToEmoji,
} from "@/utils";
import { isNull } from "lodash";
import type { Emitter } from "mitt";
import { inject, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { useTheme } from "vuetify";

// Props
const emitter = inject<Emitter<Events>>("emitter");
emitter?.on("updateDataTablePages", updateDataTablePages);
const theme = useTheme();
const showSiblings = isNull(localStorage.getItem("settings.showSiblings"))
  ? true
  : localStorage.getItem("settings.showSiblings") === "true";
const router = useRouter();
const downloadStore = storeDownload();
const romsStore = storeRoms();
const auth = storeAuth();
const page = ref(parseInt(window.location.hash.slice(1)) || 1);
const storedRomsPerPage = parseInt(localStorage.getItem("romsPerPage") ?? "");
const romsPerPage = ref(isNaN(storedRomsPerPage) ? 25 : storedRomsPerPage);
const pageCount = ref(0);
const PER_PAGE_OPTIONS = [10, 25, 50, 100];
const HEADERS = [
  {
    title: "Title",
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

// Functions
function rowClick(_: Event, row: { item: SimpleRom }) {
  router.push({ name: "rom", params: { rom: row.item.id } });
}

function updateDataTablePages() {
  pageCount.value = Math.ceil(
    romsStore.filteredRoms.length / romsPerPage.value
  );
}

function updateUrlHash() {
  window.location.hash = String(page.value);
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
    <template #item.name="{ item }">
      <td style="min-width: 400px">
        <v-list-item class="px-0">
          <template #prepend>
            <r-avatar
              :src="
                !item.igdb_id && !item.moby_id
                  ? `/assets/default/cover/small_${theme.global.name.value}_unmatched.png`
                  : item.has_cover
                  ? `/assets/romm/resources/${item.path_cover_s}`
                  : `/assets/default/cover/small_${theme.global.name.value}_missing_cover.png`
              "
            />
          </template>

          <span>{{ item.name }}</span>
          <template #append>
            <v-chip
              v-if="item.siblings && item.siblings.length > 0 && showSiblings"
              class="translucent-dark ml-2"
              size="x-small"
            >
              <span class="text-caption">+{{ item.siblings.length + 1 }}</span>
            </v-chip>
          </template>
        </v-list-item>
      </td>
    </template>
    <template #item.file_name="{ item }">
      <td style="min-width: 300px">
        <span>{{ item.file_name }}</span>
      </td>
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
      <v-btn-group divided density="compact">
        <v-btn
          :disabled="downloadStore.value.includes(item.id)"
          download
          size="small"
          @click.stop="romApi.downloadRom({ rom: item })"
        >
          <v-icon>mdi-download</v-icon>
        </v-btn>
        <v-btn
          v-if="isEmulationSupported(item.platform_slug)"
          size="small"
          :href="`/play/${item.id}`"
        >
          <v-icon>mdi-play</v-icon>
        </v-btn>
        <v-menu location="bottom">
          <template #activator="{ props }">
            <v-btn
              :disabled="!auth.scopes.includes('roms.write')"
              v-bind="props"
              size="small"
            >
              <v-icon>mdi-dots-vertical</v-icon>
            </v-btn>
          </template>
          <admin-menu :rom="item" />
        </v-menu>
      </v-btn-group>
    </template>

    <template #bottom>
      <v-divider />
      <v-row no-gutters class="pt-2 align-center justify-center">
        <v-col cols="12" sm="10" xl="11" class="px-6">
          <v-pagination
            v-model="page"
            @update:model-value="updateUrlHash"
            rounded="0"
            :show-first-last-page="true"
            active-color="romm-accent-1"
            :length="pageCount"
          />
        </v-col>
        <v-col cols="5" sm="2" xl="1">
          <v-select
            v-model="romsPerPage"
            class="pa-2"
            label="Roms per page"
            density="compact"
            variant="outlined"
            :items="PER_PAGE_OPTIONS"
            hide-details
          />
        </v-col>
      </v-row>
    </template>
  </v-data-table>
</template>

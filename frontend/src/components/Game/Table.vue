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
import { useRoute, useRouter } from "vue-router";
import { useDisplay, useTheme } from "vuetify";

// Props
const { xs } = useDisplay();
const emitter = inject<Emitter<Events>>("emitter");
emitter?.on("updateDataTablePages", updateDataTablePages);
const theme = useTheme();
const showSiblings = isNull(localStorage.getItem("settings.showSiblings"))
  ? true
  : localStorage.getItem("settings.showSiblings") === "true";
const router = useRouter();
const route = useRoute();
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

// Watch route to avoid race condition
watch(route, () => {
  page.value = parseInt(window.location.hash.slice(1)) || 1;
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
    fixed-header
    fixed-footer
    hide-default-footer
    hover
  >
    <template #item.name="{ item }">
      <td class="name-row">
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
          <v-row no-gutters
            ><v-col>{{ item.name }}</v-col></v-row
          >
          <v-row no-gutters
            ><v-col class="text-romm-accent-1">{{
              item.file_name
            }}</v-col></v-row
          >
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
    <template #item.file_size_bytes="{ item }">
      <v-chip size="x-small" label>{{
        formatBytes(item.file_size_bytes)
      }}</v-chip>
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
          @click.stop="
            $router.push({
              name: 'play',
              params: { rom: item?.id },
            })
          "
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
      <div>
        <v-row no-gutters class="pa-1 align-center justify-center">
          <v-col cols="8" sm="9" md="10" class="px-3">
            <v-pagination
              :show-first-last-page="!xs"
              v-model="page"
              @update:model-value="updateUrlHash"
              rounded="0"
              active-color="romm-accent-1"
              :length="pageCount"
            />
          </v-col>
          <v-col>
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
      </div>
    </template>
  </v-data-table>
</template>
<style scoped>
.name-row {
  min-width: 350px;
}
</style>

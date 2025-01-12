<script setup lang="ts">
import AdminMenu from "@/components/common/Game/AdminMenu.vue";
import FavBtn from "@/components/common/Game/FavBtn.vue";
import RAvatarRom from "@/components/common/Game/RAvatar.vue";
import romApi from "@/services/api/rom";
import storeDownload from "@/stores/download";
import storeRoms, { type SimpleRom } from "@/stores/roms";
import storeHeartbeat from "@/stores/heartbeat";
import type { Events } from "@/types/emitter";
import {
  formatBytes,
  isEJSEmulationSupported,
  isRuffleEmulationSupported,
  languageToEmoji,
  regionToEmoji,
} from "@/utils";
import { isNull } from "lodash";
import type { Emitter } from "mitt";
import { inject, onMounted, ref, watch, computed } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useDisplay } from "vuetify";
import { storeToRefs } from "pinia";

// Props
const { xs } = useDisplay();
const emitter = inject<Emitter<Events>>("emitter");
emitter?.on("updateDataTablePages", updateDataTablePages);
const showSiblings = isNull(localStorage.getItem("settings.showSiblings"))
  ? true
  : localStorage.getItem("settings.showSiblings") === "true";
const router = useRouter();
const route = useRoute();
const downloadStore = storeDownload();
const romsStore = storeRoms();
const { filteredRoms, selectedRoms } = storeToRefs(romsStore);
const heartbeatStore = storeHeartbeat();
const page = ref(parseInt(window.location.hash.slice(1)) || 1);
const storedRomsPerPage = parseInt(localStorage.getItem("romsPerPage") ?? "");
const itemsPerPage = ref(isNaN(storedRomsPerPage) ? 25 : storedRomsPerPage);
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
    title: "Added",
    align: "start",
    sortable: true,
    key: "created_at",
  },
  {
    title: "Released",
    align: "start",
    sortable: true,
    key: "first_release_date",
  },
  {
    title: "Rating",
    align: "start",
    sortable: true,
    key: "average_rating",
  },
  {
    title: "Languages",
    align: "start",
    sortable: false,
    key: "languages",
  },
  {
    title: "Regions",
    align: "start",
    sortable: false,
    key: "regions",
  },
  {
    title: "",
    align: "center",
    key: "actions",
    sortable: false,
  },
] as const;

const selectedRomIDs = computed(() => selectedRoms.value.map((rom) => rom.id));

// Functions
function rowClick(_: Event, row: { item: SimpleRom }) {
  router.push({ name: "rom", params: { rom: row.item.id } });
  romsStore.resetSelection();
}

function updateDataTablePages() {
  pageCount.value = Math.ceil(filteredRoms.value.length / itemsPerPage.value);
}

function updateUrlHash() {
  window.location.hash = String(page.value);
}

function checkIfEJSEmulationSupported(platformSlug: string) {
  return isEJSEmulationSupported(platformSlug, heartbeatStore.value);
}

function checkIfRuffleEmulationSupported(platformSlug: string) {
  return isRuffleEmulationSupported(platformSlug, heartbeatStore.value);
}

function updateSelectAll() {
  if (selectedRoms.value.length === filteredRoms.value.length) {
    romsStore.resetSelection();
  } else {
    romsStore.setSelection(filteredRoms.value);
  }
}

function updateSelectedRom(rom: SimpleRom) {
  if (selectedRomIDs.value.includes(rom.id)) {
    romsStore.removeFromSelection(rom);
  } else {
    romsStore.addToSelection(rom);
  }
}

watch(itemsPerPage, async () => {
  localStorage.setItem("romsPerPage", itemsPerPage.value.toString());
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
    :items-per-page="itemsPerPage"
    :items-per-page-options="PER_PAGE_OPTIONS"
    :item-value="(item: SimpleRom) => item"
    :items="filteredRoms"
    :headers="HEADERS"
    v-model="selectedRomIDs"
    v-model:page="page"
    show-select
    fixed-header
    fixed-footer
    hide-default-footer
    hover
    class="mx-2 my-1"
  >
    <template #header.data-table-select>
      <v-checkbox-btn
        :indeterminate="
          selectedRomIDs.length > 0 &&
          selectedRomIDs.length < filteredRoms.length
        "
        :model-value="selectedRomIDs.length === filteredRoms.length"
        @click.stop
        @click="updateSelectAll"
      />
    </template>
    <template #item.data-table-select="{ item }">
      <v-checkbox-btn
        :model-value="selectedRomIDs.includes(item.id)"
        @click.stop
        @click="updateSelectedRom(item)"
      />
    </template>
    <template #item.name="{ item }">
      <td>
        <v-list-item :min-width="400" class="px-0 py-2">
          <template #prepend>
            <r-avatar-rom :rom="item" />
          </template>
          <v-row no-gutters>
            <v-col>{{ item.name }}</v-col>
          </v-row>
          <v-row no-gutters>
            <v-col class="text-primary">
              {{ item.file_name }}
            </v-col>
          </v-row>
          <template #append>
            <v-chip
              v-if="
                item.sibling_roms &&
                item.sibling_roms.length > 0 &&
                showSiblings
              "
              class="translucent-dark ml-4"
              size="x-small"
            >
              <span class="text-caption">+{{ item.sibling_roms.length }}</span>
            </v-chip>
          </template>
        </v-list-item>
      </td>
    </template>
    <template #item.file_size_bytes="{ item }">
      <span class="text-no-wrap">{{ formatBytes(item.file_size_bytes) }}</span>
    </template>
    <template #item.created_at="{ item }">
      <span v-if="item.created_at" class="text-no-wrap">{{
        new Date(item.created_at).toLocaleDateString("en-US", {
          day: "2-digit",
          month: "short",
          year: "numeric",
        })
      }}</span>
      <span v-else>-</span>
    </template>
    <template #item.first_release_date="{ item }">
      <span v-if="item.first_release_date" class="text-no-wrap">{{
        new Date(item.first_release_date).toLocaleDateString("en-US", {
          day: "2-digit",
          month: "short",
          year: "numeric",
        })
      }}</span>
      <span v-else>-</span>
    </template>
    <template #item.average_rating="{ item }">
      <span v-if="item.average_rating" class="text-no-wrap">{{
        Intl.NumberFormat("en-US", {
          maximumSignificantDigits: 3,
        }).format(item.average_rating)
      }}</span>
      <span v-else>-</span>
    </template>
    <template #item.languages="{ item }">
      <div class="text-no-wrap" v-if="item.languages.length > 0">
        <span
          class="emoji"
          v-for="language in item.languages.slice(0, 3)"
          :title="`Languages: ${item.languages.join(', ')}`"
          :class="{ 'emoji-collection': item.regions.length > 3 }"
        >
          {{ languageToEmoji(language) }}
        </span>
        <spa class="reglang-super">
          {{
            item.languages.length > 3
              ? `&nbsp;+${item.languages.length - 3}`
              : ""
          }}
        </spa>
      </div>
      <span v-else>-</span>
    </template>
    <template #item.regions="{ item }">
      <div class="text-no-wrap" v-if="item.regions.length > 0">
        <span
          class="emoji"
          v-for="region in item.regions.slice(0, 3)"
          :title="`Regions: ${item.regions.join(', ')}`"
          :class="{ 'emoji-collection': item.regions.length > 3 }"
        >
          {{ regionToEmoji(region) }}
        </span>
        <spa class="reglang-super">
          {{
            item.regions.length > 3 ? `&nbsp;+${item.regions.length - 3}` : ""
          }}
        </spa>
      </div>
      <span v-else>-</span>
    </template>
    <template #item.actions="{ item }">
      <v-btn-group density="compact">
        <fav-btn :rom="item" />
        <v-btn
          :disabled="downloadStore.value.includes(item.id)"
          download
          size="small"
          @click.stop="romApi.downloadRom({ rom: item })"
        >
          <v-icon>mdi-download</v-icon>
        </v-btn>
        <v-btn
          v-if="checkIfEJSEmulationSupported(item.platform_slug)"
          size="small"
          @click.stop="
            $router.push({
              name: 'emulatorjs',
              params: { rom: item?.id },
            })
          "
        >
          <v-icon>mdi-play</v-icon>
        </v-btn>
        <v-btn
          v-if="checkIfRuffleEmulationSupported(item.platform_slug)"
          size="small"
          @click.stop="
            $router.push({
              name: 'ruffle',
              params: { rom: item?.id },
            })
          "
        >
          <v-icon>mdi-play</v-icon>
        </v-btn>
        <v-menu location="bottom">
          <template #activator="{ props }">
            <v-btn v-bind="props" size="small">
              <v-icon>mdi-dots-vertical</v-icon>
            </v-btn>
          </template>
          <admin-menu :rom="item" />
        </v-menu>
      </v-btn-group>
    </template>

    <template #bottom>
      <tfoot class="bg-surface border-t-sm position-sticky bottom-0">
        <v-row no-gutters class="pa-1 align-center justify-center">
          <v-col cols="8" sm="9" md="10" class="px-3">
            <v-pagination
              :show-first-last-page="!xs"
              v-model="page"
              @update:model-value="updateUrlHash"
              active-color="primary"
              :length="pageCount"
            />
          </v-col>
          <v-col>
            <v-select
              v-model="itemsPerPage"
              class="pa-2"
              label="Roms per page"
              density="compact"
              variant="outlined"
              :items="PER_PAGE_OPTIONS"
              hide-details
            />
          </v-col>
        </v-row>
      </tfoot>
    </template>
  </v-data-table>
</template>

<style scoped>
.reglang-super {
  vertical-align: super;
  font-size: 75%;
  opacity: 75%;
}
</style>

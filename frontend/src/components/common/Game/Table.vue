<script setup lang="ts">
import PlatformIcon from "@/components/common/Platform/Icon.vue";
import AdminMenu from "@/components/common/Game/AdminMenu.vue";
import FavBtn from "@/components/common/Game/FavBtn.vue";
import RAvatarRom from "@/components/common/Game/RAvatar.vue";
import romApi from "@/services/api/rom";
import storeConfig from "@/stores/config";
import storeDownload from "@/stores/download";
import storeHeartbeat from "@/stores/heartbeat";
import storeAuth from "@/stores/auth";
import storeGalleryFilter from "@/stores/galleryFilter";
import storeRoms, { type SimpleRom } from "@/stores/roms";
import {
  formatBytes,
  isEJSEmulationSupported,
  isRuffleEmulationSupported,
  languageToEmoji,
  regionToEmoji,
} from "@/utils";
import { ROUTES } from "@/plugins/router";
import { isNull } from "lodash";
import { storeToRefs } from "pinia";
import { computed } from "vue";
import { useRouter } from "vue-router";

// Props
withDefaults(
  defineProps<{
    showPlatformIcon?: boolean;
  }>(),
  {
    showPlatformIcon: false,
  },
);
const showSiblings = isNull(localStorage.getItem("settings.showSiblings"))
  ? true
  : localStorage.getItem("settings.showSiblings") === "true";
const router = useRouter();
const downloadStore = storeDownload();
const romsStore = storeRoms();
const { filteredRoms, selectedRoms, fetchingRoms, fetchTotalRoms } =
  storeToRefs(romsStore);
const heartbeatStore = storeHeartbeat();
const configStore = storeConfig();
const { config } = storeToRefs(configStore);
const auth = storeAuth();
const galleryFilterStore = storeGalleryFilter();

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
    key: "fs_size_bytes",
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
  router.push({ name: ROUTES.ROM, params: { rom: row.item.id } });
  romsStore.resetSelection();
}

function getTruePlatformSlug(platformSlug: string) {
  return platformSlug in config.value.PLATFORMS_VERSIONS
    ? config.value.PLATFORMS_VERSIONS[platformSlug]
    : platformSlug;
}

function checkIfEJSEmulationSupported(platformSlug: string) {
  const slug = getTruePlatformSlug(platformSlug);
  return isEJSEmulationSupported(slug, heartbeatStore.value);
}

function checkIfRuffleEmulationSupported(platformSlug: string) {
  const slug = getTruePlatformSlug(platformSlug);
  return isRuffleEmulationSupported(slug, heartbeatStore.value);
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

type SortBy = { key: keyof SimpleRom; order: "asc" | "desc" }[];

function updateOptions({ sortBy }: { sortBy: SortBy }) {
  if (!sortBy[0]) return;
  const { key, order } = sortBy[0];

  romsStore.resetPagination();
  romsStore.setOrderBy(key);
  romsStore.setOrderDir(order);
  romsStore.fetchRoms(galleryFilterStore, false);
}
</script>

<template>
  <v-data-table-server
    @update:options="updateOptions"
    @click:row="rowClick"
    :items-per-page="72"
    :items-length="fetchTotalRoms"
    :items="filteredRoms"
    :headers="HEADERS"
    v-model="selectedRomIDs"
    show-select
    fixed-header
    fixed-footer
    hide-default-footer
    :loading="fetchingRoms"
    :disable-sort="fetchingRoms"
    hover
    density="compact"
    class="rounded bg-background"
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
      <v-list-item :min-width="400" class="px-0 py-2">
        <template #prepend>
          <platform-icon
            v-if="showPlatformIcon"
            class="mr-4"
            :size="30"
            :slug="item.platform_slug"
          />
          <r-avatar-rom :rom="item" />
        </template>
        <v-row no-gutters>
          <v-col>{{ item.name }}</v-col>
        </v-row>
        <v-row no-gutters>
          <v-col class="text-primary">
            {{ item.fs_name }}
          </v-col>
        </v-row>
        <template #append>
          <v-chip
            v-if="item.siblings.length > 0 && showSiblings"
            class="translucent-dark ml-4"
            size="x-small"
          >
            <span class="text-caption">+{{ item.siblings.length }}</span>
          </v-chip>
        </template>
      </v-list-item>
    </template>
    <template #item.fs_size_bytes="{ item }">
      <span class="text-no-wrap">{{ formatBytes(item.fs_size_bytes) }}</span>
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
      <span v-if="item.metadatum.first_release_date" class="text-no-wrap">{{
        new Date(item.metadatum.first_release_date).toLocaleDateString(
          "en-US",
          {
            day: "2-digit",
            month: "short",
            year: "numeric",
          },
        )
      }}</span>
      <span v-else>-</span>
    </template>
    <template #item.average_rating="{ item }">
      <span v-if="item.metadatum.average_rating" class="text-no-wrap">{{
        Intl.NumberFormat("en-US", {
          maximumSignificantDigits: 3,
        }).format(item.metadatum.average_rating)
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
        <span class="reglang-super">
          {{
            item.languages.length > 3
              ? `&nbsp;+${item.languages.length - 3}`
              : ""
          }}
        </span>
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
        <span class="reglang-super">
          {{
            item.regions.length > 3 ? `&nbsp;+${item.regions.length - 3}` : ""
          }}
        </span>
      </div>
      <span v-else>-</span>
    </template>
    <template #item.actions="{ item }">
      <v-btn-group density="compact">
        <fav-btn :rom="item" />
        <v-btn
          :disabled="downloadStore.value.includes(item.id)"
          download
          variant="text"
          size="small"
          @click.stop="romApi.downloadRom({ rom: item })"
        >
          <v-icon>mdi-download</v-icon>
        </v-btn>
        <v-btn
          v-if="checkIfEJSEmulationSupported(item.platform_slug)"
          variant="text"
          size="small"
          @click.stop="
            $router.push({
              name: ROUTES.EMULATORJS,
              params: { rom: item?.id },
            })
          "
        >
          <v-icon>mdi-play</v-icon>
        </v-btn>
        <v-btn
          v-if="checkIfRuffleEmulationSupported(item.platform_slug)"
          variant="text"
          size="small"
          @click.stop="
            $router.push({
              name: ROUTES.RUFFLE,
              params: { rom: item?.id },
            })
          "
        >
          <v-icon>mdi-play</v-icon>
        </v-btn>
        <v-menu
          v-if="
            auth.scopes.includes('roms.write') ||
            auth.scopes.includes('roms.user.write') ||
            auth.scopes.includes('collections.write')
          "
          location="bottom"
        >
          <template #activator="{ props }">
            <v-btn v-bind="props" variant="text" size="small">
              <v-icon>mdi-dots-vertical</v-icon>
            </v-btn>
          </template>
          <admin-menu :rom="item" />
        </v-menu>
      </v-btn-group>
    </template>
  </v-data-table-server>
</template>

<style scoped>
.reglang-super {
  vertical-align: super;
  font-size: 75%;
  opacity: 75%;
}
.v-data-table {
  width: calc(100% - 16px) !important;
}
</style>

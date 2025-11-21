<script setup lang="ts">
import { useLocalStorage } from "@vueuse/core";
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { computed, inject } from "vue";
import { useRouter } from "vue-router";
import AdminMenu from "@/components/common/Game/AdminMenu.vue";
import PlayBtn from "@/components/common/Game/PlayBtn.vue";
import RAvatarRom from "@/components/common/Game/RAvatar.vue";
import MissingFromFSIcon from "@/components/common/MissingFromFSIcon.vue";
import PlatformIcon from "@/components/common/Platform/PlatformIcon.vue";
import { ROUTES } from "@/plugins/router";
import romApi from "@/services/api/rom";
import storeAuth from "@/stores/auth";
import storeCollections from "@/stores/collections";
import storeDownload from "@/stores/download";
import storeGalleryFilter from "@/stores/galleryFilter";
import storeRoms, { type SimpleRom } from "@/stores/roms";
import type { Events } from "@/types/emitter";
import { formatBytes, languageToEmoji, regionToEmoji } from "@/utils";

withDefaults(
  defineProps<{
    showPlatformIcon?: boolean;
  }>(),
  {
    showPlatformIcon: false,
  },
);
const showSiblings = useLocalStorage("settings.showSiblings", true);
const router = useRouter();
const downloadStore = storeDownload();
const romsStore = storeRoms();
const { filteredRoms, selectedRoms, fetchingRoms, fetchTotalRoms } =
  storeToRefs(romsStore);
const auth = storeAuth();
const galleryFilterStore = storeGalleryFilter();
const collectionsStore = storeCollections();
const emitter = inject<Emitter<Events>>("emitter");

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
    title: "⭐",
    align: "start",
    sortable: true,
    key: "average_rating",
  },
  {
    title: "🔠",
    align: "start",
    sortable: false,
    key: "languages",
  },
  {
    title: "🌎",
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

function hasNotes(item: SimpleRom): boolean {
  // TODO: Add note count to SimpleRom or check all_user_notes
  // For now, return false until we implement proper note counting
  return false;
}

function showNoteDialog(event: MouseEvent | KeyboardEvent, item: SimpleRom) {
  event.preventDefault();
  emitter?.emit("showNoteDialog", item);
}

function rowClick(_: Event, row: { item: SimpleRom }) {
  router.push({ name: ROUTES.ROM, params: { rom: row.item.id } });
  romsStore.resetSelection();
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
  romsStore.fetchRoms({ galleryFilter: galleryFilterStore });
}
</script>

<template>
  <v-data-table-server
    v-model="selectedRomIDs"
    :items-per-page="72"
    :items-length="fetchTotalRoms"
    :items="filteredRoms"
    :headers="HEADERS"
    show-select
    fixed-header
    fixed-footer
    hide-default-footer
    :loading="fetchingRoms"
    :disable-sort="fetchingRoms"
    hover
    density="compact"
    class="rounded bg-background"
    @update:options="updateOptions"
    @click:row="rowClick"
  >
    <template #header.data-table-select>
      <v-checkbox-btn
        :indeterminate="
          selectedRomIDs.length > 0 &&
          selectedRomIDs.length < filteredRoms.length
        "
        :model-value="selectedRomIDs.length === filteredRoms.length"
        @click.stop="updateSelectAll"
      />
    </template>
    <template #item="{ item }">
      <router-link
        :to="{ name: ROUTES.ROM, params: { rom: item.id } }"
        class="game-list-table-row d-table-row"
      >
        <div class="game-list-table-cell d-table-cell px-4">
          <v-checkbox-btn
            :model-value="selectedRomIDs.includes(item.id)"
            @click.stop="updateSelectedRom(item)"
          />
        </div>
        <div class="game-list-table-cell d-table-cell px-4">
          <v-list-item :min-width="400" class="px-0 py-2 d-flex game-list-item">
            <template #prepend>
              <PlatformIcon
                v-if="showPlatformIcon"
                class="mr-4"
                :size="30"
                :slug="item.platform_slug"
                :fs-slug="item.platform_fs_slug"
              />
              <RAvatarRom :rom="item" />
            </template>
            <v-row no-gutters>
              <v-col>
                {{ item.name }}
                <v-icon
                  v-if="collectionsStore.isFavorite(item)"
                  size="small"
                  color="primary"
                  class="ml-1"
                >
                  mdi-star
                </v-icon>
              </v-col>
            </v-row>
            <v-row no-gutters>
              <v-col class="text-primary">
                {{ item.fs_name }}
              </v-col>
            </v-row>
            <template #append>
              <v-chip
                v-if="item.hasheous_id"
                class="bg-romm-green text-white mr-1 px-1 item-chip"
                size="x-small"
                title="Verified with Hasheous"
              >
                <v-icon>mdi-check-decagram-outline</v-icon>
              </v-chip>
              <v-chip
                v-if="item.igdb_id"
                class="mr-1 pa-0 item-chip"
                size="x-small"
                title="IGDB match"
              >
                <v-avatar variant="text" size="20" rounded>
                  <v-img src="/assets/scrappers/igdb.png" />
                </v-avatar>
              </v-chip>
              <v-chip
                v-if="item.ss_id"
                class="mr-1 pa-0 item-chip"
                size="x-small"
                title="ScreenScraper match"
              >
                <v-avatar variant="text" size="20" rounded>
                  <v-img src="/assets/scrappers/ss.png" />
                </v-avatar>
              </v-chip>
              <v-chip
                v-if="item.moby_id"
                class="mr-1 pa-0 item-chip"
                size="x-small"
                title="MobyGames match"
              >
                <v-avatar variant="text" size="20" rounded>
                  <v-img src="/assets/scrappers/moby.png" />
                </v-avatar>
              </v-chip>
              <v-chip
                v-if="item.launchbox_id"
                class="mr-1 pa-0 item-chip"
                size="x-small"
                title="LaunchBox match"
              >
                <v-avatar variant="text" size="20" style="background: #185a7c">
                  <v-img src="/assets/scrappers/launchbox.png" />
                </v-avatar>
              </v-chip>
              <v-chip
                v-if="item.ra_id"
                class="mr-1 pa-0 item-chip"
                size="x-small"
                title="RetroAchievements match"
              >
                <v-avatar variant="text" size="20" rounded>
                  <v-img src="/assets/scrappers/ra.png" />
                </v-avatar>
              </v-chip>
              <v-chip
                v-if="item.flashpoint_id"
                class="mr-1 pa-0 item-chip"
                size="x-small"
                title="Flashpoint match"
              >
                <v-avatar variant="text" size="20" rounded>
                  <v-img src="/assets/scrappers/flashpoint.png" />
                </v-avatar>
              </v-chip>
              <v-chip
                v-if="item.hltb_id"
                class="mr-1 pa-0 item-chip"
                size="x-small"
                title="HowLongToBeat match"
              >
                <v-avatar variant="text" size="20" rounded>
                  <v-img src="/assets/scrappers/hltb.png" />
                </v-avatar>
              </v-chip>
              <v-chip
                v-if="item.gamelist_id"
                class="mr-1 pa-0 item-chip"
                size="x-small"
                title="ES-DE match"
              >
                <v-avatar variant="text" size="20" rounded>
                  <v-img src="/assets/scrappers/esde.png" />
                </v-avatar>
              </v-chip>
              <v-chip
                v-if="item.siblings.length > 0 && showSiblings"
                class="translucent text-white mr-1 px-1 item-chip"
                size="x-small"
                :title="`${item.siblings.length} sibling(s)`"
              >
                <v-icon>mdi-card-multiple-outline</v-icon>
              </v-chip>
              <v-chip
                v-if="hasNotes(item)"
                class="translucent text-white mr-1 px-1"
                chip
                size="x-small"
                title="View notes"
                @click.stop="showNoteDialog($event, item)"
              >
                <v-icon>mdi-notebook</v-icon>
              </v-chip>
              <MissingFromFSIcon
                v-if="item.missing_from_fs"
                :text="`Missing from filesystem: ${item.fs_path}/${item.fs_name}`"
                class="mr-1 px-1 item-chip"
                chip
                chip-size="x-small"
              />
            </template>
          </v-list-item>
        </div>
        <div class="game-list-table-cell d-table-cell px-4">
          <span class="text-no-wrap">{{
            formatBytes(item.fs_size_bytes)
          }}</span>
        </div>
        <div class="game-list-table-cell d-table-cell px-4">
          <span v-if="item.created_at" class="text-no-wrap">{{
            new Date(item.created_at).toLocaleDateString("en-US", {
              day: "2-digit",
              month: "short",
              year: "numeric",
            })
          }}</span>
          <span v-else>-</span>
        </div>
        <div class="game-list-table-cell d-table-cell px-4">
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
        </div>
        <div class="game-list-table-cell d-table-cell px-4">
          <span v-if="item.metadatum.average_rating" class="text-no-wrap">{{
            Intl.NumberFormat("en-US", {
              maximumSignificantDigits: 3,
            }).format(item.metadatum.average_rating)
          }}</span>
          <span v-else>-</span>
        </div>
        <div class="game-list-table-cell d-table-cell px-4">
          <div v-if="item.languages.length > 0" class="text-no-wrap">
            <span
              v-for="language in item.languages.slice(0, 3)"
              :key="language"
              class="emoji"
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
        </div>
        <div class="game-list-table-cell d-table-cell px-4">
          <div v-if="item.regions.length > 0" class="text-no-wrap">
            <span
              v-for="region in item.regions.slice(0, 3)"
              :key="region"
              class="emoji"
              :title="`Regions: ${item.regions.join(', ')}`"
              :class="{ 'emoji-collection': item.regions.length > 3 }"
            >
              {{ regionToEmoji(region) }}
            </span>
            <span class="reglang-super">
              {{
                item.regions.length > 3
                  ? `&nbsp;+${item.regions.length - 3}`
                  : ""
              }}
            </span>
          </div>
          <span v-else>-</span>
        </div>
        <div class="game-list-table-cell d-table-cell px-4">
          <v-btn-group density="compact">
            <v-btn
              :disabled="
                downloadStore.value.includes(item.id) || item.missing_from_fs
              "
              download
              variant="text"
              size="small"
              @click.prevent="romApi.downloadRom({ rom: item })"
            >
              <v-icon>mdi-download</v-icon>
            </v-btn>
            <PlayBtn :rom="item" variant="text" size="small" @click.prevent />
            <v-menu
              v-if="
                auth.scopes.includes('roms.write') ||
                auth.scopes.includes('roms.user.write') ||
                auth.scopes.includes('collections.write')
              "
              location="bottom"
              @click.prevent
            >
              <template #activator="{ props }">
                <v-btn
                  v-bind="props"
                  variant="text"
                  size="small"
                  @click.prevent
                >
                  <v-icon>mdi-dots-vertical</v-icon>
                </v-btn>
              </template>
              <AdminMenu :rom="item" />
            </v-menu>
          </v-btn-group>
        </div>
      </router-link>
    </template>
  </v-data-table-server>
</template>

<style scoped>
.game-list-table-row:hover {
  background-color: rgba(var(--v-theme-surface-variant), 0.08);
}

.game-list-table-cell {
  vertical-align: middle;
  border-bottom: thin solid rgba(var(--v-border-color), var(--v-border-opacity));
}

.reglang-super {
  vertical-align: super;
  font-size: 75%;
  opacity: 75%;
}

@media (max-width: 2160px) {
  .item-chip {
    transform: scale(-1, 1);
  }
}
</style>

<style>
.game-list-item .v-list-item__append {
  margin-left: auto;
  display: grid;
  grid-template-rows: 24px;
  grid-auto-flow: column;
  flex-shrink: 0;
}

@media (max-width: 2160px) {
  .game-list-item .v-list-item__append {
    grid-template-rows: 24px 24px;
    transform: scale(-1, 1);
  }
}

.game-list-item .v-list-item__append .v-list-item__spacer {
  display: none;
}
</style>

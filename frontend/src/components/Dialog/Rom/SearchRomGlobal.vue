<script setup lang="ts">
import type { RomSchema } from "@/__generated__";
import PlatformIcon from "@/components/Platform/PlatformIcon.vue";
import romApi from "@/services/api/rom";
import storeGalleryView from "@/stores/galleryView";
import type { Events } from "@/types/emitter";
import { languageToEmoji, regionToEmoji } from "@/utils";
import { identity, isNull } from "lodash";
import type { Emitter } from "mitt";
import { inject, onBeforeUnmount, ref } from "vue";
import { useRouter } from "vue-router";
import { useDisplay, useTheme } from "vuetify";

const theme = useTheme();
const { xs, mdAndDown, lgAndUp } = useDisplay();
const galleryViewStore = storeGalleryView();
const show = ref(false);
const searching = ref(false);
const router = useRouter();
const searchedRoms = ref();
const filteredRoms = ref();
const platforms = ref();
const selectedPlatform = ref();
const searchValue = ref("");
const showRegions = isNull(localStorage.getItem("settings.showRegions"))
  ? true
  : localStorage.getItem("settings.showRegions") === "true";
const showLanguages = isNull(localStorage.getItem("settings.showLanguages"))
  ? true
  : localStorage.getItem("settings.showLanguages") === "true";
const showSiblings = isNull(localStorage.getItem("settings.showSiblings"))
  ? true
  : localStorage.getItem("settings.showSiblings") === "true";

const emitter = inject<Emitter<Events>>("emitter");
emitter?.on("showSearchRomGlobalDialog", () => {
  show.value = true;
});

function clearFilter() {
  selectedPlatform.value = null;
}

async function searchRoms() {
  // Auto hide android keyboard
  const inputElement = document.getElementById("search-text-field");
  inputElement?.blur();
  searching.value = true;
  searchedRoms.value = (
    await romApi.getRoms({ searchTerm: searchValue.value, size: 250 })
  ).data.items.sort((a, b) => {
    return a.platform_name.localeCompare(b.platform_name);
  });
  platforms.value = [
    ...new Set(
      searchedRoms.value.map(
        (rom: { platform_name: string }) => rom.platform_name
      )
    ),
  ];
  filterRoms();
  searching.value = false;
}

async function filterRoms() {
  if (!selectedPlatform.value) {
    filteredRoms.value = searchedRoms.value;
  } else {
    filteredRoms.value = searchedRoms.value.filter(
      (rom: { platform_name: string }) =>
        rom.platform_name == selectedPlatform.value
    );
  }
}

function romDetails(rom: RomSchema) {
  router.push({
    name: "rom",
    params: { rom: rom.id },
  });
  closeDialog();
}

function closeDialog() {
  show.value = false;
}

onBeforeUnmount(() => {
  emitter?.off("showSearchRomGlobalDialog");
});
</script>

<template>
  <v-dialog
    :modelValue="show"
    scroll-strategy="none"
    width="auto"
    :scrim="true"
    @click:outside="closeDialog"
    @keydown.esc="closeDialog"
    no-click-animation
    persistent
  >
    <v-card
      :class="{
        'search-content': lgAndUp,
        'search-content-tablet': mdAndDown,
        'search-content-mobile': xs,
      }"
      rounded="0"
    >
      <v-toolbar density="compact" class="bg-terciary">
        <v-row class="align-center" no-gutters>
          <v-col cols="10" xs="10" sm="11" md="11" lg="11">
            <v-icon icon="mdi-magnify" class="ml-5" />
            <v-avatar :rounded="0" :size="30" class="mx-4"
              ><v-img src="/assets/isotipo.svg"
            /></v-avatar>
          </v-col>
          <v-col cols="2" xs="2" sm="1" md="1" lg="1">
            <v-btn
              @click="closeDialog"
              rounded="0"
              variant="text"
              icon="mdi-close"
              block
            />
          </v-col>
        </v-row>
      </v-toolbar>

      <v-divider class="border-opacity-25" :thickness="1" />

      <v-toolbar density="compact" class="bg-primary">
        <v-row class="align-center" no-gutters>
          <v-col cols="6" xs="6" sm="6" md="6" lg="7">
            <v-text-field
              autofocus
              id="search-text-field"
              @keyup.enter="searchRoms"
              @click:clear="searchRoms"
              v-model="searchValue"
              label="Search"
              hide-details
              class="bg-terciary"
              clearable
            />
          </v-col>
          <v-col cols="4" xs="4" sm="5" md="5" lg="4">
            <v-select
              @click:clear="clearFilter"
              clearable
              label="Platform"
              class="bg-terciary"
              hide-details
              v-model="selectedPlatform"
              @update:model-value="filterRoms"
              :items="platforms"
            >
            </v-select>
          </v-col>
          <v-col cols="2" xs="2" sm="1" md="1" lg="1">
            <v-btn
              type="submit"
              @click="searchRoms"
              class="bg-terciary"
              rounded="0"
              variant="text"
              icon="mdi-magnify"
              block
              :disabled="searching"
            />
          </v-col>
        </v-row>
      </v-toolbar>

      <v-divider class="border-opacity-25" :thickness="1" />

      <v-card-text class="pa-1 scroll">
        <v-row
          class="justify-center align-center loader-searching fill-height"
          v-show="searching"
          no-gutters
        >
          <v-progress-circular
            :width="2"
            :size="40"
            color="romm-accent-1"
            indeterminate
          />
        </v-row>
        <v-row
          class="justify-center align-center loader-searching fill-height"
          v-show="!searching && searchedRoms?.length == 0"
          no-gutters
        >
          <span>No results found</span>
        </v-row>
        <v-row no-gutters>
          <v-col
            class="pa-1"
            cols="4"
            sm="2"
            md="2"
            lg="2"
            xl="2"
            v-show="!searching"
            v-for="rom in filteredRoms"
          >
            <v-hover v-slot="{ isHovering, props }">
              <v-card
                @click="romDetails(rom)"
                v-bind="props"
                class="matched-rom"
                :class="{ 'on-hover': isHovering }"
                :elevation="isHovering ? 20 : 3"
              >
                <v-hover v-slot="{ isHovering, props }" open-delay="800">
                  <v-img
                    v-bind="props"
                    :src="
                      !rom.igdb_id && !rom.has_cover
                        ? `/assets/default/cover/big_${theme.global.name.value}_unmatched.png`
                        : !rom.has_cover
                        ? `/assets/default/cover/big_${theme.global.name.value}_missing_cover.png`
                        : `/assets/romm/resources/${rom.path_cover_l}`
                    "
                    :lazy-src="
                      !rom.igdb_id && !rom.has_cover
                        ? `/assets/default/cover/small_${theme.global.name.value}_unmatched.png`
                        : !rom.has_cover
                        ? `/assets/default/cover/small_${theme.global.name.value}_missing_cover.png`
                        : `/assets/romm/resources/${rom.path_cover_s}`
                    "
                    :aspect-ratio="3 / 4"
                  >
                    <template v-slot:placeholder>
                      <div
                        class="d-flex align-center justify-center fill-height"
                      >
                        <v-progress-circular
                          color="romm-accent-1"
                          :width="2"
                          indeterminate
                        />
                      </div>
                    </template>
                    <v-expand-transition>
                      <div
                        v-if="isHovering || !rom.has_cover"
                        class="translucent text-caption"
                        :class="{
                          'text-truncate':
                            galleryViewStore.current == 0 && !isHovering,
                        }"
                      >
                        <v-list-item>{{ rom.name }}</v-list-item>
                      </div>
                    </v-expand-transition>
                    <v-row no-gutters class="text-white px-1">
                      <v-chip
                        v-if="
                          rom.regions.filter(identity).length > 0 && showRegions
                        "
                        :title="`Regions: ${rom.regions.join(', ')}`"
                        class="translucent mr-1 mt-1 px-1"
                        :class="{ 'emoji-collection': rom.regions.length > 3 }"
                        density="compact"
                      >
                        <span
                          class="emoji"
                          v-for="region in rom.regions.slice(0, 3)"
                        >
                          {{ regionToEmoji(region) }}
                        </span>
                      </v-chip>
                      <v-chip
                        v-if="
                          rom.languages.filter(identity).length > 0 &&
                          showLanguages
                        "
                        :title="`Languages: ${rom.languages.join(', ')}`"
                        class="translucent mr-1 mt-1 px-1"
                        :class="{
                          'emoji-collection': rom.languages.length > 3,
                        }"
                        density="compact"
                      >
                        <span
                          class="emoji"
                          v-for="language in rom.languages.slice(0, 3)"
                        >
                          {{ languageToEmoji(language) }}
                        </span>
                      </v-chip>
                      <v-chip
                        v-if="
                          rom.siblings &&
                          rom.siblings.length > 0 &&
                          showSiblings
                        "
                        :title="`${rom.siblings.length + 1} versions`"
                        class="translucent mr-1 mt-1"
                        density="compact"
                      >
                        +{{ rom.siblings.length }}
                      </v-chip>
                    </v-row></v-img
                  ></v-hover
                >
                <v-card-text>
                  <v-row class="pa-1 align-center">
                    <v-col class="pa-0 ml-1 text-truncate">
                      <span>{{ rom.name }}</span>
                    </v-col>
                    <v-avatar :rounded="0" size="20" class="ml-2">
                      <platform-icon
                        :key="rom.platform_slug"
                        :slug="rom.platform_slug"
                      />
                    </v-avatar>
                  </v-row>
                </v-card-text>
              </v-card>
            </v-hover>
          </v-col>
        </v-row>
      </v-card-text>
    </v-card>
  </v-dialog>
</template>

<style scoped>
.tooltip :deep(.v-overlay__content) {
  background: rgba(201, 201, 201, 0.98) !important;
  color: rgb(41, 41, 41) !important;
}
.scroll {
  overflow-y: scroll;
}

.search-content {
  width: 60vw;
  height: 80vh;
}

.search-content-tablet {
  width: 75vw;
  height: 640px;
}

.search-content-mobile {
  width: 85vw;
  height: 640px;
}
.matched-rom {
  transition-property: all;
  transition-duration: 0.1s;
}
.matched-rom.on-hover {
  z-index: 1 !important;
  transform: scale(1.05);
}
.translucent {
  background: rgba(0, 0, 0, 0.35);
  backdrop-filter: blur(10px);
  text-shadow: 1px 1px 1px #000000, 0 0 1px #000000;
}

.emoji-collection {
  mask-image: linear-gradient(to right, black 0%, black 70%, transparent 100%);
}

.emoji {
  margin: 0 2px;
}
</style>

<script setup lang="ts">
import PlatformIcon from "@/components/Platform/PlatformIcon.vue";
import romApi from "@/services/api/rom";
import storeGalleryView from "@/stores/galleryView";
import type { Events } from "@/types/emitter";
import { languageToEmoji, regionToEmoji } from "@/utils";
import { identity, isNull } from "lodash";
import type { Emitter } from "mitt";
import GameCard from "@/components/Game/Card/Base.vue";
import GameCardFlags from "@/components/Game/Card/Flags.vue";
import { inject, onBeforeUnmount, ref } from "vue";
import { useRouter } from "vue-router";
import { useDisplay, useTheme } from "vuetify";
import { type SimpleRom } from "@/stores/roms";

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
emitter?.on("showSearchRomDialog", () => {
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
    await romApi.getRoms({ searchTerm: searchValue.value })
  ).data.sort((a, b) => {
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

function romDetails(rom: SimpleRom) {
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
  emitter?.off("showSearchRomDialog");
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
          <v-col cols="12" sm="5" md="6" lg="7">
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
          <template v-if="!xs">
            <v-col sm="5" lg="4">
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
            <v-col sm="2" md="1">
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
          </template>
        </v-row>
      </v-toolbar>

      <v-toolbar v-if="xs" density="compact" class="bg-primary">
        <v-row class="align-center" no-gutters>
          <v-col cols="10">
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
          <v-col cols="2">
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
            sm="3"
            md="2"
            v-show="!searching"
            v-for="rom in filteredRoms"
          >
            <game-card :rom="rom" title-on-hover transform-scale>
              <template #prepend-inner>
                <game-card-flags :rom="rom" />
              </template>
              <template #footer>
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
              </template>
            </game-card>
          </v-col>
        </v-row>
      </v-card-text>
    </v-card>
  </v-dialog>
</template>

<style scoped>
.search-content {
  width: 60vw;
  height: 80vh;
}

.search-content-tablet {
  width: 75vw;
  height: 775px;
}

.search-content-mobile {
  width: 85vw;
  height: 775px;
}
.matched-rom {
  transition-property: all;
  transition-duration: 0.1s;
}
.matched-rom.on-hover {
  z-index: 1 !important;
  transform: scale(1.05);
}
</style>

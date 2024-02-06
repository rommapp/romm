<script setup lang="ts">
import type { RomSchema } from "@/__generated__";
import PlatformIcon from "@/components/Platform/PlatformIcon.vue";
import romApi from "@/services/api/rom";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { inject, onBeforeUnmount, ref } from "vue";
import { useRouter } from "vue-router";
import { useDisplay, useTheme } from "vuetify";
const theme = useTheme();

const { xs, mdAndDown, lgAndUp } = useDisplay();
const show = ref(false);
const searching = ref(false);
const router = useRouter();
const searchedRoms = ref();
const filteredRoms = ref();
const platforms = ref();
const selectedPlatform = ref();
const searchValue = ref("");

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
                <v-tooltip
                  activator="parent"
                  location="top"
                  class="tooltip"
                  transition="fade-transition"
                  open-delay="1000"
                  >{{ rom.name }}</v-tooltip
                >
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
                />
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
  opacity: 1;
  transform: scale(1.05);
}
</style>

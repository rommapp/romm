<script setup lang="ts">
import GameCard from "@/components/common/Game/Card/Base.vue";
import PlatformIcon from "@/components/common/Platform/Icon.vue";
import RDialog from "@/components/common/RDialog.vue";
import romApi from "@/services/api/rom";
import type { SimpleRom } from "@/stores/roms";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { inject, onBeforeUnmount, ref } from "vue";
import { useRouter } from "vue-router";
import { useDisplay } from "vuetify";
import { useI18n } from "vue-i18n";

// Define types
type Platform = {
  platform_name: string;
  platform_slug: string;
};

type SelectItem = {
  raw: Platform;
};

// Props
const { t } = useI18n();
const { lgAndUp } = useDisplay();
const show = ref(false);
const searching = ref(false);
const searched = ref(false);
const router = useRouter();
const searchedRoms = ref<Platform[]>([]);
const filteredRoms = ref<SimpleRom[]>([]);
const platforms = ref<Platform[]>([]);
const selectedPlatform = ref<Platform | null>(null);
const searchValue = ref("");
const emitter = inject<Emitter<Events>>("emitter");
emitter?.on("showSearchRomDialog", () => {
  show.value = true;
});

async function filterRoms() {
  if (!selectedPlatform.value) {
    filteredRoms.value = searchedRoms.value as SimpleRom[];
  } else {
    filteredRoms.value = searchedRoms.value.filter(
      (rom: { platform_name: string }) =>
        rom.platform_name == selectedPlatform.value?.platform_name,
    ) as SimpleRom[];
  }
}

function clearFilter() {
  selectedPlatform.value = null;
  filterRoms();
}

async function searchRoms() {
  if (searchValue.value != "") {
    // Auto hide android keyboard
    const inputElement = document.getElementById("search-text-field");
    inputElement?.blur();
    searching.value = true;
    searched.value = true;
    searchedRoms.value = (
      await romApi.getRoms({ searchTerm: searchValue.value })
    ).data.sort((a, b) => {
      return a.platform_name.localeCompare(b.platform_name);
    });
    platforms.value = [
      ...new Map(
        searchedRoms.value.map((rom): [string, Platform] => [
          rom.platform_name,
          {
            platform_name: rom.platform_name,
            platform_slug: rom.platform_slug,
          },
        ]),
      ).values(),
    ];
    filterRoms();
    searching.value = false;
  }
}

function onGameClick(emitData: { rom: SimpleRom; event: MouseEvent }) {
  router.push({ name: "rom", params: { rom: emitData.rom.id } });
  closeDialog();
}

function closeDialog() {
  show.value = false;
  searched.value = false;
}

onBeforeUnmount(() => {
  emitter?.off("showSearchRomDialog");
});
</script>

<template>
  <r-dialog
    v-model="show"
    icon="mdi-magnify"
    :loading-condition="searching"
    :empty-state-condition="searchedRoms?.length == 0 && searched"
    empty-state-type="game"
    scroll-content
    :width="lgAndUp ? '60vw' : '95vw'"
    :height="lgAndUp ? '90vh' : '775px'"
  >
    <template #toolbar>
      <v-row class="align-center" no-gutters>
        <v-col cols="5" md="6" lg="7">
          <v-text-field
            autofocus
            id="search-text-field"
            @keyup.enter="searchRoms"
            @click:clear="searchRoms"
            v-model="searchValue"
            :disabled="searching"
            :label="t('common.search')"
            hide-details
            class="bg-terciary"
          />
        </v-col>
        <v-col cols="5" lg="4">
          <v-select
            @click:clear="clearFilter"
            :label="t('common.platform')"
            class="bg-terciary"
            item-title="platform_name"
            :disabled="platforms.length == 0 || searching"
            hide-details
            clearable
            single-line
            return-object
            v-model="selectedPlatform"
            @update:model-value="filterRoms"
            :items="platforms"
          >
            <template #item="{ props, item }">
              <v-list-item
                class="py-2"
                v-bind="props"
                :title="(item as SelectItem).raw.platform_name ?? ''"
              >
                <template #prepend>
                  <platform-icon
                    :size="35"
                    :key="(item as SelectItem).raw.platform_slug"
                    :slug="(item as SelectItem).raw.platform_slug"
                    :name="(item as SelectItem).raw.platform_name"
                  />
                </template>
              </v-list-item>
            </template>
            <template #selection="{ item }">
              <v-list-item
                class="px-0"
                :title="(item as SelectItem).raw.platform_name ?? ''"
              >
                <template #prepend>
                  <platform-icon
                    :size="35"
                    :key="(item as SelectItem).raw.platform_slug"
                    :slug="(item as SelectItem).raw.platform_slug"
                    :name="(item as SelectItem).raw.platform_name"
                  />
                </template>
              </v-list-item>
            </template>
          </v-select>
        </v-col>
        <v-col>
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
    </template>
    <template #content>
      <v-row no-gutters class="align-content-start align-center">
        <v-col
          class="pa-1 align-self-end"
          cols="4"
          sm="3"
          md="2"
          v-show="!searching"
          v-for="rom in filteredRoms"
        >
          <game-card
            :key="rom.updated_at"
            :rom="rom"
            @click="onGameClick({ rom, event: $event })"
            title-on-hover
            pointerOnHover
            withLink
            showFlags
            showFav
            transformScale
            showActionBar
            showPlatformIcon
          />
        </v-col>
      </v-row>
    </template>
  </r-dialog>
</template>

<script setup lang="ts">
import VersionSwitcher from "@/components/Details/VersionSwitcher.vue";
import RAvatar from "@/components/common/Collection/RAvatar.vue";
import romApi from "@/services/api/rom";
import storeAuth from "@/stores/auth";
import type { Collection } from "@/stores/collections";
import storeDownload from "@/stores/download";
import type { DetailedRom } from "@/stores/roms";
import { formatBytes } from "@/utils";
import { ref, watch } from "vue";

// Props
const props = defineProps<{ rom: DetailedRom }>();
const downloadStore = storeDownload();
const auth = storeAuth();
const romUser = ref(props.rom.rom_user);
const romInfo = ref([
  { label: "SHA-1", value: props.rom.sha1_hash },
  { label: "MD5", value: props.rom.md5_hash },
  { label: "CRC", value: props.rom.crc_hash },
]);

// Functions
function collectionsWithoutFavourites(collections: Collection[]) {
  return collections.filter((c) => c.name.toLowerCase() != "favourites");
}

async function toggleMainSibling() {
  romUser.value.is_main_sibling = !romUser.value.is_main_sibling;
  romApi.updateUserRomProps({
    romId: props.rom.id,
    data: romUser.value,
  });
}

watch(
  () => props.rom,
  async () => (romUser.value = props.rom.rom_user),
);
</script>
<template>
  <v-row no-gutters>
    <v-col>
      <v-row
        v-if="rom.sibling_roms && rom.sibling_roms.length > 0"
        class="align-center my-3"
        no-gutters
      >
        <v-col cols="3" xl="2">
          <span>Version</span>
        </v-col>
        <v-col>
          <v-row class="align-center" no-gutters>
            <version-switcher :rom="rom" />
            <v-tooltip
              location="top"
              class="tooltip"
              transition="fade-transition"
              text="Set as default version"
              open-delay="300"
            >
              <template #activator="{ props }">
                <v-btn
                  v-bind="props"
                  variant="flat"
                  rounded="0"
                  size="small"
                  class="ml-2"
                  @click="toggleMainSibling"
                  ><v-icon
                    :class="romUser.is_main_sibling ? '' : 'mr-1'"
                    :color="romUser.is_main_sibling ? 'romm-accent-1' : ''"
                    >{{
                      romUser.is_main_sibling
                        ? "mdi-checkbox-outline"
                        : "mdi-checkbox-blank-outline"
                    }}</v-icon
                  >{{ romUser.is_main_sibling ? "" : "Default" }}</v-btn
                >
              </template></v-tooltip
            >
          </v-row>
        </v-col>
      </v-row>
      <v-row v-if="!rom.multi" class="align-center my-3" no-gutters>
        <v-col cols="3" xl="2">
          <span>File</span>
        </v-col>
        <v-col>
          <span class="text-body-1">{{ rom.file_name }}</span>
        </v-col>
      </v-row>
      <v-row v-if="rom.multi" class="align-center my-3" no-gutters>
        <v-col cols="3" xl="2">
          <span>Files</span>
        </v-col>
        <v-col>
          <v-select
            v-model="downloadStore.filesToDownload"
            :label="rom.file_name"
            item-title="file_name"
            :items="rom.files.map((f) => f.filename)"
            rounded="0"
            density="compact"
            variant="outlined"
            return-object
            multiple
            hide-details
            clearable
            chips
          />
        </v-col>
      </v-row>
      <v-row no-gutters class="align-center my-3">
        <v-col cols="3" xl="2">
          <span>Info</span>
        </v-col>
        <v-col class="my-1">
          <v-chip size="small" class="my-1 mr-2" label>
            Size: {{ formatBytes(rom.file_size_bytes) }}
          </v-chip>
          <v-chip
            v-for="info in romInfo"
            v-if="!rom.multi && rom.sha1_hash"
            size="small"
            label
            class="my-1 mr-2"
            >{{ info.label }}: {{ info.value }}</v-chip
          >
        </v-col>
      </v-row>
      <v-row v-if="rom.tags.length > 0" class="align-center my-3" no-gutters>
        <v-col cols="3" xl="2">
          <span>Tags</span>
        </v-col>
        <v-col>
          <v-chip
            v-for="tag in rom.tags"
            :key="tag"
            size="small"
            class="mr-2"
            label
            color="romm-accent-1"
            variant="tonal"
          >
            {{ tag }}
          </v-chip>
        </v-col>
      </v-row>
      <v-row
        v-if="
          rom.user_collections &&
          collectionsWithoutFavourites(rom.user_collections).length > 0
        "
        no-gutters
        class="align-center my-3"
      >
        <v-col cols="3" xl="2">
          <span>Collections</span>
        </v-col>
        <v-col>
          <v-chip
            v-for="collection in collectionsWithoutFavourites(
              rom.user_collections,
            )"
            :to="{ name: 'collection', params: { collection: collection.id } }"
            size="large"
            class="mr-1 mt-1"
            label
          >
            <template #prepend>
              <r-avatar :size="25" :collection="collection" />
            </template>
            <span class="ml-2">{{ collection.name }}</span>
          </v-chip>
        </v-col>
      </v-row>
    </v-col>
  </v-row>
</template>

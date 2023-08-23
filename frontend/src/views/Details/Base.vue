<script setup>
import { ref, inject, onBeforeMount } from "vue";
import { useRoute } from "vue-router";
import { useDisplay } from "vuetify";
import { fetchRomApi, downloadRomApi } from "@/services/api";
import storeDownload from "@/stores/download";
import storeAuth from "@/stores/auth";
import BackgroundHeader from "@/components/Game/Details/BackgroundHeader.vue";
import AdminMenu from "@/components/AdminMenu/Base.vue";
import SearchRomDialog from "@/components/Dialog/Rom/SearchRom.vue";
import EditRomDialog from "@/components/Dialog/Rom/EditRom.vue";
import DeleteRomDialog from "@/components/Dialog/Rom/DeleteRom.vue";
import LoadingDialog from "@/components/Dialog/Loading.vue";

// Props
const route = useRoute();
const downloadStore = storeDownload();
const auth = storeAuth();
const rom = ref();
const updatedRom = ref();
const saveFiles = ref(false);
const filesToDownload = ref();
const tab = ref("details");
const downloadUrl = ref();
const { xs, mdAndDown, lgAndUp } = useDisplay();

// Event listeners bus
const emitter = inject("emitter");

// Functions
onBeforeMount(async () => {
  emitter.emit("showLoadingDialog", { loading: true, scrim: false });
  await fetchRomApi(route.params.platform, route.params.rom)
    .then((response) => {
      rom.value = response.data;
      updatedRom.value = response.data;
      downloadUrl.value = `${window.location.origin}${rom.value.download_path}`;
    })
    .catch((error) => {
      console.log(error);
    })
    .finally(() => {
      emitter.emit("showLoadingDialog", { loading: false, scrim: false });
    });
});
</script>

<template>
  <background-header v-if="rom" :image="rom.path_cover_s" />

  <div
    v-if="rom"
    :class="{
      content: lgAndUp,
      'content-tablet': mdAndDown,
      'content-mobile': xs,
    }"
  >
    <v-row class="pt-8 justify-center">
      <v-col
        :class="{
          cover: lgAndUp,
          'cover-tablet': mdAndDown,
          'cover-mobile': xs,
        }"
      >
        <v-row>
          <v-col>
            <v-card
              elevation="2"
              :loading="
                downloadStore.value.includes(rom.id)
                  ? 'romm-accent-1'
                  : null
              "
            >
              <v-img
                :src="`/assets/romm/resources/${rom.path_cover_l}`"
                :lazy-src="`/assets/romm/resources/${rom.path_cover_s}`"
                cover
              >
                <template v-slot:placeholder>
                  <div class="d-flex align-center justify-center fill-height">
                    <v-progress-circular
                      color="romm-accent-1"
                      :width="2"
                      :size="20"
                      indeterminate
                    />
                  </div>
                </template>
              </v-img>
            </v-card>
          </v-col>
        </v-row>
        <v-row class="px-3 action-buttons">
          <v-col class="pa-0">
            <template v-if="rom.multi">
              <v-btn
                @click="downloadRomApi(rom, filesToDownload)"
                :disabled="downloadStore.value.includes(rom.id)"
                rounded="0"
                color="primary"
                block
              >
                <v-icon icon="mdi-download" size="large" />
              </v-btn>
            </template>
            <template v-else>
              <v-btn
                :href="downloadUrl"
                download
                rounded="0"
                color="primary"
                block
              >
                <v-icon icon="mdi-download" size="large" />
              </v-btn>
            </template>
          </v-col>
          <v-col class="pa-0">
            <v-btn rounded="0" block :disabled="!saveFiles"
              ><v-icon icon="mdi-content-save-all" size="large"
            /></v-btn>
          </v-col>
          <v-col class="pa-0">
            <v-menu location="bottom">
              <template v-slot:activator="{ props }">
                <v-btn :disabled="!auth.scopes.includes('roms.write')" v-bind="props" rounded="0" block>
                  <v-icon icon="mdi-dots-vertical" size="large" />
                </v-btn>
              </template>
              <admin-menu :rom="rom" />
            </v-menu>
          </v-col>
        </v-row>
      </v-col>
      <v-col
        class="mt-10"
        :class="{ info: lgAndUp, 'info-tablet': mdAndDown, 'info-mobile': xs }"
      >
        <div class="text-white">
          <v-row no-gutters>
            <span class="text-h4 font-weight-bold rom-name">{{
              rom.r_name
            }}</span>
            <v-chip-group class="ml-3 mt-1 hidden-xs">
              <v-chip
                v-show="rom.region"
                size="x-small"
                class="bg-chip"
                label
                >{{ rom.region }}</v-chip
              >
              <v-chip
                v-show="rom.revision"
                size="x-small"
                class="bg-chip"
                label
                >{{ rom.revision }}</v-chip
              >
            </v-chip-group>
          </v-row>
          <v-row no-gutters class="align-center">
            <span class="font-italic mt-1 rom-platform">{{
              rom.p_name || rom.p_slug
            }}</span>
            <v-chip-group class="ml-3 mt-1 hidden-sm-and-up">
              <v-chip
                v-show="rom.region"
                size="x-small"
                class="bg-chip"
                label
                >{{ rom.region }}</v-chip
              >
              <v-chip
                v-show="rom.revision"
                size="x-small"
                class="bg-chip"
                label
                >{{ rom.revision }}</v-chip
              >
            </v-chip-group>
          </v-row>
        </div>
        <div
          :class="{
            'details-content': lgAndUp,
            'details-content-tablet': mdAndDown,
            'details-content-mobile': xs,
          }"
        >
          <v-tabs v-model="tab" slider-color="romm-accent-1" rounded="0">
            <v-tab value="details" rounded="0">Details</v-tab>
            <v-tab value="saves" rounded="0" disabled
              >Saves<span class="text-caption text-truncate ml-1"
                >[coming soon]</span
              ></v-tab
            >
            <v-tab
              v-if="rom.path_screenshots.length > 0"
              value="screenshots"
              rounded="0"
              >Screenshots</v-tab
            >
          </v-tabs>
          <v-window v-model="tab" class="mt-2">
            <v-window-item value="details">
              <v-row
                v-if="!rom.multi"
                class="d-flex align-center text-body-1 mt-0"
              >
                <v-col
                  cols="3"
                  xs="3"
                  sm="2"
                  md="2"
                  lg="2"
                  class="font-weight-medium"
                  ><span>File</span></v-col
                >
                <v-col class="text-body-1"
                  ><span>{{ rom.file_name }}</span></v-col
                >
              </v-row>
              <v-row
                v-if="rom.multi"
                class="d-flex align-center text-body-1 mt-0"
              >
                <v-col
                  cols="3"
                  xs="3"
                  sm="2"
                  md="2"
                  lg="2"
                  class="font-weight-medium"
                  ><span>Files</span></v-col
                >
                <v-col
                  ><v-select
                    :label="rom.file_name"
                    item-title="file_name"
                    v-model="filesToDownload"
                    :items="rom.files"
                    class="my-2"
                    density="compact"
                    variant="outlined"
                    return-object
                    multiple
                    hide-details
                    clearable
                    chips
                /></v-col>
              </v-row>
              <v-row class="d-flex align-center text-body-1 mt-0">
                <v-col
                  cols="3"
                  xs="3"
                  sm="2"
                  md="2"
                  lg="2"
                  class="font-weight-medium"
                  ><span>Size</span></v-col
                >
                <v-col
                  ><span
                    >{{ rom.file_size }} {{ rom.file_size_units }}</span
                  ></v-col
                >
              </v-row>
              <v-row
                v-if="rom.r_igdb_id != ''"
                class="d-flex align-center text-body-1 mt-0"
              >
                <v-col
                  cols="3"
                  xs="3"
                  sm="2"
                  md="2"
                  lg="2"
                  class="font-weight-medium"
                  ><span>IGDB</span></v-col
                >
                <v-col>
                  <v-chip
                    variant="outlined"
                    :href="`https://www.igdb.com/games/${rom.r_slug}`"
                    label
                    >{{ rom.r_igdb_id }}</v-chip
                  >
                </v-col>
              </v-row>
              <v-row
                v-if="rom.tags.length > 0"
                class="d-flex align-center text-body-1 mt-0"
              >
                <v-col
                  cols="3"
                  xs="3"
                  sm="2"
                  md="2"
                  lg="2"
                  class="font-weight-medium"
                  ><span>Tags</span></v-col
                >
                <v-col
                  ><v-chip-group class="pt-0"
                    ><v-chip
                      v-for="tag in rom.tags"
                      :key="tag"
                      class="bg-chip"
                      label
                      >{{ tag }}</v-chip
                    ></v-chip-group
                  ></v-col
                >
              </v-row>
              <v-row class="d-flex mt-3">
                <v-col class="font-weight-medium text-caption">
                  <p>{{ rom.summary }}</p>
                </v-col>
              </v-row>
            </v-window-item>
            <v-window-item value="screenshots">
              <v-row class="d-flex mt-2">
                <v-carousel
                  hide-delimiter-background
                  delimiter-icon="mdi-square"
                  class="bg-romm-black"
                  show-arrows="hover"
                  height="400"
                >
                  <v-carousel-item
                    v-for="screenshot in rom.path_screenshots"
                    :src="`/assets/romm/resources/${screenshot}`"
                  />
                </v-carousel>
              </v-row>
            </v-window-item>
            <v-window-item value="saves">
              <v-row class="d-flex mt-2"> </v-row>
            </v-window-item>
          </v-window>
        </div>
      </v-col>
    </v-row>
  </div>

  <search-rom-dialog />
  <edit-rom-dialog />
  <delete-rom-dialog />
  <loading-dialog />
</template>

<style scoped>
.scroll {
  overflow-y: scroll;
}

.rom-name,
.rom-platform {
  text-shadow: 1px 1px 3px #000000, 0 0 3px #000000;
}

.content,
.content-tablet,
.content-mobile {
  position: relative;
}

.content,
.content-tablet {
  margin-top: 64px;
  margin-left: 100px;
  margin-right: 100px;
}

.content-mobile {
  margin-top: 64px;
  margin-left: 20px;
  margin-right: 20px;
}

.cover,
.cover-tablet,
.cover-mobile {
  min-width: 245px;
  min-height: 326px;
  max-width: 245px;
  max-height: 326px;
}

.details,
.details-tablet,
.details-mobile {
  padding-left: 25px;
  padding-right: 25px;
}

.details-content {
  margin-top: 122px;
  max-width: 700px;
}

.details-content-tablet {
  margin-top: 66px;
}

.details-content-mobile {
  margin-top: 30px;
}
</style>

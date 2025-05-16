<script setup lang="ts">
import { type FilterType } from "@/stores/galleryFilter";
import RDialog from "@/components/common/RDialog.vue";
import RAvatar from "@/components/common/Collection/RAvatar.vue";
import type { DetailedRom } from "@/stores/roms";
import { ROUTES } from "@/plugins/router";
import { ref } from "vue";
import { useRouter } from "vue-router";
import { useDisplay, useTheme } from "vuetify";
import { useI18n } from "vue-i18n";
import { MdPreview } from "md-editor-v3";
import { get } from "lodash";

// Props
const { t } = useI18n();
defineProps<{ rom: DetailedRom }>();
const { xs } = useDisplay();
const theme = useTheme();
const show = ref(false);
const carousel = ref(0);
const router = useRouter();
const filters = [
  { key: "regions", path: "regions", name: t("rom.regions") },
  { key: "languages", path: "languages", name: t("rom.languages") },
  { key: "genres", path: "metadatum.genres", name: t("rom.genres") },
  {
    key: "franchises",
    path: "metadatum.franchises",
    name: t("rom.franchises"),
  },
  {
    key: "collections",
    path: "metadatum.collections",
    name: t("rom.collections"),
  },
  { key: "companies", path: "metadatum.companies", name: t("rom.companies") },
] as const;

// Functions
function onFilterClick(filter: FilterType, value: string) {
  router.push({
    name: "search",
    query: { search: "", filter, value },
  });
}
</script>
<template>
  <v-row no-gutters>
    <v-col>
      <v-divider class="mx-2 my-4" />
      <v-row
        v-if="rom.user_collections && rom.user_collections.length > 0"
        no-gutters
        class="align-center my-3"
      >
        <v-col cols="3" xl="2" class="mr-2">
          <span>RomM Collections</span>
        </v-col>
        <v-col>
          <v-row no-gutters>
            <v-col cols="12" v-for="collection in rom.user_collections">
              <v-chip
                :to="{
                  name: ROUTES.COLLECTION,
                  params: { collection: collection.id },
                }"
                size="large"
                class="mr-1 mt-1 px-0"
                label
              >
                <template #prepend>
                  <r-avatar :size="38" :collection="collection" />
                </template>
                <span class="px-4">{{ collection.name }}</span>
              </v-chip>
            </v-col>
          </v-row>
        </v-col>
      </v-row>
      <template v-for="filter in filters" :key="filter">
        <v-row
          v-if="get(rom, filter.path).length > 0"
          class="align-center my-3"
          no-gutters
        >
          <v-col cols="3" xl="2" class="text-capitalize mr-2">
            <span>{{ filter.name }}</span>
          </v-col>
          <v-col>
            <v-chip
              v-for="value in get(rom, filter.path)"
              :key="value"
              @click="onFilterClick(filter.key, value)"
              size="small"
              variant="outlined"
              class="my-1 mr-2"
              label
            >
              {{ value }}
            </v-chip>
          </v-col>
        </v-row>
      </template>
      <!-- Manually add age ratings to display logos -->
      <template
        v-if="
          rom.igdb_metadata?.age_ratings &&
          rom.igdb_metadata.age_ratings.length > 0
        "
      >
        <v-row no-gutters class="mt-5">
          <v-col cols="3" xl="2" class="text-capitalize">
            <span>Age Rating</span>
          </v-col>
          <div class="d-flex" :class="{ 'my-2': xs }">
            <v-img
              v-for="value in rom.igdb_metadata.age_ratings"
              :key="value.rating"
              @click="onFilterClick('age_ratings', value.rating)"
              :src="value.rating_cover_url"
              height="50"
              width="50"
              class="mr-4 cursor-pointer"
            />
          </div>
        </v-row>
      </template>
      <template v-if="rom.summary">
        <v-row no-gutters class="mt-4">
          <v-col class="text-caption">
            <MdPreview
              class="py-4 px-6"
              :model-value="rom.summary ?? ''"
              :theme="theme.name.value == 'dark' ? 'dark' : 'light'"
              preview-theme="vuepress"
              code-theme="github"
              :readonly="true"
            />
          </v-col>
        </v-row>
      </template>
      <template
        v-if="rom.merged_screenshots.length > 0 || rom.youtube_video_id"
      >
        <v-row no-gutters class="mt-4">
          <v-col>
            <v-carousel
              v-model="carousel"
              hide-delimiter-background
              delimiter-icon="mdi-square"
              class="bg-background"
              show-arrows="hover"
              hide-delimiters
              progress="toplayer"
              :height="xs ? '300' : '400'"
            >
              <template #prev="{ props }">
                <v-btn
                  icon="mdi-chevron-left"
                  class="translucent-dark"
                  @click="props.onClick"
                />
              </template>
              <v-carousel-item
                v-if="rom.youtube_video_id"
                :key="rom.youtube_video_id"
                content-class="d-flex justify-center align-center"
              >
                <iframe
                  height="100%"
                  width="100%"
                  :src="`https://www.youtube.com/embed/${rom.youtube_video_id}`"
                  title="YouTube video player"
                  frameborder="0"
                  allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
                  referrerpolicy="strict-origin-when-cross-origin"
                  allowfullscreen
                ></iframe>
              </v-carousel-item>
              <v-carousel-item
                v-for="screenshot_url in rom.merged_screenshots"
                :key="screenshot_url"
                :src="screenshot_url"
                class="pointer"
                @click="show = true"
              >
              </v-carousel-item>
              <template #next="{ props }">
                <v-btn
                  icon="mdi-chevron-right"
                  class="translucent-dark"
                  @click="props.onClick"
                />
              </template>
            </v-carousel>
            <r-dialog v-model="show" :width="'95vw'">
              <template #content>
                <v-carousel
                  v-model="carousel"
                  hide-delimiter-background
                  delimiter-icon="mdi-square"
                  show-arrows="hover"
                  hide-delimiters
                  class="dialog-carousel"
                >
                  <template #prev="{ props }">
                    <v-btn
                      @click="props.onClick"
                      icon="mdi-chevron-left"
                      class="translucent-dark"
                    />
                  </template>
                  <v-carousel-item
                    v-if="rom.youtube_video_id"
                    :key="rom.youtube_video_id"
                    content-class="d-flex justify-center align-center"
                  >
                    <iframe
                      height="100%"
                      width="100%"
                      :src="`https://www.youtube.com/embed/${rom.youtube_video_id}`"
                      title="YouTube video player"
                      frameborder="0"
                      allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
                      referrerpolicy="strict-origin-when-cross-origin"
                      allowfullscreen
                    ></iframe>
                  </v-carousel-item>
                  <v-carousel-item
                    v-for="screenshot_url in rom.merged_screenshots"
                    :key="screenshot_url"
                    :src="screenshot_url"
                  />
                  <template #next="{ props }">
                    <v-btn
                      icon="mdi-chevron-right"
                      class="translucent-dark"
                      @click="props.onClick"
                    />
                  </template>
                </v-carousel>
              </template>
            </r-dialog>
          </v-col>
        </v-row>
      </template>
    </v-col>
  </v-row>
</template>

<style scoped>
.dialog-carousel {
  height: calc(100vh - 110px) !important;
}
</style>

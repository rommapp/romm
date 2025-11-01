<script setup lang="ts">
import { get } from "lodash";
import { MdPreview } from "md-editor-v3";
import { computed, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useRouter } from "vue-router";
import { useDisplay, useTheme } from "vuetify";
import MediaCarousel from "@/components/Details/Info/MediaCarousel.vue";
import RDialog from "@/components/common/RDialog.vue";
import { ROUTES } from "@/plugins/router";
import { type FilterType } from "@/stores/galleryFilter";
import type { DetailedRom } from "@/stores/roms";

const props = defineProps<{ rom: DetailedRom }>();
const { t } = useI18n();
const { xs } = useDisplay();
const theme = useTheme();
const showDialog = ref(false);
const carouselValue = ref(0);
const router = useRouter();
const filters = [
  { key: "region", path: "regions", name: t("rom.regions") },
  { key: "language", path: "languages", name: t("rom.languages") },
  { key: "genre", path: "metadatum.genres", name: t("rom.genres") },
  {
    key: "franchise",
    path: "metadatum.franchises",
    name: t("rom.franchises"),
  },
  {
    key: "collection",
    path: "metadatum.collections",
    name: t("rom.collections"),
  },
  { key: "company", path: "metadatum.companies", name: t("rom.companies") },
] as const;

const dataSources = computed(() => {
  return [
    {
      name: "IGDB",
      condition: props.rom.igdb_id,
      url: `https://www.igdb.com/games/${props.rom.slug}`,
    },
    {
      name: "ScreenScraper",
      condition: props.rom.ss_id,
      url: `https://www.screenscraper.fr/gameinfos.php?gameid=${props.rom.ss_id}`,
    },
    {
      name: "MobyGames",
      condition: props.rom.moby_id,
      url: `https://www.mobygames.com/game/${props.rom.moby_id}`,
    },
    {
      name: "LaunchBox",
      condition: props.rom.launchbox_id,
      url: `https://gamesdb.launchbox-app.com/games/dbid/${props.rom.launchbox_id}`,
    },
    {
      name: "RetroAchievements",
      condition: props.rom.ra_id,
      url: `https://retroachievements.org/game/${props.rom.ra_id}`,
    },
    {
      name: "Hasheous",
      condition: props.rom.hasheous_id,
      url: `https://hasheous.org/index.html?page=dataobjectdetail&type=game&id=${props.rom.hasheous_id}`,
    },
    {
      name: "Flashpoint Project",
      condition: props.rom.flashpoint_id,
      url: `https://flashpointproject.github.io/flashpoint-database/search/#${props.rom.flashpoint_id}`,
    },
    {
      name: "HowLongToBeat",
      condition: props.rom.hltb_id,
      url: `https://howlongtobeat.com/game/${props.rom.hltb_id}`,
    },
  ].filter((source) => source.condition);
});

const coverImageSource = computed(() => {
  if (!props.rom.url_cover) return null;

  try {
    const hostname = new URL(props.rom.url_cover).hostname;

    if (hostname === "images.igdb.com") return "IGDB";
    if (
      hostname === "screenscraper.fr" ||
      hostname === "neoclone.screenscraper.fr"
    )
      return "ScreenScraper";
    if (hostname === "cdn.mobygames.com" || hostname === "cdn2.mobygames.com")
      return "MobyGames";
    if (
      hostname === "retroachievements.org" ||
      hostname === "media.retroachievements.org"
    )
      return "RetroAchievements";
    if (hostname === "images.launchbox-app.com") return "LaunchBox";
    if (
      hostname === "cdn.steamgriddb.com" ||
      hostname === "cdn2.steamgriddb.com"
    )
      return "SteamGridDB";
    if (hostname === "hasheous.org") return "Hasheous";
    if (hostname === "infinity.unstable.life") return "Flashpoint";
    if (hostname === "howlongtobeat.com") return "HowLongToBeat";

    return null;
  } catch {
    return null;
  }
});

function onFilterClick(filter: FilterType, value: string) {
  router.push({
    name: "search",
    query: { [filter]: value },
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
            <v-col
              v-for="collection in rom.user_collections"
              :key="collection.id"
              cols="12"
            >
              <v-chip
                :to="{
                  name: ROUTES.COLLECTION,
                  params: { collection: collection.id },
                }"
                size="small"
                class="my-1 mr-2 px-0"
                label
              >
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
              size="small"
              variant="outlined"
              class="my-1 mr-2"
              label
              @click="onFilterClick(filter.key, value)"
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
            <span>{{ t("rom.age-rating") }}</span>
          </v-col>
          <div class="d-flex" :class="{ 'my-2': xs }">
            <v-img
              v-for="value in rom.igdb_metadata.age_ratings"
              :key="value.rating"
              :src="value.rating_cover_url"
              height="50"
              width="50"
              class="mr-4 cursor-pointer"
              @click="onFilterClick('ageRating', value.rating)"
            />
          </div>
        </v-row>
      </template>
      <template v-if="rom.summary">
        <v-row no-gutters class="mt-4">
          <v-col class="text-caption">
            <MdPreview
              no-highlight
              no-katex
              no-mermaid
              class="py-4 px-6"
              :model-value="rom.summary ?? ''"
              :theme="theme.name.value == 'dark' ? 'dark' : 'light'"
              language="en-US"
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
            <MediaCarousel
              enable-click
              v-model="carouselValue"
              :rom="rom"
              @click="showDialog = true"
            />
            <RDialog v-model="showDialog" :width="'95vw'">
              <template #content>
                <MediaCarousel
                  v-model="carouselValue"
                  :rom="rom"
                  :height="'calc(100vh - 110px)'"
                />
              </template>
            </RDialog>
          </v-col>
        </v-row>
      </template>
      <v-row v-if="rom.is_identified">
        <v-col class="mt-4 text-right">
          <div v-if="dataSources.length > 0" class="text-grey">
            Data provided by
            <template v-for="(source, index) in dataSources" :key="source.name">
              <a
                v-if="source.condition"
                style="color: inherit"
                :href="source.url"
                target="_blank"
              >
                {{ source.name }}
              </a>
              <span v-if="source.condition && index < dataSources.length - 1">
                {{ index === dataSources.length - 2 ? " and " : ", " }}
              </span> </template
            >.
          </div>
          <div v-if="rom.url_cover && coverImageSource" class="text-grey mt-1">
            Cover art provided by
            <a :href="rom.url_cover" target="_blank" style="color: inherit">
              {{ coverImageSource }}</a
            >.
          </div>
        </v-col>
      </v-row>
    </v-col>
  </v-row>
</template>

<style scoped>
.dialog-carousel {
  height: calc(100vh - 110px) !important;
}
</style>

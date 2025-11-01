<script setup lang="ts">
import { storeToRefs } from "pinia";
import { computed } from "vue";
import { useDisplay } from "vuetify";
import FavBtn from "@/components/common/Game/FavBtn.vue";
import MissingFromFSIcon from "@/components/common/MissingFromFSIcon.vue";
import PlatformIcon from "@/components/common/Platform/PlatformIcon.vue";
import { ROUTES } from "@/plugins/router";
import storePlatforms from "@/stores/platforms";
import type { DetailedRom } from "@/stores/roms";

const props = defineProps<{ rom: DetailedRom }>();
const { smAndDown } = useDisplay();
const releaseDate = new Date(
  Number(props.rom.metadatum.first_release_date),
).toLocaleDateString("en-US", {
  day: "2-digit",
  month: "short",
  year: "numeric",
});

const platformsStore = storePlatforms();
const { allPlatforms } = storeToRefs(platformsStore);

const hashMatches = computed(() => {
  return [
    {
      name: "TOSEC",
      match: props.rom.hasheous_metadata?.tosec_match,
    },
    {
      name: "NoIntro",
      match: props.rom.hasheous_metadata?.nointro_match,
    },
    {
      name: "Redump",
      match: props.rom.hasheous_metadata?.redump_match,
    },
    {
      name: "FBNeo",
      match: props.rom.hasheous_metadata?.fbneo_match,
    },
    {
      name: "MAMEArcade",
      match: props.rom.hasheous_metadata?.mame_arcade_match,
    },
    {
      name: "MAMEMess",
      match: props.rom.hasheous_metadata?.mame_mess_match,
    },
    {
      name: "WHDLoad",
      match: props.rom.hasheous_metadata?.whdload_match,
    },
    {
      name: "PureDOS",
      match: props.rom.hasheous_metadata?.puredos_match,
    },
  ].filter((item) => item.match);
});
</script>
<template>
  <div>
    <v-row
      class="text-white text-shadow"
      :class="{ 'text-center my-4': smAndDown }"
      no-gutters
    >
      <v-col>
        <p class="text-h5 font-weight-bold pl-0 position-relative">
          <span>{{ rom.name }}</span>
          <FavBtn class="ml-2" :rom="rom" />
        </p>
      </v-col>
    </v-row>

    <v-row
      class="text-white text-shadow mt-2"
      :class="{ 'text-center': smAndDown }"
      no-gutters
    >
      <v-col>
        <v-chip
          :to="{ name: ROUTES.PLATFORM, params: { platform: rom.platform_id } }"
        >
          <MissingFromFSIcon
            v-if="
              allPlatforms.find((p) => p.id === rom.platform_id)
                ?.missing_from_fs
            "
            class="mr-2"
            text="Missing platform from filesystem"
          />
          <PlatformIcon
            :key="rom.platform_slug"
            :slug="rom.platform_slug"
            :name="rom.platform_display_name"
            :fs-slug="rom.platform_fs_slug"
            :size="30"
            class="mr-2"
          />
          {{ rom.platform_display_name }}
        </v-chip>
        <v-chip
          v-if="Number(rom.metadatum.first_release_date) > 0"
          class="mx-1"
        >
          {{ releaseDate }}
        </v-chip>
      </v-col>
    </v-row>

    <v-row
      v-if="rom.is_identified"
      class="text-white text-shadow mt-2"
      :class="{ 'text-center': smAndDown }"
      no-gutters
    >
      <v-col>
        <a
          v-if="rom.igdb_id"
          style="text-decoration: none; color: inherit"
          :href="`https://www.igdb.com/games/${rom.slug}`"
          target="_blank"
          class="mr-1"
        >
          <v-chip class="pl-0 mt-1" size="small" title="IGDB ID" @click.stop>
            <v-avatar class="mr-2" size="30" rounded="0">
              <v-img src="/assets/scrappers/igdb.png" />
            </v-avatar>
            <span>{{ rom.igdb_id }}</span>
            <v-divider class="mx-2 border-opacity-25" vertical />
            <span>{{ rom.igdb_metadata?.total_rating }}</span>
            <v-icon class="ml-1">mdi-star</v-icon>
          </v-chip>
        </a>
        <a
          v-if="rom.moby_id"
          style="text-decoration: none; color: inherit"
          :href="`https://www.mobygames.com/game/${rom.moby_id}`"
          target="_blank"
          class="mr-1"
        >
          <v-chip
            class="pl-0 mt-1"
            size="small"
            title="MobyGames ID"
            @click.stop
          >
            <v-avatar class="mr-2" size="30" rounded="0">
              <v-img src="/assets/scrappers/moby.png" />
            </v-avatar>
            <span>{{ rom.moby_id }}</span>
            <template
              v-if="
                rom.moby_metadata?.moby_score &&
                rom.moby_metadata.moby_score !== 'None'
              "
            >
              <v-divider class="mx-2 border-opacity-25" vertical />
              <span>{{
                (parseFloat(rom.moby_metadata.moby_score) * 10).toFixed(2)
              }}</span>
              <v-icon class="ml-1">mdi-star</v-icon>
            </template>
          </v-chip>
        </a>
        <a
          v-if="rom.ss_id"
          style="text-decoration: none; color: inherit"
          :href="`https://www.screenscraper.fr/gameinfos.php?gameid=${rom.ss_id}`"
          target="_blank"
          class="mr-1"
        >
          <v-chip
            class="pl-0 mt-1"
            size="small"
            title="ScreenScraper ID"
            @click.stop
          >
            <v-avatar class="mr-2" size="30" rounded="0">
              <v-img src="/assets/scrappers/ss.png" style="margin-left: -2px" />
            </v-avatar>
            <span>{{ rom.ss_id }}</span>
            <template v-if="rom.ss_metadata?.ss_score">
              <v-divider class="mx-2 border-opacity-25" vertical />
              <span>{{
                (parseFloat(rom.ss_metadata.ss_score) * 10).toFixed(2)
              }}</span>
              <v-icon class="ml-1">mdi-star</v-icon>
            </template>
          </v-chip>
        </a>
        <a
          v-if="rom.launchbox_id"
          style="text-decoration: none; color: inherit"
          :href="`https://gamesdb.launchbox-app.com/games/dbid/${rom.launchbox_id}`"
          target="_blank"
          class="mr-1"
        >
          <v-chip
            class="pl-0 mt-1"
            size="small"
            title="LaunchBox ID"
            @click.stop
          >
            <v-avatar
              class="mr-2"
              size="30"
              rounded="0"
              style="background: #185a7c"
            >
              <v-img src="/assets/scrappers/launchbox.png" />
            </v-avatar>
            <span>{{ rom.launchbox_id }}</span>
            <template v-if="rom.launchbox_metadata?.community_rating">
              <v-divider class="mx-2 border-opacity-25" vertical />
              <span>{{
                (rom.launchbox_metadata.community_rating * 20).toFixed(2)
              }}</span>
              <v-icon class="ml-1">mdi-star</v-icon>
            </template>
          </v-chip>
        </a>
        <a
          v-if="rom.ra_id"
          style="text-decoration: none; color: inherit"
          :href="`https://retroachievements.org/game/${rom.ra_id}`"
          target="_blank"
          class="mr-1"
        >
          <v-chip
            class="pl-0 mt-1"
            size="small"
            title="RetroAchievements ID"
            @click.stop
          >
            <v-avatar class="mr-2" size="30" rounded="0">
              <v-img src="/assets/scrappers/ra.png" style="margin-left: -2px" />
            </v-avatar>
            <span>{{ rom.ra_id }}</span>
          </v-chip>
        </a>
        <a
          v-if="rom.hasheous_id"
          style="text-decoration: none; color: inherit"
          :href="`https://hasheous.org/index.html?page=dataobjectdetail&type=game&id=${rom.hasheous_id}`"
          target="_blank"
          class="mr-1"
        >
          <v-chip
            class="pl-0 mt-1"
            size="small"
            title="Hasheous ID"
            @click.stop
          >
            <v-avatar class="mr-2 bg-surface pa-1" size="30" rounded="0">
              <v-img src="/assets/scrappers/hasheous.png" />
            </v-avatar>
            <span>{{ rom.hasheous_id }}</span>
          </v-chip>
        </a>
        <a
          v-if="rom.flashpoint_id"
          style="text-decoration: none; color: inherit"
          :href="`https://flashpointproject.github.io/flashpoint-database/search/#${rom.flashpoint_id}`"
          target="_blank"
          class="mr-1"
        >
          <v-chip class="pl-0 mt-1" size="small" title="Flashpoint ID">
            <v-avatar class="mr-2 bg-surface pa-1" size="30" rounded="0">
              <v-img src="/assets/scrappers/flashpoint.png" />
            </v-avatar>
            <span>{{ rom.flashpoint_id.split("-").pop() }}…</span>
          </v-chip>
        </a>
        <a
          v-if="rom.hltb_id"
          style="text-decoration: none; color: inherit"
          :href="`https://howlongtobeat.com/game/${rom.hltb_id}`"
          target="_blank"
          class="mr-1"
        >
          <v-chip class="pl-0 mt-1" size="small" title="HowLongToBeat ID">
            <v-avatar class="mr-2 bg-surface pa-1" size="30" rounded="0">
              <v-img src="/assets/scrappers/hltb.png" />
            </v-avatar>
            <span>{{ rom.hltb_id }}</span>
            <template v-if="rom.hltb_metadata?.review_score">
              <v-divider class="mx-2 border-opacity-25" vertical />
              <span>{{ rom.hltb_metadata.review_score.toFixed(1) }}</span>
              <v-icon class="ml-1">mdi-star</v-icon>
            </template>
          </v-chip>
        </a>
        <v-chip
          v-if="rom.gamelist_id"
          class="px-0 mr-1 mt-1"
          size="small"
          title="ES-DE (gamelist.xml)"
        >
          <v-avatar size="30" rounded="0">
            <v-img src="/assets/scrappers/esde.png" />
          </v-avatar>
        </v-chip>
        <a
          v-if="rom.sgdb_id"
          style="text-decoration: none; color: inherit"
          :href="`https://www.steamgriddb.com/game/${rom.sgdb_id}`"
          target="_blank"
          class="mr-1"
        >
          <v-chip class="pl-0 mt-1" size="small" title="SGDB ID">
            <v-avatar class="mr-2" size="30" rounded="0">
              <v-img src="/assets/scrappers/sgdb.png" />
            </v-avatar>
            <span>{{ rom.sgdb_id }}</span>
          </v-chip>
        </a>
      </v-col>
    </v-row>
    <v-row
      v-if="rom.hasheous_id"
      class="text-white text-shadow mt-2"
      :class="{ 'text-center': smAndDown }"
      no-gutters
    >
      <v-col cols="12">
        <v-chip
          v-for="hash in hashMatches"
          :key="hash.name"
          class="pl-0 mt-1 mr-1"
          size="small"
          title="Verified with Hasheous"
        >
          <v-avatar class="bg-romm-green" size="30" rounded="0">
            <v-icon>mdi-check-decagram-outline</v-icon>
          </v-avatar>
          <span class="ml-2">{{ hash.name }}</span>
        </v-chip>
      </v-col>
    </v-row>
  </div>
</template>

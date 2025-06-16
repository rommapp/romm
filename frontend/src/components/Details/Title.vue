<script setup lang="ts">
import FavBtn from "@/components/common/Game/FavBtn.vue";
import PlatformIcon from "@/components/common/Platform/Icon.vue";
import MissingFromFSIcon from "@/components/common/MissingFromFSIcon.vue";
import { ROUTES } from "@/plugins/router";
import type { DetailedRom } from "@/stores/roms";
import storePlatforms from "@/stores/platforms";
import { storeToRefs } from "pinia";
import { useDisplay } from "vuetify";

// Props
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
          <fav-btn class="ml-2" :rom="rom" />
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
          <missing-from-f-s-icon
            v-if="
              allPlatforms.find((p) => p.id === rom.platform_id)
                ?.missing_from_fs
            "
            class="mr-2"
            text="Missing platform from filesystem"
          />
          <platform-icon
            :key="rom.platform_slug"
            :slug="rom.platform_slug"
            :name="rom.platform_name"
            :fs-slug="rom.platform_fs_slug"
            :size="30"
            class="mr-2"
          />
          {{ rom.platform_display_name }}
        </v-chip>
        <v-chip
          v-if="Number(rom.metadatum.first_release_date) > 0"
          class="font-italic ma-1"
          size="small"
        >
          {{ releaseDate }}
        </v-chip>
        <v-chip v-if="!smAndDown && rom.revision" size="small" class="ma-1">
          Revision {{ rom.revision }}
        </v-chip>
      </v-col>
    </v-row>

    <v-row
      v-if="smAndDown && rom.revision"
      class="text-white text-shadow mt-2 text-center"
      no-gutters
    >
      <v-col>
        <v-chip v-if="rom.revision" size="small" class="ml-1">
          Revision {{ rom.revision }}
        </v-chip>
      </v-col>
    </v-row>

    <v-row
      v-if="rom.is_identified"
      class="text-white text-shadow mt-2"
      :class="{ 'text-center': smAndDown }"
      no-gutters
    >
      <v-col cols="12">
        <a
          v-if="rom.igdb_id"
          style="text-decoration: none; color: inherit"
          :href="`https://www.igdb.com/games/${rom.slug}`"
          target="_blank"
          class="mr-1"
        >
          <v-chip class="pl-0 mt-1" size="small" @click.stop>
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
          v-if="rom.ss_id"
          style="text-decoration: none; color: inherit"
          :href="`https://www.screenscraper.fr/gameinfos.php?gameid=${rom.ss_id}`"
          target="_blank"
          class="mr-1"
        >
          <v-chip class="pl-0 mt-1" size="small" @click.stop>
            <v-avatar class="mr-2" size="30" rounded="0">
              <v-img src="/assets/scrappers/ss.png" />
            </v-avatar>
            <span>{{ rom.ss_id }}</span>
            <v-divider class="mx-2 border-opacity-25" vertical />
            <span>{{ rom.ss_metadata?.ss_score }}</span>
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
          <v-chip class="pl-0 mt-1" size="small" @click.stop>
            <v-avatar class="mr-2" size="30" rounded="0">
              <v-img src="/assets/scrappers/moby.png" />
            </v-avatar>
            <span>{{ rom.moby_id }}</span>
            <v-divider class="mx-2 border-opacity-25" vertical />
            <span>{{ rom.moby_metadata?.moby_score }}</span>
            <v-icon class="ml-1">mdi-star</v-icon>
          </v-chip>
        </a>
        <a
          v-if="rom.ra_id"
          style="text-decoration: none; color: inherit"
          :href="`https://retroachievements.org/game/${rom.ra_id}`"
          target="_blank"
          class="mr-1"
        >
          <v-chip class="pl-0 mt-1" size="small" @click.stop>
            <v-avatar class="mr-2" size="25" rounded="1">
              <v-img src="/assets/scrappers/ra.png" />
            </v-avatar>
            <span>{{ rom.ra_id }}</span>
          </v-chip>
        </a>
        <span v-if="rom.launchbox_id" class="mr-1">
          <v-chip class="pl-0 mt-1" size="small">
            <v-avatar class="mr-2" size="30" rounded="0">
              <v-img src="/assets/scrappers/launchbox.png" />
            </v-avatar>
            <span>{{ rom.launchbox_id }}</span>
            <v-divider class="mx-2 border-opacity-25" vertical />
            <span>{{
              rom.launchbox_metadata?.community_rating?.toFixed(2)
            }}</span>
            <v-icon class="ml-1">mdi-star</v-icon>
          </v-chip>
        </span>
        <span v-if="rom.hasheous_id" class="mr-1">
          <v-chip class="pl-0 mt-1" size="small">
            <v-avatar class="mr-2 pa-1" size="30" rounded="0">
              <v-img src="/assets/scrappers/hasheous.png" />
            </v-avatar>
            <span>{{ rom.hasheous_id }}</span>
          </v-chip>
        </span>
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
          v-if="rom.hasheous_metadata?.tosec_match"
          prepend-icon="mdi-check"
          class="mt-1 mr-1"
          size="small"
          title="Passed CRC, SHA1 and MD5 checksum checks"
        >
          <span>Verified</span>
          <v-divider class="mx-2 border-opacity-25" vertical />
          <span>TOSEC</span>
        </v-chip>
        <v-chip
          v-if="rom.hasheous_metadata?.nointro_match"
          prepend-icon="mdi-check"
          class="mt-1 mr-1"
          size="small"
          title="Passed CRC, SHA1 and MD5 checksum checks"
        >
          <span>Verified</span>
          <v-divider class="mx-2 border-opacity-25" vertical />
          <span>NoIntro</span>
        </v-chip>
      </v-col>
    </v-row>
  </div>
</template>

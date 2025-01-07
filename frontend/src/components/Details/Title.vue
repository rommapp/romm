<script setup lang="ts">
import FavBtn from "@/components/common/Game/FavBtn.vue";
import PlatformIcon from "@/components/common/Platform/Icon.vue";
import type { Platform } from "@/stores/platforms";
import type { DetailedRom } from "@/stores/roms";
import { languageToEmoji, regionToEmoji } from "@/utils";
import { identity } from "lodash";
import { useDisplay } from "vuetify";

// Props
const props = defineProps<{ rom: DetailedRom }>();
const { smAndDown } = useDisplay();
const releaseDate = new Date(
  Number(props.rom.first_release_date) * 1000,
).toLocaleDateString("en-US", {
  day: "2-digit",
  month: "short",
  year: "numeric",
});
const hasReleaseDate = Number(props.rom.first_release_date) > 0;
</script>
<template>
  <div>
    <v-row
      class="text-white text-shadow"
      :class="{ 'text-center my-4': smAndDown }"
      no-gutters
    >
      <v-col>
        <p class="text-h5 font-weight-bold pl-0">
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
          :to="{ name: 'platform', params: { platform: rom.platform_id } }"
        >
          {{ rom.platform_display_name }}
          <platform-icon
            :key="rom.platform_slug"
            :slug="rom.platform_slug"
            :name="rom.platform_name"
            :size="30"
            class="ml-2"
          />
        </v-chip>
        <v-chip
          v-if="hasReleaseDate && !smAndDown"
          class="ml-1 font-italic"
          size="x-small"
        >
          {{ releaseDate }}
        </v-chip>
        <v-chip
          v-if="Number(rom.first_release_date) > 0 && smAndDown"
          class="font-italic ml-1"
          size="x-small"
        >
          {{ releaseDate }}
        </v-chip>
        <template v-if="!smAndDown">
          <v-chip
            class="ml-1"
            v-if="rom.regions.filter(identity).length > 0"
            size="small"
            :title="`Regions: ${rom.regions.join(', ')}`"
          >
            <span v-for="region in rom.regions" :key="region" class="px-1">{{
              regionToEmoji(region)
            }}</span>
          </v-chip>
          <v-chip
            v-if="rom.languages.filter(identity).length > 0"
            size="small"
            class="ml-1"
            :title="`Languages: ${rom.languages.join(', ')}`"
          >
            <span
              v-for="language in rom.languages"
              :key="language"
              class="px-1"
              >{{ languageToEmoji(language) }}</span
            >
          </v-chip>
          <v-chip v-if="rom.revision" size="small" class="ml-1">
            Revision {{ rom.revision }}
          </v-chip>
        </template>
      </v-col>
    </v-row>

    <v-row
      v-if="
        smAndDown &&
        rom.regions.filter(identity).length > 0 &&
        rom.languages.filter(identity).length > 0 &&
        rom.revision
      "
      class="text-white text-shadow mt-2 text-center"
      no-gutters
    >
      <v-col>
        <v-chip
          class="ml-1"
          v-if="rom.regions.filter(identity).length > 0"
          size="small"
          :title="`Regions: ${rom.regions.join(', ')}`"
        >
          <span v-for="region in rom.regions" :key="region" class="px-1">{{
            regionToEmoji(region)
          }}</span>
        </v-chip>
        <v-chip
          v-if="rom.languages.filter(identity).length > 0"
          size="small"
          class="ml-1"
          :title="`Languages: ${rom.languages.join(', ')}`"
        >
          <span
            v-for="language in rom.languages"
            :key="language"
            class="px-1"
            >{{ languageToEmoji(language) }}</span
          >
        </v-chip>
        <v-chip v-if="rom.revision" size="small" class="ml-1">
          Revision {{ rom.revision }}
        </v-chip>
      </v-col>
    </v-row>

    <v-row
      v-if="rom.igdb_id || rom.moby_id"
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
        >
          <v-chip size="x-small" @click.stop>
            <span>IGDB</span>
            <v-divider class="mx-2 border-opacity-25" vertical />
            <span>ID: {{ rom.igdb_id }}</span>
            <v-divider class="mx-2 border-opacity-25" vertical />
            <span>Rating: {{ rom.igdb_metadata?.total_rating }}</span>
          </v-chip>
        </a>
        <a
          v-if="rom.moby_id"
          style="text-decoration: none; color: inherit"
          :href="`https://www.mobygames.com/game/${rom.moby_id}`"
          target="_blank"
          :class="{ 'ml-1': rom.igdb_id }"
        >
          <v-chip size="x-small" @click.stop>
            <span>Mobygames</span>
            <v-divider class="mx-2 border-opacity-25" vertical />
            <span>ID: {{ rom.moby_id }}</span>
            <v-divider class="mx-2 border-opacity-25" vertical />
            <span>Rating: {{ rom.moby_metadata?.moby_score }}</span>
          </v-chip>
        </a>
      </v-col>
    </v-row>
  </div>
</template>

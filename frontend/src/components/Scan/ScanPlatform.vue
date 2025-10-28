<script setup lang="ts">
import { useI18n } from "vue-i18n";
import RomListItem from "@/components/common/Game/ListItem.vue";
import PlatformIcon from "@/components/common/Platform/PlatformIcon.vue";
import type { ScanningPlatform } from "@/stores/scanning";

defineProps<{ platform: ScanningPlatform }>();

const { t } = useI18n();
</script>

<template>
  <v-expansion-panel-title static>
    <v-list-item class="pa-0">
      <template #prepend>
        <v-avatar rounded="0" size="40">
          <PlatformIcon
            v-if="platform.slug"
            :key="platform.slug"
            :slug="platform.slug"
            :name="platform.display_name"
          />
        </v-avatar>
      </template>
      {{ platform.display_name }}
      <template #append>
        <v-chip class="ml-3" color="primary" size="x-small" label>
          {{ platform.roms.length }}
        </v-chip>
        <v-chip
          v-if="!platform.is_identified"
          color="red"
          size="small"
          class="ml-3"
          label
        >
          <v-icon class="mr-1"> mdi-close </v-icon>
          {{ t("scan.not-identified").toUpperCase() }}
        </v-chip>
      </template>
    </v-list-item>
  </v-expansion-panel-title>
  <v-expansion-panel-text class="bg-toplayer">
    <RomListItem
      v-for="rom in platform.roms"
      :key="rom.id"
      class="pa-4"
      :rom="rom"
      with-link
      with-filename
    >
      <template #append>
        <template v-if="rom.is_identifying">
          <v-chip color="orange" size="x-small" label>
            <v-icon class="mr-1"> mdi-search-web </v-icon>
            Identifying…
          </v-chip>
        </template>
        <template v-else>
          <v-chip v-if="rom.is_unidentified" color="red" size="x-small" label>
            <v-icon class="mr-1"> mdi-close </v-icon>
            {{ t("scan.not-identified") }}
          </v-chip>
          <v-chip
            v-if="rom.hasheous_id"
            title="Verified with Hasheous"
            class="text-white pa-0 mr-1"
            size="small"
          >
            <v-avatar class="bg-romm-green" size="26" rounded="0">
              <v-icon>mdi-check-decagram-outline</v-icon>
            </v-avatar>
          </v-chip>
          <v-chip
            v-if="rom.igdb_id"
            class="pa-0 mr-1"
            size="small"
            title="IGDB match"
          >
            <v-avatar size="26" rounded>
              <v-img src="/assets/scrappers/igdb.png" />
            </v-avatar>
          </v-chip>
          <v-chip
            v-if="rom.ss_id"
            class="pa-0 mr-1"
            size="small"
            title="ScreenScraper match"
          >
            <v-avatar size="26" rounded>
              <v-img src="/assets/scrappers/ss.png" />
            </v-avatar>
          </v-chip>
          <v-chip
            v-if="rom.moby_id"
            class="pa-0 mr-1"
            size="small"
            title="MobyGames match"
          >
            <v-avatar size="26" rounded>
              <v-img src="/assets/scrappers/moby.png" />
            </v-avatar>
          </v-chip>
          <v-chip
            v-if="rom.launchbox_id"
            class="pa-0 mr-1"
            size="small"
            title="LaunchBox match"
          >
            <v-avatar size="26" style="background: #185a7c">
              <v-img src="/assets/scrappers/launchbox.png" />
            </v-avatar>
          </v-chip>
          <v-chip
            v-if="rom.ra_id"
            class="pa-0 mr-1"
            size="small"
            title="RetroAchievements match"
          >
            <v-avatar size="26" rounded>
              <v-img src="/assets/scrappers/ra.png" />
            </v-avatar>
          </v-chip>
          <v-chip
            v-if="rom.hasheous_id"
            class="pa-1 mr-1 bg-surface"
            size="small"
            title="Hasheous match"
          >
            <v-avatar size="18" rounded>
              <v-img src="/assets/scrappers/hasheous.png" />
            </v-avatar>
          </v-chip>
          <v-chip
            v-if="rom.flashpoint_id"
            class="pa-1 mr-1 bg-surface"
            size="small"
            title="Flashpoint match"
          >
            <v-avatar size="18" rounded>
              <v-img src="/assets/scrappers/flashpoint.png" />
            </v-avatar>
          </v-chip>
          <v-chip
            v-if="rom.hltb_id"
            class="pa-1 mr-1 bg-surface"
            size="small"
            title="HowLongToBeat match"
          >
            <v-avatar size="18" rounded>
              <v-img src="/assets/scrappers/hltb.png" />
            </v-avatar>
          </v-chip>
          <v-chip
            v-if="rom.gamelist_id"
            class="pa-1 mr-1 bg-surface"
            size="small"
            title="ES-DE match"
          >
            <v-avatar size="18" rounded>
              <v-img src="/assets/scrappers/esde.png" />
            </v-avatar>
          </v-chip>
        </template>
      </template>
    </RomListItem>
    <v-list-item v-if="platform.roms.length == 0" class="text-center my-2">
      {{ t("scan.no-new-roms") }}
    </v-list-item>
  </v-expansion-panel-text>
</template>
<style scoped>
.v-chip {
  contain: layout style paint;
}

.v-avatar {
  contain: layout style paint;
}
</style>

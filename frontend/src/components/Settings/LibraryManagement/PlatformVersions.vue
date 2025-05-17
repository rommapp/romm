<script setup lang="ts">
import AddBtn from "@/components/Settings/LibraryManagement/AddBtn.vue";
import CreatePlatformVersionDialog from "@/components/Settings/LibraryManagement/Dialog/CreatePlatformVersion.vue";
import DeletePlatformVersionDialog from "@/components/Settings/LibraryManagement/Dialog/DeletePlatformVersion.vue";
import PlatformBindCard from "@/components/Settings/LibraryManagement/PlatformBindCard.vue";
import RSection from "@/components/common/RSection.vue";
import storeAuth from "@/stores/auth";
import storeConfig from "@/stores/config";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { inject, ref } from "vue";
import { useI18n } from "vue-i18n";

// Props
const { t } = useI18n();
const emitter = inject<Emitter<Events>>("emitter");
const authStore = storeAuth();
const configStore = storeConfig();
const { config } = storeToRefs(configStore);
const editable = ref(false);
</script>

<template>
  <r-section
    icon="mdi-gamepad-variant"
    :title="t('settings.platforms-versions')"
    class="mx-2 mt-4 mb-2"
  >
    <template #toolbar-title-append>
      <v-tooltip bottom max-width="400">
        <template #activator="{ props }">
          <v-btn
            v-bind="props"
            size="small"
            variant="text"
            icon="mdi-information-outline"
          />
        </template>
        <p>
          Versions of the same platform. A common example is Capcom Play System
          1 is an arcade system. Platform versions will let you setup a custom
          platform for RomM to import and tell RomM which platform it needs to
          scrape against.
        </p>
      </v-tooltip>
    </template>
    <template #toolbar-append>
      <v-btn
        v-if="authStore.scopes.includes('platforms.write')"
        class="ma-2"
        size="small"
        :color="editable ? 'primary' : ''"
        variant="text"
        icon="mdi-cog"
        @click="editable = !editable"
      />
    </template>
    <template #content>
      <v-row no-gutters class="align-center">
        <v-col
          v-for="(slug, fsSlug) in config.PLATFORMS_VERSIONS"
          :key="slug"
          cols="6"
          sm="4"
          md="3"
          lg="2"
          :title="slug"
        >
          <platform-bind-card
            :editable="authStore.scopes.includes('platforms.write') && editable"
            :slug="slug"
            :fs-slug="fsSlug"
            class="mx-1 mt-2"
            @click-edit="
              emitter?.emit('showCreatePlatformVersionDialog', {
                fsSlug: fsSlug,
                slug: slug,
              })
            "
            @click-delete="
              emitter?.emit('showDeletePlatformVersionDialog', {
                fsSlug: fsSlug,
                slug: slug,
              })
            "
          />
        </v-col>
        <v-col cols="6" sm="4" md="3" lg="2" class="px-1 pt-2">
          <add-btn
            :enabled="editable"
            @click="
              emitter?.emit('showCreatePlatformVersionDialog', {
                fsSlug: '',
                slug: '',
              })
            "
          />
        </v-col>
      </v-row>
    </template>
  </r-section>

  <create-platform-version-dialog />
  <delete-platform-version-dialog />
</template>

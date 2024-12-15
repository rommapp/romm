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
  >
    <template #toolbar-append>
      <v-btn
        v-if="authStore.scopes.includes('platforms.write')"
        class="ma-2"
        rounded="0"
        size="small"
        :color="editable ? 'romm-accent-1' : ''"
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
        <v-col cols="6" sm="4" md="3" lg="2" class="px-1">
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

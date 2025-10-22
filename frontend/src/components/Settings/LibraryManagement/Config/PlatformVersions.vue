<script setup lang="ts">
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { inject, ref } from "vue";
import { useI18n } from "vue-i18n";
import AddBtn from "@/components/Settings/LibraryManagement/Config/AddBtn.vue";
import CreatePlatformVersionDialog from "@/components/Settings/LibraryManagement/Config/Dialog/CreatePlatformVersion.vue";
import DeletePlatformVersionDialog from "@/components/Settings/LibraryManagement/Config/Dialog/DeletePlatformVersion.vue";
import PlatformBindCard from "@/components/Settings/LibraryManagement/Config/PlatformBindCard.vue";
import RSection from "@/components/common/RSection.vue";
import storeAuth from "@/stores/auth";
import storeConfig from "@/stores/config";
import type { Events } from "@/types/emitter";

const { t } = useI18n();
const emitter = inject<Emitter<Events>>("emitter");
const authStore = storeAuth();
const configStore = storeConfig();
const { config } = storeToRefs(configStore);
const editable = ref(false);
</script>

<template>
  <RSection
    icon="mdi-gamepad-variant"
    :title="t('settings.platforms-versions')"
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
          Platform versions allow you to create custom platform entries for
          games that belong to the same system but have different versions.
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
        :disabled="!config.CONFIG_FILE_WRITABLE"
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
          <PlatformBindCard
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
          <AddBtn
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
      <CreatePlatformVersionDialog />
      <DeletePlatformVersionDialog />
    </template>
  </RSection>
</template>

<script setup lang="ts">
import AddBtn from "@/components/Management/AddBtn.vue";
import PlatformBindCard from "@/components/Management/PlatformBindCard.vue";
import RSection from "@/components/common/RSection.vue";
import storeAuth from "@/stores/auth";
import storeConfig from "@/stores/config";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { inject, ref } from "vue";

// Props
const emitter = inject<Emitter<Events>>("emitter");
const authStore = storeAuth();
const configStore = storeConfig();
const { config } = storeToRefs(configStore);
const editable = ref(false);
</script>

<template>
  <r-section icon="mdi-controller" title="Platforms Bindings">
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
          v-for="(slug, fsSlug) in config.PLATFORMS_BINDING"
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
              emitter?.emit('showCreatePlatformBindingDialog', {
                fsSlug: fsSlug,
                slug: slug,
              })
            "
            @click-delete="
              emitter?.emit('showDeletePlatformBindingDialog', {
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
              emitter?.emit('showCreatePlatformBindingDialog', {
                fsSlug: '',
                slug: '',
              })
            "
          />
        </v-col>
      </v-row>
    </template>
  </r-section>
</template>

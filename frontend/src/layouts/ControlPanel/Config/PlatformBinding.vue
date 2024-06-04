<script setup lang="ts">
import AddBtn from "@/components/ControlPanel/Config/AddBtn.vue";
import PlatformBindCard from "@/components/ControlPanel/Config/PlatformBindCard.vue";
import RSection from "@/components/common/Section.vue";
import storeAuth from "@/stores/auth";
import storeConfig from "@/stores/config";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { inject, ref } from "vue";

// Props
const emitter = inject<Emitter<Events>>("emitter");
const configStore = storeConfig();
const authStore = storeAuth();
const platformsBinding = configStore.value.PLATFORMS_BINDING;
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
          v-for="(slug, fsSlug) in platformsBinding"
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

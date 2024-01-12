<script setup lang="ts">
import { ref, inject } from "vue";
import type { Emitter } from "mitt";
import type { Events } from "@/types/emitter";
import storeHeartbeat from "@/stores/heartbeat";
import api from "@/services/api";

// Props
const show = ref(false);
const heartbeat = storeHeartbeat();
const emitter = inject<Emitter<Events>>("emitter");
const fsSlug = ref("");
const slug = ref("");
emitter?.on("showCreatePlatformBindingDialog", () => {
  show.value = true;
});

// Functions
function addBindPlatform() {
  api.addPlatformBindConfig({ fsSlug: fsSlug.value, slug: slug.value });
  heartbeat.addPlatformBinding(fsSlug.value, slug.value);
  closeDialog();
  fsSlug.value = "";
  slug.value = "";
}

function closeDialog() {
  show.value = false;
}
</script>
<template>
  <v-dialog v-model="show" max-width="500px" :scrim="false">
    <v-card>
      <v-toolbar density="compact" class="bg-terciary">
        <v-row class="align-center" no-gutters>
          <v-col cols="10">
            <v-icon icon="mdi-controller" class="ml-5" />
            <v-icon icon="mdi-menu-right" class="ml-1 text-romm-gray" />
            <v-icon icon="mdi-controller" class="ml-1 text-romm-accent-1" />
          </v-col>
          <v-col>
            <v-btn
              @click="closeDialog"
              class="bg-terciary"
              rounded="0"
              variant="text"
              icon="mdi-close"
              block
            />
          </v-col>
        </v-row>
      </v-toolbar>
      <v-divider class="border-opacity-25" :thickness="1" />

      <v-card-text>
        <v-row class="pa-2 align-center" no-gutters>
          <v-text-field
            @keyup.enter=""
            v-model="fsSlug"
            label="Folder name"
            variant="outlined"
            required
            hide-details
          />
          <v-icon icon="mdi-menu-right" class="mx-2 text-romm-gray" />
          <v-text-field
            class="text-romm-accent-1"
            @keyup.enter=""
            v-model="slug"
            label="RomM platform"
            color="romm-accent-1"
            base-color="romm-accent-1"
            variant="outlined"
            required
            hide-details
          />
        </v-row>
        <v-row class="justify-center pa-2" no-gutters>
          <v-btn @click="closeDialog" class="bg-terciary">Cancel</v-btn>
          <v-btn
            @click="addBindPlatform()"
            class="text-romm-green bg-terciary ml-5"
          >
            Create
          </v-btn>
        </v-row>
      </v-card-text>
    </v-card>
  </v-dialog>
</template>

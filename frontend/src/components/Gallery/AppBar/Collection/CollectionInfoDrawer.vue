<script setup lang="ts">
import CollectionCard from "@/components/common/Collection/Card.vue";
import DeleteCollectionDialog from "@/components/common/Collection/Dialog/DeleteCollection.vue";
import EditCollectionDialog from "@/components/common/Collection/Dialog/EditCollection.vue";
import RSection from "@/components/common/RSection.vue";
import storeAuth from "@/stores/auth";
import storeNavigation from "@/stores/navigation";
import storeRoms from "@/stores/roms";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { inject, ref } from "vue";
import { useDisplay } from "vuetify";
import { useI18n } from "vue-i18n";

// Props
const { t } = useI18n();
const { xs } = useDisplay();
const emitter = inject<Emitter<Events>>("emitter");
const viewportWidth = ref(window.innerWidth);
const auth = storeAuth();
const romsStore = storeRoms();
const { currentCollection } = storeToRefs(romsStore);
const navigationStore = storeNavigation();
const { activeCollectionInfoDrawer } = storeToRefs(navigationStore);
const collectionInfoFields = [
  {
    key: "rom_count",
    label: "Roms",
  },
  {
    key: "user__username",
    label: t("collection.owner"),
  },
];
</script>

<template>
  <v-navigation-drawer
    v-model="activeCollectionInfoDrawer"
    floating
    mobile
    :width="xs ? viewportWidth : '500'"
    v-if="currentCollection"
  >
    <v-row no-gutters class="justify-center align-center pa-4">
      <v-col style="max-width: 240px" cols="12">
        <div class="text-center justify-center align-center">
          <collection-card
            :key="currentCollection.updated_at"
            :collection="currentCollection"
          />
        </div>
        <div
          class="text-center mt-4"
          v-if="auth.scopes.includes('collections.write')"
        >
          <p class="text-h5 font-weight-bold pl-0">
            <span>{{ currentCollection.name }}</span>
          </p>
          <p class="text-subtitle-2">
            <span>{{ currentCollection.description }}</span>
          </p>
          <v-chip class="mt-4" size="small" color="romm-accent-1"
            ><v-icon class="mr-1">{{
              currentCollection.is_public ? "mdi-lock-open" : "mdi-lock"
            }}</v-icon
            >{{
              currentCollection.is_public
                ? t("collection.public")
                : t("collection.private")
            }}</v-chip
          >
          <div class="mt-4">
            <v-btn
              v-if="currentCollection.user__username === auth.user?.username"
              rounded="4"
              @click="
                emitter?.emit('showEditCollectionDialog', {
                  ...currentCollection,
                })
              "
              class="bg-terciary"
            >
              <template #prepend>
                <v-icon>mdi-pencil-box</v-icon>
              </template>
              {{ t("collection.edit-collection") }}
            </v-btn>
          </div>
        </div>
      </v-col>
      <v-col cols="12">
        <v-card class="mt-4 bg-terciary fill-width" elevation="0">
          <v-card-text class="pa-4">
            <template
              v-for="(field, index) in collectionInfoFields"
              :key="field.key"
            >
              <div
                v-if="
                  currentCollection[field.key as keyof typeof currentCollection]
                "
                :class="{ 'mt-4': index !== 0 }"
              >
                <p class="text-subtitle-1 text-decoration-underline">
                  {{ field.label }}
                </p>
                <p class="text-subtitle-2">
                  {{
                    currentCollection[
                      field.key as keyof typeof currentCollection
                    ]
                  }}
                </p>
              </div>
            </template>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>
    <r-section
      v-if="
        auth.scopes.includes('collections.write') &&
        currentCollection.user__username === auth.user?.username
      "
      icon="mdi-alert"
      icon-color="red"
      :title="t('collection.danger-zone')"
      elevation="0"
    >
      <template #content>
        <div class="text-center">
          <v-btn
            class="text-romm-red bg-terciary ma-2"
            variant="flat"
            @click="
              emitter?.emit('showDeleteCollectionDialog', currentCollection)
            "
          >
            <v-icon class="text-romm-red mr-2">mdi-delete</v-icon>
            {{ t("collection.delete-collection") }}
          </v-btn>
        </div>
      </template>
    </r-section>
  </v-navigation-drawer>

  <edit-collection-dialog />
  <delete-collection-dialog />
</template>

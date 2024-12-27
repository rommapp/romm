<script setup lang="ts">
import CollectionCard from "@/components/common/Collection/Card.vue";
import DeleteCollectionDialog from "@/components/common/Collection/Dialog/DeleteCollection.vue";
import RSection from "@/components/common/RSection.vue";
import type { UpdatedCollection } from "@/services/api/collection";
import storeCollection from "@/stores/collections";
import collectionApi from "@/services/api/collection";
import storeAuth from "@/stores/auth";
import storeHeartbeat from "@/stores/heartbeat";
import storeNavigation from "@/stores/navigation";
import storeRoms from "@/stores/roms";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { inject, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useDisplay, useTheme } from "vuetify";

// Props
const { t } = useI18n();
const { xs } = useDisplay();
const emitter = inject<Emitter<Events>>("emitter");
const viewportWidth = ref(window.innerWidth);
const theme = useTheme();
const auth = storeAuth();
const romsStore = storeRoms();
const collectionsStore = storeCollection();
const { currentCollection } = storeToRefs(romsStore);
const { allCollections } = storeToRefs(collectionsStore);
const navigationStore = storeNavigation();
const imagePreviewUrl = ref<string | undefined>("");
const removeCover = ref(false);
const heartbeat = storeHeartbeat();
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
const updating = ref(false);
const updatedCollection = ref<UpdatedCollection>({} as UpdatedCollection);
const isEditable = ref(false);
emitter?.on("updateUrlCover", (url_cover) => {
  updatedCollection.value.url_cover = url_cover;
  setArtwork(url_cover);
});

// Functions
function showEditable() {
  updatedCollection.value = { ...currentCollection.value } as UpdatedCollection;
  imagePreviewUrl.value = "";
  removeCover.value = false;
  isEditable.value = true;
}

function closeEditable() {
  updatedCollection.value = {} as UpdatedCollection;
  imagePreviewUrl.value = "";
  isEditable.value = false;
}

function triggerFileInput() {
  const fileInput = document.getElementById("file-input");
  fileInput?.click();
}

function previewImage(event: Event) {
  const input = event.target as HTMLInputElement;
  if (!input.files) return;

  const reader = new FileReader();
  reader.onload = () => {
    setArtwork(reader.result?.toString() || "");
  };
  if (input.files[0]) {
    reader.readAsDataURL(input.files[0]);
  }
}

function setArtwork(imageUrl: string) {
  if (!imageUrl) return;
  imagePreviewUrl.value = imageUrl;
  removeCover.value = false;
}

async function removeArtwork() {
  imagePreviewUrl.value = `/assets/default/cover/big_${theme.global.name.value}_collection.png`;
  removeCover.value = true;
}

async function updateCollection() {
  if (!updatedCollection.value) return;
  updating.value = true;
  isEditable.value = !isEditable.value;
  await collectionApi
    .updateCollection({
      collection: updatedCollection.value,
      removeCover: removeCover.value,
    })
    .then(({ data: collection }) => {
      emitter?.emit("snackbarShow", {
        msg: "Collection updated successfully",
        icon: "mdi-check-bold",
        color: "green",
      });
      currentCollection.value = collection;
      const index = allCollections.value.findIndex(
        (p) => p.id === collection.id,
      );
      if (index !== -1) {
        allCollections.value[index] = collection;
      }
    })
    .catch((error) => {
      emitter?.emit("snackbarShow", {
        msg: `Failed to update collection: ${
          error.response?.data?.msg || error.message
        }`,
        icon: "mdi-close-circle",
        color: "red",
      });
    });
  updatedCollection.value = {} as UpdatedCollection;
  imagePreviewUrl.value = "";
  updating.value = false;
}
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
          <div class="position-absolute append-top-right">
            <template
              v-if="
                currentCollection.user__username === auth.user?.username &&
                auth.scopes.includes('collections.write')
              "
            >
              <v-btn
                v-if="!isEditable"
                :loading="updating"
                class="bg-terciary"
                @click="showEditable"
                size="small"
              >
                <template #loader>
                  <v-progress-circular
                    color="romm-accent-1"
                    :width="2"
                    :size="20"
                    indeterminate
                  />
                </template>
                <v-icon>mdi-pencil</v-icon></v-btn
              >
              <template v-else>
                <v-btn @click="closeEditable" size="small" class="bg-terciary"
                  ><v-icon color="romm-red">mdi-close</v-icon></v-btn
                >
                <v-btn
                  @click="updateCollection()"
                  size="small"
                  class="bg-terciary ml-1"
                  ><v-icon color="romm-green">mdi-check</v-icon></v-btn
                >
              </template>
            </template>
          </div>
          <collection-card
            :key="currentCollection.updated_at"
            :show-title="false"
            :with-link="false"
            :collection="currentCollection"
            :src="imagePreviewUrl"
          >
            <template v-if="isEditable" #append-inner>
              <v-btn-group rounded="0" divided density="compact">
                <v-btn
                  title="Search for cover in SteamGridDB"
                  :disabled="
                    !heartbeat.value.METADATA_SOURCES?.STEAMGRIDDB_ENABLED
                  "
                  size="small"
                  class="translucent-dark"
                  @click="
                    emitter?.emit('showSearchCoverDialog', {
                      term: currentCollection.name as string,
                      aspectRatio: null,
                    })
                  "
                >
                  <v-icon size="large">mdi-image-search-outline</v-icon>
                </v-btn>
                <v-btn
                  title="Upload custom cover"
                  size="small"
                  class="translucent-dark"
                  @click="triggerFileInput"
                >
                  <v-icon size="large">mdi-upload</v-icon>
                  <v-file-input
                    id="file-input"
                    v-model="updatedCollection.artwork"
                    accept="image/*"
                    hide-details
                    class="file-input"
                    @change="previewImage"
                  />
                </v-btn>
                <v-btn
                  title="Remove cover"
                  size="small"
                  class="translucent-dark"
                  @click="removeArtwork"
                >
                  <v-icon size="large" class="text-romm-red">mdi-delete</v-icon>
                </v-btn>
              </v-btn-group>
            </template>
          </collection-card>
        </div>
      </v-col>
      <v-col cols="12">
        <div class="text-center mt-4">
          <div v-if="!isEditable">
            <div>
              <span class="text-h5 font-weight-bold pl-0">{{
                currentCollection.name
              }}</span>
            </div>
            <div>
              <span class="text-subtitle-2">{{
                currentCollection.description
              }}</span>
            </div>
            <v-chip
              class="mt-4"
              size="small"
              :color="currentCollection.is_public ? 'romm-accent-1' : ''"
              ><v-icon class="mr-1">{{
                currentCollection.is_public ? "mdi-lock-open" : "mdi-lock"
              }}</v-icon
              >{{
                currentCollection.is_public
                  ? t("collection.public")
                  : t("collection.private")
              }}</v-chip
            >
          </div>
          <div class="text-center" v-else>
            <v-text-field
              class="mt-2"
              v-model="updatedCollection.name"
              :label="t('collection.name')"
              variant="outlined"
              required
              density="compact"
              hide-details
              @keyup.enter="updateCollection()"
            />
            <v-text-field
              class="mt-4"
              v-model="updatedCollection.description"
              :label="t('collection.description')"
              variant="outlined"
              required
              density="compact"
              hide-details
              @keyup.enter="updateCollection()"
            />
            <v-switch
              class="mt-2"
              v-model="updatedCollection.is_public"
              color="romm-accent-1"
              false-icon="mdi-lock"
              true-icon="mdi-lock-open"
              inset
              hide-details
              :label="
                updatedCollection.is_public
                  ? t('collection.public-desc')
                  : t('collection.private-desc')
              "
            />
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
              <div :class="{ 'mt-4': index !== 0 }">
                <v-chip size="small" class="mr-2 px-0" label>
                  <v-chip label>{{ field.label }}</v-chip
                  ><span class="px-2">{{
                    currentCollection[
                      field.key as keyof typeof currentCollection
                    ]?.toString()
                      ? currentCollection[
                          field.key as keyof typeof currentCollection
                        ]
                      : "N/A"
                  }}</span>
                </v-chip>
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

  <delete-collection-dialog />
</template>
<style scoped>
.append-top-right {
  top: 0.3rem;
  right: 0.3rem;
  z-index: 1;
}
</style>

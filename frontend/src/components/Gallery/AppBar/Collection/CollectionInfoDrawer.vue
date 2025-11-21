<script setup lang="ts">
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { computed, inject, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useDisplay } from "vuetify";
import CollectionCard from "@/components/common/Collection/Card.vue";
import DeleteCollectionDialog from "@/components/common/Collection/Dialog/DeleteCollection.vue";
import DeleteSmartCollectionDialog from "@/components/common/Collection/Dialog/DeleteSmartCollection.vue";
import RSection from "@/components/common/RSection.vue";
import type { UpdatedCollection } from "@/services/api/collection";
import collectionApi from "@/services/api/collection";
import storeAuth from "@/stores/auth";
import storeCollection from "@/stores/collections";
import storeHeartbeat from "@/stores/heartbeat";
import storeNavigation from "@/stores/navigation";
import storeRoms from "@/stores/roms";
import type { Events } from "@/types/emitter";
import { getCollectionCoverImage } from "@/utils/covers";

const { t } = useI18n();
const { smAndDown } = useDisplay();
const emitter = inject<Emitter<Events>>("emitter");
const auth = storeAuth();
const romsStore = storeRoms();
const collectionsStore = storeCollection();
const { currentCollection } = storeToRefs(romsStore);
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
const collectionCoverImage = computed(() =>
  getCollectionCoverImage(updatedCollection.value.name),
);

emitter?.on("updateUrlCover", (coverUrl) => {
  setArtwork(coverUrl);
});

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

function setArtwork(coverUrl: string) {
  if (!coverUrl) return;
  updatedCollection.value.url_cover = coverUrl;
  imagePreviewUrl.value = coverUrl;
  removeCover.value = false;
}

async function removeArtwork() {
  imagePreviewUrl.value = collectionCoverImage.value;
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
    .then(({ data }) => {
      emitter?.emit("snackbarShow", {
        msg: "Collection updated successfully",
        icon: "mdi-check-bold",
        color: "green",
      });
      currentCollection.value = data;
      collectionsStore.updateCollection(data);
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
    v-if="currentCollection"
    v-model="activeCollectionInfoDrawer"
    mobile
    floating
    width="500"
    :class="{
      'ml-2': activeCollectionInfoDrawer,
      'drawer-mobile': smAndDown && activeCollectionInfoDrawer,
    }"
    class="bg-surface rounded mt-4 mb-2 pa-1 unset-height"
  >
    <v-row no-gutters class="justify-center align-center pa-2">
      <v-col style="max-width: 240px" cols="12">
        <div class="text-center justify-center align-center">
          <div class="position-absolute append-top-right mr-5">
            <template
              v-if="
                currentCollection.user__username === auth.user?.username &&
                auth.scopes.includes('collections.write')
              "
            >
              <v-btn
                v-if="!isEditable"
                :loading="updating"
                class="bg-toplayer"
                size="small"
                @click="showEditable"
              >
                <template #loader>
                  <v-progress-circular
                    color="primary"
                    :width="2"
                    :size="20"
                    indeterminate
                  />
                </template>
                <v-icon>mdi-pencil</v-icon>
              </v-btn>
              <template v-else>
                <v-btn size="small" class="bg-toplayer" @click="closeEditable">
                  <v-icon color="romm-red"> mdi-close </v-icon>
                </v-btn>
                <v-btn
                  size="small"
                  class="bg-toplayer ml-1"
                  @click="updateCollection"
                >
                  <v-icon color="romm-green"> mdi-check </v-icon>
                </v-btn>
              </template>
            </template>
          </div>
          <CollectionCard
            :key="currentCollection.updated_at"
            :show-title="false"
            :with-link="false"
            :collection="currentCollection"
            :cover-src="imagePreviewUrl"
          >
            <template v-if="isEditable" #append-inner>
              <v-btn-group rounded="0" divided density="compact">
                <v-btn
                  title="Search for cover in SteamGridDB"
                  :disabled="
                    !heartbeat.value.METADATA_SOURCES?.STEAMGRIDDB_API_ENABLED
                  "
                  size="small"
                  class="translucent"
                  @click="
                    emitter?.emit('showSearchCoverDialog', {
                      term: currentCollection.name,
                    })
                  "
                >
                  <v-icon size="large"> mdi-image-search-outline </v-icon>
                </v-btn>
                <v-btn
                  title="Upload custom cover"
                  size="small"
                  class="translucent"
                  @click="triggerFileInput"
                >
                  <v-icon size="large"> mdi-cloud-upload-outline </v-icon>
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
                  class="translucent"
                  @click="removeArtwork"
                >
                  <v-icon size="large" class="text-romm-red">
                    mdi-delete
                  </v-icon>
                </v-btn>
              </v-btn-group>
            </template>
          </CollectionCard>
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
              :color="currentCollection.is_public ? 'primary' : ''"
            >
              <v-icon class="mr-1">
                {{ currentCollection.is_public ? "mdi-lock-open" : "mdi-lock" }}
              </v-icon>
              {{
                currentCollection.is_public
                  ? t("collection.public")
                  : t("collection.private")
              }}
            </v-chip>
          </div>
          <div v-else class="text-center">
            <v-text-field
              v-model="updatedCollection.name"
              class="mt-2"
              :label="t('collection.name')"
              variant="outlined"
              required
              density="compact"
              hide-details
              @keyup.enter="updateCollection"
            />
            <v-text-field
              v-model="updatedCollection.description"
              class="mt-4"
              :label="t('collection.description')"
              variant="outlined"
              required
              density="compact"
              hide-details
              @keyup.enter="updateCollection"
            />
            <v-switch
              v-model="updatedCollection.is_public"
              class="mt-2"
              color="primary"
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
        <v-card class="mt-4 bg-toplayer fill-width" elevation="0">
          <v-card-text class="pa-4 d-flex">
            <template v-for="field in collectionInfoFields" :key="field.key">
              <div>
                <v-chip size="small" class="mr-2 px-0" label>
                  <v-chip label> {{ field.label }} </v-chip
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
    <RSection
      v-if="
        auth.scopes.includes('collections.write') &&
        currentCollection.user__username === auth.user?.username
      "
      icon="mdi-alert"
      icon-color="red"
      :title="t('collection.danger-zone')"
      elevation="0"
      title-divider
      bg-color="bg-toplayer"
      class="mx-2"
    >
      <template #content>
        <div class="text-center">
          <v-btn
            class="text-romm-red bg-toplayer ma-2"
            variant="flat"
            @click="
              emitter?.emit('showDeleteCollectionDialog', currentCollection)
            "
          >
            <v-icon class="text-romm-red mr-2"> mdi-delete </v-icon>
            {{ t("collection.delete-collection") }}
          </v-btn>
        </div>
      </template>
    </RSection>
  </v-navigation-drawer>

  <DeleteCollectionDialog />
  <DeleteSmartCollectionDialog />
</template>
<style scoped>
.append-top-right {
  top: 0.3rem;
  right: 0.3rem;
  z-index: 1;
}
</style>

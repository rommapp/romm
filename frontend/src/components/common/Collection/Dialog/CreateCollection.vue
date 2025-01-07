<script setup lang="ts">
import CollectionCard from "@/components/common/Collection/Card.vue";
import RDialog from "@/components/common/RDialog.vue";
import collectionApi, {
  type UpdatedCollection,
} from "@/services/api/collection";
import storeCollections from "@/stores/collections";
import storeHeartbeat from "@/stores/heartbeat";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { inject, ref } from "vue";
import { useDisplay, useTheme } from "vuetify";
import { useI18n } from "vue-i18n";

// Props
const { t } = useI18n();
const theme = useTheme();
const { mdAndUp } = useDisplay();
const show = ref(false);
const heartbeat = storeHeartbeat();
const collection = ref<UpdatedCollection>({} as UpdatedCollection);
const collectionsStore = storeCollections();
const imagePreviewUrl = ref<string | undefined>("");
const removeCover = ref(false);
const emitter = inject<Emitter<Events>>("emitter");
emitter?.on("showCreateCollectionDialog", () => {
  show.value = true;
  removeCover.value = false;
});
emitter?.on("updateUrlCover", (url_cover) => {
  if (!collection.value) return;
  collection.value.url_cover = url_cover;
  setArtwork(url_cover);
});

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
  imagePreviewUrl.value = `/assets/default/cover/big_${theme.global.name.value}_missing_cover.png`;
  removeCover.value = true;
}

async function createCollection() {
  if (!collection.value) return;

  emitter?.emit("showLoadingDialog", { loading: true, scrim: true });

  await collectionApi
    .createCollection({
      collection: collection.value,
    })
    .then(({ data }) => {
      collectionsStore.add(data);
      if (data.name.toLowerCase() == "favourites") {
        collectionsStore.setFavCollection(data);
      }
      emitter?.emit("snackbarShow", {
        msg: `Collection ${data.name} created successfully!`,
        icon: "mdi-check-bold",
        color: "green",
        timeout: 2000,
      });
      show.value = false;
    })
    .catch((error) => {
      console.log(error);
      emitter?.emit("snackbarShow", {
        msg: error.response.data.detail,
        icon: "mdi-close-circle",
        color: "red",
      });
    })
    .finally(() => {
      emitter?.emit("showLoadingDialog", { loading: false, scrim: false });
      closeDialog();
    });
}

function closeDialog() {
  show.value = false;
  collection.value = {} as UpdatedCollection;
  imagePreviewUrl.value = "";
}
</script>

<template>
  <r-dialog
    @close="closeDialog"
    v-model="show"
    icon="mdi-bookmark-box-multiple"
    :width="mdAndUp ? '55vw' : '95vw'"
  >
    <template #content>
      <v-row class="align-center pa-2" no-gutters>
        <v-col cols="12" lg="7" xl="9">
          <v-row class="pa-2" no-gutters>
            <v-col>
              <v-text-field
                v-model="collection.name"
                :label="t('collection.name')"
                variant="outlined"
                required
                hide-details
                @keyup.enter="createCollection()"
              />
            </v-col>
          </v-row>
          <v-row class="pa-2" no-gutters>
            <v-col>
              <v-text-field
                v-model="collection.description"
                class="mt-1"
                :label="t('collection.description')"
                variant="outlined"
                required
                hide-details
                @keyup.enter="createCollection()"
              />
            </v-col>
          </v-row>
        </v-col>
        <v-col>
          <v-row class="pa-2 justify-center" no-gutters>
            <v-col class="cover">
              <collection-card
                :key="collection.updated_at"
                :show-title="false"
                :with-link="false"
                :collection="collection"
                :src="imagePreviewUrl"
              >
                <template #append-inner>
                  <v-btn-group rounded="0" divided density="compact">
                    <v-btn
                      :disabled="
                        !heartbeat.value.METADATA_SOURCES?.STEAMGRIDDB_ENABLED
                      "
                      size="small"
                      class="translucent-dark"
                      @click="
                        emitter?.emit('showSearchCoverDialog', {
                          term: collection.name as string,
                          aspectRatio: null,
                        })
                      "
                    >
                      <v-icon size="large">mdi-image-search-outline</v-icon>
                    </v-btn>
                    <v-btn
                      size="small"
                      class="translucent-dark"
                      @click="triggerFileInput"
                    >
                      <v-icon size="large">mdi-pencil</v-icon>
                      <v-file-input
                        id="file-input"
                        v-model="collection.artwork"
                        accept="image/*"
                        hide-details
                        class="file-input"
                        @change="previewImage"
                      />
                    </v-btn>
                    <v-btn
                      size="small"
                      class="translucent-dark"
                      @click="removeArtwork"
                    >
                      <v-icon size="large" class="text-romm-red"
                        >mdi-delete</v-icon
                      >
                    </v-btn>
                  </v-btn-group>
                </template>
              </collection-card>
            </v-col>
          </v-row>
        </v-col>
      </v-row>
    </template>
    <template #append>
      <v-row class="justify-center mt-4 mb-2" no-gutters>
        <v-btn-group divided density="compact">
          <v-btn class="bg-terciary" @click="closeDialog">
            {{ t("common.cancel") }}
          </v-btn>
          <v-btn
            class="bg-terciary text-romm-green"
            :disabled="!collection.name"
            :variant="!collection.name ? 'plain' : 'flat'"
            @click="createCollection"
          >
            {{ t("common.create") }}
          </v-btn>
        </v-btn-group>
      </v-row>
    </template>
  </r-dialog>
</template>
<style scoped>
.cover {
  min-width: 240px;
  min-height: 330px;
  max-width: 240px;
  max-height: 330px;
}
</style>

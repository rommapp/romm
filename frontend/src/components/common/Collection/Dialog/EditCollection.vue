<script setup lang="ts">
import CollectionCard from "@/components/common/Collection/Card.vue";
import RDialog from "@/components/common/RDialog.vue";
import type { UpdatedCollection } from "@/services/api/collection";
import collectionApi from "@/services/api/collection";
import collectionStore, { type Collection } from "@/stores/collections";
import storeHeartbeat from "@/stores/heartbeat";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { inject, ref } from "vue";
import { useDisplay, useTheme } from "vuetify";

// Props
const theme = useTheme();
const { mdAndUp } = useDisplay();
const show = ref(false);
const storeCollection = collectionStore();
const collection = ref<UpdatedCollection>({} as UpdatedCollection);
const imagePreviewUrl = ref<string | undefined>("");
const removeCover = ref(false);
const heartbeat = storeHeartbeat();
const emitter = inject<Emitter<Events>>("emitter");
emitter?.on("showEditCollectionDialog", (collectionToEdit: Collection) => {
  collection.value = collectionToEdit;
  show.value = true;
});
emitter?.on("updateUrlCover", (url_cover) => {
  if (!collection.value) return;
  collection.value.url_cover = url_cover;
  imagePreviewUrl.value = url_cover;
});

// Functions
function triggerFileInput() {
  const fileInput = document.getElementById("file-input");
  fileInput?.click();
}

function previewImage(event: Event) {
  const input = event.target as HTMLInputElement;
  if (!input.files) return;

  const reader = new FileReader();
  reader.onload = () => {
    imagePreviewUrl.value = reader.result?.toString();
  };
  if (input.files[0]) {
    reader.readAsDataURL(input.files[0]);
  }
}

async function removeArtwork() {
  imagePreviewUrl.value = `/assets/default/cover/big_${theme.global.name.value}_collection.png`;
  removeCover.value = true;
}

async function editCollection() {
  if (!collection.value) return;

  emitter?.emit("showLoadingDialog", { loading: true, scrim: true });

  await collectionApi
    .updateCollection({
      collection: collection.value,
    })
    .then(({ data }) => {
      storeCollection.update(data);
      emitter?.emit("snackbarShow", {
        msg: `Collection updated successfully!`,
        icon: "mdi-check-bold",
        color: "green",
        timeout: 2000,
      });
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
    v-if="collection"
    @close="closeDialog"
    v-model="show"
    icon="mdi-pencil-box"
    :width="mdAndUp ? '55vw' : '95vw'"
  >
    <template #content>
      <v-row class="align-center pa-2" no-gutters>
        <v-col cols="12" lg="7" xl="9">
          <v-row class="pa-2" no-gutters>
            <v-col>
              <v-text-field
                v-model="collection.name"
                class="py-2"
                label="Name"
                variant="outlined"
                required
                hide-details
                @keyup.enter="editCollection"
              />
            </v-col>
          </v-row>
          <v-row class="pa-2" no-gutters>
            <v-col>
              <v-text-field
                v-model="collection.description"
                class="py-2"
                label="Description"
                variant="outlined"
                required
                hide-details
                @keyup.enter="editCollection"
              />
            </v-col>
          </v-row>
          <v-row class="pa-2" no-gutters>
            <v-col>
              <v-switch
                v-model="collection.is_public"
                :label="collection.is_public ? 'Public (visible to everyone)' : 'Private (only visible to me)'"
                color="romm-accent-1"
                class="px-2"
                hide-details
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
                      :disabled="!heartbeat.value.METADATA_SOURCES?.STEAMGRIDDB_ENABLED"
                      size="small"
                      class="translucent-dark"
                      @click="
                        emitter?.emit(
                          'showSearchCoverDialog',
                          collection.name as string
                        )
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
          <v-btn class="bg-terciary" @click="closeDialog"> Cancel </v-btn>
          <v-btn class="text-romm-green bg-terciary" @click="editCollection">
            Update
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

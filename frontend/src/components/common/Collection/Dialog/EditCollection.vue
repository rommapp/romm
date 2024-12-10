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
import { useI18n } from "vue-i18n";

// Props
const { t } = useI18n();
const theme = useTheme();
const { smAndDown, mdAndUp, lgAndUp } = useDisplay();
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
  imagePreviewUrl.value = `/assets/default/cover/big_${theme.global.name.value}_collection.png`;
  removeCover.value = true;
}

async function editCollection() {
  if (!collection.value) return;

  emitter?.emit("showLoadingDialog", { loading: true, scrim: true });

  await collectionApi
    .updateCollection({
      collection: collection.value,
      removeCover: removeCover.value,
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
    :width="lgAndUp ? '65vw' : '95vw'"
  >
    <template #content>
      <v-row class="align-center pa-2" no-gutters>
        <v-col cols="12" md="8" xl="9">
          <v-row class="px-2" no-gutters>
            <v-col>
              <v-text-field
                v-model="collection.name"
                class="py-2"
                :label="t('collection.name')"
                variant="outlined"
                required
                hide-details
                @keyup.enter="editCollection"
              />
            </v-col>
          </v-row>
          <v-row class="px-2" no-gutters>
            <v-col>
              <v-text-field
                v-model="collection.description"
                class="py-2"
                :label="t('collection.description')"
                variant="outlined"
                required
                hide-details
                @keyup.enter="editCollection"
              />
            </v-col>
          </v-row>
          <v-row class="px-2" no-gutters>
            <v-col>
              <v-switch
                v-model="collection.is_public"
                color="romm-accent-1"
                class="px-2"
                false-icon="mdi-lock"
                true-icon="mdi-lock-open"
                inset
                hide-details
                :label="
                  collection.is_public
                    ? t('collection.public-desc')
                    : t('collection.private-desc')
                "
              />
            </v-col>
          </v-row>
        </v-col>
        <v-col cols="12" md="4" xl="3">
          <v-row
            class="justify-center"
            :class="{ 'mt-4': smAndDown }"
            no-gutters
          >
            <v-col style="max-width: 240px">
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
      <v-row class="justify-center pa-2 mt-1" no-gutters>
        <v-btn-group divided density="compact">
          <v-btn class="bg-terciary" @click="closeDialog">
            {{ t("common.cancel") }}
          </v-btn>
          <v-btn class="text-romm-green bg-terciary" @click="editCollection">
            {{ t("common.update") }}
          </v-btn>
        </v-btn-group>
      </v-row>
    </template>
  </r-dialog>
</template>

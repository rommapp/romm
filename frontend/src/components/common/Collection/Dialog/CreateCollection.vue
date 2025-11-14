<script setup lang="ts">
import type { Emitter } from "mitt";
import { computed, inject, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useRouter } from "vue-router";
import { useDisplay } from "vuetify";
import CollectionCard from "@/components/common/Collection/Card.vue";
import RDialog from "@/components/common/RDialog.vue";
import { ROUTES } from "@/plugins/router";
import collectionApi, {
  type UpdatedCollection,
} from "@/services/api/collection";
import storeCollections from "@/stores/collections";
import storeHeartbeat from "@/stores/heartbeat";
import type { Events } from "@/types/emitter";
import { getMissingCoverImage } from "@/utils/covers";

const { t } = useI18n();
const { mdAndUp } = useDisplay();
const router = useRouter();
const show = ref(false);
const heartbeat = storeHeartbeat();
const collection = ref<UpdatedCollection>({
  name: "",
  path_covers_large: [],
  path_covers_small: [],
} as unknown as UpdatedCollection);
const collectionsStore = storeCollections();
const imagePreviewUrl = ref<string | undefined>("");
const removeCover = ref(false);
const emitter = inject<Emitter<Events>>("emitter");
emitter?.on("showCreateCollectionDialog", () => {
  show.value = true;
  removeCover.value = false;
});
emitter?.on("updateUrlCover", (coverUrl) => {
  setArtwork(coverUrl);
});

const missingCoverImage = computed(() =>
  getMissingCoverImage(collection.value.name || ""),
);

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
  if (!coverUrl || !collection.value) return;
  collection.value.url_cover = coverUrl;
  imagePreviewUrl.value = coverUrl;
  removeCover.value = false;
}

async function removeArtwork() {
  imagePreviewUrl.value = missingCoverImage.value;
  removeCover.value = true;
}

async function createCollection() {
  if (!collection.value) return;

  emitter?.emit("showLoadingDialog", { loading: true, scrim: true });

  try {
    const { data } = await collectionApi.createCollection({
      collection: collection.value,
    });

    emitter?.emit("snackbarShow", {
      msg: `Collection ${data.name} created successfully!`,
      icon: "mdi-check-bold",
      color: "green",
      timeout: 2000,
    });
    collectionsStore.addCollection(data);
    if (data.is_favorite) collectionsStore.setFavoriteCollection(data);
    emitter?.emit("showLoadingDialog", { loading: false, scrim: false });
    router.push({ name: ROUTES.COLLECTION, params: { collection: data.id } });
    closeDialog();
  } catch (error) {
    console.error(error);
    emitter?.emit("snackbarShow", {
      msg: "Failed to create collection",
      icon: "mdi-close-circle",
      color: "red",
    });
  }
}

function closeDialog() {
  show.value = false;
  collection.value = {} as UpdatedCollection;
  imagePreviewUrl.value = "";
}
</script>

<template>
  <RDialog
    v-model="show"
    icon="mdi-bookmark-box-multiple"
    :width="mdAndUp ? '45vw' : '95vw'"
    @close="closeDialog"
  >
    <template #header>
      <v-card-title>{{ t("collection.create-collection") }}</v-card-title>
    </template>
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
                @keyup.enter="createCollection"
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
                @keyup.enter="createCollection"
              />
            </v-col>
          </v-row>
          <v-row class="pa-2" no-gutters>
            <v-col>
              <v-switch
                v-model="collection.is_public"
                :label="t('collection.public-desc')"
                color="primary"
                hide-details
              />
            </v-col>
          </v-row>
        </v-col>
        <v-col>
          <v-row class="pa-2 justify-center" no-gutters>
            <v-col class="cover">
              <CollectionCard
                :key="collection.updated_at"
                :show-title="false"
                :with-link="false"
                :collection="collection"
                :cover-src="imagePreviewUrl"
                title-on-hover
              >
                <template #append-inner>
                  <v-btn-group divided density="compact">
                    <v-btn
                      :disabled="
                        !heartbeat.value.METADATA_SOURCES
                          ?.STEAMGRIDDB_API_ENABLED
                      "
                      size="small"
                      class="translucent"
                      @click="
                        emitter?.emit('showSearchCoverDialog', {
                          term: collection.name,
                        })
                      "
                    >
                      <v-icon size="large"> mdi-image-search-outline </v-icon>
                    </v-btn>
                    <v-btn
                      size="small"
                      class="translucent"
                      @click="triggerFileInput"
                    >
                      <v-icon size="large"> mdi-pencil </v-icon>
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
            </v-col>
          </v-row>
        </v-col>
      </v-row>
    </template>
    <template #append>
      <v-divider />
      <v-row class="justify-center pa-2" no-gutters>
        <v-btn-group divided density="compact">
          <v-btn class="bg-toplayer" @click="closeDialog">
            {{ t("common.cancel") }}
          </v-btn>
          <v-btn
            class="bg-toplayer text-romm-green"
            :disabled="!collection.name"
            :variant="!collection.name ? 'plain' : 'flat'"
            @click="createCollection"
          >
            {{ t("common.create") }}
          </v-btn>
        </v-btn-group>
      </v-row>
    </template>
  </RDialog>
</template>
<style scoped>
.cover {
  min-width: 240px;
  min-height: 330px;
  max-width: 240px;
  max-height: 330px;
}
</style>

<script setup lang="ts">
import type { Emitter } from "mitt";
import { inject, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import CreateClientTokenDialog from "@/components/Settings/ClientApiTokens/Dialog/CreateClientToken.vue";
import DeleteClientTokenDialog from "@/components/Settings/ClientApiTokens/Dialog/DeleteClientToken.vue";
import RSection from "@/components/common/RSection.vue";
import clientTokenApi, {
  type ClientTokenSchema,
} from "@/services/api/client-token";
import type { Events } from "@/types/emitter";
import { formatTimestamp } from "@/utils";

const { t, locale } = useI18n();
const tokenSearch = ref("");
const tokens = ref<ClientTokenSchema[]>([]);
const emitter = inject<Emitter<Events>>("emitter");

const HEADERS = [
  {
    title: "Name",
    align: "start",
    sortable: true,
    key: "name",
  },
  {
    title: "Scopes",
    align: "start",
    sortable: false,
    key: "scopes",
  },
  {
    title: "Expires",
    align: "start",
    sortable: true,
    key: "expires_at",
  },
  {
    title: "Last used",
    align: "start",
    sortable: true,
    key: "last_used_at",
  },
  { title: "", align: "end", key: "actions", sortable: false },
] as const;

function fetchTokens() {
  clientTokenApi
    .fetchTokens()
    .then(({ data }) => {
      tokens.value = data;
    })
    .catch((error) => {
      console.error(error);
    });
}

onMounted(fetchTokens);

function onTokenCreated() {
  fetchTokens();
}

function onTokenDeleted(tokenId: number) {
  tokens.value = tokens.value.filter((t) => t.id !== tokenId);
}
</script>

<template>
  <RSection
    icon="mdi-key-variant"
    :title="t('settings.client-api-tokens')"
    class="ma-2"
  >
    <template #content>
      <v-text-field
        v-model="tokenSearch"
        prepend-inner-icon="mdi-magnify"
        :label="t('common.search')"
        single-line
        hide-details
        clearable
        rounded="0"
        density="comfortable"
        class="bg-surface"
      />
      <v-data-table-virtual
        :style="{ 'max-height': '75dvh' }"
        :search="tokenSearch"
        :headers="HEADERS"
        :items="tokens"
        :sort-by="[{ key: 'name', order: 'asc' }]"
        fixed-header
        fixed-footer
        density="comfortable"
        class="rounded bg-background"
        hide-default-footer
      >
        <template #header.actions>
          <v-btn
            prepend-icon="mdi-plus"
            variant="outlined"
            density="compact"
            class="text-primary"
            @click="emitter?.emit('showCreateClientTokenDialog', null)"
          >
            {{ t("common.create") }}
          </v-btn>
        </template>
        <template #item.name="{ item }">
          <v-list-item class="pa-0" min-width="120px">
            {{ item.name }}
          </v-list-item>
        </template>
        <template #item.scopes="{ item }">
          <v-chip
            v-for="scope in item.scopes"
            :key="scope"
            size="x-small"
            class="mr-1"
            label
          >
            {{ scope }}
          </v-chip>
        </template>
        <template #item.expires_at="{ item }">
          {{
            item.expires_at
              ? formatTimestamp(item.expires_at, locale)
              : t("settings.client-token-expiry-never")
          }}
        </template>
        <template #item.last_used_at="{ item }">
          {{
            item.last_used_at ? formatTimestamp(item.last_used_at, locale) : "-"
          }}
        </template>
        <template #item.actions="{ item }">
          <v-btn-group divided density="compact" variant="text">
            <v-btn
              size="small"
              title="Regenerate"
              @click="emitter?.emit('showRegenerateClientTokenDialog', item)"
            >
              <v-icon>mdi-refresh</v-icon>
            </v-btn>
            <v-btn
              class="text-romm-red"
              size="small"
              title="Delete"
              @click="emitter?.emit('showDeleteClientTokenDialog', item)"
            >
              <v-icon>mdi-delete</v-icon>
            </v-btn>
          </v-btn-group>
        </template>
      </v-data-table-virtual>
    </template>
  </RSection>

  <CreateClientTokenDialog @created="onTokenCreated" />
  <DeleteClientTokenDialog @deleted="onTokenDeleted" />
</template>

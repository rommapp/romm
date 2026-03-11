<script setup lang="ts">
import type { Emitter } from "mitt";
import { inject, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import RSection from "@/components/common/RSection.vue";
import clientTokenApi, {
  type ClientTokenAdminSchema,
} from "@/services/api/client-token";
import type { Events } from "@/types/emitter";
import { formatTimestamp } from "@/utils";

const { t, locale } = useI18n();
const tokenSearch = ref("");
const tokens = ref<ClientTokenAdminSchema[]>([]);
const emitter = inject<Emitter<Events>>("emitter");

const HEADERS = [
  {
    title: "User",
    align: "start",
    sortable: true,
    key: "username",
  },
  {
    title: "Token Name",
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
    .fetchAllTokens()
    .then(({ data }) => {
      tokens.value = data;
    })
    .catch((error) => {
      console.error(error);
    });
}

async function adminDelete(tokenId: number) {
  await clientTokenApi
    .adminDeleteToken(tokenId)
    .then(() => {
      tokens.value = tokens.value.filter((t) => t.id !== tokenId);
      emitter?.emit("snackbarShow", {
        msg: t("settings.client-token-deleted"),
        icon: "mdi-check",
        color: "romm-green",
        timeout: 4000,
      });
    })
    .catch(({ response, message }) => {
      emitter?.emit("snackbarShow", {
        msg: `Unable to revoke token: ${
          response?.data?.detail || response?.statusText || message
        }`,
        icon: "mdi-close-circle",
        color: "red",
      });
    });
}

onMounted(fetchTokens);
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
        :style="{ 'max-height': '40dvh' }"
        :search="tokenSearch"
        :headers="HEADERS"
        :items="tokens"
        :sort-by="[{ key: 'username', order: 'asc' }]"
        fixed-header
        fixed-footer
        density="comfortable"
        class="rounded bg-background"
        hide-default-footer
      >
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
          <v-btn
            size="small"
            variant="text"
            class="text-romm-red"
            @click="adminDelete(item.id)"
          >
            <v-icon>mdi-delete</v-icon>
          </v-btn>
        </template>
      </v-data-table-virtual>
    </template>
  </RSection>
</template>

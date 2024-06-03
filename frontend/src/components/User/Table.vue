<script setup lang="ts">
import userApi from "@/services/api/user";
import storeAuth from "@/stores/auth";
import storeUsers, { type User } from "@/stores/users";
import type { Events } from "@/types/emitter";
import { defaultAvatarPath, formatTimestamp } from "@/utils";
import type { Emitter } from "mitt";
import { inject, onMounted, ref } from "vue";

defineProps<{ userSearch: string }>();
const emitter = inject<Emitter<Events>>("emitter");
const usersStore = storeUsers();
const auth = storeAuth();
const HEADERS = [
  {
    title: "",
    align: "start",
    sortable: false,
    key: "avatar_path",
    width: "40px",
  },
  {
    title: "Username",
    align: "start",
    sortable: true,
    key: "username",
  },
  {
    title: "Role",
    align: "start",
    sortable: true,
    key: "role",
  },
  {
    title: "Last active",
    align: "start",
    sortable: true,
    key: "last_active",
  },
  {
    title: "Enabled",
    align: "start",
    sortable: true,
    key: "enabled",
  },
  { title: "", align: "end", key: "actions", sortable: false },
] as const;
const PER_PAGE_OPTIONS = [10, 25, 50, 100];
const page = ref(1);
const storedUsersPerPage = parseInt(localStorage.getItem("usersPerPage") ?? "");
const usersPerPage = ref(isNaN(storedUsersPerPage) ? 25 : storedUsersPerPage);
const pageCount = ref(0);
emitter?.on("updateDataTablePages", updateDataTablePages);

function updateDataTablePages() {
  pageCount.value = Math.ceil(usersStore.all.length / usersPerPage.value);
}

function disableUser(user: User) {
  userApi.updateUser(user).catch(({ response, message }) => {
    emitter?.emit("snackbarShow", {
      msg: `Unable to disable/enable user: ${
        response?.data?.detail || response?.statusText || message
      }`,
      icon: "mdi-close-circle",
      color: "red",
      timeout: 5000,
    });
  });
}

onMounted(() => {
  userApi
    .fetchUsers()
    .then(({ data }) => {
      usersStore.set(data);
    })
    .catch((error) => {
      console.log(error);
    });
});
</script>

<template>
  <v-data-table
    v-model:items-per-page="usersPerPage"
    v-model:page="page"
    :items-per-page-options="PER_PAGE_OPTIONS"
    :search="userSearch"
    :headers="HEADERS"
    :items="usersStore.all"
    :sort-by="[{ key: 'username', order: 'asc' }]"
  >
    <template #item.avatar_path="{ item }">
      <v-avatar>
        <v-img
          :src="
            item.avatar_path
              ? `/assets/romm/assets/${item.avatar_path}`
              : defaultAvatarPath
          "
        />
      </v-avatar>
    </template>
    <template #item.last_active="{ item }">
      {{ formatTimestamp(item.last_active) }}
    </template>
    <template #item.enabled="{ item }">
      <v-switch
        v-model="item.enabled"
        color="romm-accent-1"
        :disabled="item.id == auth.user?.id"
        hide-details
        @change="disableUser(item)"
      />
    </template>
    <template #item.actions="{ item }">
      <v-btn
        variant="text"
        class="ma-1 bg-terciary"
        size="small"
        rounded="0"
        @click="emitter?.emit('showEditUserDialog', item)"
      >
        <v-icon>mdi-pencil</v-icon>
      </v-btn>
      <v-btn
        variant="text"
        class="ma-1 bg-terciary text-romm-red"
        size="small"
        rounded="0"
        @click="emitter?.emit('showDeleteUserDialog', item)"
      >
        <v-icon>mdi-delete</v-icon>
      </v-btn>
    </template>

    <template #bottom>
      <v-divider class="border-opacity-25" />
      <v-row no-gutters class="pt-2 align-center">
        <v-col cols="11" class="px-6">
          <v-pagination
            v-model="page"
            rounded="0"
            :show-first-last-page="true"
            active-color="romm-accent-1"
            :length="pageCount"
          />
        </v-col>
        <v-col cols="5" sm="2" xl="1">
          <v-select
            v-model="usersPerPage"
            class="pa-2"
            label="Users per page"
            density="compact"
            variant="outlined"
            :items="PER_PAGE_OPTIONS"
            hide-details
          />
        </v-col>
      </v-row>
    </template>
  </v-data-table>
</template>

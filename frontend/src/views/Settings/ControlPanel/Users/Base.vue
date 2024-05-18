<script setup lang="ts">
import userApi from "@/services/api/user";
import storeAuth from "@/stores/auth";
import storeUsers, { type User } from "@/stores/users";
import type { Events } from "@/types/emitter";
import { defaultAvatarPath, formatTimestamp } from "@/utils";
import type { Emitter } from "mitt";
import { inject, onMounted, ref } from "vue";

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

const PER_PAGE_OPTIONS = [
  { value: 5, title: "5" },
  { value: 10, title: "10" },
  { value: 25, title: "25" },
  { value: -1, title: "$vuetify.dataFooter.itemsPerPageAll" },
];

// Props
const emitter = inject<Emitter<Events>>("emitter");
const auth = storeAuth();
const usersStore = storeUsers();
const usersPerPage = ref(5);
const userSearch = ref("");

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
  <v-card rounded="0" elevation="0">
    <v-toolbar class="bg-terciary" density="compact">
      <v-toolbar-title class="text-button"
        ><v-icon class="mr-3">mdi-account-group</v-icon>Users</v-toolbar-title
      >
      <v-btn
        prepend-icon="mdi-plus"
        variant="outlined"
        class="text-romm-accent-1"
        @click="emitter?.emit('showCreateUserDialog', null)"
      >
        Add
      </v-btn>
    </v-toolbar>

    <v-divider class="border-opacity-25" />

    <v-card-text class="pa-0">
      <v-text-field
        v-model="userSearch"
        prepend-inner-icon="mdi-magnify"
        label="Search"
        rounded="0"
        single-line
        hide-details
        clearable
        density="comfortable"
        class="bg-secondary"
      />
      <v-data-table
        :items-per-page-options="PER_PAGE_OPTIONS"
        v-model:items-per-page="usersPerPage"
        :search="userSearch"
        :headers="HEADERS"
        :items="usersStore.all"
        :sort-by="[{ key: 'username', order: 'asc' }]"
      >
        <template v-slot:item.avatar_path="{ item }">
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
        <template v-slot:item.last_active="{ item }">
          {{ formatTimestamp(item.last_active) }}
        </template>
        <template v-slot:item.enabled="{ item }">
          <v-switch
            color="romm-accent-1"
            :disabled="item.id == auth.user?.id"
            v-model="item.enabled"
            @change="disableUser(item)"
            hide-details
          />
        </template>
        <template v-slot:item.actions="{ item }">
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
            ><v-icon>mdi-delete</v-icon></v-btn
          >
        </template>
      </v-data-table>
    </v-card-text>
  </v-card>
</template>

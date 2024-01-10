<script setup lang="ts">
import { ref, inject, onMounted } from "vue";
import type { Emitter } from "mitt";
import { VDataTable } from "vuetify/labs/VDataTable";
import type { Events } from "@/types/emitter";

import api from "@/services/api";
import storeAuth from "@/stores/auth";
import storeUsers from "@/stores/users";
import { defaultAvatarPath } from "@/utils";
import CreateUserDialog from "@/components/Dialog/User/CreateUser.vue";
import EditUserDialog from "@/components/Dialog/User/EditUser.vue";
import DeleteUserDialog from "@/components/Dialog/User/DeleteUser.vue";
import type { UserItem } from "@/types/emitter";

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

function disableUser(user: UserItem) {
  api.updateUser(user).catch(({ response, message }) => {
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
  api
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
                item.raw.avatar_path
                  ? `/assets/romm/resources/${item.raw.avatar_path}`
                  : defaultAvatarPath
              "
            />
          </v-avatar>
        </template>
        <template v-slot:item.enabled="{ item }">
          <v-switch
            color="romm-accent-1"
            :disabled="item.raw.id == auth.user?.id"
            v-model="item.raw.enabled"
            @change="disableUser(item.raw)"
            hide-details
          />
        </template>
        <template v-slot:item.actions="{ item }">
          <v-btn
            variant="text"
            class="ma-1 bg-terciary"
            size="small"
            rounded="0"
            @click="emitter?.emit('showEditUserDialog', item.raw)"
          >
            <v-icon>mdi-pencil</v-icon>
          </v-btn>
          <v-btn
            variant="text"
            class="ma-1 bg-terciary text-romm-red"
            size="small"
            rounded="0"
            @click="emitter?.emit('showDeleteUserDialog', item.raw)"
            ><v-icon>mdi-delete</v-icon></v-btn
          >
        </template>
      </v-data-table>
    </v-card-text>

    <create-user-dialog />
    <edit-user-dialog />
    <delete-user-dialog />
  </v-card>
</template>

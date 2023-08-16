<script setup>
import { ref, inject } from "vue";
import { VDataTable } from "vuetify/labs/VDataTable";
import CreateUserDialog from "@/components/Dialog/User/CreateUser.vue";
import EditUserDialog from "@/components/Dialog/User/EditUser.vue";
import DeleteUserDialog from "@/components/Dialog/User/DeleteUser.vue";

const emitter = inject("emitter");

const usersHeaders = [
  {
    title: "Username",
    align: "start",
    sortable: true,
    key: "username",
  },
  {
    title: "Rol",
    align: "start",
    sortable: true,
    key: "rol",
  },
  { align: "end", key: "actions", sortable: false },
];
const users = ref([
  {
    id: 1,
    username: "User 1",
    rol: "Admin",
  },
  {
    id: 2,
    username: "User 2",
    rol: "user",
  },
  {
    id: 3,
    username: "User 3",
    rol: "Admin",
  },
  {
    id: 4,
    username: "User 4",
    rol: "user",
  },
  {
    id: 5,
    username: "User 5",
    rol: "user",
  },
  {
    id: 6,
    username: "User 6",
    rol: "user",
  },
  {
    id: 7,
    username: "User 7",
    rol: "Admin",
  },
  {
    id: 8,
    username: "User 8",
    rol: "user",
  },
  {
    id: 9,
    username: "User 9",
    rol: "Admin",
  },
  {
    id: 10,
    username: "User 10",
    rol: "user",
  },
  {
    id: 11,
    username: "User 13123",
    rol: "Admin",
  },
  {
    id: 12,
    username: "User 2",
    rol: "user",
  },
  {
    id: 13,
    username: "User 3",
    rol: "Admin",
  },
  {
    id: 14,
    username: "User 4",
    rol: "user",
  },
  {
    id: 15,
    username: "User 5",
    rol: "user",
  },
  {
    id: 16,
    username: "User 6",
    rol: "user",
  },
  {
    id: 17,
    username: "User 7",
    rol: "Admin",
  },
  {
    id: 18,
    username: "User 8",
    rol: "user",
  },
  {
    id: 19,
    username: "User 9",
    rol: "Admin",
  },
]);
const usersPerPage = ref(5);
const usersPerPageOptions = [
  { value: 5, title: "5" },
  { value: 10, title: "10" },
  { value: 25, title: "25" },
  { value: -1, title: "$vuetify.dataFooter.itemsPerPageAll" },
];
const userSearch = ref("");
</script>
<template>
  <v-card rounded="0">
    <v-toolbar class="bg-terciary" density="compact">
      <v-toolbar-title class="text-button"
        ><v-icon class="mr-3">mdi-account-group</v-icon>Users</v-toolbar-title
      >
      <v-btn
        prepend-icon="mdi-plus"
        variant="outlined"
        class="text-rommAccent1"
        @click="emitter.emit('showCreateUserDialog')"
      >
        Add user
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
      ></v-text-field>

      <create-user-dialog />

      <edit-user-dialog />

      <delete-user-dialog />
      <v-data-table
        :items-per-page-options="usersPerPageOptions"
        v-model:items-per-page="usersPerPage"
        :search="userSearch"
        :headers="usersHeaders"
        :items="users"
        :sort-by="[{ key: 'username', order: 'asc' }]"
      >
        <template v-slot:item.actions="{ item }">
          <v-btn
            class="me-2 bg-terciary"
            @click="emitter.emit('showEditUserDialog', { ...item.raw })"
          >
            <v-icon>mdi-pencil</v-icon>
          </v-btn>
          <v-btn
            class="bg-terciary text-rommRed"
            @click="emitter.emit('showDeleteUserDialog', item.raw)"
            ><v-icon>mdi-delete</v-icon></v-btn
          >
        </template>
      </v-data-table>
    </v-card-text>
  </v-card>
</template>

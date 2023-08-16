<script setup>
import { ref, inject } from "vue";

const user = ref({
  username: "",
  password: "",
  rol: "user",
});
const show = ref(false);

const emitter = inject("emitter");
emitter.on("showCreateUserDialog", () => {
  show.value = true;
});

function createUser() {
  // TODO: create user endpoint
  console.log("Creating user:")
  console.log(user.value)
  show.value = false;
  user.value = { username: "", password: "", rol: "user" };
}
</script>
<template>
  <v-dialog v-model="show" max-width="500px" :scrim="false">
    
    <v-card>
      <v-toolbar density="compact" class="bg-terciary">
        <v-row class="align-center" no-gutters>
          <v-col cols="10">
            <v-icon icon="mdi-account" class="ml-5 mr-2" />
          </v-col>
          <v-col>
            <v-btn
              @click="show = false"
              class="bg-terciary"
              rounded="0"
              variant="text"
              icon="mdi-close"
              block
            />
          </v-col>
        </v-row>
      </v-toolbar>
      <v-divider class="border-opacity-25" :thickness="1" />

      <v-card-text>
        <v-row class="pa-2" no-gutters>
          <v-col>
            <v-text-field
              rounded="0"
              variant="outlined"
              v-model="user.username"
              label="username"
              required
              hide-details
              clearable
            ></v-text-field>
          </v-col>
        </v-row>
        <v-row class="pa-2" no-gutters>
          <v-col>
            <v-text-field
              rounded="0"
              variant="outlined"
              v-model="user.password"
              label="Password"
              required
              hide-details
              clearable
            ></v-text-field>
          </v-col>
        </v-row>
        <v-row class="pa-2" no-gutters>
          <v-col>
            <v-select
              v-model="user.rol"
              rounded="0"
              variant="outlined"
              :items="['admin', 'user']"
              label="Rol"
              required
              hide-details
            ></v-select>
          </v-col>
        </v-row>
        <v-row class="justify-center pa-2" no-gutters>
          <v-btn @click="show = false" class="bg-terciary">Cancel</v-btn>
          <v-btn class="text-rommGreen bg-terciary ml-5" @click="createUser()"
            >Create</v-btn
          >
        </v-row>
      </v-card-text>
    </v-card>
  </v-dialog>
</template>

<script setup>
import axios from 'axios'
import { ref } from "vue";
import { useTheme } from "vuetify";

const server = "localhost"
const port = "5000"

const platforms = ref([])
console.log("Getting platforms...")
const GetPlatforms = async () => {
    await axios.get('http://'+server+':'+port+'/platforms').then((response) => {
        console.log("Platforms loaded!")
        console.log(response.data.data)
        platforms.value = response.data.data
    })
}
GetPlatforms()

const scan = (overwrite) => {
    scaning = true
    axios.get('http://'+server+':'+port+'/scan?overwrite='+overwrite).then((response) => {
        console.log("scan completed")
        console.log(response.data)
        scaning = false
    })
}

const theme = useTheme();
const darkMode = ref(true);
const toggleTheme = () => {
  theme.global.name.value = darkMode.value ? "dark" : "light"
}

</script>

<template>
    
    <v-navigation-drawer width="250">
        <v-list>
            <v-list-item prepend-icon="mdi mdi-controller">Rom Manager</v-list-item>
        </v-list>

        <v-divider ></v-divider>

        <v-list nav>
            <v-list-item v-for="platform in platforms" 
                :title="platform.name" 
                :value="platform.slug"
                :key="platform"
                @:click="$emit('currentPlatform', platform.slug)"/>
        </v-list>

        <v-divider ></v-divider>

        <v-list>
            <v-btn color="secondary" prepend-icon="mdi mdi-magnify-scan" @click="scan()" inset class="ml-3">Scan</v-btn>
        </v-list>

        <v-divider ></v-divider>

        <v-list>
            <v-switch prepend-icon="mdi mdi-brightness-6" v-model="darkMode" @change="toggleTheme()" inset class="pl-3"/>
        </v-list>

    </v-navigation-drawer>

</template>

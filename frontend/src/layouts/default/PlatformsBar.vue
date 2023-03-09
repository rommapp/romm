<script>
import axios from 'axios'
export default {
    data() {
        return {
            server: "asgard",
            port: "5000",
            currentPlatform: "",
            platformsLoaded: false,
            scaning: false
        };
    },
    created() {
        console.log("Getting platforms...")
        axios.get('http://'+this.server+':'+this.port+'/platforms').then((response) => {
            console.log("Platforms loaded!")
            console.log(response.data)
            this.platforms = response.data.data
            this.platformsLoaded = true
        })
    },
    methods: {
        scan(overwrite) {
            this.scaning = true
            axios.get('http://'+this.server+':'+this.port+'/scan?overwrite='+overwrite).then((response) => {
                console.log("scan completed")
                console.log(response.data)
                this.scaning = false
            })
        }
    }
}
</script>

<template>
    <v-layout>
      <v-navigation-drawer thene="dark" class="transparent">

        <v-list>
          <v-list-item prepend-icon="mdi mdi-controller">Rom Manager</v-list-item>
        </v-list>

        <v-divider class="text-black"></v-divider>

        <v-list :items="platforms" item-title="name" item-value="slug" density="compact" nav v-if="platformsLoaded" />
        
      </v-navigation-drawer>
    </v-layout>
</template>

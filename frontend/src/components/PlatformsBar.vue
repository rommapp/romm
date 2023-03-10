<script>
import axios from 'axios'
export default {
    data() {
        return {
            server: "localhost",
            port: "5000",
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
    
    <v-navigation-drawer theme="dark" width="250" >
        <v-list>
            <v-list-item prepend-icon="mdi mdi-controller">Rom Manager</v-list-item>
        </v-list>

        <v-divider class="text-white"></v-divider>

        <v-list nav v-if="platformsLoaded">
            <v-list-item v-for="platform in platforms"
                :title="platform.name" 
                :value="platform.slug" 
                :key="platform.slug" 
                @:click="$emit('currentPlatform', platform.slug)"/>
        </v-list>
    </v-navigation-drawer>

</template>

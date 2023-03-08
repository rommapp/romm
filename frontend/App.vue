<script>
import Game from './components/Game.vue';
import axios from 'axios'
export default {
    data() {
        return {
            server: "asgard",
            port: "5001",
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
    <div class="plat_container">
        <div class="table_plat">
            <ul class="row_plat">
                <li v-if="platformsLoaded" v-for="platform in platforms">
                    <div>
                        <a v-on:click="this.currentPlatform = platform.slug">
                            <img class="plat" :src=platform.path_logo>
                        </a>
                    </div>
                </li>
            </ul>
        </div>
    </div>
    <!-- <div class="game_container">
        <Game v-if="platformsLoaded" :platform=this.currentPlatform :key=this.currentPlatform />
    </div> -->
    <div>
        <div class="table_plat">
            <ul class="row_plat">
                <li>
                    <button @click="scan(false)">Scan</button>
                </li>
                <li>
                    <button @click="scan(true)">Force Scan</button>
                </li>
                <li>
                    <h3 v-if="scaning">Scanning...</h3>
                </li>
            </ul>
        </div>
    </div>
</template>

<style scoped>
* {
    box-sizing: border-box;
}

.plat {
    text-decoration: none;
    color: hsla(160, 100%, 37%, 1);
    transition: 0.4s;
    max-width: 160px;
    max-height: 160px;
}

.table_plat .row_plat {
    /* border: 2px solid green; */
    display: flex;
    flex-wrap: wrap;
    list-style: none;
    padding-left: 40px;
    padding-right: 40px;
}

.table_plat .row_plat li {
    /* border: 2px solid red; */
    text-align: center;
    padding-left: 20px;
    padding-right: 20px;
    font-size: x-small;
}
</style>
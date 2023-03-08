<script>
import axios from 'axios'
export default {
    props: { platform: String },
    data() {
        return {
            server: "asgard",
            gamesLoaded: null,
        };
    },
    created() {
        console.log("Getting roms...")
        axios.get('http://'+this.server+':5000/platforms/'+this.platform+'/roms').then((response) => {
            console.log("Romds loaded!")
            console.log(response.data)
            this.games = response.data
            this.gamesLoaded = true
        })
    }
}
</script>

<template>
    <div class="table_games">
        <ul class="row_games">
            <li v-if="gamesLoaded" v-for="game in games">
                <div>
                    <img class="game_cover" :src=game.props.cover_url>
                    <h3 class="game_title">{{ game.filename }}</h3>
                </div>
            </li>
        </ul>
    </div>
</template>

<style scoped>
.table_games .row_games {
    /* border: 2px solid blue; */
    display: flex;
    flex-wrap: wrap;
    list-style: none;
    padding-left: 40px;
    padding-right: 40px;
}

.table_games .row_games li {
    /* border: 2px solid purple; */
    text-align: center;
    padding: 5px;
    font-size: x-small;
    padding-bottom: 40px;
}

.table_games .row_games li .game_title {
    width: 205px;
}

.table_games .row_games li .game_cover {
    width: 205px;
}
</style>
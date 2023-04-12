<script setup>
import { inject } from "vue"
import { useRouter } from 'vue-router'
import { useDisplay } from "vuetify"

// Props
const props = defineProps(['platform', 'rail'])
const { mobile } = useDisplay()
const router = useRouter()

// Event listeners bus
const emitter = inject('emitter')

// Functions
async function selectPlatform(platform){    
    if(mobile.value){emitter.emit('togglePlatforms')}
    await router.push(import.meta.env.BASE_URL)
    localStorage.setItem('selectedPlatform', JSON.stringify(platform))
    emitter.emit('selectedPlatform', platform)
}
</script>

<template>
    <v-list-item
        :value="platform.slug"
        :key="platform"
        @:click="selectPlatform(platform)" class="pt-4 pb-4">
        <p class="text-subtitle-2 text-truncate">{{ rail ? '' : platform.name }}</p>
        <template v-slot:prepend>
            <v-avatar :rounded="0"><v-img :src="'/assets/platforms/'+platform.slug+'.ico'"></v-img></v-avatar>
        </template>
        <template v-slot:append>
            <v-chip class="ml-4" size="small">{{ platform.n_roms }}</v-chip>
        </template>
    </v-list-item>
</template>

<style scoped>
.v-navigation-drawer--rail:not(.v-navigation-drawer--is-hovering) .v-list .v-avatar {
  --v-avatar-height: 40px;
}
</style>
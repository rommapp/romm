<script setup>
// Props
const props = defineProps(['rom', 'isHovering', 'hoverProps', 'size'])
const forceImgReload = Date.now()
</script>

<template>
    <router-link
        style="text-decoration: none; color: inherit;"
        :to="`/platform/${$route.params.platform}/rom/${rom.id}`">
        <v-img
            :value="rom.id"
            :key="rom.id"
            v-bind="hoverProps"
            :src="'/assets'+rom.path_cover_l+'?reload='+forceImgReload"
            :lazy-src="'/assets'+rom.path_cover_s+'?reload='+forceImgReload"
            class="cover"
            cover>
            <template v-slot:placeholder>
                <div class="d-flex align-center justify-center fill-height">
                    <v-progress-circular color="rommAccent1" indeterminate/>
                </div>
            </template>
            <v-expand-transition>
                <div 
                    v-if="isHovering || !rom.has_cover"
                    class="rom-title d-flex transition-fast-in-fast-out bg-tooltip text-caption">
                    <v-list-item>{{ rom.file_name }}</v-list-item>
                </div>
            </v-expand-transition>
            <v-chip-group class="pl-1 pt-0">
                <v-chip v-show="rom.multi"
                    size="x-small"
                    class="bg-chip"
                    label>
                    {{ rom.files.length }}
                </v-chip>
                <v-chip
                    v-show="rom.region"
                    size="x-small"
                    class="bg-chip"
                    label>
                    {{ rom.region }}
                </v-chip>
                <v-chip
                    v-show="rom.revision"
                    size="x-small"
                    class="bg-chip"
                    label>
                    {{ rom.revision }}
                </v-chip>
            </v-chip-group>
        </v-img>
    </router-link>
</template>

<style scoped>
.v-card .rom-title{
    transition: opacity .4s ease-in-out;
}
.rom-title.on-hover {
    opacity: 1;
}
.rom-title:not(.on-hover) {
    opacity: 0.85;
}
</style>

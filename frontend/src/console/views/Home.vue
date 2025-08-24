<template>
  <div
    ref="scrollContainerRef"
    class="relative h-screen overflow-y-auto overflow-x-hidden"
  >
    <div class="relative h-full flex flex-col">
      <div class="mt-8 ml-8 flex items-center gap-3 select-none pb-3">
        <RIsotipo
          :size="40"
          :avatar="false"
        />
        <div class="text-white/90 font-bold text-[28px] drop-shadow-xl">
          Console
        </div>
      </div>

      <div
        v-if="loading"
        class="text-center text-fgDim mt-16"
      >
        Loading platforms…
      </div>
      <div
        v-else-if="error"
        class="text-center text-red-400 mt-16"
      >
        {{ error }}
      </div>
      <div v-else>
        <section
          ref="platformsSectionRef"
          class="px-8 pb-2"
        >
          <h2 class="text-xl font-bold text-fg0 mb-3 drop-shadow">
            Platforms
          </h2>
          <div class="relative h-[220px]">
            <button
              class="absolute top-1/2 -translate-y-1/2 left-2 w-10 h-10 bg-black/70 border border-white/20 rounded-full flex items-center justify-center text-fg0 cursor-pointer transition-all backdrop-blur z-20 hover:bg-accent2/80 hover:border-accent2"
              @click="prevSystem"
            >
              ◀
            </button>
            <button
              class="absolute top-1/2 -translate-y-1/2 right-2 w-10 h-10 bg-black/70 border border-white/20 rounded-full flex items-center justify-center text-fg0 cursor-pointer transition-all backdrop-blur z-20 hover:bg-accent2/80 hover:border-accent2"
              @click="nextSystem"
            >
              ▶
            </button>
            <div
              ref="systemsRef"
              class="w-full h-full overflow-x-auto overflow-y-hidden no-scrollbar [scrollbar-width:none] [-ms-overflow-style:none]"
              @wheel.prevent="onWheelSystems"
            >
              <div class="flex items-center gap-6 h-full px-8 min-w-max">
                <SystemCard
                  v-for="(p,i) in platforms"
                  :key="p.id"
                  :system="p"
                  :index="i"
                  :selected="navigationMode==='systems' && i===selectedIndex"
                  @click="goPlatform(p.id)"
                  @mouseenter="selectedIndex=i"
                  @focus="selectedIndex=i"
                />
              </div>
            </div>
          </div>
        </section>

        <section
          v-if="recent.length>0"
          ref="recentSectionRef"
          class="px-8 pb-8"
        >
          <h2 class="text-xl font-bold text-fg0 mb-3 drop-shadow">
            Recently Played
          </h2>
          <div class="relative h-[400px]">
            <button
              class="absolute top-1/2 -translate-y-1/2 left-2 w-10 h-10 bg-black/70 border border-white/20 rounded-full flex items-center justify-center text-fg0 cursor-pointer transition-all backdrop-blur z-20 hover:bg-accent2/80 hover:border-accent2"
              @click="prevRecent"
            >
              ◀
            </button>
            <button
              class="absolute top-1/2 -translate-y-1/2 right-2 w-10 h-10 bg-black/70 border border-white/20 rounded-full flex items-center justify-center text-fg0 cursor-pointer transition-all backdrop-blur z-20 hover:bg-accent2/80 hover:border-accent2"
              @click="nextRecent"
            >
              ▶
            </button>
            <div
              ref="recentRef"
              class="w-full h-full overflow-x-auto overflow-y-hidden no-scrollbar [scrollbar-width:none] [-ms-overflow-style:none]"
              @wheel.prevent="onWheelRecent"
            >
              <div class="flex items-center gap-4 h-full px-8 min-w-max">
                <GameCard
                  v-for="(g,i) in recent"
                  :key="`${g.platform_id}-${g.id}`"
                  :rom="g"
                  :index="i"
                  :is-recent="true"
                  :selected="navigationMode==='recent' && i===recentIndex"
                  :loaded="true"
                  @click="goGame(g)"
                  @mouseenter="recentIndex=i"
                  @focus="recentIndex=i"
                />
              </div>
            </div>
          </div>
        </section>

        <section
          v-if="collections.length>0"
          ref="collectionsSectionRef"
          class="px-8 pb-8"
        >
          <h2 class="text-xl font-bold text-fg0 mb-3 drop-shadow">
            Collections
          </h2>
          <div class="relative h-[400px]">
            <button
              class="absolute top-1/2 -translate-y-1/2 left-2 w-10 h-10 bg-black/70 border border-white/20 rounded-full flex items-center justify-center text-fg0 cursor-pointer transition-all backdrop-blur z-20 hover:bg-accent2/80 hover:border-accent2"
              @click="prevCollection"
            >
              ◀
            </button>
            <button
              class="absolute top-1/2 -translate-y-1/2 right-2 w-10 h-10 bg-black/70 border border-white/20 rounded-full flex items-center justify-center text-fg0 cursor-pointer transition-all backdrop-blur z-20 hover:bg-accent2/80 hover:border-accent2"
              @click="nextCollection"
            >
              ▶
            </button>
            <div
              ref="collectionsRef"
              class="w-full h-full overflow-x-auto overflow-y-hidden no-scrollbar [scrollbar-width:none] [-ms-overflow-style:none]"
              @wheel.prevent="onWheelCollections"
            >
              <div class="flex items-center gap-4 h-full px-8 min-w-max">
                <CollectionCard
                  v-for="(c,i) in collections"
                  :key="`collection-${c.id}`"
                  :collection="c"
                  :index="i"
                  :selected="navigationMode==='collections' && i===collectionsIndex"
                  :loaded="true"
                  @click="goCollection(c.id)"
                  @mouseenter="collectionsIndex=i"
                  @focus="collectionsIndex=i"
                />
              </div>
            </div>
          </div>
        </section>
      </div>

      <div class="fixed top-4 right-4 z-20 flex gap-2">
        <button
          class="w-12 h-12 bg-black/80 border border-white/20 rounded-md text-fg0 cursor-pointer flex items-center justify-center text-xl transition-all backdrop-blur hover:bg-white/10 hover:border-white/40 hover:-translate-y-0.5 hover:shadow-lg"
          :class="{ 'border-[var(--accent-2)] bg-[var(--accent-2)]/15 shadow-[0_0_0_2px_var(--accent-2),_0_0_18px_-4px_var(--accent-2)] -translate-y-0.5': navigationMode==='controls' && controlIndex===0 }"
          title="Exit Console Mode (F1)"
          @click="exitConsoleMode"
        >
          ⏻
        </button>
        <button
          class="w-12 h-12 bg-black/80 border border-white/20 rounded-md text-fg0 cursor-pointer flex items-center justify-center text-xl transition-all backdrop-blur hover:bg-white/10 hover:border-white/40 hover:-translate-y-0.5 hover:shadow-lg"
          :class="{ 'border-[var(--accent-2)] bg-[var(--accent-2)]/15 shadow-[0_0_0_2px_var(--accent-2),_0_0_18px_-4px_var(--accent-2)] -translate-y-0.5': navigationMode==='controls' && controlIndex===1 }"
          title="Fullscreen (F11)"
          @click="toggleFullscreen"
        >
          ⛶
        </button>
      </div>
      
      <NavigationHint
        :show-back="false"
        :show-toggle-favorite="navigationMode === 'recent'"
      />
    </div>
  </div>
</template>
<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import platformApi from '@/services/api/platform';
import romApi from '@/services/api/rom';
import collectionApi from '@/services/api/collection';
import storeCollections, { type Collection } from '@/stores/collections';
import { storeToRefs } from 'pinia';
import SystemCard from '@/console/components/SystemCard.vue';
import GameCard from '@/console/components/GameCard.vue';
import CollectionCard from '@/console/components/CollectionCard.vue';
import NavigationHint from '@/console/components/NavigationHint.vue';
import RIsotipo from '@/components/common/RIsotipo.vue';
import type { PlatformSchema } from '@/__generated__/models/PlatformSchema';
import { SUPPORTED_WEB_PLATFORM_SET } from '@/console/constants/platforms';
import type { SimpleRomSchema } from '@/__generated__/models/SimpleRomSchema';
import type { CollectionSchema } from '@/__generated__/models/CollectionSchema';
import { useInputScope } from '@/console/composables/useInputScope';
import type { InputAction } from '@/console/input/actions';

const router = useRouter();
const collectionsStore = storeCollections();
const { favoriteCollection } = storeToRefs(collectionsStore);
const platforms = ref<PlatformSchema[]>([]);
const recent = ref<SimpleRomSchema[]>([]);
const collections = ref<CollectionSchema[]>([]);
const loading = ref(true);
const error = ref('');
const navigationMode = ref<'systems'|'recent'|'collections'|'controls'>('systems');
const selectedIndex = ref(0);
const recentIndex = ref(0);
const collectionsIndex = ref(0);
const controlIndex = ref(0);
const scrollContainerRef = ref<HTMLDivElement>();
const systemsRef = ref<HTMLDivElement>();
const recentRef = ref<HTMLDivElement>();
const collectionsRef = ref<HTMLDivElement>();
const platformsSectionRef = ref<HTMLElement>();
const recentSectionRef = ref<HTMLElement>();
const collectionsSectionRef = ref<HTMLElement>();

function onWheelSystems(e: WheelEvent){
  const el = systemsRef.value; if(!el) return;
  el.scrollLeft += (e.deltaY || e.deltaX);
}
function onWheelRecent(e: WheelEvent){
  const el = recentRef.value; if(!el) return;
  el.scrollLeft += (e.deltaY || e.deltaX);
}
function onWheelCollections(e: WheelEvent){
  const el = collectionsRef.value; if(!el) return;
  el.scrollLeft += (e.deltaY || e.deltaX);
}

function scrollToCurrentRow(){
  const behavior: ScrollBehavior = 'smooth';
  switch(navigationMode.value){
  case 'systems': scrollContainerRef.value?.scrollTo({ top: 0, behavior }); break;
    case 'recent': recentSectionRef.value?.scrollIntoView({ behavior, block: 'start' }); break;
    case 'collections': collectionsSectionRef.value?.scrollIntoView({ behavior, block: 'start' }); break;
    default: break;
  }
}

// Exit console mode by exiting fullscreen and navigating to main RomM interface
function exitConsoleMode() {
  if (document.fullscreenElement) {
    document.exitFullscreen?.();
  }
  router.push({ name: 'home' });
}

function toggleFullscreen(){ const de = document.documentElement as HTMLElement & { requestFullscreen?: () => Promise<void> }; if(!document.fullscreenElement) de.requestFullscreen?.(); else document.exitFullscreen?.(); }
function goPlatform(id:number){ router.push({ name: 'console-platform', params: { id } }); }
function goGame(g: SimpleRomSchema){ router.push({ name: 'console-rom', params: { rom: g.id }, query: { id: g.platform_id } }); }
function goCollection(id: number){ router.push({ name: 'console-collection', params: { id } }); }

function scrollToSelected(container: HTMLDivElement|undefined, el: HTMLElement|undefined){ if(!container||!el) return; const cr=container.getBoundingClientRect(); const er=el.getBoundingClientRect(); const left= el.offsetLeft - (cr.width/2) + (er.width/2); container.scrollTo({ left, behavior:'smooth' }); }

function prevSystem(){ selectedIndex.value = (selectedIndex.value - 1 + platforms.value.length) % platforms.value.length; tickScroll(); }
function nextSystem(){ selectedIndex.value = (selectedIndex.value + 1) % platforms.value.length; tickScroll(); }
function prevRecent(){ recentIndex.value = (recentIndex.value - 1 + recent.value.length) % recent.value.length; tickRecentScroll(); }
function nextRecent(){ recentIndex.value = (recentIndex.value + 1) % recent.value.length; tickRecentScroll(); }
function prevCollection(){ collectionsIndex.value = (collectionsIndex.value - 1 + collections.value.length) % collections.value.length; tickCollectionsScroll(); }
function nextCollection(){ collectionsIndex.value = (collectionsIndex.value + 1) % collections.value.length; tickCollectionsScroll(); }

function tickScroll(){ const w = window as unknown as { systemCardElements?: HTMLElement[] }; const el = w.systemCardElements?.[selectedIndex.value]; scrollToSelected(systemsRef.value!, el); }
function tickRecentScroll(){ const w = window as unknown as { recentGameElements?: HTMLElement[] }; const el = w.recentGameElements?.[recentIndex.value]; scrollToSelected(recentRef.value!, el); }
function tickCollectionsScroll(){ const w = window as unknown as { collectionCardElements?: HTMLElement[] }; const el = w.collectionCardElements?.[collectionsIndex.value]; scrollToSelected(collectionsRef.value!, el); }

async function toggleFavorite() {
  let rom: SimpleRomSchema | undefined;
  
  if (navigationMode.value === 'recent' && recent.value.length > 0) {
    rom = recent.value[recentIndex.value];
  }
  
  if (!rom || !favoriteCollection.value) return;

  try {
    const isCurrentlyFavorite = collectionsStore.isFavorite(rom);
    
    if (!isCurrentlyFavorite) {
      favoriteCollection.value.rom_ids.push(rom.id);
    } else {
      favoriteCollection.value.rom_ids = favoriteCollection.value.rom_ids.filter((id: number) => id !== rom.id);
    }

    const { data } = await collectionApi.updateCollection({ 
      collection: favoriteCollection.value as Collection 
    });
    
    favoriteCollection.value = data;
    collectionsStore.updateCollection(data);
  } catch (error) {
    console.error('Failed to toggle favorite:', error);
  }
}

const { on } = useInputScope();
function handleAction(action: InputAction): boolean {
  switch(action){
    case 'moveLeft':
      if(navigationMode.value==='systems'){ prevSystem(); return true; }
      if(navigationMode.value==='recent'){ prevRecent(); return true; }
      if(navigationMode.value==='collections'){ prevCollection(); return true; }
      if(navigationMode.value==='controls'){ controlIndex.value=(controlIndex.value-1+2)%2; return true; }
      return false;
    case 'moveRight':
      if(navigationMode.value==='systems'){ nextSystem(); return true; }
      if(navigationMode.value==='recent'){ nextRecent(); return true; }
      if(navigationMode.value==='collections'){ nextCollection(); return true; }
      if(navigationMode.value==='controls'){ controlIndex.value=(controlIndex.value+1)%2; return true; }
      return false;
    case 'moveUp':
      if(navigationMode.value==='systems') { navigationMode.value='controls'; return true; }
      if(navigationMode.value==='recent') { navigationMode.value='systems'; scrollToCurrentRow(); return true; }
      if(navigationMode.value==='collections') { navigationMode.value= recent.value.length>0 ? 'recent' : 'systems'; scrollToCurrentRow(); return true; }
      return false;
    case 'moveDown':
      if(navigationMode.value==='systems') { navigationMode.value= recent.value.length>0 ? 'recent' : (collections.value.length>0 ? 'collections' : 'controls'); scrollToCurrentRow(); return true; }
      if(navigationMode.value==='recent') { navigationMode.value= collections.value.length>0 ? 'collections' : 'controls'; scrollToCurrentRow(); return true; }
      if(navigationMode.value==='controls') { navigationMode.value='systems'; return true; }
      return false;
    case 'confirm':
      if(navigationMode.value==='systems' && platforms.value[selectedIndex.value]) { router.push({ name:'console-platform', params: { id: platforms.value[selectedIndex.value].id } }); return true; }
      if(navigationMode.value==='recent' && recent.value[recentIndex.value]) { router.push({ name:'console-rom', params:{ rom: recent.value[recentIndex.value].id }, query:{ id: recent.value[recentIndex.value].platform_id } }); return true; }
      if(navigationMode.value==='collections' && collections.value[collectionsIndex.value]) { router.push({ name:'console-collection', params: { id: collections.value[collectionsIndex.value].id } }); return true; }
      if(navigationMode.value==='controls') { if(controlIndex.value===0) exitConsoleMode(); else toggleFullscreen(); return true; }
      return false;
    case 'back':
      return true;
    case 'toggleFavorite':
      if(navigationMode.value === 'recent') {
        toggleFavorite();
        return true;
      }
      return false;
    default:
      return false;
  }
}

onMounted(async () => {
  try{
    const { data: plats } = await platformApi.getPlatforms();
    // Filter to only web-playable systems & hide those with zero roms.
    // NOTE: Adjust WEB_PLAYABLE_SLUGS to match the definitive supported set.
    platforms.value = plats.filter(p => p.rom_count > 0 && (SUPPORTED_WEB_PLATFORM_SET.has(p.slug) || SUPPORTED_WEB_PLATFORM_SET.has(p.fs_slug)));
    const { data: recents } = await romApi.getRecentPlayedRoms();
    recent.value = recents.items ?? [];
    const { data: cols } = await collectionApi.getCollections();
    collections.value = cols ?? [];
  
    // Initialize collections store for favorites functionality
    collectionsStore.setCollections(cols ?? []);
    collectionsStore.setFavoriteCollection(
    cols?.find(collection => collection.name.toLowerCase() === "favourites")
  );
} catch(err: unknown){ error.value = err instanceof Error ? err.message : 'Failed to load'; }
  finally{ loading.value = false; }
  off = on(handleAction);
});
let off: (() => void) | null = null;
onUnmounted(() => { off?.(); off = null; });
</script>

<style scoped>
</style>

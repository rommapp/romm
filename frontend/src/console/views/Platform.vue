<template>
  <div class="relative min-h-screen overflow-y-auto overflow-x-hidden max-w-[100vw] flex">
    <BackButton 
      :text="platformTitle" 
      :on-back="goBackToHome" 
    />
    <div
      class="fixed inset-0 z-0 bg-cover bg-center blur-[40px] saturate-[1.3] scale-105 pointer-events-none"
      :style="{ backgroundImage: displayCover ? `url('${displayCover}')` : '' }"
    />
    <div class="fixed inset-0 z-10 bg-gradient-to-b from-black/80 via-black/40 to-black/95 pointer-events-none" />

    <div
      class="relative z-20 flex-1 min-w-0 pr-[40px]"
      :style="{ width: 'calc(100vw - 40px)' }"
    >
      <div
        v-if="loading"
        class="text-center text-fgDim mt-8"
      >
        Loading games…
      </div>
      <div
        v-else-if="error"
        class="text-center text-red-400 mt-8"
      >
        {{ error }}
      </div>
      <div v-else>
        <div
          v-if="filtered.length===0"
          class="text-center text-fgDim p-4"
        >
          No games found.
        </div>
        <div
          ref="gridRef"
          class="grid grid-cols-[repeat(auto-fill,minmax(250px,250px))] justify-center my-12 gap-5 px-13 md:px-16 lg:px-20 xl:px-28 py-8 relative z-10 w-full box-border overflow-x-hidden"
          @mouseleave="hoverIndex = null"
        >
          <GameCard
            v-for="(rom,i) in filtered"
            :key="rom.id"
            :rom="rom"
            :index="i"
            :selected="!inAlphabet && i===selectedIndex"
            :loaded="!!loadedMap[rom.id]"
            @click="selectAndOpen(i, rom)"
            @mouseenter="onCardEnter(i)"
            @focus="mouseSelect(i)"
            @loaded="markLoaded(rom.id)"
          />
        </div>
      </div>
    </div>

    <div
      class="w-[40px] bg-black/30 backdrop-blur border-l border-white/10 fixed top-0 right-0 h-screen overflow-hidden z-30 flex-shrink-0"
      :class="{ 'bg-[rgba(248,180,0,0.75)] border-l-[rgba(248,180,0,0.75)]': inAlphabet }"
    >
      <div class="flex flex-col h-screen pa-2 items-center justify-evenly">
        <button
          v-for="(L,i) in letters"
          :key="L"
          class="bg-white/5 border border-white/10 text-fgDim rounded w-7 h-7 text-[0.7rem] font-semibold flex items-center justify-center shrink-0 transition-all hover:text-fg0 hover:border-white/30 hover:bg-white/10"
          :class="{ 'bg-[var(--accent-2)] border-[var(--accent)] text-white shadow-[0_0_0_2px_rgba(248,180,0,1)]': inAlphabet && i===alphaIndex }"
          @click="jumpToLetter(L)"
        >
          {{ L }}
        </button>
      </div>
    </div>
    <NavigationHint />
  </div>
</template>
<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import romApi from '@/services/api/rom';
import GameCard from '@/console/components/GameCard.vue';
import NavigationHint from '@/console/components/NavigationHint.vue';
import BackButton from '@/console/components/BackButton.vue';
import type { SimpleRomSchema } from '@/__generated__/models/SimpleRomSchema';
import { useInputScope } from '@/console/composables/useInputScope';
import type { InputAction } from '@/console/input/actions';
import { useSpatialNav } from '@/console/composables/useSpatialNav';

const route = useRoute();
const router = useRouter();
const platformId = Number(route.params.id);

const roms = ref<SimpleRomSchema[]>([]);
const loading = ref(true);
const error = ref('');
const selectedIndex = ref(0);
const hoverIndex = ref<number|null>(null);
const query = ref('');
const loadedMap = ref<Record<number, boolean>>({});
const keyboardMode = ref(false);
let keyboardTimeout: number | undefined;
const inAlphabet = ref(false);
const alphaIndex = ref(0);
const gridRef = ref<HTMLDivElement>();

const letters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'.split('');

function goBackToHome() {
  router.push({ name: 'console-home' });
}

const platformTitle = computed(() =>
  current.value?.platform_name || current.value?.platform_slug?.toUpperCase() || 'Platform'
);

const filtered = computed(() => {
  const q = query.value.trim().toLowerCase();
  return q ? roms.value.filter(r => (r.name||'').toLowerCase().includes(q)) : roms.value;
});

const current = computed(() => filtered.value[selectedIndex.value] || filtered.value[0]);
const displayRom = computed(() => hoverIndex.value != null ? filtered.value[hoverIndex.value] : current.value);
type MaybeExtraCovers = Partial<{ cover_url: string; cover: string }>;
const displayCover = computed(() => {
  const r = displayRom.value as (SimpleRomSchema & MaybeExtraCovers) | undefined;
  if (!r) return '';
  return (
    r.path_cover_large ||
    r.path_cover_small ||
    r.url_cover ||
    r.cover_url ||
    r.cover ||
    ''
  );
});

function getCols(): number {
  if (!gridRef.value) return 4;
  try{
    const style = window.getComputedStyle(gridRef.value);
    return Math.max(1, style.gridTemplateColumns.split(' ').length);
  }catch{
    return 4;
  }
}

function allCardElements(): HTMLElement[] {
  const w = window as unknown as { gameCardElements?: HTMLElement[] };
  const arr = (w.gameCardElements || []).filter(Boolean) as HTMLElement[];
  if (arr.length) return arr;
  const qs = gridRef.value?.querySelectorAll?.('button.relative.block.bg-\\[var\\(--tile\\)\\]');
  return qs ? Array.from(qs) as HTMLElement[] : [];
}

function sameRow(i: number, j: number): boolean {
  const els = allCardElements();
  const a = els[i]; const b = els[j];
  if (!a || !b) return false;
  return a.offsetTop === b.offsetTop;
}

function scrollToSelected(){
  if(!keyboardMode.value || filtered.value.length===0) return;
  requestAnimationFrame(() => {
    const w = window as unknown as { gameCardElements?: HTMLElement[] };
    const el = w.gameCardElements?.[selectedIndex.value];
  const fallback = document.querySelectorAll('.block.bg-\\[var\\(--tile\\)\\]');
    const target = el || (fallback[selectedIndex.value] as HTMLElement | undefined);
    if(target?.scrollIntoView) target.scrollIntoView({ behavior:'smooth', block:'center', inline:'nearest' });
  });
}

watch(selectedIndex, () => { if(keyboardMode.value) scrollToSelected(); });

const { on } = useInputScope();
const { moveLeft, moveUp } = useSpatialNav(selectedIndex, getCols, () => filtered.value.length);

function handleAction(action: InputAction): boolean {
  if(!filtered.value.length) return false;
  keyboardMode.value = true; window.clearTimeout(keyboardTimeout); keyboardTimeout = window.setTimeout(()=> keyboardMode.value=false, 3000);

  if(inAlphabet.value){
    if(action==='moveLeft'){ inAlphabet.value=false; return true; }
    if(action==='moveUp'){ alphaIndex.value = Math.max(0, alphaIndex.value-1); return true; }
    if(action==='moveDown'){ alphaIndex.value = Math.min(letters.length-1, alphaIndex.value+1); return true; }
    if(action==='confirm'){
      const L = letters[alphaIndex.value];
  const idx = filtered.value.findIndex(r => normalizeTitle(r.name||'').startsWith(L));
      if(idx>=0){ selectedIndex.value = idx; inAlphabet.value=false; }
      return true;
    }
    return true;
  }

  switch(action){
    case 'moveRight':{
      const next = selectedIndex.value + 1;
      const count = filtered.value.length;
      if (next >= count || !sameRow(selectedIndex.value, next)) {
        inAlphabet.value = true; alphaIndex.value = 0; return true;
      }
      selectedIndex.value = next; return true; }
    case 'moveLeft': moveLeft(); return true;
    case 'moveUp': moveUp(); return true;
    case 'moveDown': {
      const cols = getCols();
      const count = filtered.value.length;
      const next = selectedIndex.value + cols;
      if (next < count) { selectedIndex.value = next; return true; }
      // If there's a shorter last row, clamp to the last available item instead of a dead cell
      if (count > 0) { selectedIndex.value = count - 1; return true; }
      return true; }
  case 'back': router.push({ name: 'console-home' }); return true;
    case 'confirm': {
      const rom = filtered.value[selectedIndex.value];
      router.push({ name: 'console-rom', params: { rom: rom.id }, query: { id: platformId } });
      return true; }
    default: return false;
  }
}

function mouseSelect(i:number){ if(!keyboardMode.value) selectedIndex.value = i; }
function onCardEnter(i:number){ hoverIndex.value = i; if(!keyboardMode.value) selectedIndex.value = i; }
function selectAndOpen(i:number, rom: SimpleRomSchema){ selectedIndex.value = i; router.push({ name: 'console-rom', params: { rom: rom.id }, query: { id: platformId } }); }
function jumpToLetter(L:string){
  const idx = filtered.value.findIndex(r => normalizeTitle(r.name||'').startsWith(L));
  if(idx>=0){
    selectedIndex.value = idx; inAlphabet.value=false; keyboardMode.value=true; window.clearTimeout(keyboardTimeout); keyboardTimeout = window.setTimeout(()=> keyboardMode.value=false, 3000);
  }
}

function normalizeTitle(name: string): string {
  const upper = name.toUpperCase();
  // Ignore common leading articles for alphabet navigation;
  return upper.replace(/^THE\s+/, '');
}

let off: (() => void) | null = null;
onMounted(async () => {
  try{
    const { data } = await romApi.getRoms({ platformId, limit: 500, orderBy: 'name', orderDir: 'asc' });
    roms.value = data.items ?? [];
    // mark those without cover as loaded immediately (no skeleton needed)
    for (const r of roms.value) {
      if (!r.url_cover && !r.path_cover_large && !r.path_cover_small) {
        loadedMap.value[r.id] = true;
      }
    }
  }catch(err: unknown){ error.value = err instanceof Error ? err.message : 'Failed to load roms'; }
  finally{ loading.value = false; }
  off = on(handleAction);
});

onUnmounted(() => { off?.(); off = null; });

function markLoaded(id: number){ loadedMap.value[id] = true; }
</script>

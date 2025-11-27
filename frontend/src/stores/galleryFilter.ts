import { defineStore } from "pinia";
import type { PlatformSchema } from "@/__generated__";
import { romStatusMap } from "@/utils";

export type Platform = PlatformSchema;

export type FilterType =
  | "genre"
  | "franchise"
  | "collection"
  | "company"
  | "ageRating"
  | "status"
  | "region"
  | "language";

const defaultFilterState = {
  activeFilterDrawer: false,
  searchTerm: null as string | null,
  filterPlatforms: [] as Platform[],
  filterGenres: [] as string[],
  filterFranchises: [] as string[],
  filterCollections: [] as string[],
  filterCompanies: [] as string[],
  filterAgeRatings: [] as string[],
  filterRegions: [] as string[],
  filterLanguages: [] as string[],
  filterStatuses: Object.values(romStatusMap).map((status) => status.text),
  filterUnmatched: false,
  filterMatched: false,
  filterFavorites: null as boolean | null, // null = all, true = favorites, false = not favorites
  filterDuplicates: null as boolean | null, // null = all, true = duplicates, false = not duplicates
  filterPlayables: null as boolean | null, // null = all, true = playables, false = not playables
  filterRA: null as boolean | null, // null = all, true = has RA, false = no RA
  filterMissing: null as boolean | null, // null = all, true = missing, false = not missing
  filterVerified: null as boolean | null, // null = all, true = verified, false = not verified
  selectedPlatform: null as Platform | null,
  selectedGenre: null as string | null,
  selectedFranchise: null as string | null,
  selectedCollection: null as string | null,
  selectedCompany: null as string | null,
  selectedAgeRating: null as string | null,
  selectedRegion: null as string | null,
  selectedLanguage: null as string | null,
  selectedStatus: null as string | null,
};

export default defineStore("galleryFilter", {
  state: () => ({ ...defaultFilterState }),

  actions: {
    switchActiveFilterDrawer() {
      this.activeFilterDrawer = !this.activeFilterDrawer;
    },
    setFilterPlatforms(platforms: Platform[]) {
      this.filterPlatforms = platforms;
    },
    setFilterGenres(genres: string[]) {
      this.filterGenres = genres;
    },
    setFilterFranchises(franchises: string[]) {
      this.filterFranchises = franchises;
    },
    setFilterCollections(collections: string[]) {
      this.filterCollections = collections;
    },
    setFilterCompanies(companies: string[]) {
      this.filterCompanies = companies;
    },
    setFilterAgeRatings(ageRatings: string[]) {
      this.filterAgeRatings = ageRatings;
    },
    setFilterRegions(regions: string[]) {
      this.filterRegions = regions;
    },
    setFilterLanguages(languages: string[]) {
      this.filterLanguages = languages;
    },
    setSelectedFilterPlatform(platform: Platform) {
      this.selectedPlatform = platform
        ? this.filterPlatforms.find((p) => p.id === platform.id) || null
        : null;
    },
    setSelectedFilterGenre(genre: string) {
      this.selectedGenre = genre;
    },
    setSelectedFilterFranchise(franchise: string) {
      this.selectedFranchise = franchise;
    },
    setSelectedFilterCollection(collection: string) {
      this.selectedCollection = collection;
    },
    setSelectedFilterCompany(company: string) {
      this.selectedCompany = company;
    },
    setSelectedFilterAgeRating(ageRating: string) {
      this.selectedAgeRating = ageRating;
    },
    setSelectedFilterRegion(region: string) {
      this.selectedRegion = region;
    },
    setSelectedFilterLanguage(language: string) {
      this.selectedLanguage = language;
    },
    setSelectedFilterStatus(status: string) {
      this.selectedStatus = status;
    },
    setFilterUnmatched(value: boolean) {
      this.filterUnmatched = value;
      this.filterMatched = false;
    },
    switchFilterUnmatched() {
      this.filterUnmatched = !this.filterUnmatched;
      this.filterMatched = false;
    },
    setFilterMatched(value: boolean) {
      this.filterMatched = value;
      this.filterUnmatched = false;
    },
    switchFilterMatched() {
      this.filterMatched = !this.filterMatched;
      this.filterUnmatched = false;
    },
    setFilterFavorites(value: boolean | null) {
      this.filterFavorites = value;
    },
    setFilterFavoritesState(state: "all" | "favorites" | "not-favorites") {
      switch (state) {
        case "favorites":
          this.filterFavorites = true;
          break;
        case "not-favorites":
          this.filterFavorites = false;
          break;
        default: // "all"
          this.filterFavorites = null;
          break;
      }
    },
    switchFilterFavorites() {
      if (this.filterFavorites === null) {
        this.filterFavorites = true;
      } else if (this.filterFavorites === true) {
        this.filterFavorites = false;
      } else {
        this.filterFavorites = null;
      }
    },
    setFilterDuplicates(value: boolean | null) {
      this.filterDuplicates = value;
    },
    setFilterDuplicatesState(state: "all" | "duplicates" | "not-duplicates") {
      switch (state) {
        case "duplicates":
          this.filterDuplicates = true;
          break;
        case "not-duplicates":
          this.filterDuplicates = false;
          break;
        default: // "all"
          this.filterDuplicates = null;
          break;
      }
    },
    switchFilterDuplicates() {
      if (this.filterDuplicates === null) {
        this.filterDuplicates = true;
      } else if (this.filterDuplicates === true) {
        this.filterDuplicates = false;
      } else {
        this.filterDuplicates = null;
      }
    },
    setFilterPlayables(value: boolean | null) {
      this.filterPlayables = value;
    },
    setFilterPlayablesState(state: "all" | "playables" | "not-playables") {
      switch (state) {
        case "playables":
          this.filterPlayables = true;
          break;
        case "not-playables":
          this.filterPlayables = false;
          break;
        default: // "all"
          this.filterPlayables = null;
          break;
      }
    },
    switchFilterPlayables() {
      if (this.filterPlayables === null) {
        this.filterPlayables = true;
      } else if (this.filterPlayables === true) {
        this.filterPlayables = false;
      } else {
        this.filterPlayables = null;
      }
    },
    setFilterRA(value: boolean | null) {
      this.filterRA = value;
    },
    setFilterRAState(state: "all" | "has-ra" | "no-ra") {
      switch (state) {
        case "has-ra":
          this.filterRA = true;
          break;
        case "no-ra":
          this.filterRA = false;
          break;
        default: // "all"
          this.filterRA = null;
          break;
      }
    },
    switchFilterRA() {
      if (this.filterRA === null) {
        this.filterRA = true;
      } else if (this.filterRA === true) {
        this.filterRA = false;
      } else {
        this.filterRA = null;
      }
    },
    setFilterMissing(value: boolean | null) {
      this.filterMissing = value;
    },
    setFilterMissingState(state: "all" | "missing" | "not-missing") {
      switch (state) {
        case "missing":
          this.filterMissing = true;
          break;
        case "not-missing":
          this.filterMissing = false;
          break;
        default: // "all"
          this.filterMissing = null;
          break;
      }
    },
    switchFilterMissing() {
      if (this.filterMissing === null) {
        this.filterMissing = true;
      } else if (this.filterMissing === true) {
        this.filterMissing = false;
      } else {
        this.filterMissing = null;
      }
    },
    setFilterVerified(value: boolean | null) {
      this.filterVerified = value;
    },
    setFilterVerifiedState(state: "all" | "verified" | "not-verified") {
      switch (state) {
        case "verified":
          this.filterVerified = true;
          break;
        case "not-verified":
          this.filterVerified = false;
          break;
        default: // "all"
          this.filterVerified = null;
          break;
      }
    },
    switchFilterVerified() {
      if (this.filterVerified === null) {
        this.filterVerified = true;
      } else if (this.filterVerified === true) {
        this.filterVerified = false;
      } else {
        this.filterVerified = null;
      }
    },
    isFiltered() {
      return Boolean(
        this.filterUnmatched ||
          this.filterMatched ||
          this.filterFavorites !== null ||
          this.filterDuplicates !== null ||
          this.filterPlayables !== null ||
          this.filterRA !== null ||
          this.filterMissing !== null ||
          this.filterVerified !== null ||
          this.selectedPlatform ||
          this.selectedGenre ||
          this.selectedFranchise ||
          this.selectedCollection ||
          this.selectedCompany ||
          this.selectedAgeRating ||
          this.selectedRegion ||
          this.selectedLanguage ||
          this.selectedStatus,
      );
    },
    reset() {
      Object.assign(this, { ...defaultFilterState });
    },
    resetFilters() {
      this.selectedPlatform = null;
      this.selectedGenre = null;
      this.selectedFranchise = null;
      this.selectedCollection = null;
      this.selectedCompany = null;
      this.selectedAgeRating = null;
      this.selectedRegion = null;
      this.selectedLanguage = null;
      this.selectedStatus = null;
      this.filterUnmatched = false;
      this.filterMatched = false;
      this.filterFavorites = null;
      this.filterDuplicates = null;
      this.filterPlayables = null;
      this.filterRA = null;
      this.filterMissing = null;
      this.filterVerified = null;
    },
  },
});

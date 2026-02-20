import { defineStore } from "pinia";
import type { PlatformSchema } from "@/__generated__";
import { romStatusMap } from "@/utils";

export type Platform = PlatformSchema;

export type FilterType =
  | "genres"
  | "franchises"
  | "collections"
  | "companies"
  | "ageRatings"
  | "statuses"
  | "regions"
  | "languages"
  | "playerCounts";

export type FilterLogicOperator = "any" | "all" | "none";

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
  filterPlayerCounts: [] as string[],
  filterStatuses: Object.keys(romStatusMap),
  filterMatched: null as boolean | null, // null = all, true = matched, false = unmatched
  filterFavorites: null as boolean | null, // null = all, true = favorites, false = not favorites
  filterDuplicates: null as boolean | null, // null = all, true = duplicates, false = not duplicates
  filterPlayables: null as boolean | null, // null = all, true = playables, false = not playables
  filterRA: null as boolean | null, // null = all, true = has RA, false = no RA
  filterMissing: null as boolean | null, // null = all, true = missing, false = not missing
  filterVerified: null as boolean | null, // null = all, true = verified, false = not verified
  selectedPlatform: null as Platform | null,
  selectedPlatforms: [] as Platform[],
  selectedGenres: [] as string[],
  selectedFranchises: [] as string[],
  selectedCollections: [] as string[],
  selectedCompanies: [] as string[],
  selectedAgeRatings: [] as string[],
  selectedRegions: [] as string[],
  selectedLanguages: [] as string[],
  selectedPlayerCounts: [] as string[],
  selectedStatuses: [] as string[],
  // Logic operators for multi-select filters
  genresLogic: "any" as FilterLogicOperator,
  franchisesLogic: "any" as FilterLogicOperator,
  collectionsLogic: "any" as FilterLogicOperator,
  companiesLogic: "any" as FilterLogicOperator,
  ageRatingsLogic: "any" as FilterLogicOperator,
  regionsLogic: "any" as FilterLogicOperator,
  languagesLogic: "any" as FilterLogicOperator,
  statusesLogic: "any" as FilterLogicOperator,
  playerCountsLogic: "any" as FilterLogicOperator,
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
    setFilterPlayerCounts(playerCounts: string[]) {
      this.filterPlayerCounts = playerCounts;
    },
    setSelectedFilterPlatform(platform: Platform) {
      this.selectedPlatform = platform
        ? this.filterPlatforms.find((p) => p.id === platform.id) || null
        : null;
    },
    setSelectedFilterPlatforms(platforms: Platform[]) {
      this.selectedPlatforms = platforms;
      // Clear single platform selection to avoid conflicts
      this.selectedPlatform = null;
    },
    setSelectedFilterGenres(genres: string[]) {
      this.selectedGenres = genres;
    },
    setGenresLogic(logic: FilterLogicOperator) {
      this.genresLogic = logic;
    },
    setSelectedFilterFranchises(franchises: string[]) {
      this.selectedFranchises = franchises;
    },
    setFranchisesLogic(logic: FilterLogicOperator) {
      this.franchisesLogic = logic;
    },
    setSelectedFilterCollections(collections: string[]) {
      this.selectedCollections = collections;
    },
    setCollectionsLogic(logic: FilterLogicOperator) {
      this.collectionsLogic = logic;
    },
    setSelectedFilterCompanies(companies: string[]) {
      this.selectedCompanies = companies;
    },
    setCompaniesLogic(logic: FilterLogicOperator) {
      this.companiesLogic = logic;
    },
    setSelectedFilterAgeRatings(ageRatings: string[]) {
      this.selectedAgeRatings = ageRatings;
    },
    setAgeRatingsLogic(logic: FilterLogicOperator) {
      this.ageRatingsLogic = logic;
    },
    setSelectedFilterRegions(regions: string[]) {
      this.selectedRegions = regions;
    },
    setRegionsLogic(logic: FilterLogicOperator) {
      this.regionsLogic = logic;
    },
    setSelectedFilterLanguages(languages: string[]) {
      this.selectedLanguages = languages;
    },
    setLanguagesLogic(logic: FilterLogicOperator) {
      this.languagesLogic = logic;
    },
    setSelectedFilterPlayerCounts(playerCounts: string[]) {
      this.selectedPlayerCounts = playerCounts;
    },
    setPlayerCountsLogic(logic: FilterLogicOperator) {
      this.playerCountsLogic = logic;
    },
    setSelectedFilterStatuses(statuses: string[]) {
      this.selectedStatuses = statuses;
    },
    setStatusesLogic(logic: FilterLogicOperator) {
      this.statusesLogic = logic;
    },
    setFilterMatched(value: boolean | null) {
      this.filterMatched = value;
    },
    setFilterMatchedState(state: "all" | "matched" | "unmatched") {
      switch (state) {
        case "matched":
          this.filterMatched = true;
          break;
        case "unmatched":
          this.filterMatched = false;
          break;
        default: // "all"
          this.filterMatched = null;
          break;
      }
    },
    switchFilterMatched() {
      if (this.filterMatched === null) {
        this.filterMatched = true;
      } else if (this.filterMatched === true) {
        this.filterMatched = false;
      } else {
        this.filterMatched = null;
      }
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
        this.filterMatched !== null ||
        this.filterFavorites !== null ||
        this.filterDuplicates !== null ||
        this.filterPlayables !== null ||
        this.filterRA !== null ||
        this.filterMissing !== null ||
        this.filterVerified !== null ||
        this.selectedPlatform ||
        this.selectedPlatforms.length > 0 ||
        this.selectedGenres.length > 0 ||
        this.selectedFranchises.length > 0 ||
        this.selectedCollections.length > 0 ||
        this.selectedCompanies.length > 0 ||
        this.selectedAgeRatings.length > 0 ||
        this.selectedRegions.length > 0 ||
        this.selectedLanguages.length > 0 ||
        this.selectedPlayerCounts.length > 0 ||
        this.selectedStatuses.length > 0,
      );
    },
    reset() {
      Object.assign(this, { ...defaultFilterState });
    },
    resetFilters() {
      this.selectedPlatform = null;
      this.selectedPlatforms = [];
      this.selectedGenres = [];
      this.selectedFranchises = [];
      this.selectedCollections = [];
      this.selectedCompanies = [];
      this.selectedAgeRatings = [];
      this.selectedRegions = [];
      this.selectedLanguages = [];
      this.selectedPlayerCounts = [];
      this.selectedStatuses = [];
      this.filterMatched = null;
      this.filterFavorites = null;
      this.filterDuplicates = null;
      this.filterPlayables = null;
      this.filterRA = null;
      this.filterMissing = null;
      this.filterVerified = null;
      // Reset logic operators to default
      this.genresLogic = "any";
      this.franchisesLogic = "any";
      this.collectionsLogic = "any";
      this.companiesLogic = "any";
      this.ageRatingsLogic = "any";
      this.regionsLogic = "any";
      this.languagesLogic = "any";
      this.statusesLogic = "any";
      this.playerCountsLogic = "any";
    },
  },
});

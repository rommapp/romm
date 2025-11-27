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
  selectedPlatforms: [] as Platform[],
  selectedGenre: null as string | null,
  selectedGenres: [] as string[],
  selectedFranchise: null as string | null,
  selectedFranchises: [] as string[],
  selectedCollection: null as string | null,
  selectedCollections: [] as string[],
  selectedCompany: null as string | null,
  selectedCompanies: [] as string[],
  selectedAgeRating: null as string | null,
  selectedAgeRatings: [] as string[],
  selectedRegion: null as string | null,
  selectedRegions: [] as string[],
  selectedLanguage: null as string | null,
  selectedLanguages: [] as string[],
  selectedStatus: null as string | null,
  selectedStatuses: [] as string[],
  // Logic operators for multi-select filters
  platformsLogic: "any" as "any" | "all",
  genresLogic: "any" as "any" | "all",
  franchisesLogic: "any" as "any" | "all",
  collectionsLogic: "any" as "any" | "all",
  companiesLogic: "any" as "any" | "all",
  ageRatingsLogic: "any" as "any" | "all",
  regionsLogic: "any" as "any" | "all",
  languagesLogic: "any" as "any" | "all",
  statusesLogic: "any" as "any" | "all",
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
    setSelectedFilterPlatforms(platforms: Platform[]) {
      this.selectedPlatforms = platforms;
    },
    setPlatformsLogic(logic: "any" | "all") {
      this.platformsLogic = logic;
    },
    setSelectedFilterGenre(genre: string) {
      this.selectedGenre = genre;
    },
    setSelectedFilterGenres(genres: string[]) {
      this.selectedGenres = genres;
    },
    setGenresLogic(logic: "any" | "all") {
      this.genresLogic = logic;
    },
    setSelectedFilterFranchise(franchise: string) {
      this.selectedFranchise = franchise;
    },
    setSelectedFilterFranchises(franchises: string[]) {
      this.selectedFranchises = franchises;
    },
    setFranchisesLogic(logic: "any" | "all") {
      this.franchisesLogic = logic;
    },
    setSelectedFilterCollection(collection: string) {
      this.selectedCollection = collection;
    },
    setSelectedFilterCollections(collections: string[]) {
      this.selectedCollections = collections;
    },
    setCollectionsLogic(logic: "any" | "all") {
      this.collectionsLogic = logic;
    },
    setSelectedFilterCompany(company: string) {
      this.selectedCompany = company;
    },
    setSelectedFilterCompanies(companies: string[]) {
      this.selectedCompanies = companies;
    },
    setCompaniesLogic(logic: "any" | "all") {
      this.companiesLogic = logic;
    },
    setSelectedFilterAgeRating(ageRating: string) {
      this.selectedAgeRating = ageRating;
    },
    setSelectedFilterAgeRatings(ageRatings: string[]) {
      this.selectedAgeRatings = ageRatings;
    },
    setAgeRatingsLogic(logic: "any" | "all") {
      this.ageRatingsLogic = logic;
    },
    setSelectedFilterRegion(region: string) {
      this.selectedRegion = region;
    },
    setSelectedFilterRegions(regions: string[]) {
      this.selectedRegions = regions;
    },
    setRegionsLogic(logic: "any" | "all") {
      this.regionsLogic = logic;
    },
    setSelectedFilterLanguage(language: string) {
      this.selectedLanguage = language;
    },
    setSelectedFilterLanguages(languages: string[]) {
      this.selectedLanguages = languages;
    },
    setLanguagesLogic(logic: "any" | "all") {
      this.languagesLogic = logic;
    },
    setSelectedFilterStatus(status: string) {
      this.selectedStatus = status;
    },
    setSelectedFilterStatuses(statuses: string[]) {
      this.selectedStatuses = statuses;
    },
    setStatusesLogic(logic: "any" | "all") {
      this.statusesLogic = logic;
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
          this.selectedPlatforms.length > 0 ||
          this.selectedGenre ||
          this.selectedGenres.length > 0 ||
          this.selectedFranchise ||
          this.selectedFranchises.length > 0 ||
          this.selectedCollection ||
          this.selectedCollections.length > 0 ||
          this.selectedCompany ||
          this.selectedCompanies.length > 0 ||
          this.selectedAgeRating ||
          this.selectedAgeRatings.length > 0 ||
          this.selectedRegion ||
          this.selectedRegions.length > 0 ||
          this.selectedLanguage ||
          this.selectedLanguages.length > 0 ||
          this.selectedStatus ||
          this.selectedStatuses.length > 0,
      );
    },
    reset() {
      Object.assign(this, { ...defaultFilterState });
    },
    resetFilters() {
      this.selectedPlatform = null;
      this.selectedPlatforms = [];
      this.selectedGenre = null;
      this.selectedGenres = [];
      this.selectedFranchise = null;
      this.selectedFranchises = [];
      this.selectedCollection = null;
      this.selectedCollections = [];
      this.selectedCompany = null;
      this.selectedCompanies = [];
      this.selectedAgeRating = null;
      this.selectedAgeRatings = [];
      this.selectedRegion = null;
      this.selectedRegions = [];
      this.selectedLanguage = null;
      this.selectedLanguages = [];
      this.selectedStatus = null;
      this.selectedStatuses = [];
      this.filterUnmatched = false;
      this.filterMatched = false;
      this.filterFavorites = null;
      this.filterDuplicates = null;
      this.filterPlayables = null;
      this.filterRA = null;
      this.filterMissing = null;
      this.filterVerified = null;
      // Reset logic operators to default
      this.platformsLogic = "any";
      this.genresLogic = "any";
      this.franchisesLogic = "any";
      this.collectionsLogic = "any";
      this.companiesLogic = "any";
      this.ageRatingsLogic = "any";
      this.regionsLogic = "any";
      this.languagesLogic = "any";
      this.statusesLogic = "any";
    },
  },
});

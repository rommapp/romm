import type { PlatformSchema } from "@/__generated__";
import { romStatusMap } from "@/utils";
import { defineStore } from "pinia";

export type Platform = PlatformSchema;

export type FilterType =
  | "genres"
  | "franchises"
  | "collections"
  | "companies"
  | "age_ratings"
  | "status"
  | "regions"
  | "languages";

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
  filterFavourites: false,
  filterDuplicates: false,
  filterPlayables: false,
  filterRA: false,
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
    switchFilterUnmatched() {
      this.filterUnmatched = !this.filterUnmatched;
      this.filterMatched = false;
    },
    disableFilterUnmatched() {
      this.filterUnmatched = false;
    },
    switchFilterMatched() {
      this.filterMatched = !this.filterMatched;
      this.filterUnmatched = false;
    },
    disableFilterMatched() {
      this.filterMatched = false;
    },
    switchFilterFavourites() {
      this.filterFavourites = !this.filterFavourites;
    },
    disableFilterFavourites() {
      this.filterFavourites = false;
    },
    switchFilterDuplicates() {
      this.filterDuplicates = !this.filterDuplicates;
    },
    disableFilterDuplicates() {
      this.filterDuplicates = false;
    },
    switchFilterPlayables() {
      this.filterPlayables = !this.filterPlayables;
    },
    disableFilterPlayables() {
      this.filterPlayables = false;
    },
    switchFilterRA() {
      this.filterRA = !this.filterRA;
    },
    disableFilterRA() {
      this.filterRA = false;
    },
    isFiltered() {
      return Boolean(
        this.filterUnmatched ||
          this.filterMatched ||
          this.filterFavourites ||
          this.filterDuplicates ||
          this.filterPlayables ||
          this.filterRA ||
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
      this.selectedStatus = null;
      this.disableFilterUnmatched();
      this.disableFilterMatched();
      this.disableFilterFavourites();
      this.disableFilterDuplicates();
      this.disableFilterPlayables();
      this.disableFilterRA();
    },
  },
});

// RomM v2 Component Library — barrel export.
//
// Only design-system *primitives* live here. Specializations (BackBtn,
// PlatformTile, InfoPanel, …) belong under src/v2/components/<feature>/
// and are imported directly, not through this barrel.
//
// Rule: every export below must be general enough that two or more
// features depend on it, and must ship a Storybook story.
//
// Folders mirror Storybook categories (primitives, forms, structural,
// menus, overlays, data, media).

// Primitives
export * from "./primitives/RAlert";
export * from "./primitives/RAvatar";
export * from "./primitives/RBadge";
export * from "./primitives/RBtn";
export * from "./primitives/RCard";
export * from "./primitives/RChip";
export * from "./primitives/RDivider";
export * from "./primitives/REmptyState";
export * from "./primitives/RIcon";
export * from "./primitives/RImg";
export * from "./primitives/RLetterHeading";
export * from "./primitives/RProgressCircular";
export * from "./primitives/RSkeletonBlock";
export * from "./primitives/RSliderBtnGroup";
export * from "./primitives/RSpinner";
export * from "./primitives/RTabNav";
export * from "./primitives/RTag";

// Forms
export * from "./forms/RCheckbox";
export * from "./forms/RForm";
export * from "./forms/RRating";
export * from "./forms/RSelect";
export * from "./forms/RSlider";
export * from "./forms/RSwitch";
export * from "./forms/RTextField";

// Structural
export * from "./structural/RCollapsible";
export * from "./structural/RList";
export * from "./structural/RListItem";
export * from "./structural/RToolbar";
export * from "./structural/RTooltip";
export * from "./structural/RVirtualScroller";

// Menus
export * from "./menus/RMenu";
export * from "./menus/RMenuPanel";
export * from "./menus/RMenuDivider";
export * from "./menus/RMenuHeader";
export * from "./menus/RMenuItem";
export * from "./menus/RMenuSearch";

// Overlays
export * from "./overlays/RCarousel";
export * from "./overlays/RDialog";

// Data
export * from "./data/RTable";

// Media
export * from "./media/RPlatformIcon";

// (GameCard lives under components/GameCard/ — it's a feature
// composite that depends on stores + useGameActions, not a lib primitive.)

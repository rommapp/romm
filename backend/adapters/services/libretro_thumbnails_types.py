import enum


@enum.unique
class LibretroArtType(enum.StrEnum):
    BOX_ART = "Named_Boxarts"
    TITLE_SCREEN = "Named_Titles"
    LOGO = "Named_Logos"
    SCREENSHOT = "Named_Snaps"

import re
from dataclasses import dataclass
from enum import StrEnum

from config import LIBRARY_BASE_PATH


class StructureMacro(StrEnum):
    """Built-in macros for library structure patterns."""

    PLATFORM = "platform"
    GAME = "game"
    CUSTOM = "custom"


@dataclass
class StructureSegment:
    """Represents a single segment in a library structure path."""

    name: str
    is_macro: bool
    macro_type: StructureMacro | None = None
    is_required: bool = False


class LibraryStructure:
    """Parses and manages custom library structure patterns."""

    # Regex to match macro patterns like {library}, {platform}, etc.
    MACRO_PATTERN = re.compile(r"\{([^}]+)\}")

    # Required macros for different structure types
    REQUIRED_ROM_MACROS = {StructureMacro.PLATFORM, StructureMacro.GAME}
    REQUIRED_FIRMWARE_MACROS = {StructureMacro.PLATFORM}

    def __init__(self, structure_string: str, structure_type: str = "roms"):
        """
        Initialize structure parser.

        Args:
            structure_string: Structure pattern like "{roms}/{platform}/{game}"
            structure_type: Type of structure ("roms" or "firmware")
        """
        self.structure_string = structure_string
        self.structure_type = structure_type
        self.segments = self._parse_structure()
        self._validate_structure()

    def _parse_structure(self) -> list[StructureSegment]:
        """Parse the structure string into segments."""
        segments = []
        parts = self.structure_string.split("/")

        for part in parts:
            if not part:
                continue

            macro_match = self.MACRO_PATTERN.match(part)
            if macro_match:
                macro_name = macro_match.group(1)
                macro_type = self._get_macro_type(macro_name)
                is_required = (
                    macro_type in self.REQUIRED_ROM_MACROS
                    if self.structure_type == "roms"
                    else macro_type in self.REQUIRED_FIRMWARE_MACROS
                )

                segments.append(
                    StructureSegment(
                        name=macro_name,
                        is_macro=True,
                        macro_type=macro_type,
                        is_required=is_required,
                    )
                )
            else:
                segments.append(
                    StructureSegment(name=part, is_macro=False, is_required=False)
                )

        return segments

    def _get_macro_type(self, macro_name: str) -> StructureMacro:
        """Determine the type of macro based on its name."""
        macro_map = {
            "platform": StructureMacro.PLATFORM,
            "game": StructureMacro.GAME,
        }

        return macro_map.get(macro_name, StructureMacro.CUSTOM)

    def _validate_structure(self) -> None:
        """Validate that the structure contains required macros."""
        macro_types = {
            segment.macro_type for segment in self.segments if segment.is_macro
        }

        # Check for required macros based on structure type
        if self.structure_type == "roms":
            required_macros = self.REQUIRED_ROM_MACROS
        else:  # firmware
            required_macros = self.REQUIRED_FIRMWARE_MACROS

        if not required_macros.issubset(macro_types):
            missing = required_macros - macro_types
            raise ValueError(
                f"{self.structure_type.title()} structure must contain required macros: {missing}"
            )

    def get_custom_macros(self) -> list[str]:
        """Get list of custom macro names in the structure."""
        return [
            segment.name
            for segment in self.segments
            if segment.is_macro and segment.macro_type == StructureMacro.CUSTOM
        ]

    def resolve_path(self, **kwargs: str) -> str:
        """
        Build a concrete path from the structure using provided values.

        Args:
            **kwargs: Values for macros (e.g., platform="gba", game="pokemon.gba")

        Returns:
            Resolved path string
        """
        path_parts = []

        print(f"DEBUG: Resolving path with kwargs: {kwargs}")
        print(f"DEBUG: Segments: {self.segments}")

        for segment in self.segments:
            if segment.is_macro:
                # For platform, game, and custom macros
                value = kwargs.get(segment.name)
                if value is None:
                    raise ValueError(f"Missing value for macro '{segment.name}'")
                path_parts.append(value)
            else:
                path_parts.append(segment.name)

        return "/".join(path_parts)

    def extract_metadata(self, file_path: str) -> list[str]:
        """
        Extract custom macro values from a file path as tags.

        Args:
            file_path: File path to extract metadata from

        Returns:
            List of tags in format "macro_name:value"
        """
        # Remove library base path if present
        if file_path.startswith(LIBRARY_BASE_PATH):
            file_path = file_path[len(LIBRARY_BASE_PATH) :].lstrip("/")

        path_parts = file_path.split("/")
        tags = []

        # Create a mapping of position to macro name
        macro_positions = {}
        for i, segment in enumerate(self.segments):
            if segment.is_macro and segment.macro_type == StructureMacro.CUSTOM:
                macro_positions[i] = segment.name

        # Extract values for custom macros as tags
        for position, macro_name in macro_positions.items():
            if position < len(path_parts):
                tags.append(f"{macro_name}:{path_parts[position]}")

        return tags

    def get_platform_position(self) -> int:
        """Get the position of the platform segment in the structure."""
        for i, segment in enumerate(self.segments):
            if segment.macro_type == StructureMacro.PLATFORM:
                return i
        raise ValueError("Platform macro not found in structure")

    def get_platforms_directory(self) -> str:
        """Get the directory where platforms are located."""
        # For structures like {roms}/{platform}/{region}/{game},
        # platforms are at the first level after the base directory
        # So we need to find the first non-macro segment before platform
        path_parts = []
        for segment in self.segments:
            if segment.macro_type == StructureMacro.PLATFORM:
                break
            if not segment.is_macro:
                path_parts.append(segment.name)

        return "/".join(path_parts) if path_parts else ""

    def supports_mixed_games(self) -> bool:
        """Check if structure supports both single-file and multi-file games."""
        # Only ROM structures support mixed games
        if self.structure_type != "roms":
            return False
        # With the unified {game} macro, all ROM structures support mixed games
        return any(
            segment.macro_type == StructureMacro.GAME for segment in self.segments
        )

    def __str__(self) -> str:
        return self.structure_string

    def __repr__(self) -> str:
        return f"LibraryStructure('{self.structure_string}')"

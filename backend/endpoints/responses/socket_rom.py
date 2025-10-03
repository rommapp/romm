from __future__ import annotations

from endpoints.responses.rom import RomSchema
from models.rom import Rom


class SocketRomSchema(RomSchema):
    """ROM schema for socket emissions with sensitive data filtered out."""

    @classmethod
    def from_orm_with_factory(cls, db_rom: Rom) -> SocketRomSchema:
        """Create schema instance with sensitive data excluded."""
        # Create a copy of the ROM object to avoid modifying the original
        rom_copy = Rom(
            id=db_rom.id,
            igdb_id=db_rom.igdb_id,
            sgdb_id=db_rom.sgdb_id,
            moby_id=db_rom.moby_id,
            ss_id=db_rom.ss_id,
            ra_id=db_rom.ra_id,
            launchbox_id=db_rom.launchbox_id,
            hasheous_id=db_rom.hasheous_id,
            tgdb_id=db_rom.tgdb_id,
            flashpoint_id=db_rom.flashpoint_id,
            hltb_id=db_rom.hltb_id,
            platform_id=db_rom.platform_id,
            platform_slug=db_rom.platform_slug,
            platform_fs_slug=db_rom.platform_fs_slug,
            platform_name=db_rom.platform_name,
            platform_custom_name=db_rom.platform_custom_name,
            platform_display_name=db_rom.platform_display_name,
            fs_name=db_rom.fs_name,
            fs_name_no_tags=db_rom.fs_name_no_tags,
            fs_name_no_ext=db_rom.fs_name_no_ext,
            fs_extension=db_rom.fs_extension,
            # Exclude sensitive filesystem paths
            # fs_path=db_rom.fs_path,  # Excluded
            fs_size_bytes=db_rom.fs_size_bytes,
            name=db_rom.name,
            slug=db_rom.slug,
            summary=db_rom.summary,
            alternative_names=db_rom.alternative_names,
            youtube_video_id=db_rom.youtube_video_id,
            metadatum=db_rom.metadatum,
            igdb_metadata=db_rom.igdb_metadata,
            moby_metadata=db_rom.moby_metadata,
            ss_metadata=db_rom.ss_metadata,
            launchbox_metadata=db_rom.launchbox_metadata,
            hasheous_metadata=db_rom.hasheous_metadata,
            flashpoint_metadata=db_rom.flashpoint_metadata,
            hltb_metadata=db_rom.hltb_metadata,
            # Exclude sensitive filesystem paths
            # path_cover_small=db_rom.path_cover_small,  # Excluded
            # path_cover_large=db_rom.path_cover_large,  # Excluded
            url_cover=db_rom.url_cover,
            has_manual=db_rom.has_manual,
            # path_manual=db_rom.path_manual,  # Excluded
            url_manual=db_rom.url_manual,
            is_identifying=db_rom.is_identifying,
            is_unidentified=db_rom.is_unidentified,
            is_identified=db_rom.is_identified,
            revision=db_rom.revision,
            regions=db_rom.regions,
            languages=db_rom.languages,
            tags=db_rom.tags,
            crc_hash=db_rom.crc_hash,
            md5_hash=db_rom.md5_hash,
            sha1_hash=db_rom.sha1_hash,
            multi=db_rom.multi,
            has_simple_single_file=db_rom.has_simple_single_file,
            has_nested_single_file=db_rom.has_nested_single_file,
            has_multiple_files=db_rom.has_multiple_files,
            files=db_rom.files,
            # Exclude sensitive filesystem paths
            # full_path=db_rom.full_path,  # Excluded
            created_at=db_rom.created_at,
            updated_at=db_rom.updated_at,
            missing_from_fs=db_rom.missing_from_fs,
            siblings=db_rom.siblings,
            rom_user=db_rom.rom_user,
        )

        # Set the filtered fields to None using object.__setattr__ to bypass read-only properties
        object.__setattr__(rom_copy, "fs_path", None)
        object.__setattr__(rom_copy, "path_cover_small", None)
        object.__setattr__(rom_copy, "path_cover_large", None)
        object.__setattr__(rom_copy, "path_manual", None)
        object.__setattr__(rom_copy, "full_path", None)

        return cls.model_validate(rom_copy)

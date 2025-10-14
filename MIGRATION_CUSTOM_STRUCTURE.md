# Custom Library Structure Migration Guide

This guide explains how to migrate from the old hardcoded library structures to the new flexible custom structure system.

## Overview

RomM now supports custom library structures using macro-based patterns. This replaces the previous two hardcoded structures with a flexible configuration system.

## What Changed

### Old System

RomM previously supported two hardcoded structures:

1. **High Priority**: `roms/{platform}/{games}` (if `{roms}` folder exists at library root)
2. **Low Priority**: `{platform}/roms/{games}` (fallback)

### New System

RomM now uses configurable structures defined in `config.yml`:

- **Default Structure**: `roms/{platform}/{game}` (relative to LIBRARY_BASE_PATH)
- **Custom Structures**: Any pattern using available macros
- **Custom Macros**: Extract additional metadata as tags

## Migration Steps

### 1. Check Your Current Structure

RomM will automatically detect if you're using the old low-priority structure and show a warning at startup.

### 2. Update Your Configuration

Add the structure configuration to your `config.yml`:

```yaml
filesystem:
  structure: "roms/{platform}/{game}" # Default structure
  firmware_structure: "bios/{platform}" # Default firmware structure
```

### 3. Restart RomM

After updating your configuration and reorganizing files, restart RomM.

## Custom Structure Examples

### Basic Structures

```yaml
# Single and multi-file games (automatic detection)
structure: "roms/{platform}/{game}"
```

### Advanced Structures with Custom Macros

```yaml
# Organize by region
structure: 'roms/{platform}/{region}/{game}'
# Results in: roms/gba/usa/pokemon.gba
# Extracts: region=usa

# Organize by collection
structure: 'roms/{platform}/{collection}/{game}'
# Results in: roms/nes/nintendo/mario.nes
# Extracts: collection=nintendo

# Complex organization
structure: 'roms/{platform}/{region}/{collection}/{game}'
# Results in: roms/snes/usa/nintendo/mario.sfc
# Extracts: region=usa, collection=nintendo
```

### Firmware Structures

```yaml
# Default firmware structure
firmware_structure: 'bios/{platform}'
# Results in: bios/gba/, bios/snes/, etc.

# Organize firmware by region
firmware_structure: 'bios/{platform}/{region}'
# Results in: bios/gba/usa/, bios/snes/japan/, etc.
```

## Available Macros

### Required Macros

- `{platform}` - Platform directory

### Game Macro

- `{game}` - Game files or directories (automatically detects single-file vs multi-file games)

### Custom Macros

- `{<name>}` - Any custom name will be extracted as tags
- Examples: `{region}`, `{collection}`, `{genre}`, `{year}`

## Custom Tags

Custom macros are automatically extracted and stored as tags in the existing `tags` field:

```yaml
# Structure: 'roms/{platform}/{region}/{collection}/{game}'
# Path: library/roms/snes/usa/nintendo/mario.sfc
# Extracted tags: ["region:usa", "collection:nintendo"]
```

These tags are stored in the database's existing `tags` field and can be used for:

- Filtering games by custom criteria
- Creating smart collections
- Advanced search functionality

## Troubleshooting

### Structure Validation Errors

If you get structure validation errors:

1. **Missing required macros**: Ensure your structure contains `{platform}` and `{game}`
2. **Invalid macro names**: Only use `{platform}`, `{game}`, or custom `{<name>}` patterns
3. **Path separator**: Use `/` as the path separator

### Migration Issues

1. **Old structure detected**: Follow the migration steps above
2. **Files not found**: Ensure your file organization matches the configured structure
3. **Custom tags not extracted**: Verify your custom macros are in the correct positions in the path

### Performance Considerations

- Complex structures with many custom macros may impact scan performance
- Consider the trade-off between organization and performance
- Test with a small subset of games first

## Backward Compatibility

- The default structure `roms/{platform}/{game}` matches the old high-priority structure
- Users with the old low-priority structure must migrate manually
- RomM will detect and warn about old structures at startup

## Future Enhancements

The custom structure system enables future features:

- UI for viewing and filtering by custom tags
- Automatic tag-based collections
- Frontend structure configuration editor
- Advanced search and filtering capabilities

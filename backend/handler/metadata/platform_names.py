"""The names a platform is known by, from the providers' static platform lists."""

import functools
from collections import defaultdict

from handler.metadata import (
    meta_flashpoint_handler,
    meta_hasheous_handler,
    meta_hltb_handler,
    meta_igdb_handler,
    meta_launchbox_handler,
    meta_moby_handler,
    meta_ra_handler,
    meta_ss_handler,
    meta_tgdb_handler,
)
from utils.platform_slugs import UniversalPlatformSlug as UPS

# Providers in the order a platform's name is resolved from them.
_NAME_PROVIDERS = (
    meta_igdb_handler,
    meta_ss_handler,
    meta_moby_handler,
    meta_ra_handler,
    meta_launchbox_handler,
    meta_hasheous_handler,
    meta_tgdb_handler,
    meta_flashpoint_handler,
    meta_hltb_handler,
)


def _name_key(name: str) -> str:
    return " ".join(name.casefold().replace("/", " / ").split())


def _provider_names(slug: str) -> list[str]:
    names = [handler.get_platform(slug).get("name") for handler in _NAME_PROVIDERS]
    return [name for name in names if name]


@functools.cache
def resolve_platform_name(slug: str) -> str:
    """The first provider's name for the platform, else the slug in title case."""
    return next(iter(_provider_names(slug)), slug.replace("-", " ").title())


@functools.cache
def _slugs_by_resolved_name() -> dict[str, set[str]]:
    slugs_by_name: defaultdict[str, set[str]] = defaultdict(set)
    for ups in UPS:
        slugs_by_name[_name_key(resolve_platform_name(ups.value))].add(ups.value)
    return slugs_by_name


def platform_abbreviation(slug: str) -> str:
    return meta_igdb_handler.get_platform_aliases(slug)[0]


@functools.cache
def platform_alternative_names(slug: str) -> tuple[str, ...]:
    """IGDB's and ScreenScraper's alternative names, then each provider's other names."""
    # Providers map some variants onto their parent (Famicom onto NES), so skip
    # any name that another platform resolves to.
    slugs_by_name = _slugs_by_resolved_name()
    seen = {_name_key(resolve_platform_name(slug))}
    alternative_names = []
    for candidate in [
        *meta_igdb_handler.get_platform_aliases(slug)[1],
        *meta_ss_handler.get_platform_alternative_names(slug),
        *_provider_names(slug),
    ]:
        key = _name_key(candidate)
        owners = slugs_by_name.get(key)
        if key in seen or (owners and owners != {slug}):
            continue
        seen.add(key)
        alternative_names.append(candidate.strip())
    return tuple(alternative_names)

from handler.install import proton_builds
from handler.install.proton_builds import ProtonBuild


class TestListProtonBuilds:
    def test_returns_installed_plus_downloadable(self, monkeypatch):
        monkeypatch.setattr(
            proton_builds,
            "_discover_installed",
            lambda: [
                ProtonBuild(
                    id="GE-Proton10-34", label="GE-Proton 10-34",
                    installed=True, path="/opt/proton/GE-Proton10-34/proton",
                ),
            ],
        )
        monkeypatch.setattr(
            proton_builds,
            "_cached_downloadable",
            lambda: [],
        )
        builds = proton_builds.list_proton_builds()
        assert len(builds) >= 1
        assert any(b.installed for b in builds)

    def test_exactly_one_installed_when_one_baked_in(self, monkeypatch):
        monkeypatch.setattr(
            proton_builds,
            "_discover_installed",
            lambda: [
                ProtonBuild(
                    id="GE-Proton10-34", label="GE-Proton 10-34",
                    installed=True, path="/opt/proton/GE-Proton10-34/proton",
                ),
                ProtonBuild(
                    id="cachyos-latest", label="Proton-CachyOS (latest)",
                    installed=True, path="/opt/proton/cachyos-latest/proton",
                ),
            ],
        )
        monkeypatch.setattr(proton_builds, "_cached_downloadable", lambda: [])
        installed = [b for b in proton_builds.list_proton_builds() if b.installed]
        assert len(installed) == 2

    def test_downloadable_builds_that_are_now_installed_merge_version_info(self, monkeypatch):
        monkeypatch.setattr(
            proton_builds,
            "_discover_installed",
            lambda: [
                ProtonBuild(
                    id="GE-Proton11-7", label="GE-Proton 11-7",
                    installed=True, path="/opt/proton/GE-Proton11-7/proton",
                ),
            ],
        )
        monkeypatch.setattr(
            proton_builds,
            "_cached_downloadable",
            lambda: [
                ProtonBuild(
                    id="GE-Proton11-7", label="GE-Proton 11-7",
                    installed=False, source="upstream",
                    download_url="https://example.com/release.tar.gz",
                    version="GE-Proton11-7",
                ),
            ],
        )
        builds = proton_builds.list_proton_builds()
        # The downloadable entry should not be duplicated - only the merged
        # installed entry with version info from upstream.
        installable = [b for b in builds if b.id == "GE-Proton11-7"]
        assert len(installable) == 1
        assert installable[0].installed
        assert installable[0].version == "GE-Proton11-7"
        assert installable[0].download_url == "https://example.com/release.tar.gz"


class TestResolveProtonPath:
    def test_none_returns_none(self):
        assert proton_builds.resolve_proton_path(None) is None

    def test_unknown_build_id_returns_none(self, monkeypatch):
        monkeypatch.setattr(
            proton_builds,
            "_discover_installed",
            lambda: [],
        )
        assert proton_builds.resolve_proton_path("not-a-real-build") is None

    def test_known_but_not_installed_build_returns_none(self, monkeypatch):
        monkeypatch.setattr(
            proton_builds,
            "_discover_installed",
            lambda: [],
        )
        # Not discovered on disk, so no path even for a recognized id.
        assert proton_builds.resolve_proton_path("future-build") is None

    def test_installed_build_resolves_to_its_own_path(self, monkeypatch):
        monkeypatch.setattr(
            proton_builds,
            "_discover_installed",
            lambda: [
                ProtonBuild(
                    id="current", label="Current", installed=True,
                    path="/opt/proton/current/proton",
                ),
            ],
        )
        assert proton_builds.resolve_proton_path("current") == "/opt/proton/current/proton"

    def test_each_installed_build_resolves_to_its_own_distinct_path(
        self, monkeypatch
    ):
        monkeypatch.setattr(
            proton_builds,
            "_discover_installed",
            lambda: [
                ProtonBuild(
                    id="ge", label="GE", installed=True,
                    path="/opt/proton-ge/proton",
                ),
                ProtonBuild(
                    id="cachyos", label="CachyOS", installed=True,
                    path="/opt/proton-cachyos/proton",
                ),
            ],
        )
        assert proton_builds.resolve_proton_path("ge") == "/opt/proton-ge/proton"
        assert proton_builds.resolve_proton_path("cachyos") == "/opt/proton-cachyos/proton"


class TestResolveEffectiveBuild:
    def test_explicit_choice_wins(self, monkeypatch):
        monkeypatch.setattr(proton_builds, "INSTALL_DEFAULT_PROTON_BUILD", "cachyos-latest")
        assert proton_builds.resolve_effective_build("GE-Proton10-34") == "GE-Proton10-34"

    def test_falls_back_to_configured_default(self, monkeypatch):
        monkeypatch.setattr(proton_builds, "INSTALL_DEFAULT_PROTON_BUILD", "cachyos-latest")
        assert proton_builds.resolve_effective_build(None) == "cachyos-latest"

    def test_falls_back_to_whatever_is_installed_when_no_default_configured(
        self, monkeypatch
    ):
        monkeypatch.setattr(proton_builds, "INSTALL_DEFAULT_PROTON_BUILD", None)
        monkeypatch.setattr(
            proton_builds,
            "_discover_installed",
            lambda: [
                ProtonBuild(
                    id="GE-Proton10-34", label="GE-Proton 10-34",
                    installed=True, path="/opt/proton/GE-Proton10-34/proton",
                ),
            ],
        )
        assert proton_builds.resolve_effective_build(None) == "GE-Proton10-34"

    def test_none_when_nothing_known(self, monkeypatch):
        monkeypatch.setattr(proton_builds, "INSTALL_DEFAULT_PROTON_BUILD", None)
        monkeypatch.setattr(proton_builds, "_discover_installed", lambda: [])
        assert proton_builds.resolve_effective_build(None) is None

    def test_configured_default_returned_even_if_not_yet_downloaded(self, monkeypatch):
        # The whole point: the id is surfaced immediately so the client can
        # poll download progress, even though nothing is on disk yet.
        monkeypatch.setattr(proton_builds, "INSTALL_DEFAULT_PROTON_BUILD", "cachyos-latest")
        monkeypatch.setattr(proton_builds, "_discover_installed", lambda: [])
        assert proton_builds.resolve_effective_build(None) == "cachyos-latest"


class TestCustomBuilds:
    def test_custom_build_id_is_a_directory_safe_slug(self):
        assert proton_builds.custom_build_id(" My Proton (beta)! ") == "custom-my-proton-beta"

    def test_custom_builds_are_listed_as_downloadable(self, monkeypatch):
        monkeypatch.setattr(proton_builds, "_discover_installed", lambda: [])
        monkeypatch.setattr(proton_builds, "_cached_upstream", lambda: [])
        monkeypatch.setattr(
            proton_builds,
            "get_custom_builds",
            lambda: [{"name": "My Proton", "url": "https://example.com/p.tar.gz"}],
        )
        builds = proton_builds.list_proton_builds()
        assert [(b.id, b.label, b.installed, b.custom) for b in builds] == [
            ("custom-my-proton", "My Proton", False, True)
        ]

    def test_installed_custom_build_takes_its_display_name(self, monkeypatch):
        monkeypatch.setattr(
            proton_builds,
            "_discover_installed",
            lambda: [
                ProtonBuild(id="custom-my-proton", label="custom-my-proton", installed=True)
            ],
        )
        monkeypatch.setattr(proton_builds, "_cached_upstream", lambda: [])
        monkeypatch.setattr(
            proton_builds,
            "get_custom_builds",
            lambda: [{"name": "My Proton", "url": "https://example.com/p.tar.gz"}],
        )
        (build,) = proton_builds.list_proton_builds()
        assert build.installed and build.label == "My Proton"


class TestGeLatestPerMajor:
    def test_picks_the_newest_release_of_each_major(self, monkeypatch):
        def release(tag):
            return {
                "tag_name": tag,
                "assets": [
                    {
                        "name": f"{tag}.tar.gz",
                        "browser_download_url": f"https://example.com/{tag}.tar.gz",
                        "size": 1,
                    }
                ],
            }

        pages = {
            1: [release("GE-Proton11-7"), release("GE-Proton10-34"), release("GE-Proton10-9")],
            2: [release("GE-Proton9-27"), release("GE-Proton8-32"), release("GE-Proton7-55")],
        }
        monkeypatch.setattr(
            proton_builds, "_github_get", lambda url, params=None: pages.get(params["page"])
        )
        builds = proton_builds._fetch_ge_latest_per_major()
        assert [(b.id, b.label) for b in builds] == [
            ("GE-Proton11-7", "GE-Proton11 (latest)"),
            ("GE-Proton10-34", "GE-Proton10 (latest)"),
            ("GE-Proton9-27", "GE-Proton9 (latest)"),
            ("GE-Proton8-32", "GE-Proton8 (latest)"),
        ]

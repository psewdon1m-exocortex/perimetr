import json

from app.updater import check_github_release


class FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self, _limit):
        return json.dumps([
            {
                "tag_name": "agent-v9.0.0",
                "draft": False,
                "prerelease": False,
                "html_url": "https://github.com/example/platform/releases/tag/agent-v9.0.0",
                "published_at": "2026-07-28T00:00:00Z",
            },
            {
                "tag_name": "perimetr-v1.2.0",
                "draft": False,
                "prerelease": False,
                "html_url": "https://github.com/example/platform/releases/tag/perimetr-v1.2.0",
                "published_at": "2026-07-28T00:00:00Z",
            },
        ]).encode("utf-8")


def test_release_check_selects_only_the_requested_service_tag():
    observed = {}

    def opener(request, timeout):
        observed["url"] = request.full_url
        observed["timeout"] = timeout
        return FakeResponse()

    result = check_github_release(
        repository_url="https://github.com/example/exocortex-perimetr",
        service="perimetr",
        current_version="1.1.0",
        timeout_seconds=4,
        opener=opener,
    )

    assert observed["url"] == "https://api.github.com/repos/example/exocortex-perimetr/releases?per_page=100"
    assert observed["timeout"] == 4
    assert result["available_version"] == "1.2.0"
    assert result["update_available"] is True
    assert result["apply_via"] == "updater"


def test_release_check_prefers_stable_over_same_version_prerelease():
    class StableResponse(FakeResponse):
        def read(self, _limit):
            return json.dumps([
                {"tag_name": "perimetr-v2.0.0-rc.1", "draft": False},
                {"tag_name": "perimetr-v2.0.0", "draft": False},
            ]).encode("utf-8")

    result = check_github_release(
        repository_url="https://github.com/example/platform",
        service="perimetr",
        current_version="1.1.0",
        timeout_seconds=4,
        opener=lambda *_args, **_kwargs: StableResponse(),
    )

    assert result["available_version"] == "2.0.0"

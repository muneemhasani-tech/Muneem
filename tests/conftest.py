import asyncio
import copy

import httpx
import pytest

from lead_verifier.cache import Cache
from lead_verifier.config import DEFAULTS
from lead_verifier.pipeline import Pipeline
from lead_verifier.quota import Quota

KEYS = {
    "qev_api_key": "qk", "verifalia_username": "vu", "verifalia_password": "vp",
    "webrisk_api_key": "wk", "urlhaus_auth_key": "uk",
}


def make_cfg(**over):
    cfg = copy.deepcopy(DEFAULTS)
    cfg["retry"] = {"attempts": 3, "backoff_seconds": [0, 0, 0]}
    for k, v in over.items():
        if isinstance(v, dict):
            cfg[k].update(v)
        else:
            cfg[k] = v
    return cfg


@pytest.fixture
def cfg():
    return make_cfg()


@pytest.fixture
def cache():
    c = Cache(":memory:")
    yield c
    c.close()


@pytest.fixture
def quota(cache, cfg):
    return Quota(cache, cfg["providers"])


def run(coro):
    return asyncio.run(coro)


def with_client(fn):
    """Run `async fn(client)` inside an httpx client (respx patches it globally)."""
    async def go():
        async with httpx.AsyncClient() as c:
            return await fn(c)
    return asyncio.run(go())


async def fake_mx(domain):
    return "no_mx" if "nodomain" in domain else "ok"

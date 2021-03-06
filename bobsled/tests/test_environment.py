import os
import pytest
from unittest import mock
from ..environment import EnvironmentProvider
from ..base import Environment


@pytest.fixture
def simpleenv():
    filename = os.path.join(os.path.dirname(__file__), "environments.yml")
    return EnvironmentProvider(filename)


@pytest.mark.asyncio
async def test_get_environment_names(simpleenv):
    await simpleenv.update_environments()
    assert set(simpleenv.get_environment_names()) == {"one", "two"}


@pytest.mark.asyncio
async def test_get_environment(simpleenv):
    await simpleenv.update_environments()
    assert simpleenv.get_environment("one") == Environment(
        "one", {"number": 123, "word": "hello"}, ["word"]
    )


@pytest.mark.asyncio
async def test_mask_variables(simpleenv):
    await simpleenv.update_environments()
    assert (
        simpleenv.mask_variables("hello this is a test, but 123 is masked")
        == "hello this is a test, but **ONE/NUMBER** is masked"
    )


@pytest.mark.asyncio
async def test_get_environment_paramstore():
    filename = os.path.join(os.path.dirname(__file__), "paramstore_env.yml")
    psenv = EnvironmentProvider(filename)
    # patch paramstore loader so we don't have to do a bunch of moto stuff that
    # doesn't really work well with async
    with mock.patch("bobsled.environment.paramstore_loader", new=lambda x: "ps-" + x):
        await psenv.update_environments()
    assert psenv.get_environment("one") == Environment(
        "one", {"number": "ps-/bobsledtest/number", "word": "ps-/bobsledtest/word"}, []
    )

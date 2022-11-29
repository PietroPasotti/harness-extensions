import itertools
import random
import shutil
from hashlib import md5
from unittest import mock
from pathlib import Path

import pytest as pytest

from spellbook import spellbook_fetch, CHARM_CACHE_DEFAULT_DIR, CHARM_SHELF_DEFAULT_DIR

root = Path(__file__).parent


@pytest.fixture(autouse=True, scope='module')
def cache_setup():
    for x in [CHARM_CACHE_DEFAULT_DIR, CHARM_SHELF_DEFAULT_DIR]:
        assert not x.exists()

    yield

    for x in [CHARM_CACHE_DEFAULT_DIR, CHARM_SHELF_DEFAULT_DIR]:
        assert x.exists()
        shutil.rmtree(x)


class SubProcMock:
    ret_value = "10"
    root: Path = Path()

    def __call__(self, *args, **kwargs):
        if args[0].startswith('find'):
            return self.ret_value
        elif args[0].startswith('charmcraft'):
            charm_file = self.root / f"{random.randint(100000,900000)}.charm"
            charm_file.touch(exist_ok=True)
            return str(charm_file)
        raise ValueError(args)


@pytest.mark.parametrize('copy_tag, hash_value, charm_name', itertools.product(
        ('boo', None),
        ('12ab', "21344", "891"),
        ('origin', "tester", "foo12_ab", "-a_dc"),
))
@mock.patch("spellbook.getoutput", new_callable=SubProcMock)
def test_cache_populate(subproc, copy_tag, hash_value, charm_name):
    subproc.ret_value = hash_value
    subproc.root = root
    origin_charm = spellbook_fetch(root, charm_name, use_cache=True, copy_tag=copy_tag)
    assert origin_charm.name == f"{charm_name}.{copy_tag}.charm"
    hexmd5 = md5(subproc.ret_value.encode("utf-8")).hexdigest()
    assert (CHARM_CACHE_DEFAULT_DIR / f"{charm_name}.{hexmd5}.charm").exists()



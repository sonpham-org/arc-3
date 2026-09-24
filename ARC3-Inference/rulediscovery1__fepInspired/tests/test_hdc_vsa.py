# Author: Claude Opus 5.5 (Bubba)
# Date: 24-September-2026
# PURPOSE: Stage-1 tests for hdc/vsa.py (roadmap docs/plans/2026-09-24-hdc-ghost-roadmap.md): binding is
#   exactly invertible, random vectors are nearly orthogonal, fractional powers make a spatial shift exact,
#   and one item is recovered from a small bundle. The capacity curve itself is measured by hdc/stage1_capacity.py.
# SRP/DRY check: Pass -- tests only.
from __future__ import annotations

import numpy as np

from rulediscovery1__fepInspired.hdc.vsa import VSA


def test_bind_unbind_recovers_item():
    v = VSA(1024, seed=1)
    a, b = v.rand(), v.rand()
    assert v.sim(v.unbind(v.bind(a, b), b), a) > 0.999


def test_random_vectors_nearly_orthogonal():
    v = VSA(1024, seed=2)
    a, b = v.rand(), v.rand()
    assert abs(v.sim(a, b)) < 5 / np.sqrt(1024)


def test_fractional_power_shift_is_exact():
    v = VSA(1024, seed=3)
    for x, dx in ((3.0, 6.0), (-12.0, 6.0), (0.5, 1.25)):
        assert np.allclose(v.power(v.X, x) * v.power(v.X, dx), v.power(v.X, x + dx))
    assert np.allclose(v.disp(0, 0), 1.0)


def test_shift_is_invertible_and_decorrelates():
    v = VSA(1024, seed=4)
    a = v.rand()
    assert np.allclose(v.shift(v.shift(a, 7), -7), a)
    assert abs(v.sim(v.shift(a, 1), a)) < 5 / np.sqrt(1024)


def test_small_bundle_cleanup():
    v = VSA(1024, seed=5)
    book = v.rand(50)
    keys = v.rand(10)
    mem = v.bundle([v.bind(k, book[i]) for i, k in enumerate(keys)])
    assert all(v.cleanup(v.unbind(mem, k), book) == i for i, k in enumerate(keys))

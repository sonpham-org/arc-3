"""Minimal numpy-backed stand-in for the torch API the HiCache host pool code uses.

Views share memory exactly like numpy views; .view(shape) refuses to copy (numpy
shape assignment), matching torch.view's no-copy rule for the cases used here.
Every root allocation is registered so emulated kernels can bounds-check raw
byte copies against the allocation an address belongs to.
"""

from __future__ import annotations

import ctypes

import numpy as np


class dtype:
    def __init__(self, name, np_dtype):
        self.name = name
        self.np = np.dtype(np_dtype)
        self.itemsize = self.np.itemsize
        self.is_floating_point = name.startswith(("float", "bfloat"))

    def __repr__(self):
        return f"torch.{self.name}"


uint8 = dtype("uint8", np.uint8)
int8 = dtype("int8", np.int8)
int16 = dtype("int16", np.int16)
int32 = dtype("int32", np.int32)
int64 = dtype("int64", np.int64)
long = int64
uint64 = dtype("uint64", np.uint64)
bool = dtype("bool", np.bool_)  # noqa: A001
float32 = dtype("float32", np.float32)
float16 = dtype("float16", np.float16)
bfloat16 = dtype("bfloat16", np.uint16)  # storage-only stand-in
float8_e4m3fn = dtype("float8_e4m3fn", np.uint8)
float8_e5m2 = dtype("float8_e5m2", np.uint8)
float8_e4m3fnuz = dtype("float8_e4m3fnuz", np.uint8)
float4_e2m1fn_x2 = dtype("float4_e2m1fn_x2", np.uint8)

_BY_NP = {}
for _d in (uint8, int8, int16, int32, int64, uint64, bool, float32, float16):
    _BY_NP.setdefault(_d.np, _d)

ALLOCATIONS = []  # (start, end, label, array): the array is kept alive, so no
# registered range can be freed and reused while it is registered.


def reset_allocations():
    ALLOCATIONS.clear()


def _register(arr, label):
    start = arr.__array_interface__["data"][0]
    ALLOCATIONS.append((start, start + arr.nbytes, label, arr))


def allocation_of(addr):
    for start, end, label, _ in ALLOCATIONS:
        if start <= addr < end:
            return start, end, label
    raise AssertionError(f"address {addr:#x} is in no allocation")


def _dev(device):
    if device is None:
        return "cpu"
    return str(device)


class Size(tuple):
    pass


class Tensor:
    def __init__(self, arr, device="cpu", dtype_=None):
        self.a = arr
        self._device = _dev(device)
        self._dtype = dtype_ if dtype_ is not None else _BY_NP[arr.dtype]

    # -- metadata ---------------------------------------------------------
    @property
    def shape(self):
        return Size(self.a.shape)

    @property
    def dtype(self):
        return self._dtype

    @property
    def device(self):
        return self._device

    @property
    def is_cuda(self):
        return self._device.startswith("cuda")

    @property
    def ndim(self):
        return self.a.ndim

    def dim(self):
        return self.a.ndim

    def numel(self):
        return int(self.a.size)

    def element_size(self):
        return self._dtype.itemsize

    def data_ptr(self):
        return self.a.__array_interface__["data"][0]

    def is_contiguous(self):
        return self.a.flags["C_CONTIGUOUS"]

    def size(self, i=None):
        return Size(self.a.shape) if i is None else self.a.shape[i]

    def stride(self, i=None):
        strides = tuple(s // self.a.itemsize for s in self.a.strides)
        return strides if i is None else strides[i]

    def __len__(self):
        return self.a.shape[0]

    def __repr__(self):
        return f"FakeTensor({self.shape}, {self._dtype}, {self._device})"

    # -- indexing ---------------------------------------------------------
    @staticmethod
    def _np_index(idx):
        if isinstance(idx, tuple):
            return tuple(Tensor._np_index(i) for i in idx)
        if isinstance(idx, Tensor):
            return idx.a
        return idx

    def __getitem__(self, idx):
        out = self.a[self._np_index(idx)]
        if not isinstance(out, np.ndarray):
            out = np.asarray(out, dtype=self.a.dtype)
        return Tensor(out, self._device, self._dtype)

    def __setitem__(self, idx, value):
        if isinstance(value, Tensor):
            value = value.a
        self.a[self._np_index(idx)] = value

    # -- views --------------------------------------------------------------
    def view(self, *shape):
        if len(shape) == 1 and isinstance(shape[0], dtype):
            new = shape[0]
            return Tensor(self.a.view(new.np), self._device, new)
        if len(shape) == 1 and isinstance(shape[0], (tuple, list)):
            shape = tuple(shape[0])
        out = self.a.view()
        out.shape = shape  # raises when a copy would be needed, like torch.view
        return Tensor(out, self._device, self._dtype)

    def reshape(self, *shape):
        if len(shape) == 1 and isinstance(shape[0], (tuple, list)):
            shape = tuple(shape[0])
        return Tensor(self.a.reshape(shape), self._device, self._dtype)

    def flatten(self):
        return Tensor(self.a.reshape(-1), self._device, self._dtype)

    def transpose(self, d0, d1):
        return Tensor(np.swapaxes(self.a, d0, d1), self._device, self._dtype)

    def contiguous(self):
        if self.is_contiguous():
            return self
        out = np.ascontiguousarray(self.a)
        _register(out, "contiguous copy")
        return Tensor(out, self._device, self._dtype)

    def clone(self):
        out = self.a.copy()
        _register(out, "clone")
        return Tensor(out, self._device, self._dtype)

    def to(self, device=None, dtype_=None, non_blocking=False, **kw):
        if isinstance(device, dtype):
            dtype_, device = device, None
        dtype_ = dtype_ or kw.get("dtype")
        out = self.a.copy() if dtype_ is None else self.a.astype(dtype_.np)
        _register(out, "to")
        return Tensor(out, self._device if device is None else device, dtype_ or self._dtype)

    def cpu(self):
        return self.to("cpu")

    def long(self):
        return self if self._dtype is int64 else self.to(dtype_=int64)

    def tolist(self):
        return self.a.tolist()

    def item(self):
        return self.a.item()

    def fill_(self, value):
        self.a.fill(value)
        return self

    def zero_(self):
        return self.fill_(0)

    def any(self):
        return Tensor(np.asarray(self.a.any()), self._device, bool)

    def all(self):
        return Tensor(np.asarray(self.a.all()), self._device, bool)

    def __bool__(self):
        return builtins_bool(self.a.all())

    def split(self, size):
        return [self[i : i + size] for i in range(0, len(self), size)]

    def record_stream(self, stream):
        pass

    # -- arithmetic ---------------------------------------------------------
    def _bin(self, other, op):
        other = other.a if isinstance(other, Tensor) else other
        out = op(self.a, other)
        if out.dtype == np.bool_:
            return Tensor(out, self._device, bool)
        return Tensor(out.astype(self.a.dtype, copy=False), self._device, self._dtype)

    def __floordiv__(self, other):
        return self._bin(other, np.floor_divide)

    def __mod__(self, other):
        return self._bin(other, np.mod)

    def __add__(self, other):
        return self._bin(other, np.add)

    def __sub__(self, other):
        return self._bin(other, np.subtract)

    def __mul__(self, other):
        return self._bin(other, np.multiply)

    def __eq__(self, other):
        return self._bin(other, np.equal)

    def __ne__(self, other):
        return self._bin(other, np.not_equal)

    __hash__ = object.__hash__


import builtins as _builtins  # noqa: E402

builtins_bool = _builtins.bool


def _new(arr, device, dtype_, label):
    _register(arr, label)
    return Tensor(arr, device, dtype_)


def _shape(args):
    if len(args) == 1 and isinstance(args[0], (tuple, list)):
        return tuple(args[0])
    return tuple(args)


def empty(*shape, dtype=float32, device=None, pin_memory=False, **kw):
    return _new(np.zeros(_shape(shape), dtype=dtype.np), device, dtype, "empty")


def zeros(*shape, dtype=float32, device=None, pin_memory=False, **kw):
    return _new(np.zeros(_shape(shape), dtype=dtype.np), device, dtype, "zeros")


def empty_like(t, **kw):
    return _new(np.zeros_like(t.a), t.device, t.dtype, "empty_like")


def zeros_like(t, **kw):
    return empty_like(t)


def full_like(t, value, **kw):
    return _new(np.full_like(t.a, value), t.device, t.dtype, "full_like")


def tensor(data, dtype=None, device=None):
    dtype = dtype or int64
    return _new(np.array(data, dtype=dtype.np), device, dtype, "tensor")


def arange(*args, dtype=int64, device=None):
    return _new(np.arange(*args, dtype=dtype.np), device, dtype, "arange")


def cat(tensors, dim=0):
    tensors = list(tensors)
    return _new(
        np.concatenate([t.a for t in tensors], axis=dim),
        tensors[0].device,
        tensors[0].dtype,
        "cat",
    )


def equal(a, b):
    return a.shape == b.shape and builtins_bool(np.array_equal(a.a, b.a))


class _Distributed:
    @staticmethod
    def is_available():
        return False

    @staticmethod
    def is_initialized():
        return False


distributed = _Distributed()


class _Cuda:
    @staticmethod
    def is_available():
        return True


cuda = _Cuda()

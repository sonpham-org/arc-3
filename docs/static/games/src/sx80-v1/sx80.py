# Copycat sx80: rules of public ARC-AGI-3 game sp80, new maps, colours and art.
# Built and verified by autoresearch-arena arc3games/copycats/cc_sp80.py.
# MIT License
#
# Copyright (c) 2026 ARC Prize Foundation
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np
from arcengine import (
    BlockingMode,
    InteractionMode,
    ActionInput,
    ARCBaseGame,
    Camera,
    GameAction,
    Level,
    RenderableUserDisplay,
    Sprite,
)

sprites = {
    'bodekplurlf16': Sprite(
        pixels=[
        [3, 3, 2, 2, 3, 3, 2, 2, 3, 3, 2, 2, 3, 3, 2, 2, 3, 3],
        [2, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 3],
        [2, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 2],
        [3, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 2],
        [3, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 3],
        [2, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 3],
        [2, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 2],
        [3, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 2],
        [3, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 3],
        [2, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 3],
        [2, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 2],
        [3, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 2],
        [3, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 3],
        [2, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 3],
        [2, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 2],
        [3, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 2],
        [3, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 3],
        [2, 3, 3, 2, 2, 3, 3, 2, 2, 3, 3, 2, 2, 3, 3, 2, 2, 3],
    ],
        name='bodekplurlf16',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
    ),
    'bodekplurlf20': Sprite(
        pixels=[
        [3, 3, 2, 2, 3, 3, 2, 2, 3, 3, 2, 2, 3, 3, 2, 2, 3, 3, 2, 2, 3, 3],
        [2, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 3],
        [2, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 2],
        [3, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 2],
        [3, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 3],
        [2, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 3],
        [2, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 2],
        [3, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 2],
        [3, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 3],
        [2, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 3],
        [2, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 2],
        [3, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 2],
        [3, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 3],
        [2, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 3],
        [2, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 2],
        [3, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 2],
        [3, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 3],
        [2, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 3],
        [2, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 2],
        [3, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 2],
        [3, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 3],
        [2, 3, 3, 2, 2, 3, 3, 2, 2, 3, 3, 2, 2, 3, 3, 2, 2, 3, 3, 2, 2, 3],
    ],
        name='bodekplurlf20',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
    ),
    'bodekplurlf32': Sprite(
        pixels=[
        [3, 3, 2, 2, 3, 3, 2, 2, 3, 3, 2, 2, 3, 3, 2, 2, 3, 3, 2, 2, 3, 3, 2, 2, 3, 3, 2, 2, 3, 3, 2, 2, 3, 3],
        [2, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 3],
        [2, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 2],
        [3, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 2],
        [3, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 3],
        [2, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 3],
        [2, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 2],
        [3, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 2],
        [3, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 3],
        [2, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 3],
        [2, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 2],
        [3, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 2],
        [3, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 3],
        [2, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 3],
        [2, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 2],
        [3, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 2],
        [3, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 3],
        [2, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 3],
        [2, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 2],
        [3, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 2],
        [3, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 3],
        [2, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 3],
        [2, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 2],
        [3, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 2],
        [3, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 3],
        [2, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 3],
        [2, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 2],
        [3, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 2],
        [3, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 3],
        [2, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 3],
        [2, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 2],
        [3, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 2],
        [3, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 3],
        [2, 3, 3, 2, 2, 3, 3, 2, 2, 3, 3, 2, 2, 3, 3, 2, 2, 3, 3, 2, 2, 3, 3, 2, 2, 3, 3, 2, 2, 3, 3, 2, 2, 3],
    ],
        name='bodekplurlf32',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
    ),
    'liolfvkveqg': Sprite(
        pixels=[
        [6],
    ],
        name='liolfvkveqg',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['liolfvkveqg'],
    ),
    'plzwjbfyfli-3': Sprite(
        pixels=[
        [8, 8, 8],
    ],
        name='plzwjbfyfli-3',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['plzwjbfyfli', 'sys_click'],
    ),
    'plzwjbfyfli-4': Sprite(
        pixels=[
        [8, 8, 8, 8],
    ],
        name='plzwjbfyfli-4',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['plzwjbfyfli', 'sys_click'],
    ),
    'plzwjbfyfli-4h': Sprite(
        pixels=[
        [8],
        [8],
        [8],
        [8],
    ],
        name='plzwjbfyfli-4h',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['plzwjbfyfli', 'sys_click'],
    ),
    'plzwjbfyfli-5': Sprite(
        pixels=[
        [8, 8, 8, 8, 8],
    ],
        name='plzwjbfyfli-5',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['plzwjbfyfli', 'sys_click'],
    ),
    'plzwjbfyfli-5-sowlljgtjvn': Sprite(
        pixels=[
        [8, 8, 4, 8, 8],
    ],
        name='plzwjbfyfli-5-sowlljgtjvn',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['plzwjbfyfli', 'sowlljgtjvn', 'sys_click'],
    ),
    'plzwjbfyfli-6': Sprite(
        pixels=[
        [8, 8, 8, 8, 8, 8],
    ],
        name='plzwjbfyfli-6',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['plzwjbfyfli', 'sys_click'],
    ),
    'plzwjbfyfli-7': Sprite(
        pixels=[
        [8, 8, 8, 8, 8, 8, 8],
    ],
        name='plzwjbfyfli-7',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['plzwjbfyfli'],
    ),
    'plzwjbfyfli-7-sowlljgtjvn': Sprite(
        pixels=[
        [8, 8, 8, 4, 8, 8, 8],
    ],
        name='plzwjbfyfli-7-sowlljgtjvn',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['plzwjbfyfli', 'sowlljgtjvn'],
    ),
    'plzwjbfyfli-8': Sprite(
        pixels=[
        [8, 8, 8, 8, 8, 8, 8, 8],
    ],
        name='plzwjbfyfli-8',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['plzwjbfyfli', 'sys_click'],
    ),
    'repwkzbkhxl': Sprite(
        pixels=[
        [11, -1, 11],
        [11, 11, 11],
    ],
        name='repwkzbkhxl',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['repwkzbkhxl'],
    ),
    'sowlljgtjvn': Sprite(
        pixels=[
        [4],
    ],
        name='sowlljgtjvn',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['sowlljgtjvn'],
    ),
    'tuvkdkhdokr-lexuhyxqrsm': Sprite(
        pixels=[
        [15, -1],
        [15, 15],
    ],
        name='tuvkdkhdokr-lexuhyxqrsm',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['tuvkdkhdokr', 'sys_click'],
    ),
    'tuvkdkhdokr-riwynidseun': Sprite(
        pixels=[
        [-1, 15],
        [15, 15],
    ],
        name='tuvkdkhdokr-riwynidseun',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['tuvkdkhdokr', 'sys_click'],
    ),
    'waoewejnqzc': Sprite(
        pixels=[
        [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
    ],
        name='waoewejnqzc',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['waoewejnqzc'],
    ),
}
levels = [
    # Level 1
    Level(
        sprites=[
            sprites['bodekplurlf16'].clone().set_position(0, 0),
            sprites['liolfvkveqg'].clone().set_position(7, 2),
            sprites['plzwjbfyfli-5'].clone().set_position(10, 5),
            sprites['repwkzbkhxl'].clone().set_position(10, 14),
            sprites['repwkzbkhxl'].clone().set_position(4, 14),
            sprites['sowlljgtjvn'].clone().set_position(7, 1),
            sprites['waoewejnqzc'].clone().set_position(-15, 16),
        ],
        grid_size=(18, 18),
        data={'steps': 30, 'dojfslwbg': 90},
    ),
    # Level 2
    Level(
        sprites=[
            sprites['bodekplurlf16'].clone().set_position(0, 0),
            sprites['liolfvkveqg'].clone().set_position(11, 2),
            sprites['plzwjbfyfli-3'].clone().set_position(9, 11),
            sprites['plzwjbfyfli-3'].clone().set_position(7, 9),
            sprites['plzwjbfyfli-5'].clone().set_position(4, 4),
            sprites['repwkzbkhxl'].clone().set_position(12, 14),
            sprites['repwkzbkhxl'].clone().set_position(8, 14),
            sprites['repwkzbkhxl'].clone().set_position(4, 14),
            sprites['sowlljgtjvn'].clone().set_position(11, 1),
            sprites['waoewejnqzc'].clone().set_position(-15, 16),
        ],
        grid_size=(18, 18),
        data={'steps': 45, 'dojfslwbg': 270},
    ),
    # Level 3
    Level(
        sprites=[
            sprites['bodekplurlf16'].clone().set_position(0, 0),
            sprites['liolfvkveqg'].clone().set_position(15, 2),
            sprites['liolfvkveqg'].clone().set_position(2, 2),
            sprites['liolfvkveqg'].clone().set_position(10, 2),
            sprites['plzwjbfyfli-4'].clone().set_position(1, 11),
            sprites['plzwjbfyfli-5'].clone().set_position(10, 11),
            sprites['plzwjbfyfli-6'].clone().set_position(1, 4),
            sprites['plzwjbfyfli-6'].clone().set_position(7, 6),
            sprites['repwkzbkhxl'].clone().set_position(13, 14),
            sprites['repwkzbkhxl'].clone().set_position(2, 14),
            sprites['repwkzbkhxl'].clone().set_position(7, 14),
            sprites['sowlljgtjvn'].clone().set_position(15, 1),
            sprites['sowlljgtjvn'].clone().set_position(2, 1),
            sprites['sowlljgtjvn'].clone().set_position(10, 1),
            sprites['waoewejnqzc'].clone().set_position(-15, 16),
        ],
        grid_size=(18, 18),
        data={'steps': 100, 'dojfslwbg': 270},
    ),
    # Level 4
    Level(
        sprites=[
            sprites['bodekplurlf20'].clone().set_position(0, 0),
            sprites['liolfvkveqg'].clone().set_position(13, 2),
            sprites['plzwjbfyfli-4'].clone().set_position(4, 13),
            sprites['plzwjbfyfli-4'].clone().set_position(5, 16),
            sprites['plzwjbfyfli-5'].clone().set_position(14, 4),
            sprites['plzwjbfyfli-5'].clone().set_position(5, 9),
            sprites['plzwjbfyfli-7-sowlljgtjvn'].clone().set_position(5, 6),
            sprites['repwkzbkhxl'].clone().set_position(16, 18),
            sprites['repwkzbkhxl'].clone().set_position(2, 18),
            sprites['repwkzbkhxl'].clone().set_position(10, 18),
            sprites['repwkzbkhxl'].clone().set_position(6, 18),
            sprites['sowlljgtjvn'].clone().set_position(13, 1),
            sprites['waoewejnqzc'].clone().set_position(-11, 20),
        ],
        grid_size=(22, 22),
        data={'steps': 120, 'dojfslwbg': 90},
    ),
    # Level 5
    Level(
        sprites=[
            sprites['bodekplurlf20'].clone().set_position(0, 0),
            sprites['liolfvkveqg'].clone().set_position(15, 2),
            sprites['liolfvkveqg'].clone().set_position(7, 2),
            sprites['plzwjbfyfli-3'].clone().set_position(5, 14),
            sprites['plzwjbfyfli-4'].clone().set_position(8, 10),
            sprites['plzwjbfyfli-5'].clone().set_position(12, 16),
            Sprite(
                pixels=[
                [11, -1, 11],
                [11, 11, 11],
            ],
                name='repwkzbkhxl',
                x=2,
                y=7,
                rotation=90,
                blocking=BlockingMode.PIXEL_PERFECT,
                interaction=InteractionMode.TANGIBLE,
                tags=['repwkzbkhxl'],
            ),
            sprites['repwkzbkhxl'].clone().set_position(16, 18),
            sprites['repwkzbkhxl'].clone().set_position(12, 18),
            sprites['repwkzbkhxl'].clone().set_position(6, 18),
            sprites['sowlljgtjvn'].clone().set_position(15, 1),
            sprites['sowlljgtjvn'].clone().set_position(7, 1),
            sprites['tuvkdkhdokr-riwynidseun'].clone().set_position(7, 5),
            sprites['waoewejnqzc'].clone().set_position(-11, 20),
            Sprite(
                pixels=[
                [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            ],
                name='waoewejnqzc',
                x=1,
                y=1,
                rotation=270,
                blocking=BlockingMode.PIXEL_PERFECT,
                interaction=InteractionMode.TANGIBLE,
                tags=['waoewejnqzc'],
            ),
            Sprite(
                pixels=[
                [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            ],
                name='waoewejnqzc',
                x=21,
                y=1,
                rotation=270,
                blocking=BlockingMode.PIXEL_PERFECT,
                interaction=InteractionMode.TANGIBLE,
                tags=['waoewejnqzc'],
            ),
        ],
        grid_size=(22, 22),
        data={'steps': 100, 'dojfslwbg': 270},
    ),
    # Level 6
    Level(
        sprites=[
            sprites['bodekplurlf20'].clone().set_position(0, 0),
            sprites['liolfvkveqg'].clone().set_position(11, 2),
            sprites['plzwjbfyfli-4h'].clone().set_position(16, 16),
            sprites['plzwjbfyfli-5-sowlljgtjvn'].clone().set_position(5, 4),
            Sprite(
                pixels=[
                [11, -1, 11],
                [11, 11, 11],
            ],
                name='repwkzbkhxl',
                x=2,
                y=10,
                rotation=90,
                blocking=BlockingMode.PIXEL_PERFECT,
                interaction=InteractionMode.TANGIBLE,
                tags=['repwkzbkhxl'],
            ),
            sprites['repwkzbkhxl'].clone().set_position(10, 18),
            Sprite(
                pixels=[
                [11, -1, 11],
                [11, 11, 11],
            ],
                name='repwkzbkhxl',
                x=18,
                y=12,
                rotation=270,
                blocking=BlockingMode.PIXEL_PERFECT,
                interaction=InteractionMode.TANGIBLE,
                tags=['repwkzbkhxl'],
            ),
            Sprite(
                pixels=[
                [11, -1, 11],
                [11, 11, 11],
            ],
                name='repwkzbkhxl',
                x=18,
                y=7,
                rotation=270,
                blocking=BlockingMode.PIXEL_PERFECT,
                interaction=InteractionMode.TANGIBLE,
                tags=['repwkzbkhxl'],
            ),
            sprites['sowlljgtjvn'].clone().set_position(11, 1),
            sprites['tuvkdkhdokr-lexuhyxqrsm'].clone().set_position(11, 15),
            sprites['tuvkdkhdokr-riwynidseun'].clone().set_position(15, 6),
            sprites['waoewejnqzc'].clone().set_position(-11, 20),
            Sprite(
                pixels=[
                [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            ],
                name='waoewejnqzc',
                x=1,
                y=1,
                rotation=270,
                blocking=BlockingMode.PIXEL_PERFECT,
                interaction=InteractionMode.TANGIBLE,
                tags=['waoewejnqzc'],
            ),
            Sprite(
                pixels=[
                [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            ],
                name='waoewejnqzc',
                x=20,
                y=1,
                rotation=270,
                blocking=BlockingMode.PIXEL_PERFECT,
                interaction=InteractionMode.TANGIBLE,
                tags=['waoewejnqzc'],
            ),
        ],
        grid_size=(22, 22),
        data={'steps': 120, 'dojfslwbg': 90},
    ),
]
BACKGROUND_COLOR = 12
PADDING_COLOR = 1


class sklgkadoxw(RenderableUserDisplay):
    """."""

    def __init__(self, vwbodnowge: int = 0):
        self.vwbodnowge = vwbodnowge
        self.current_steps = vwbodnowge
        super().__init__()

    def fymfsbgqso(self, pfhpxrnpci: int) -> None:
        self.current_steps = max(0, min(pfhpxrnpci, self.vwbodnowge))

    def render_interface(self, frame: np.ndarray) -> np.ndarray:
        if self.vwbodnowge == 0:
            return frame
        ouoessvdbk = self.current_steps / self.vwbodnowge
        zzmgpljlhw = round(64 * ouoessvdbk)
        for x in range(64):
            if x < zzmgpljlhw:
                frame[0, x] = 14
            else:
                frame[0, x] = 0
        return frame


class ntashmkaxf(RenderableUserDisplay):
    """."""

    def __init__(self, dojfslwbg: int = 0):
        self._k = dojfslwbg // 90 % 4

    def set_rotation(self, dojfslwbg: int) -> None:
        self._k = dojfslwbg // 90 % 4

    def render_interface(self, frame: np.ndarray) -> np.ndarray:
        if self._k == 0:
            return frame
        return np.rot90(frame, k=self._k).copy()


class _Sx80Rules(ARCBaseGame):
    """."""

    mfkgvxzkbj = {
        1: {
            GameAction.ACTION1: GameAction.ACTION4,
            GameAction.ACTION2: GameAction.ACTION3,
            GameAction.ACTION3: GameAction.ACTION1,
            GameAction.ACTION4: GameAction.ACTION2,
        },
        2: {
            GameAction.ACTION1: GameAction.ACTION2,
            GameAction.ACTION2: GameAction.ACTION1,
            GameAction.ACTION3: GameAction.ACTION4,
            GameAction.ACTION4: GameAction.ACTION3,
        },
        3: {
            GameAction.ACTION1: GameAction.ACTION3,
            GameAction.ACTION2: GameAction.ACTION4,
            GameAction.ACTION3: GameAction.ACTION2,
            GameAction.ACTION4: GameAction.ACTION1,
        },
    }
    othselxnik = {
        1: {
            GameAction.ACTION1: GameAction.ACTION3,
            GameAction.ACTION2: GameAction.ACTION4,
            GameAction.ACTION3: GameAction.ACTION2,
            GameAction.ACTION4: GameAction.ACTION1,
        },
        2: {
            GameAction.ACTION1: GameAction.ACTION2,
            GameAction.ACTION2: GameAction.ACTION1,
            GameAction.ACTION3: GameAction.ACTION4,
            GameAction.ACTION4: GameAction.ACTION3,
        },
        3: {
            GameAction.ACTION1: GameAction.ACTION4,
            GameAction.ACTION2: GameAction.ACTION3,
            GameAction.ACTION3: GameAction.ACTION1,
            GameAction.ACTION4: GameAction.ACTION2,
        },
    }
    dkvpswzsjg: str
    vsoxmtrhqt: Optional[Sprite]
    hmxltcipkc: List[Tuple[Sprite, int, int]]
    xpcxocsmmq: List[Sprite]
    kfdcqkodyy: bool
    lybfalkrdl: bool
    cevwbinfgl: Set[Sprite]
    onoqwewztl: Set[Sprite]
    trhynadhiz: int
    lijmqzmgnw: sklgkadoxw
    avangppqui: bool

    def __init__(self) -> None:
        self.dkvpswzsjg = "change"
        self.vsoxmtrhqt = None
        self.hmxltcipkc = []
        self.xpcxocsmmq = []
        self.kfdcqkodyy = False
        self.lybfalkrdl = False
        self.cevwbinfgl = set()
        self.onoqwewztl = set()
        self.trhynadhiz = 0
        self.lijmqzmgnw = sklgkadoxw(vwbodnowge=0)
        self.avangppqui = False
        self.yqejjfwwh = False
        self.zlhbnhpcq = 0
        self.lyremoheq = 0
        self.fahhoimkk = 0
        self.jinpztikz = ntashmkaxf(0)
        zgzbkvrwm = Camera(
            background=BACKGROUND_COLOR,
            letter_box=PADDING_COLOR,
            interfaces=[self.lijmqzmgnw, self.jinpztikz],
        )
        super().__init__(
            game_id="sp80",
            levels=levels,
            camera=zgzbkvrwm,
            available_actions=[1, 2, 3, 4, 5, 6],
        )

    def on_set_level(self, level: Level) -> None:
        self.dkvpswzsjg = "change"
        self.vsoxmtrhqt = None
        self.hmxltcipkc = []
        self.xpcxocsmmq = []
        self.kfdcqkodyy = False
        self.lybfalkrdl = False
        self.cevwbinfgl = set()
        self.onoqwewztl = set()
        self.avangppqui = False
        self.yqejjfwwh = False
        self.lyremoheq = 0
        for s in level.get_sprites_by_tag("plzwjbfyfli"):
            s.pixels[(s.pixels >= 0) & (s.pixels != 4)] = 8
        for s in level.get_sprites():
            if s.name == "repwkzbkhxl":
                s.pixels[s.pixels >= 0] = 11
        for s in level.get_sprites_by_tag("waoewejnqzc"):
            s.pixels[s.pixels >= 0] = 1
        pfhpxrnpci = level.get_data("steps") or 50
        self.zlhbnhpcq = pfhpxrnpci
        self.lijmqzmgnw.vwbodnowge = pfhpxrnpci
        self.lijmqzmgnw.fymfsbgqso(pfhpxrnpci)
        uhbgnthefe = self.gsvsxaspkc()
        if uhbgnthefe:
            self.mmzrajuxwp(uhbgnthefe)
        dojfslwbg = level.get_data("dojfslwbg") or 0
        self.fahhoimkk = dojfslwbg // 90 % 4
        self.jinpztikz.set_rotation(dojfslwbg)

    def fbrwmvzsym(self) -> List[Sprite]:
        return [s for s in self.current_level.get_sprites_by_tag("plzwjbfyfli")] + [s for s in self.current_level.get_sprites_by_tag("tuvkdkhdokr")]

    def qbsoyazkhk(self) -> List[Sprite]:
        return [s for s in self.current_level.get_sprites_by_tag("liolfvkveqg")]

    def mxdlffpzkc(self) -> List[Sprite]:
        return [s for s in self.current_level.get_sprites_by_tag("repwkzbkhxl")]

    def vgpoqzieha(self) -> List[Sprite]:
        return [s for s in self.current_level.get_sprites_by_tag("waoewejnqzc")]

    def gsvsxaspkc(self) -> Optional[Sprite]:
        bewcnjlccv = self.fbrwmvzsym()
        if not bewcnjlccv:
            return None
        _W = self.current_level.grid_size[0] - 2
        return min(bewcnjlccv, key=lambda vcnqlwquvy: (_W - (vcnqlwquvy.x - 1) - vcnqlwquvy.width) ** 2 + (vcnqlwquvy.y - 1) ** 2)

    def husluhmboo(self, hualjkqrro: Sprite, x: int, y: int) -> bool:
        """."""
        ozlpegmuiw = hualjkqrro.width
        thjmlectxc = hualjkqrro.height
        if y < 4:
            return False
        for ifavaamret in self.mxdlffpzkc():
            rx, ry = (ifavaamret.x, ifavaamret.y)
            fykwwtgsjv = ifavaamret.width
            zgqksrdiou = ifavaamret.height
            if x < rx + fykwwtgsjv + 1 and x + ozlpegmuiw > rx - 1 and (y < ry + zgqksrdiou + 1) and (y + thjmlectxc > ry - 1):
                return False
        return True

    def oioatzlrlu(self, ukutpdlsfq: Sprite, tkwwsinjpi: Sprite) -> bool:
        ax1, ay1, ax2, ay2 = (
            ukutpdlsfq.x,
            ukutpdlsfq.y,
            ukutpdlsfq.x + ukutpdlsfq.width,
            ukutpdlsfq.y + ukutpdlsfq.height,
        )
        bx1, by1, bx2, by2 = (
            tkwwsinjpi.x,
            tkwwsinjpi.y,
            tkwwsinjpi.x + tkwwsinjpi.width,
            tkwwsinjpi.y + tkwwsinjpi.height,
        )
        return ax1 < bx2 and ax2 > bx1 and (ay1 < by2) and (ay2 > by1)

    def mmzrajuxwp(self, hualjkqrro: Sprite) -> None:
        if self.vsoxmtrhqt is not None:
            self.ntuflwihof()
        self.vsoxmtrhqt = hualjkqrro
        if hualjkqrro is not None:
            hualjkqrro.pixels[(hualjkqrro.pixels >= 0) & (hualjkqrro.pixels != 4)] = 9
            hualjkqrro.set_layer(1)
        self.avangppqui = True

    def ntuflwihof(self) -> None:
        if self.vsoxmtrhqt is not None:
            nogozwphuv = 15 if "tuvkdkhdokr" in self.vsoxmtrhqt.tags else 8
            self.vsoxmtrhqt.pixels[(self.vsoxmtrhqt.pixels >= 0) & (self.vsoxmtrhqt.pixels != 4)] = nogozwphuv
            self.vsoxmtrhqt.set_layer(0)
        self.vsoxmtrhqt = None

    def vdwhttyyfq(self) -> None:
        self.dkvpswzsjg = "spill"
        self.ntuflwihof()
        self.hmxltcipkc = [(lpaiwmascx, 0, 1) for lpaiwmascx in self.qbsoyazkhk()]
        self.xpcxocsmmq = []
        self.kfdcqkodyy = False
        self.lybfalkrdl = False
        self.cevwbinfgl = set()
        self.onoqwewztl = set()
        for lwigswghhd in self.current_level.get_sprites_by_tag("sowlljgtjvn"):
            px, py = (lwigswghhd.x, lwigswghhd.y)
            cuftbajfn = lwigswghhd.pixels
            for y in range(cuftbajfn.shape[0]):
                for x in range(cuftbajfn.shape[1]):
                    if int(cuftbajfn[y, x]) == 4:
                        qxatjlxbsr, mdktzafzgr = (px + x, py + y)
                        lxmalbxucn = self.current_level.get_sprite_at(qxatjlxbsr, mdktzafzgr + 1)
                        ingqkycxdt = lxmalbxucn and "liolfvkveqg" in getattr(lxmalbxucn, "tags", [])
                        if not ingqkycxdt and self.current_level.get_sprite_at(qxatjlxbsr, mdktzafzgr + 1) is None:
                            yfwryonwmf = sprites["liolfvkveqg"].clone().set_position(qxatjlxbsr, mdktzafzgr + 1)
                            self.current_level.add_sprite(yfwryonwmf)
                            self.hmxltcipkc.append((yfwryonwmf, 0, 1))
                            self.xpcxocsmmq.append(yfwryonwmf)

    def lpqbikobah(self) -> None:
        for s in self.xpcxocsmmq:
            self.current_level.remove_sprite(s)
        self.xpcxocsmmq = []
        for s in self.mxdlffpzkc():
            s.pixels[s.pixels >= 0] = 11
        for s in self.vgpoqzieha():
            s.pixels[s.pixels >= 0] = 1
        self.cevwbinfgl = set()
        self.onoqwewztl = set()
        self.dkvpswzsjg = "change"
        self.kfdcqkodyy = False
        self.lybfalkrdl = False
        self.hmxltcipkc = []
        self.lyremoheq += 1
        uhbgnthefe = self.gsvsxaspkc()
        if uhbgnthefe:
            self.mmzrajuxwp(uhbgnthefe)

    def step(self) -> None:
        action_id, action_data = self.krehtwyvlu()
        if self.dkvpswzsjg == "change":
            if action_id != GameAction.RESET:
                self.ytqycovhld(1)
            if action_id == GameAction.ACTION6:
                tkqedciqx = action_data.get("x", 0)
                dqkivrvrc = action_data.get("y", 0)
                zvlpmllzzi = self.camera.display_to_grid(tkqedciqx, dqkivrvrc)
                if zvlpmllzzi:
                    qxatjlxbsr, mdktzafzgr = zvlpmllzzi
                    cbfkqeecgo: Optional[Sprite] = None
                    for vcnqlwquvy in self.fbrwmvzsym():
                        if vcnqlwquvy.x <= qxatjlxbsr < vcnqlwquvy.x + vcnqlwquvy.width and vcnqlwquvy.y <= mdktzafzgr < vcnqlwquvy.y + vcnqlwquvy.height:
                            cbfkqeecgo = vcnqlwquvy
                            break
                    if cbfkqeecgo:
                        self.mmzrajuxwp(cbfkqeecgo)
                        self.yqejjfwwh = True
                        self.complete_action()
                        return
            if self.vsoxmtrhqt is not None:
                zmgbkzxvf, wcrkcuoyr = (0, 0)
                if action_id == GameAction.ACTION1:
                    wcrkcuoyr = -1
                elif action_id == GameAction.ACTION2:
                    wcrkcuoyr = 1
                elif action_id == GameAction.ACTION3:
                    zmgbkzxvf = -1
                elif action_id == GameAction.ACTION4:
                    zmgbkzxvf = 1
                if zmgbkzxvf != 0 or wcrkcuoyr != 0:
                    ssgevmwqov = self.vsoxmtrhqt.x + zmgbkzxvf
                    jppwwnrrfn = self.vsoxmtrhqt.y + wcrkcuoyr
                    if self.husluhmboo(self.vsoxmtrhqt, ssgevmwqov, jppwwnrrfn):
                        collisions = self.try_move_sprite(self.vsoxmtrhqt, zmgbkzxvf, wcrkcuoyr)
                        if len(collisions) > 0 and all(["plzwjbfyfli" in c.tags or "tuvkdkhdokr" in c.tags for c in collisions]):
                            self.vsoxmtrhqt.move(zmgbkzxvf, wcrkcuoyr)
                    self.yqejjfwwh = False
                    self.complete_action()
                    self.avangppqui = False
                    return
            if action_id == GameAction.ACTION5:
                if self.lyremoheq >= 4:
                    self.lose()
                    self.complete_action()
                    return
                self.vdwhttyyfq()
                self.avangppqui = False
                self.yqejjfwwh = False
                return
            self.complete_action()
            return
        elif self.dkvpswzsjg == "spill":
            if self.lybfalkrdl:
                nldokazwta = self.mxdlffpzkc()
                zmkiirynyo = all((r in self.cevwbinfgl for r in nldokazwta))
                if self.kfdcqkodyy or not zmkiirynyo:
                    if self.trhynadhiz < 6:
                        for qyutcrxkne in self.onoqwewztl:
                            qyutcrxkne.pixels[qyutcrxkne.pixels >= 0] = 14 if self.trhynadhiz % 2 == 1 else 1
                        if self.trhynadhiz < 5:
                            for ifavaamret in self.mxdlffpzkc():
                                if ifavaamret not in self.cevwbinfgl:
                                    ifavaamret.pixels[ifavaamret.pixels >= 0] = 0 if self.trhynadhiz % 2 == 0 else 11
                        self.trhynadhiz += 1
                    else:
                        self.lpqbikobah()
                        if self.zlhbnhpcq <= 0:
                            self.lose()
                        self.complete_action()
                else:
                    self.complete_action()
                    self.next_level()
                return
            hhrqsxbmic: List[Tuple[Sprite, int, int]] = []
            for lpaiwmascx, zmgbkzxvf, wcrkcuoyr in self.hmxltcipkc:
                zmgbkzxvf = -zmgbkzxvf  # copycat: work in the original's (unmirrored) frame
                tayzpnizn, lxrpmtrmq = (lpaiwmascx.x, lpaiwmascx.y)
                obzjtntha, unvkukvdu = (-1, 1) if wcrkcuoyr != 0 else (0, 0)
                vwwcczstp, kghcadhlp = (-1, 1) if wcrkcuoyr == 0 else (0, 0)
                qkwtogjpyx = [(obzjtntha, vwwcczstp), (unvkukvdu, kghcadhlp)]
                lxmalbxucn = self.current_level.get_sprite_at(tayzpnizn - zmgbkzxvf, lxrpmtrmq + wcrkcuoyr)
                if lxmalbxucn is None:
                    yfwryonwmf = sprites["liolfvkveqg"].clone().set_position(tayzpnizn - zmgbkzxvf, lxrpmtrmq + wcrkcuoyr)
                    self.current_level.add_sprite(yfwryonwmf)
                    hhrqsxbmic.append((yfwryonwmf, -zmgbkzxvf, wcrkcuoyr))
                    self.xpcxocsmmq.append(yfwryonwmf)
                    continue
                if "liolfvkveqg" in lxmalbxucn.tags:
                    hhrqsxbmic.append((lxmalbxucn, -zmgbkzxvf, wcrkcuoyr))
                if "plzwjbfyfli" in lxmalbxucn.tags:
                    for oizjapxnvj, zrgzlvcvcr in qkwtogjpyx:
                        if self.current_level.get_sprite_at(tayzpnizn - oizjapxnvj, lxrpmtrmq + zrgzlvcvcr) is None:
                            yfwryonwmf = sprites["liolfvkveqg"].clone().set_position(tayzpnizn - oizjapxnvj, lxrpmtrmq + zrgzlvcvcr)
                            self.current_level.add_sprite(yfwryonwmf)
                            hhrqsxbmic.append((yfwryonwmf, -zmgbkzxvf, wcrkcuoyr))
                            self.xpcxocsmmq.append(yfwryonwmf)
                    continue
                if "repwkzbkhxl" in lxmalbxucn.tags:
                    owyqnbmyij = self.current_level.get_sprite_at(tayzpnizn - obzjtntha, lxrpmtrmq + vwwcczstp)
                    faksfmaezd = self.current_level.get_sprite_at(tayzpnizn - unvkukvdu, lxrpmtrmq + kghcadhlp)
                    if owyqnbmyij is lxmalbxucn and faksfmaezd is lxmalbxucn:
                        lxmalbxucn.pixels[lxmalbxucn.pixels >= 0] = 13
                        self.cevwbinfgl.add(lxmalbxucn)
                        continue
                    else:
                        for oizjapxnvj, zrgzlvcvcr in qkwtogjpyx:
                            if self.current_level.get_sprite_at(tayzpnizn - oizjapxnvj, lxrpmtrmq + zrgzlvcvcr) is None:
                                yfwryonwmf = sprites["liolfvkveqg"].clone().set_position(tayzpnizn - oizjapxnvj, lxrpmtrmq + zrgzlvcvcr)
                                self.current_level.add_sprite(yfwryonwmf)
                                hhrqsxbmic.append((yfwryonwmf, -zmgbkzxvf, wcrkcuoyr))
                                self.xpcxocsmmq.append(yfwryonwmf)
                        continue
                if "tuvkdkhdokr" in lxmalbxucn.tags:
                    owyqnbmyij = self.current_level.get_sprite_at(tayzpnizn - obzjtntha, lxrpmtrmq + vwwcczstp)
                    faksfmaezd = self.current_level.get_sprite_at(tayzpnizn - unvkukvdu, lxrpmtrmq + kghcadhlp)
                    if owyqnbmyij is lxmalbxucn and faksfmaezd is None:
                        nizmgdznmn = wcrkcuoyr
                        yevagjsmfn = -zmgbkzxvf
                        yfwryonwmf = sprites["liolfvkveqg"].clone().set_position(tayzpnizn - nizmgdznmn, lxrpmtrmq + yevagjsmfn)
                        self.current_level.add_sprite(yfwryonwmf)
                        hhrqsxbmic.append((yfwryonwmf, -nizmgdznmn, yevagjsmfn))
                        self.xpcxocsmmq.append(yfwryonwmf)
                    if faksfmaezd is lxmalbxucn and owyqnbmyij is None:
                        nizmgdznmn = -wcrkcuoyr
                        yevagjsmfn = zmgbkzxvf
                        yfwryonwmf = sprites["liolfvkveqg"].clone().set_position(tayzpnizn - nizmgdznmn, lxrpmtrmq + yevagjsmfn)
                        self.current_level.add_sprite(yfwryonwmf)
                        hhrqsxbmic.append((yfwryonwmf, -nizmgdznmn, yevagjsmfn))
                        self.xpcxocsmmq.append(yfwryonwmf)
                    else:
                        for oizjapxnvj, zrgzlvcvcr in qkwtogjpyx:
                            if self.current_level.get_sprite_at(tayzpnizn - oizjapxnvj, lxrpmtrmq + zrgzlvcvcr) is None:
                                yfwryonwmf = sprites["liolfvkveqg"].clone().set_position(tayzpnizn - oizjapxnvj, lxrpmtrmq + zrgzlvcvcr)
                                self.current_level.add_sprite(yfwryonwmf)
                                hhrqsxbmic.append((yfwryonwmf, -zmgbkzxvf, wcrkcuoyr))
                                self.xpcxocsmmq.append(yfwryonwmf)
                        continue
                if "waoewejnqzc" in lxmalbxucn.tags:
                    lxmalbxucn.pixels[lxmalbxucn.pixels >= 0] = 14
                    self.onoqwewztl.add(lxmalbxucn)
                    self.kfdcqkodyy = True
                    continue
            self.hmxltcipkc = hhrqsxbmic
            if not self.hmxltcipkc:
                self.lybfalkrdl = True
                self.trhynadhiz = 0
            return

    def ojydygjkdb(self, hyutemwrji: int, shkslvxwqs: int) -> Tuple[int, int]:
        """."""
        k = self.fahhoimkk
        if k == 0:
            return (hyutemwrji, shkslvxwqs)
        if k == 1:
            return (63 - shkslvxwqs, hyutemwrji)
        if k == 2:
            return (63 - hyutemwrji, 63 - shkslvxwqs)
        return (shkslvxwqs, 63 - hyutemwrji)

    def rqlmciubuz(self, qxatjlxbsr: int, mdktzafzgr: int) -> Tuple[int, int]:
        """."""
        k = self.fahhoimkk
        if k == 0:
            return (qxatjlxbsr, mdktzafzgr)
        if k == 1:
            return (mdktzafzgr, 63 - qxatjlxbsr)
        if k == 2:
            return (63 - qxatjlxbsr, 63 - mdktzafzgr)
        return (63 - mdktzafzgr, qxatjlxbsr)

    def krehtwyvlu(self) -> Tuple[GameAction, Dict[str, Any]]:
        """."""
        k = self.fahhoimkk
        hwpdaniibf = self.action.id
        data = self.action.data
        if k == 0:
            return (hwpdaniibf, data)
        if hwpdaniibf in self.mfkgvxzkbj.get(k, {}):
            return (self.mfkgvxzkbj[k][hwpdaniibf], data)
        if hwpdaniibf == GameAction.ACTION6:
            hyutemwrji = data.get("x", 0)
            shkslvxwqs = data.get("y", 0)
            qxatjlxbsr, mdktzafzgr = self.ojydygjkdb(hyutemwrji, shkslvxwqs)
            return (hwpdaniibf, {"x": qxatjlxbsr, "y": mdktzafzgr})
        return (hwpdaniibf, data)

    def ytqycovhld(self, uarpgqegqg: int) -> None:
        """."""
        self.zlhbnhpcq = max(0, self.zlhbnhpcq - uarpgqegqg)
        self.lijmqzmgnw.fymfsbgqso(self.zlhbnhpcq)
        if self.zlhbnhpcq <= 0:
            self.lose()
            self.complete_action()
            return


# ── copycat layer ───────────────────────────────────────────────────────────────
# Colour assignment for this copycat: displayed colour = _CC_PALETTE[engine colour].
# Applied to the camera's final 64x64 output only, so the game's own rules (some of which
# read sprite colours) are untouched.
_CC_PALETTE = np.array([14, 2, 4, 5, 3, 12, 9, 1, 15, 6, 11, 13, 0, 7, 8, 10], dtype=np.int8)


class _CcCamera(Camera):
    def render(self, sprites):
        frame = super().render(sprites)
        frame = np.asarray(frame)
        out = frame.copy()
        mask = (frame >= 0) & (frame <= 15)
        out[mask] = _CC_PALETTE[frame[mask].astype(np.int64)]
        return out


class Sx80(_Sx80Rules):
    def __init__(self) -> None:
        super().__init__()
        if type(self._camera) is Camera:
            self._camera.__class__ = _CcCamera
        if not isinstance(self._camera, _CcCamera):
            raise RuntimeError("copycat palette camera not installed")
        self._game_id = 'sx80'

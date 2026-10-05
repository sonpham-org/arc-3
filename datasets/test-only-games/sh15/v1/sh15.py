# HELD-OUT TEST COPY -- TEST ONLY, NEVER TRAIN. su15 is in our team's held-out set; this
# copycat (sh15) exists only to measure play on unseen surface variants of it. Do not feed it,
# its frames or its solution replay into any training, fine-tuning, RL or prompt-example pipeline.
#
# Author: Claude Opus 5.5 (Bubba sub-agent), 04-October-2026, built by tools/gen_sh15.py.
# Copycat of su15 (Sucking Up): same rules, mirrored and reworked fields, decoys, moved step bar, new colours.
# Rule code below: ARC Prize Foundation su15, MIT licence (notice follows), class renamed
# and subclassed; only the patches listed in the builder were made.
#
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

from typing import Any

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
    '0': Sprite(
        pixels=[
        [10],
    ],
        name='0',
        layer=10,
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['0', 'zmlxwcvwb'],
    ),
    '0000ucykrekiwe': Sprite(
        pixels=[
        [-2, -2, 7, -2, -2],
        [-2, 7, -2, 7, -2],
        [7, -2, -2, -2, 7],
        [-2, 7, 7, 7, -2],
    ],
        name='0000ucykrekiwe',
        layer=-1,
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['rgjznrcin'],
    ),
    '1': Sprite(
        pixels=[
        [6, 6],
        [6, 6],
    ],
        name='1',
        layer=9,
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['zmlxwcvwb', '1'],
    ),
    '0001ebagdfaujt': Sprite(
        pixels=[
        [13, -2, 13, -2, 13],
        [-2, 13, -2, 13, -2],
        [13, 13, 13, 13, 13],
        [-2, 13, 13, 13, -2],
    ],
        name='0001ebagdfaujt',
        layer=-1,
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['rgjznrcin'],
    ),
    '2': Sprite(
        pixels=[
        [15, 15, 15],
        [15, 15, 15],
        [15, 15, 15],
    ],
        name='2',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['2', 'zmlxwcvwb'],
    ),
    '0002wjigybqaof': Sprite(
        pixels=[
        [-1, -1, 14, -1, -1],
        [-1, 14, -1, 14, -1],
        [14, -1, 14, -1, 14],
        [-1, 14, -1, 14, -1],
    ],
        name='0002wjigybqaof',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['rgjznrcin'],
    ),
    '3': Sprite(
        pixels=[
        [11, 11, 11, 11],
        [11, 11, 11, 11],
        [11, 11, 11, 11],
        [11, 11, 11, 11],
    ],
        name='3',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['3', 'zmlxwcvwb'],
    ),
    '0003zdfkbzzqvx': Sprite(
        pixels=[
        [-1, -1, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, -1, -1],
        [-1, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, -1],
        [9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9],
        [9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9],
        [9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9],
        [9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9],
        [9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9],
        [-1, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, -1],
        [-1, -1, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, -1, -1],
    ],
        name='0003zdfkbzzqvx',
        layer=-2,
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['xkstxyqbs'],
    ),
    '4': Sprite(
        pixels=[
        [12, 12, 12, 12, 12],
        [12, 12, 12, 12, 12],
        [12, 12, 12, 12, 12],
        [12, 12, 12, 12, 12],
        [12, 12, 12, 12, 12],
    ],
        name='4',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['zmlxwcvwb', '4'],
    ),
    '0004srpvwsidmy': Sprite(
        pixels=[
        [12, 12, 12, 12, 12],
        [12, 12, 12, 12, 12],
        [12, 12, 12, 12, 12],
        [12, 12, 12, 12, 12],
        [12, 12, 12, 12, 12],
    ],
        name='0004srpvwsidmy',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['rgjznrcin'],
    ),
    '5': Sprite(
        pixels=[
        [8, 8, 8, 8, 8, 8, 8],
        [8, 8, 8, 8, 8, 8, 8],
        [8, 8, 8, 8, 8, 8, 8],
        [8, 8, 8, 8, 8, 8, 8],
        [8, 8, 8, 8, 8, 8, 8],
        [8, 8, 8, 8, 8, 8, 8],
        [8, 8, 8, 8, 8, 8, 8],
    ],
        name='5',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['zmlxwcvwb', '5'],
    ),
    '0005aqsukaogvw': Sprite(
        pixels=[
        [1, 1, 1, 1, 1],
        [0, 0, 0, 1, 1],
        [1, 1, 1, 1, 1],
        [0, 0, 0, 1, 1],
        [1, 1, 1, 1, 1],
    ],
        name='0005aqsukaogvw',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
    ),
    '6': Sprite(
        pixels=[
        [9, 9, 9, 9, 9, 9, 9, 9],
        [9, 9, 9, 9, 9, 9, 9, 9],
        [9, 9, 9, 9, 9, 9, 9, 9],
        [9, 9, 9, 9, 9, 9, 9, 9],
        [9, 9, 9, 9, 9, 9, 9, 9],
        [9, 9, 9, 9, 9, 9, 9, 9],
        [9, 9, 9, 9, 9, 9, 9, 9],
        [9, 9, 9, 9, 9, 9, 9, 9],
    ],
        name='6',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['zmlxwcvwb', '6'],
    ),
    '0006japsohcqlw': Sprite(
        pixels=[
        [-1, 10, -1, -1],
        [10, 10, 10, 10],
        [-1, 10, -1, -1],
    ],
        name='0006japsohcqlw',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
    ),
    '7': Sprite(
        pixels=[
        [7, 7, 7, 7, 7, 7, 7, 7, 7],
        [7, 7, 7, 7, 7, 7, 7, 7, 7],
        [7, 7, 7, 7, 7, 7, 7, 7, 7],
        [7, 7, 7, 7, 7, 7, 7, 7, 7],
        [7, 7, 7, 7, 7, 7, 7, 7, 7],
        [7, 7, 7, 7, 7, 7, 7, 7, 7],
        [7, 7, 7, 7, 7, 7, 7, 7, 7],
        [7, 7, 7, 7, 7, 7, 7, 7, 7],
        [7, 7, 7, 7, 7, 7, 7, 7, 7],
    ],
        name='7',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['7', 'zmlxwcvwb'],
    ),
    '0007husrwenosq': Sprite(
        pixels=[
        [1, 1, 0, 1, 1],
        [1, 1, 0, 1, 1],
        [1, 1, 0, 0, 0],
        [1, 1, 1, 1, 1],
        [1, 1, 1, 1, 1],
    ],
        name='0007husrwenosq',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
    ),
    '8': Sprite(
        pixels=[
        [14, 14, 14, 14, 14, 14, 14, 14, 14, 14],
        [14, 14, 14, 14, 14, 14, 14, 14, 14, 14],
        [14, 14, 14, 14, 14, 14, 14, 14, 14, 14],
        [14, 14, 14, 14, 14, 14, 14, 14, 14, 14],
        [14, 14, 14, 14, 14, 14, 14, 14, 14, 14],
        [14, 14, 14, 14, 14, 14, 14, 14, 14, 14],
        [14, 14, 14, 14, 14, 14, 14, 14, 14, 14],
        [14, 14, 14, 14, 14, 14, 14, 14, 14, 14],
        [14, 14, 14, 14, 14, 14, 14, 14, 14, 14],
        [14, 14, 14, 14, 14, 14, 14, 14, 14, 14],
    ],
        name='8',
        layer=2,
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['8', 'zmlxwcvwb'],
    ),
    '0008hngjwqibfi': Sprite(
        pixels=[
        [-1, -1, 9, 9, 9, 9, 9, -1, -1],
        [-1, 9, 9, 9, 9, 9, 9, 9, -1],
        [9, 9, 9, 9, 9, 9, 9, 9, 9],
        [9, 9, 9, 9, 9, 9, 9, 9, 9],
        [9, 9, 9, 9, 9, 9, 9, 9, 9],
        [9, 9, 9, 9, 9, 9, 9, 9, 9],
        [9, 9, 9, 9, 9, 9, 9, 9, 9],
        [-1, 9, 9, 9, 9, 9, 9, 9, -1],
        [-1, -1, 9, 9, 9, 9, 9, -1, -1],
    ],
        name='0008hngjwqibfi',
        layer=-3,
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['xkstxyqbs'],
    ),
    '0009mbvjylwely': Sprite(
        pixels=[
        [4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5],
        [4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5],
        [4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5],
        [4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5],
        [4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4],
        [4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4],
        [4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4],
        [4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4],
        [4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4],
        [4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4],
    ],
        name='0009mbvjylwely',
        layer=-2,
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
    ),
    '0010adfaghocih': Sprite(
        pixels=[
        [6, 6],
        [6, 6],
    ],
        name='0010adfaghocih',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
    ),
    '0011gdcfsxhtwi': Sprite(
        pixels=[
        [14, 7, 9, 8, 12, 11, 15, 6, 10],
    ],
        name='0011gdcfsxhtwi',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
    ),
    '0012qpdeinaukn': Sprite(
        pixels=[
        [8, -1, 12, -1, 11, -1, 15, -1, 6, -1, 10],
    ],
        name='0012qpdeinaukn',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
    ),
    '0013nddbuhpkbi': Sprite(
        pixels=[
        [4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4],
        [4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4],
        [4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4],
        [4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4],
    ],
        name='0013nddbuhpkbi',
        layer=-2,
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
    ),
    '0014mjywekiwam': Sprite(
        pixels=[
        [11, 11, 11, 11],
        [11, 11, 11, 11],
        [11, 11, 11, 11],
        [11, 11, 11, 11],
    ],
        name='0014mjywekiwam',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['rgjznrcin'],
    ),
    '0015zcgpfmnvss': Sprite(
        pixels=[
        [-1, -1, 9, 9, 9, 9, 9, -1, -1],
        [-1, 9, 9, 9, 9, 9, 9, 9, -1],
        [9, 9, 9, 9, 9, 9, 9, 9, 9],
        [9, 9, 9, 9, 9, 9, 9, 9, 9],
        [9, 9, 9, 9, 9, 9, 9, 9, 9],
        [9, 9, 9, 9, 9, 9, 9, 9, 9],
        [9, 9, 9, 9, 9, 9, 9, 9, 9],
        [-1, 9, 9, 9, 9, 9, 9, 9, -1],
        [-1, -1, 9, 9, 9, 9, 9, -1, -1],
    ],
        name='0015zcgpfmnvss',
        layer=-3,
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['xkstxyqbs'],
    ),
    '0016fnrcxwfvtx': Sprite(
        pixels=[
        [15, 15, 15],
        [15, 15, 15],
        [15, 15, 15],
    ],
        name='0016fnrcxwfvtx',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['rgjznrcin'],
    ),
    '0017dcrmyjphec': Sprite(
        pixels=[
        [5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5],
        [5, 13, 13, 5, 5, 14, 14, 5, 5, 7, 7, 5],
        [5, 13, 13, 5, 5, 14, 14, 5, 5, 7, 7, 5],
        [5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5],
    ],
        name='0017dcrmyjphec',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
    ),
    '0018lnncvbueuo': Sprite(
        pixels=[
        [-1, -1, 9, 9, 9, 9, -1, -1],
        [-1, 9, 9, 9, 9, 9, 9, -1],
        [9, 9, 9, 9, 9, 9, 9, 9],
        [9, 9, 9, 9, 9, 9, 9, 9],
        [9, 9, 9, 9, 9, 9, 9, 9],
        [9, 9, 9, 9, 9, 9, 9, 9],
        [-1, 9, 9, 9, 9, 9, 9, -1],
        [-1, -1, 9, 9, 9, 9, -1, -1],
    ],
        name='0018lnncvbueuo',
        layer=-1,
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
    ),
    '0019oikveatxnp': Sprite(
        pixels=[
        [-1, -1, -1, 0, 0, 0, 0, 0, -1, -1, -1],
        [-1, -1, 0, -1, -1, -1, -1, -1, 0, -1, -1],
        [-1, 0, -1, -1, -1, -1, -1, -1, -1, 0, -1],
        [0, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0],
        [0, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0],
        [0, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0],
        [0, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0],
        [0, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0],
        [-1, 0, -1, -1, -1, -1, -1, -1, -1, 0, -1],
        [-1, -1, 0, -1, -1, -1, -1, -1, 0, -1, -1],
        [-1, -1, -1, 0, 0, 0, 0, 0, -1, -1, -1],
    ],
        name='0019oikveatxnp',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['ooutlqdaq'],
    ),
    '0020qkplcbivxi': Sprite(
        pixels=[
        [-2, 0, -2, -2],
        [0, 0, 0, -2],
        [-2, 0, -2, -2],
        [-2, -2, -2, -2],
    ],
        name='0020qkplcbivxi',
        layer=5,
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['ooutlqdaq'],
    ),
    '0021ojxxllwxqr': Sprite(
        pixels=[
        [-1, -1, -1, -1, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, -1, -1, -1, -1],
        [4, 4, 4, 4, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 4, 4, 4, 4],
        [4, 4, 4, 4, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 4, 4, 4, 4],
        [-1, -1, -1, -1, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, -1, -1, -1, -1],
    ],
        name='0021ojxxllwxqr',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
    ),
    '0022xgjoqvpfrf': Sprite(
        pixels=[
        [4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4],
        [4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4],
        [4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4],
        [4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4],
    ],
        name='0022xgjoqvpfrf',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
    ),
    '0023wzvifjzfsl': Sprite(
        pixels=[
        [4, 4, 4, 4, 4, 4, 4, 4],
        [4, 4, 4, 4, 4, 4, 4, 4],
        [4, 4, 4, 4, 4, 4, 4, 4],
        [4, 4, 4, 4, 4, 4, 4, 4],
    ],
        name='0023wzvifjzfsl',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
    ),
    '0024ritdjmiele': Sprite(
        pixels=[
        [4, 4, 4, 4, 4, 4, 4, 4],
        [4, 4, 4, 4, 4, 4, 4, 4],
        [4, 4, 4, 4, 4, 4, 4, 4],
        [4, 4, 4, 4, 4, 4, 4, 4],
    ],
        name='0024ritdjmiele',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
    ),
    '0025foufrvfdur': Sprite(
        pixels=[
        [4, 4, 4, 4, 4, 4, 4, 4],
        [4, 4, 4, 4, 4, 4, 4, 4],
        [4, 4, 4, 4, 4, 4, 4, 4],
        [4, 4, 4, 4, 4, 4, 4, 4],
    ],
        name='0025foufrvfdur',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
    ),
    '0026rogcizlhho': Sprite(
        pixels=[
        [4, 4, 4, 4, 4, 4, 4, 4],
        [4, 4, 4, 4, 4, 4, 4, 4],
        [4, 4, 4, 4, 4, 4, 4, 4],
        [4, 4, 4, 4, 4, 4, 4, 4],
    ],
        name='0026rogcizlhho',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
    ),
    '0027blsxsorecj': Sprite(
        pixels=[
        [3, 3, 3],
        [3, 3, 3],
        [3, 3, 3],
    ],
        name='0027blsxsorecj',
        layer=-1,
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
    ),
    '0028hjlrsjwzqg': Sprite(
        pixels=[
        [3, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
        [-1, -1, 3, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
        [-1, -1, -1, -1, 3, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
        [-1, -1, -1, -1, -1, -1, 3, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
        [-1, -1, -1, -1, -1, -1, -1, -1, 3, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 3, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 3, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 3, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 3, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 3, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 3, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 3, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 3, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 3, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 3, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 3, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 3, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 3, -1, -1, -1, -1, -1, -1, -1, -1],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 3, -1, -1, -1, -1, -1, -1],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 3, -1, -1, -1, -1],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 3, -1, -1],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 3],
    ],
        name='0028hjlrsjwzqg',
        layer=-2,
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
    ),
    '0029obpugmgzgr': Sprite(
        pixels=[
        [0],
    ],
        name='0029obpugmgzgr',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
    ),
    'ybnveypak': Sprite(
        pixels=[
        [-2, -2, 7, -2, -2],
        [-2, 7, -2, 7, -2],
        [7, -2, -2, -2, 7],
        [-2, 7, 7, 7, -2],
    ],
        name='ybnveypak',
        layer=-1,
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['ybnveypak'],
    ),
    'ybnveypak2': Sprite(
        pixels=[
        [-1, -1, 14, -1, -1],
        [-1, 14, -1, 14, -1],
        [14, -1, 14, -1, 14],
        [-1, 14, -1, 14, -1],
    ],
        name='ybnveypak2',
        layer=-1,
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['ybnveypak2'],
    ),
    'ybnveypak3': Sprite(
        pixels=[
        [13, -2, 13, -2, 13],
        [-2, 13, -2, 13, -2],
        [13, 13, 13, 13, 13],
        [-2, 13, 13, 13, -2],
    ],
        name='ybnveypak3',
        layer=-1,
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['ybnveypak3'],
    ),
}
levels = [
    # Level 1
    Level(
        sprites=[
            sprites['2'].clone().set_position(38, 46),
            sprites['0008hngjwqibfi'].clone().set_position(19, 13),
            sprites['0009mbvjylwely'].clone().set_position(0, 0),
            sprites['0016fnrcxwfvtx'].clone().set_position(31, 4),
            sprites['0020qkplcbivxi'].clone().set_position(52, 52),
            sprites['0022xgjoqvpfrf'].clone().set_position(40, 0),
            sprites['0027blsxsorecj'].clone().set_position(14, 14),
            sprites['0028hjlrsjwzqg'].clone().set_position(15, 15),
            sprites['0'].clone().set_position(13, 53),
            sprites['0'].clone().set_position(31, 61),
            sprites['0'].clone().set_position(24, 50),
        ],
        grid_size=(64, 64),
        data={'xkstxyqbs': [2, 1], 'steps': 32},
    ),
    # Level 2
    Level(
        sprites=[
            sprites['0'].clone().set_position(28, 33),
            sprites['0'].clone().set_position(50, 40),
            sprites['0'].clone().set_position(30, 42),
            sprites['0'].clone().set_position(51, 33),
            sprites['0'].clone().set_position(47, 46),
            sprites['0'].clone().set_position(38, 51),
            sprites['0'].clone().set_position(20, 54),
            sprites['0'].clone().set_position(14, 53),
            sprites['0008hngjwqibfi'].clone().set_position(23, 23),
            sprites['0009mbvjylwely'].clone().set_position(0, 0),
            Sprite(
                pixels=[
                [8, -1, 12, -1, 11, -1, 15, -1, 6, -1, 10],
            ],
                name='0012qpdeinaukn',
                x=52,
                y=1,
                scale=2,
                blocking=BlockingMode.PIXEL_PERFECT,
                interaction=InteractionMode.TANGIBLE,
            ),
            sprites['0014mjywekiwam'].clone().set_position(30, 3),
            sprites['0023wzvifjzfsl'].clone().set_position(40, 0),
            sprites['1'].clone().set_position(14, 15),
            sprites['0'].clone().set_position(2, 29),
            sprites['0'].clone().set_position(48, 17),
        ],
        grid_size=(64, 64),
        data={'xkstxyqbs': [3, 1], 'steps': 32},
    ),
    # Level 3
    Level(
        sprites=[
            sprites['0'].clone().set_position(10, 34),
            sprites['0'].clone().set_position(1, 33),
            sprites['0'].clone().set_position(24, 23),
            sprites['0'].clone().set_position(27, 21),
            sprites['0'].clone().set_position(50, 30),
            sprites['0'].clone().set_position(54, 29),
            sprites['1'].clone().set_position(17, 30),
            sprites['1'].clone().set_position(34, 34),
            sprites['1'].clone().set_position(37, 21),
            sprites['0008hngjwqibfi'].clone().set_position(49, 49),
            sprites['0008hngjwqibfi'].clone().set_position(33, 50),
            sprites['0009mbvjylwely'].clone().set_position(0, 0),
            Sprite(
                pixels=[
                [8, -1, 12, -1, 11, -1, 15, -1, 6, -1, 10],
            ],
                name='0012qpdeinaukn',
                x=52,
                y=1,
                scale=2,
                blocking=BlockingMode.PIXEL_PERFECT,
                interaction=InteractionMode.TANGIBLE,
            ),
            sprites['0014mjywekiwam'].clone().set_position(30, 3),
            sprites['0016fnrcxwfvtx'].clone().set_position(25, 4),
            sprites['0024ritdjmiele'].clone().set_position(40, 0),
            sprites['0'].clone().set_position(6, 55),
            sprites['0'].clone().set_position(16, 11),
            sprites['0'].clone().set_position(21, 61),
        ],
        grid_size=(64, 64),
        data={'xkstxyqbs': [[3, 1], [2, 1]], 'steps': 48},
    ),
    # Level 4
    Level(
        sprites=[
            sprites['0'].clone().set_position(56, 34),
            sprites['0'].clone().set_position(55, 26),
            sprites['0'].clone().set_position(32, 27),
            sprites['0'].clone().set_position(31, 32),
            sprites['0'].clone().set_position(30, 43),
            sprites['0'].clone().set_position(30, 45),
            sprites['0'].clone().set_position(52, 40),
            sprites['0'].clone().set_position(42, 43),
            sprites['0008hngjwqibfi'].clone().set_position(51, 47),
            sprites['0009mbvjylwely'].clone().set_position(0, 0),
            Sprite(
                pixels=[
                [8, -1, 12, -1, 11, -1, 15, -1, 6, -1, 10],
            ],
                name='0012qpdeinaukn',
                x=52,
                y=1,
                scale=2,
                blocking=BlockingMode.PIXEL_PERFECT,
                interaction=InteractionMode.TANGIBLE,
            ),
            sprites['0014mjywekiwam'].clone().set_position(30, 3),
            sprites['0025foufrvfdur'].clone().set_position(40, 0),
            sprites['ybnveypak'].clone().set_position(14, 21),
            sprites['1'].clone().set_position(5, 25),
            sprites['0'].clone().set_position(13, 13),
            sprites['0'].clone().set_position(20, 59),
        ],
        grid_size=(64, 64),
        data={'xkstxyqbs': [3, 1], 'steps': 48},
    ),
    # Level 5
    Level(
        sprites=[
            sprites['0'].clone().set_position(13, 61),
            sprites['0'].clone().set_position(7, 48),
            sprites['0'].clone().set_position(54, 62),
            sprites['0'].clone().set_position(56, 44),
            sprites['1'].clone().set_position(43, 22),
            sprites['1'].clone().set_position(11, 22),
            sprites['1'].clone().set_position(47, 25),
            sprites['1'].clone().set_position(13, 27),
            sprites['0008hngjwqibfi'].clone().set_position(23, 12),
            sprites['0009mbvjylwely'].clone().set_position(0, 0),
            Sprite(
                pixels=[
                [8, -1, 12, -1, 11, -1, 15, -1, 6, -1, 10],
            ],
                name='0012qpdeinaukn',
                x=52,
                y=1,
                scale=2,
                blocking=BlockingMode.PIXEL_PERFECT,
                interaction=InteractionMode.TANGIBLE,
            ),
            sprites['0014mjywekiwam'].clone().set_position(30, 3),
            sprites['0026rogcizlhho'].clone().set_position(40, 0),
            sprites['ybnveypak'].clone().set_position(57, 43),
            sprites['ybnveypak'].clone().set_position(27, 48),
            sprites['1'].clone().set_position(25, 56),
            sprites['0'].clone().set_position(48, 42),
            sprites['0'].clone().set_position(37, 55),
        ],
        grid_size=(64, 64),
        data={'xkstxyqbs': [3, 1], 'steps': 32},
    ),
    # Level 6
    Level(
        sprites=[
            sprites['0000ucykrekiwe'].clone().set_position(23, 3),
            sprites['5'].clone().set_position(32, 28),
            sprites['0008hngjwqibfi'].clone().set_position(54, 16),
            sprites['0008hngjwqibfi'].clone().set_position(16, 37),
            sprites['0009mbvjylwely'].clone().set_position(0, 0),
            Sprite(
                pixels=[
                [8, -1, 12, -1, 11, -1, 15, -1, 6, -1, 10],
            ],
                name='0012qpdeinaukn',
                x=52,
                y=1,
                scale=2,
                blocking=BlockingMode.PIXEL_PERFECT,
                interaction=InteractionMode.TANGIBLE,
            ),
            sprites['0014mjywekiwam'].clone().set_position(30, 3),
            sprites['ybnveypak'].clone().set_position(44, 30),
            sprites['1'].clone().set_position(16, 28),
            sprites['0'].clone().set_position(6, 60),
            sprites['1'].clone().set_position(55, 50),
        ],
        grid_size=(64, 64),
        data={'xkstxyqbs': [[3, 1], ['0030xjmmfvfpqm', 1]], 'steps': 32},
    ),
    # Level 7
    Level(
        sprites=[
            sprites['1'].clone().set_position(53, 25),
            sprites['1'].clone().set_position(36, 25),
            sprites['1'].clone().set_position(58, 30),
            sprites['1'].clone().set_position(40, 31),
            sprites['5'].clone().set_position(11, 44),
            sprites['0008hngjwqibfi'].clone().set_position(35, 10),
            sprites['0008hngjwqibfi'].clone().set_position(7, 22),
            sprites['0009mbvjylwely'].clone().set_position(0, 0),
            Sprite(
                pixels=[
                [8, -1, 12, -1, 11, -1, 15, -1, 6, -1, 10],
            ],
                name='0012qpdeinaukn',
                x=52,
                y=1,
                scale=2,
                blocking=BlockingMode.PIXEL_PERFECT,
                interaction=InteractionMode.TANGIBLE,
            ),
            sprites['0014mjywekiwam'].clone().set_position(30, 3),
            sprites['0014mjywekiwam'].clone().set_position(24, 3),
            sprites['ybnveypak'].clone().set_position(46, 52),
            sprites['ybnveypak'].clone().set_position(17, 60),
            sprites['1'].clone().set_position(40, 51),
            sprites['1'].clone().set_position(58, 59),
            sprites['0'].clone().set_position(2, 30),
        ],
        grid_size=(64, 64),
        data={'xkstxyqbs': [3, 2], 'steps': 32},
    ),
    # Level 8
    Level(
        sprites=[
            sprites['0002wjigybqaof'].clone().set_position(15, 3),
            sprites['3'].clone().set_position(52, 53),
            sprites['3'].clone().set_position(58, 49),
            sprites['0004srpvwsidmy'].clone().set_position(29, 2),
            sprites['0004srpvwsidmy'].clone().set_position(22, 2),
            sprites['5'].clone().set_position(40, 19),
            sprites['0008hngjwqibfi'].clone().set_position(3, 23),
            sprites['0008hngjwqibfi'].clone().set_position(50, 14),
            sprites['0008hngjwqibfi'].clone().set_position(14, 44),
            sprites['0008hngjwqibfi'].clone().set_position(52, 52),
            sprites['0009mbvjylwely'].clone().set_position(0, 0),
            Sprite(
                pixels=[
                [8, -1, 12, -1, 11, -1, 15, -1, 6, -1, 10],
            ],
                name='0012qpdeinaukn',
                x=52,
                y=1,
                scale=2,
                blocking=BlockingMode.PIXEL_PERFECT,
                interaction=InteractionMode.TANGIBLE,
            ),
            sprites['0017dcrmyjphec'].clone().set_position(52, 5),
            sprites['ybnveypak'].clone().set_position(11, 34),
            sprites['ybnveypak'].clone().set_position(33, 48),
            sprites['ybnveypak'].clone().set_position(15, 46),
        ],
        grid_size=(64, 64),
        data={'xkstxyqbs': [[4, 2], ['0031xcwudgivus', 1]], 'steps': 48},
    ),
    # Level 9
    Level(
        sprites=[
            sprites['1'].clone().set_position(47, 57),
            sprites['1'].clone().set_position(42, 57),
            sprites['0001ebagdfaujt'].clone().set_position(17, 3),
            sprites['0004srpvwsidmy'].clone().set_position(29, 2),
            sprites['5'].clone().set_position(20, 46),
            sprites['0008hngjwqibfi'].clone().set_position(32, 52),
            sprites['0008hngjwqibfi'].clone().set_position(3, 50),
            sprites['0008hngjwqibfi'].clone().set_position(45, 55),
            sprites['0009mbvjylwely'].clone().set_position(0, 0),
            Sprite(
                pixels=[
                [8, -1, 12, -1, 11, -1, 15, -1, 6, -1, 10],
            ],
                name='0012qpdeinaukn',
                x=52,
                y=1,
                scale=2,
                blocking=BlockingMode.PIXEL_PERFECT,
                interaction=InteractionMode.TANGIBLE,
            ),
            sprites['0016fnrcxwfvtx'].clone().set_position(24, 4),
            sprites['0017dcrmyjphec'].clone().set_position(52, 5),
            sprites['ybnveypak'].clone().set_position(0, 16),
            sprites['ybnveypak'].clone().set_position(46, 12),
            sprites['ybnveypak'].clone().set_position(48, 18),
            sprites['ybnveypak'].clone().set_position(4, 32),
        ],
        grid_size=(64, 64),
        data={'xkstxyqbs': [[4, 1], ['0032qekmtelwqi', 1], [2, 1]], 'steps': 48},
    ),
]


class cqrtilsbtt(RenderableUserDisplay):
    def __init__(self, qhtizyoapk: "_Sh15Rules", ccgddjelir: int):
        self.ccgddjelir = ccgddjelir
        self.current_steps = ccgddjelir
        self.qhtizyoapk = qhtizyoapk
        self.penalty: int = 0

    def eenqiqjzrp(self, toqyobvhxn: int) -> None:
        self.current_steps = max(0, min(toqyobvhxn, self.ccgddjelir))

    def yijsqthvjp(self) -> bool:
        if self.current_steps > 0:
            self.current_steps -= 1
        return self.current_steps > 0

    def fwlvpsqftm(self) -> bool:
        if self.current_steps > 0:
            self.current_steps -= 2 + self.penalty * 2
            self.penalty += 1
        return self.current_steps > 0

    def fzacxrogtf(self) -> None:
        self.current_steps = self.ccgddjelir
        self.penalty = 0

    def render_interface(self, frame: np.ndarray) -> np.ndarray:
        jgomoaufmn: float = self.current_steps / self.ccgddjelir
        # COPYCAT: the step bar is the RIGHT column, filling upward (original: bottom row)
        bqnkerlyqo = int(np.ceil(jgomoaufmn * 64))
        frame[64 - bqnkerlyqo :, 63] = pynrefijae
        return frame


BACKGROUND_COLOR = 5
PADDING_COLOR = 3
zigquexafk: int = -1
pynrefijae: int = 0
krvpnrsbrk: int = 1
orsyjkibvm: int = 2
qonaydbzmh: int = 3
aivrrglqej: int = 4
achiodicac: int = 5
qedddbwazx: int = 6
gmfzfcmzwk: int = 7
yepjhaonen: int = 8
jaigvvwupo: int = 9
ixcfgykcau: int = 10
xepxkjbrxn: int = 11
juhvlkmsnv: int = 12
hsgjxpddyq: int = 13
iwctpsqzhd: int = 14
hnizokhtrr: int = 15
laalrfemee: list[int] = [
    ixcfgykcau,
    qedddbwazx,
    hnizokhtrr,
    xepxkjbrxn,
    juhvlkmsnv,
    yepjhaonen,
    jaigvvwupo,
    gmfzfcmzwk,
    iwctpsqzhd,
]
pqxlzdqwbo: list[str] = ["0", "1", "2", "3", "4", "5", "6", "7", "8"]
hlfobwiewm: str = "zmlxwcvwb"
gtjphwocyu: str = "xkstxyqbs"
wklxqtblde: str = ""
hytiizjifk: str = "0030xjmmfvfpqm"
uzyoevbukk: str = "0031xcwudgivus"
wvbbduitdw: str = "0032qekmtelwqi"
ieyrpvflsf: str = "ybnveypak"
fmrxwztzmt: str = "ybnveypak2"
jzfqlydkvt: str = "ybnveypak3"
hhakphrpzr: int = 8
dfqzqaaojo: int = 4
kenolueiiy: int = 4
zutnqpuurv: int = 16
gvvyzrusqq: int = 10
qsqeqpepjy: int = 63


class _Sh15Rules(ARCBaseGame):
    def __init__(self) -> None:
        self.step_counter_ui = cqrtilsbtt(self, 128)
        camera = Camera(
            background=BACKGROUND_COLOR,
            letter_box=PADDING_COLOR,
            interfaces=[self.step_counter_ui],
        )
        self.ojzsjmpic: int = 64
        self.fchredntr: int = 64
        self.lkujttxgs: list[Sprite] = []
        self.fezhhzhih: list[Sprite] = []
        self.powykypsm: list[Sprite] = []
        self.kcuphgwar: dict[Sprite, str] = {}
        self.kqywaxhmsb: dict[Sprite, int] = {}
        self.yxpvimvli: np.ndarray = np.zeros((0, 2), dtype=np.int64)
        self.oxgxfichu: np.ndarray = np.zeros((0,), dtype=np.int64)
        self.kdalkftcb: tuple[int, int] = (0, 0)
        self.xxkedcuzq: list[Sprite] = []
        self.tmfwtfcyv: list[Sprite] = []
        self.xwrhpebfn: int = 0
        self.gdamdvokm: int = dfqzqaaojo
        self.kacsjmxae: int = hhakphrpzr
        self.ikskfqldi: int = kenolueiiy
        self.sqwdaqczb: bool = False
        self.vdgmwvrhd: dict[Sprite, tuple[float, float]] = {}
        self.lphwskxbh: dict[Sprite, tuple[float, float]] = {}
        self.ksuxajatq: set[Sprite] = set()
        self.tsepktxda: dict[Sprite, int] = {}
        self.wqkwfwgny: dict[Sprite, tuple[float, float]] = {}
        self.xydvujvak: dict[Sprite, tuple[float, float]] = {}
        self.lvpppoehd: dict[Sprite, tuple[float, float]] = {}
        self.rmziewkdi: int = 4
        self.dgpsayght: int = 4
        self.ttwugcsth: float = 10.0
        self.idbgnpolc: set[Sprite] = set()
        self.yghzqxumz: dict[Sprite, int] = {}
        self.ppvvgaayv: dict[Sprite, int] = {}
        self.vmgyqpnfu: Sprite | None = None
        self.vxsrkfddz: float = float(self.kacsjmxae)
        self.kqyosprvc: float = float(self.kacsjmxae)
        self.sdrzkrjcp: np.ndarray | None = None
        self.zdoyfxons: np.ndarray | None = None
        self.cmaswhinr: list[Sprite] = []
        self.pbwlyyjqy: dict[Sprite, np.ndarray] = {}
        self.souzbwugw: int = 0
        self.hirfdeznh: int = zutnqpuurv
        self.vsfwpngmx: bool = False
        self.qygchysnh: str = "none"
        self.dsqlbvwaj: list[Any] | None = None
        self.nscnqkkvg: list[list[tuple[str, int, int, int]]] = []
        super().__init__(game_id="su15", levels=levels, camera=camera, available_actions=[6, 7])

    def izzmxojnvq(self) -> None:
        vapqydocml = self.current_level.get_data("steps")
        if vapqydocml:
            self.step_counter_ui.ccgddjelir = vapqydocml
            self.step_counter_ui.fzacxrogtf()

    def on_set_level(self, level: Level) -> None:
        self.actions: list[ActionInput] = []
        for i in range(16):
            for uwfbekaqks in range(14):
                y = 10 + uwfbekaqks * 4
                self.actions.append(ActionInput(id=GameAction.ACTION6.value, data={"x": i * 4, "y": y}))
        self.izzmxojnvq()
        tgarpfsft = self.current_level.grid_size
        if tgarpfsft is not None:
            self.ojzsjmpic = tgarpfsft[0]
            self.fchredntr = tgarpfsft[1]
        self.dsqlbvwaj = self.current_level.get_data("xkstxyqbs")
        self.qbykqfzrj = self.current_level.get_sprites_by_tag("rgjznrcin")
        self.bicnaxoxq: Sprite | None = None
        bwjkvmuijy = self.current_level.get_sprites_by_tag("ooutlqdaq")
        if self.level_index == 0:
            self.bicnaxoxq = bwjkvmuijy[0]
        self.oicctzexh = False
        self.lkujttxgs = self.current_level.get_sprites_by_tag(hlfobwiewm)
        gztdwgccej: list[Sprite] = self.current_level.get_sprites_by_tag(ieyrpvflsf)
        mvfqadxopc: list[Sprite] = self.current_level.get_sprites_by_tag(fmrxwztzmt)
        ronmgtbgaf: list[Sprite] = self.current_level.get_sprites_by_tag(jzfqlydkvt)
        self.fezhhzhih = []
        self.fezhhzhih.extend(gztdwgccej)
        self.fezhhzhih.extend(mvfqadxopc)
        self.fezhhzhih.extend(ronmgtbgaf)
        self.powykypsm = self.current_level.get_sprites_by_tag(gtjphwocyu)
        self.kcuphgwar = {}
        for anemzlanjq in gztdwgccej:
            self.kcuphgwar[anemzlanjq] = hytiizjifk
        for anemzlanjq in mvfqadxopc:
            self.kcuphgwar[anemzlanjq] = uzyoevbukk
        for anemzlanjq in ronmgtbgaf:
            self.kcuphgwar[anemzlanjq] = wvbbduitdw
        self.kqywaxhmsb.clear()
        for idssvowyh in self.lkujttxgs:
            pkjjooafkc = self.btfgzectsd(idssvowyh)
            self.kqywaxhmsb[idssvowyh] = pkjjooafkc
        self.zmcyxbptrw()
        self.xxkedcuzq = []
        self.tmfwtfcyv = []
        self.vdgmwvrhd = {}
        self.lphwskxbh = {}
        self.kdalkftcb = (0, 0)
        self.xwrhpebfn = 0
        self.vxsrkfddz = float(self.kacsjmxae)
        if self.gdamdvokm > 1:
            self.kqyosprvc = float(self.kacsjmxae) / float(self.gdamdvokm - 1)
        else:
            self.kqyosprvc = float(self.kacsjmxae)
        self.ksuxajatq = set()
        self.tsepktxda = {}
        self.wqkwfwgny = {}
        self.xydvujvak = {}
        self.lvpppoehd = {}
        self.yghzqxumz = {}
        self.ppvvgaayv = {}
        self.idbgnpolc = set()
        self.vmgyqpnfu = sprites["0029obpugmgzgr"].clone()
        self.vmgyqpnfu.pixels = np.full((64, 64), zigquexafk, dtype=np.int64)
        self.current_level.add_sprite(self.vmgyqpnfu)
        vcefodtkwk = self.vmgyqpnfu.pixels
        vqrpxjxvb, kwkzrvive = vcefodtkwk.shape
        gehegqvlkc = np.arange(vqrpxjxvb, dtype=np.float32)
        nmutwuwxtr = np.arange(kwkzrvive, dtype=np.float32)
        self.zdoyfxons, self.sdrzkrjcp = np.meshgrid(gehegqvlkc, nmutwuwxtr, indexing="ij")
        self.jdphqevryx()
        self.cmaswhinr = []
        self.pbwlyyjqy = {}
        self.souzbwugw = 0
        self.vsfwpngmx = False
        self.qygchysnh = "none"
        self.sqwdaqczb = False
        self.gtmjjdjwl = 0
        self.nscnqkkvg = []
        self.hlsimbcfgc()

    def step(self) -> None:
        if self.vsfwpngmx:
            if self.qygchysnh == "pkqcyfpgc":
                wcgdceupc = 0
                for k in self.qbykqfzrj:
                    nmupxyoavc = k.pixels >= 0
                    k.pixels[nmupxyoavc] = pynrefijae
                    wcgdceupc += 1
                for ucjbljdyjj in self.powykypsm:
                    nmupxyoavc = ucjbljdyjj.pixels >= 0
                    ucjbljdyjj.pixels[nmupxyoavc] = pynrefijae
                self.gtmjjdjwl += 1
                if self.gtmjjdjwl > 10:
                    self.next_level()
                    self.complete_action()
                return
            elif self.qygchysnh == "hquxbykfc":
                rztxdwacar = self.pkrdtzfrth()
                if not self.sqwdaqczb and self.xwrhpebfn >= self.gdamdvokm:
                    self.mdetahtgad()
                    self.sqwdaqczb = True
                    if self.qygchysnh == "ivqtcpakv":
                        return
                if self.cbdhpcilgb():
                    self.jdphqevryx()
                    self.vsfwpngmx = True
                    self.qygchysnh = "pkqcyfpgc"
                    return
                if rztxdwacar:
                    return
                self.vsfwpngmx = False
                self.qygchysnh = "none"
                if not self.xspiwkmfbs():
                    self.oicctzexh = True
                    for k in self.qbykqfzrj:
                        nmupxyoavc = k.pixels >= 0
                        k.pixels[nmupxyoavc] = orsyjkibvm
                    for ucjbljdyjj in self.powykypsm:
                        nmupxyoavc = ucjbljdyjj.pixels >= 0
                        ucjbljdyjj.pixels[nmupxyoavc] = orsyjkibvm
                if self.level_index == 0 and (self.lkujttxgs[0]._x != 3 or self.lkujttxgs[0]._y != 58):
                    if self.bicnaxoxq:
                        self.bicnaxoxq._x = 500
                if self.cbdhpcilgb():
                    self.vsfwpngmx = True
                    self.qygchysnh = "pkqcyfpgc"
                    return
                if len(self.current_level.get_sprites_by_tag("zmlxwcvwb")) == 0:
                    self.lose()
                if not self.step_counter_ui.yijsqthvjp():
                    self.lose()
                self.complete_action()
                return
            if self.qygchysnh == "ivqtcpakv":
                if self.eynzbmjgmr():
                    return
                self.qygchysnh = "none"
                self.vsfwpngmx = False
                self.dvqlynnpid()
                if not self.step_counter_ui.fwlvpsqftm():
                    self.lose()
                    self.complete_action()
                    return
                self.vczehveskr()
                self.complete_action()
                return
            self.vsfwpngmx = False
            self.qygchysnh = "none"
            self.complete_action()
            return
        if self.action.id == GameAction.ACTION6:
            ocsjwrogtp = self.action.data.get("x", 0)
            bmstufadsr = self.action.data.get("y", 0)
            wvckcaajnj = self.camera.display_to_grid(ocsjwrogtp, bmstufadsr)
            if wvckcaajnj is not None:
                grid_x, grid_y = wvckcaajnj
                self.hlsimbcfgc()
                if self.level_index == 0:
                    pvfacacejd = self.current_level.get_sprite_at(grid_x, grid_y, "ooutlqdaq")
                    if pvfacacejd is not None:
                        pvfacacejd._x = 500
                self.axaxyjxqoe(grid_x, grid_y)
                if self.vsfwpngmx:
                    return
            self.complete_action()
            return
        if self.action.id == GameAction.ACTION7:
            self.vczehveskr()
            self.complete_action()
            return
        self.complete_action()

    def axaxyjxqoe(self, grid_x: int, grid_y: int) -> None:
        if grid_y <= gvvyzrusqq - 1 or grid_y >= qsqeqpepjy:
            return
        self.zmcyxbptrw()
        gftsvpxuiq = self.kacsjmxae
        self.ksuxajatq = set()
        self.tsepktxda = {}
        self.wqkwfwgny = {}
        self.xydvujvak = {}
        self.lvpppoehd = {}
        self.yghzqxumz = {}
        self.ppvvgaayv = {}
        self.idbgnpolc = set()
        self.xxkedcuzq = []
        for vqfzoppoqx in self.lkujttxgs:
            if self.kcqeohsztd(grid_x, grid_y, gftsvpxuiq, vqfzoppoqx):
                self.xxkedcuzq.append(vqfzoppoqx)
        self.tmfwtfcyv = []
        self.vdgmwvrhd = {}
        self.lphwskxbh = {}
        if self.fezhhzhih:
            for anemzlanjq in self.fezhhzhih:
                if not self.kcqeohsztd(grid_x, grid_y, gftsvpxuiq, anemzlanjq):
                    continue
                self.tmfwtfcyv.append(anemzlanjq)
                rfugedgvat = self.kcuphgwar.get(anemzlanjq, hytiizjifk)
                bxbzzazmbh = self.dfqhmningy(rfugedgvat)
                if bxbzzazmbh == 1:
                    ybnveypak_center_x, ybnveypak_center_y = self.jdeyppambj(anemzlanjq)
                    yyfwojnham = float(grid_x) - float(ybnveypak_center_x)
                    vbjhtiatba = float(grid_y) - float(ybnveypak_center_y)
                    rkgmfvqbjv = yyfwojnham * yyfwojnham + vbjhtiatba * vbjhtiatba
                    if rkgmfvqbjv > 0.0:
                        rnivijjyic = rkgmfvqbjv**0.5
                        cznadydpzu = yyfwojnham / rnivijjyic
                        iikhmkaafd = vbjhtiatba / rnivijjyic
                    else:
                        cznadydpzu = 0.0
                        iikhmkaafd = 0.0
                    self.vdgmwvrhd[anemzlanjq] = (
                        cznadydpzu,
                        iikhmkaafd,
                    )
                    self.lphwskxbh[anemzlanjq] = (
                        float(anemzlanjq.x),
                        float(anemzlanjq.y),
                    )
        self.kdalkftcb = (grid_x, grid_y)
        self.xwrhpebfn = 0
        self.vxsrkfddz = float(self.kacsjmxae)
        if self.gdamdvokm > 1:
            self.kqyosprvc = float(self.kacsjmxae) / float(self.gdamdvokm - 1)
        else:
            self.kqyosprvc = float(self.kacsjmxae)
        self.sqwdaqczb = False
        self.vsfwpngmx = True
        self.qygchysnh = "hquxbykfc"
        self.rgxlnsrafr()

    def rgxlnsrafr(self) -> None:
        if self.vmgyqpnfu is None:
            return
        if self.vmgyqpnfu.pixels is None:
            return
        if self.sdrzkrjcp is None or self.zdoyfxons is None:
            return
        pixels = self.vmgyqpnfu.pixels
        pixels[:, :] = zigquexafk
        gftsvpxuiq = self.vxsrkfddz
        if gftsvpxuiq <= 0.0:
            return
        japluzaoug, umozkwcyky = self.kdalkftcb
        nqdbgihms = self.sdrzkrjcp - float(japluzaoug)
        osrxilboj = self.zdoyfxons - float(umozkwcyky)
        oxnygnotwd = nqdbgihms * nqdbgihms + osrxilboj * osrxilboj
        zzxrzkzznt = gftsvpxuiq + 0.5
        fxsqdowuki = max(0.0, gftsvpxuiq - 0.5)
        nimbwqhcib = zzxrzkzznt * zzxrzkzznt
        ahgqxgjvku = fxsqdowuki * fxsqdowuki
        enmwfircgg = (oxnygnotwd <= nimbwqhcib) & (oxnygnotwd >= ahgqxgjvku)
        pixels[enmwfircgg] = pynrefijae

    def jdphqevryx(self) -> None:
        if self.vmgyqpnfu is None:
            return
        if self.vmgyqpnfu.pixels is None:
            return
        self.vmgyqpnfu.pixels[:, :] = zigquexafk

    def mdetahtgad(self) -> None:
        self.qzquneuehr()
        if self.qygchysnh == "ivqtcpakv":
            return
        if not self.xxkedcuzq:
            return
        self.zmcyxbptrw()
        ovfvfdmrud = len(self.xxkedcuzq)
        if ovfvfdmrud < 2:
            return
        vqqhofowim = [self.kqywaxhmsb.get(sprite, 0) for sprite in self.xxkedcuzq]
        kqmetscwmn = list(range(ovfvfdmrud))

        def gowqbwwsed(index: int) -> int:
            while kqmetscwmn[index] != index:
                kqmetscwmn[index] = kqmetscwmn[kqmetscwmn[index]]
                index = kqmetscwmn[index]
            return index

        def qdyhkwlnyx(krrzhdajaz: int, rgulzzwawh: int) -> None:
            qixjotkvyq = gowqbwwsed(krrzhdajaz)
            fxjjzkgcgl = gowqbwwsed(rgulzzwawh)
            if qixjotkvyq == fxjjzkgcgl:
                return
            kqmetscwmn[fxjjzkgcgl] = qixjotkvyq

        for i in range(ovfvfdmrud):
            hspentbnhg = self.xxkedcuzq[i]
            for uwfbekaqks in range(i + 1, ovfvfdmrud):
                mjiosbwmpx = self.xxkedcuzq[uwfbekaqks]
                if not self.nbfpjkxrnp(hspentbnhg, mjiosbwmpx):
                    continue
                rcfypaeddu = vqqhofowim[i]
                qnvvfsoqxc = vqqhofowim[uwfbekaqks]
                if rcfypaeddu != qnvvfsoqxc:
                    self.awbfxdhccd([hspentbnhg, mjiosbwmpx])
                    return
                qdyhkwlnyx(i, uwfbekaqks)
        ypjyzbmprw: dict[int, list[int]] = {}
        for index in range(ovfvfdmrud):
            kyhdycbnus = gowqbwwsed(index)
            if kyhdycbnus not in ypjyzbmprw:
                ypjyzbmprw[kyhdycbnus] = []
            ypjyzbmprw[kyhdycbnus].append(index)
        zgqoekdave: list[list[Sprite]] = []
        for wwzgpunthz in ypjyzbmprw.values():
            if len(wwzgpunthz) < 2:
                continue
            snzvwlrppz: list[Sprite] = []
            for index in wwzgpunthz:
                snzvwlrppz.append(self.xxkedcuzq[index])
            zgqoekdave.append(snzvwlrppz)
        if not zgqoekdave:
            return
        self.nhtlfoopnx(zgqoekdave)
        self.zmcyxbptrw()

    def qzquneuehr(self) -> None:
        andzintqcy = len(self.fezhhzhih)
        if andzintqcy < 2:
            return
        hhiiqyhjow: list[str] = [self.kcuphgwar.get(anemzlanjq, hytiizjifk) for anemzlanjq in self.fezhhzhih]
        kqmetscwmn = list(range(andzintqcy))

        def gowqbwwsed(index: int) -> int:
            while kqmetscwmn[index] != index:
                kqmetscwmn[index] = kqmetscwmn[kqmetscwmn[index]]
                index = kqmetscwmn[index]
            return index

        def qdyhkwlnyx(krrzhdajaz: int, rgulzzwawh: int) -> None:
            qixjotkvyq = gowqbwwsed(krrzhdajaz)
            fxjjzkgcgl = gowqbwwsed(rgulzzwawh)
            if qixjotkvyq == fxjjzkgcgl:
                return
            kqmetscwmn[fxjjzkgcgl] = qixjotkvyq

        for i in range(andzintqcy):
            kfsbjqyrrw = self.fezhhzhih[i]
            for uwfbekaqks in range(i + 1, andzintqcy):
                cdvujwxdfn = self.fezhhzhih[uwfbekaqks]
                if not self.nbfpjkxrnp(kfsbjqyrrw, cdvujwxdfn):
                    continue
                gfireydfrc = hhiiqyhjow[i]
                rklaapxvoe = hhiiqyhjow[uwfbekaqks]
                if gfireydfrc != rklaapxvoe:
                    self.awbfxdhccd([kfsbjqyrrw, cdvujwxdfn])
                    return
                qdyhkwlnyx(i, uwfbekaqks)
        ypjyzbmprw: dict[int, list[int]] = {}
        for index in range(andzintqcy):
            kyhdycbnus = gowqbwwsed(index)
            if kyhdycbnus not in ypjyzbmprw:
                ypjyzbmprw[kyhdycbnus] = []
            ypjyzbmprw[kyhdycbnus].append(index)
        zgqoekdave: list[list[Sprite]] = []
        for wwzgpunthz in ypjyzbmprw.values():
            if len(wwzgpunthz) < 2:
                continue
            snzvwlrppz: list[Sprite] = []
            for index in wwzgpunthz:
                snzvwlrppz.append(self.fezhhzhih[index])
            zgqoekdave.append(snzvwlrppz)
        if not zgqoekdave:
            return
        self.lgrcinsiro(zgqoekdave)

    def nhtlfoopnx(self, zgqoekdave: list[list[Sprite]]) -> None:
        pbfbrrqdff = len(pqxlzdqwbo) - 1

        def neefixscnn(sprite: Sprite) -> None:
            if sprite in self.ksuxajatq:
                self.ksuxajatq.discard(sprite)
            if sprite in self.tsepktxda:
                del self.tsepktxda[sprite]
            if sprite in self.wqkwfwgny:
                del self.wqkwfwgny[sprite]
            if sprite in self.xydvujvak:
                del self.xydvujvak[sprite]
            if sprite in self.lvpppoehd:
                del self.lvpppoehd[sprite]
            if sprite in self.ppvvgaayv:
                del self.ppvvgaayv[sprite]
            if sprite in self.idbgnpolc:
                self.idbgnpolc.discard(sprite)

        for snzvwlrppz in zgqoekdave:
            if not snzvwlrppz:
                continue
            pkjjooafkc = self.kqywaxhmsb.get(snzvwlrppz[0], 0)
            if pkjjooafkc >= pbfbrrqdff:
                for sprite in snzvwlrppz:
                    neefixscnn(sprite)
                    self.current_level.remove_sprite(sprite)
                    if sprite in self.lkujttxgs:
                        self.lkujttxgs.remove(sprite)
                    if sprite in self.kqywaxhmsb:
                        del self.kqywaxhmsb[sprite]
                    if sprite in self.xxkedcuzq:
                        self.xxkedcuzq.remove(sprite)
                continue
            pljvvgnzca = pkjjooafkc + 1
            lbwxpvpmok = pqxlzdqwbo[pljvvgnzca]
            qivzbymurt = sprites[lbwxpvpmok]
            qzpprflhhj = qivzbymurt.clone()
            jlkbdcssnx = 0
            lhsprshuve = 0
            for sprite in snzvwlrppz:
                japluzaoug, umozkwcyky = self.jdeyppambj(sprite)
                jlkbdcssnx += japluzaoug
                lhsprshuve += umozkwcyky
            japluzaoug = jlkbdcssnx // len(snzvwlrppz)
            umozkwcyky = lhsprshuve // len(snzvwlrppz)
            if qzpprflhhj.pixels is not None:
                sprite_height, sprite_width = qzpprflhhj.pixels.shape
            else:
                sprite_height, sprite_width = (1, 1)
            lswmtgatho = japluzaoug - sprite_width // 2
            fxxzdqxseh = umozkwcyky - sprite_height // 2
            if lswmtgatho < 0:
                lswmtgatho = 0
            max_x = self.ojzsjmpic - sprite_width
            if lswmtgatho > max_x:
                lswmtgatho = max_x
            if fxxzdqxseh < gvvyzrusqq:
                fxxzdqxseh = gvvyzrusqq
            if fxxzdqxseh > qsqeqpepjy:
                fxxzdqxseh = qsqeqpepjy
            max_y = self.fchredntr - sprite_height
            if fxxzdqxseh > max_y:
                fxxzdqxseh = max_y
            qzpprflhhj.set_position(lswmtgatho, fxxzdqxseh)
            self.current_level.add_sprite(qzpprflhhj)
            self.lkujttxgs.append(qzpprflhhj)
            self.kqywaxhmsb[qzpprflhhj] = pljvvgnzca
            for sprite in snzvwlrppz:
                neefixscnn(sprite)
                self.current_level.remove_sprite(sprite)
                if sprite in self.lkujttxgs:
                    self.lkujttxgs.remove(sprite)
                if sprite in self.kqywaxhmsb:
                    del self.kqywaxhmsb[sprite]
                if sprite in self.xxkedcuzq:
                    self.xxkedcuzq.remove(sprite)

    def lgrcinsiro(self, zgqoekdave: list[list[Sprite]]) -> None:
        for snzvwlrppz in zgqoekdave:
            if not snzvwlrppz:
                continue
            qjzanqzagz = snzvwlrppz[0]
            rfugedgvat = self.kcuphgwar.get(qjzanqzagz, hytiizjifk)
            lmxscdggyk = self.caaczjajzu(rfugedgvat)
            if lmxscdggyk is None:
                for anemzlanjq in snzvwlrppz:
                    self.cnbyleshjj(anemzlanjq)
                continue
            trlnaqwkjs = self.rhziiktjfu(lmxscdggyk)
            gnrtfcxhpx = trlnaqwkjs.clone()
            jlkbdcssnx = 0
            lhsprshuve = 0
            for anemzlanjq in snzvwlrppz:
                japluzaoug, umozkwcyky = self.jdeyppambj(anemzlanjq)
                jlkbdcssnx += japluzaoug
                lhsprshuve += umozkwcyky
            japluzaoug = jlkbdcssnx // len(snzvwlrppz)
            umozkwcyky = lhsprshuve // len(snzvwlrppz)
            if gnrtfcxhpx.pixels is not None:
                sprite_height, sprite_width = gnrtfcxhpx.pixels.shape
            else:
                sprite_height, sprite_width = (1, 1)
            lswmtgatho = japluzaoug - sprite_width // 2
            fxxzdqxseh = umozkwcyky - sprite_height // 2
            if lswmtgatho < 0:
                lswmtgatho = 0
            max_x = self.ojzsjmpic - sprite_width
            if lswmtgatho > max_x:
                lswmtgatho = max_x
            if fxxzdqxseh < gvvyzrusqq:
                fxxzdqxseh = gvvyzrusqq
            if fxxzdqxseh > qsqeqpepjy:
                fxxzdqxseh = qsqeqpepjy
            max_y = self.fchredntr - sprite_height
            if fxxzdqxseh > max_y:
                fxxzdqxseh = max_y
            gnrtfcxhpx.set_position(lswmtgatho, fxxzdqxseh)
            self.current_level.add_sprite(gnrtfcxhpx)
            self.fezhhzhih.append(gnrtfcxhpx)
            self.kcuphgwar[gnrtfcxhpx] = lmxscdggyk
            if self.vsfwpngmx and self.qygchysnh == "hquxbykfc":
                self.yghzqxumz[gnrtfcxhpx] = self.gdamdvokm
            for anemzlanjq in snzvwlrppz:
                self.cnbyleshjj(anemzlanjq)

    def awbfxdhccd(self, lnzfiekhpm: list[Sprite]) -> None:
        self.jdphqevryx()
        self.cmaswhinr = []
        self.pbwlyyjqy = {}
        for sprite in lnzfiekhpm:
            if sprite.pixels is None:
                continue
            if sprite in self.pbwlyyjqy:
                continue
            self.cmaswhinr.append(sprite)
            self.pbwlyyjqy[sprite] = sprite.pixels.copy()
        for sprite in self.cmaswhinr:
            pixels = sprite.pixels
            nmupxyoavc = pixels > -1
            pixels[nmupxyoavc] = pynrefijae
        self.souzbwugw = 0
        self.vsfwpngmx = True
        self.qygchysnh = "ivqtcpakv"

    def eynzbmjgmr(self) -> bool:
        if not self.cmaswhinr:
            return False
        yxjjutvbki = self.souzbwugw // 2 % 2 == 0
        for sprite in self.cmaswhinr:
            if sprite.pixels is None:
                continue
            pixels = sprite.pixels
            if sprite not in self.pbwlyyjqy:
                continue
            if yxjjutvbki:
                nmupxyoavc = pixels > -1
                pixels[nmupxyoavc] = pynrefijae
            else:
                bfikaltben = self.pbwlyyjqy[sprite]
                pixels[:, :] = bfikaltben
        self.souzbwugw += 1
        if self.souzbwugw < self.hirfdeznh:
            return True
        return False

    def dvqlynnpid(self) -> None:
        for sprite, bfikaltben in self.pbwlyyjqy.items():
            if sprite.pixels is None:
                continue
            sprite.pixels[:, :] = bfikaltben
        self.cmaswhinr = []
        self.pbwlyyjqy = {}

    def pkrdtzfrth(self) -> bool:
        japluzaoug, umozkwcyky = self.kdalkftcb
        vnhiibmkoy: list[Sprite] = []
        if self.xxkedcuzq:
            vnhiibmkoy.extend(self.xxkedcuzq)
        if self.tmfwtfcyv:
            vnhiibmkoy.extend(self.tmfwtfcyv)
        msskikgokt = self.knkahdczsl()
        for sprite in vnhiibmkoy:
            if sprite in self.ksuxajatq:
                continue
            if sprite in self.fezhhzhih and msskikgokt:
                continue
            ixodhycija = sprite in self.vdgmwvrhd and sprite in self.lphwskxbh
            if ixodhycija:
                cznadydpzu, iikhmkaafd = self.vdgmwvrhd[sprite]
                hsopfzmdrz, fhrepqlzmy = self.lphwskxbh[sprite]
                wprumcasdq = float(self.ikskfqldi * 0.85)
                hsopfzmdrz += cznadydpzu * wprumcasdq
                fhrepqlzmy += iikhmkaafd * wprumcasdq
                lswmtgatho = int(round(hsopfzmdrz))
                fxxzdqxseh = int(round(fhrepqlzmy))
            else:
                sprite_center_x, sprite_center_y = self.jdeyppambj(sprite)
                dx = japluzaoug - sprite_center_x
                dy = umozkwcyky - sprite_center_y
                ifotaevzvy = 0
                lunqhmdjwn = 0
                if dx > 0:
                    ifotaevzvy = min(self.ikskfqldi, dx)
                elif dx < 0:
                    ifotaevzvy = max(-self.ikskfqldi, dx)
                if dy > 0:
                    lunqhmdjwn = min(self.ikskfqldi, dy)
                elif dy < 0:
                    lunqhmdjwn = max(-self.ikskfqldi, dy)
                lswmtgatho = sprite.x + ifotaevzvy
                fxxzdqxseh = sprite.y + lunqhmdjwn
            if sprite.pixels is not None:
                sprite_height, sprite_width = sprite.pixels.shape
            else:
                sprite_height, sprite_width = (1, 1)
            if lswmtgatho < 0:
                lswmtgatho = 0
            max_x = self.ojzsjmpic - sprite_width
            if lswmtgatho > max_x:
                lswmtgatho = max_x
            if fxxzdqxseh < gvvyzrusqq:
                fxxzdqxseh = gvvyzrusqq
            if fxxzdqxseh > qsqeqpepjy:
                fxxzdqxseh = qsqeqpepjy
            max_y = self.fchredntr - sprite_height
            if fxxzdqxseh > max_y:
                fxxzdqxseh = max_y
            if ixodhycija:
                self.lphwskxbh[sprite] = (
                    float(lswmtgatho),
                    float(fxxzdqxseh),
                )
            sprite.set_position(lswmtgatho, fxxzdqxseh)
        self.sgmsqapcxe()
        if self.qygchysnh != "hquxbykfc":
            self.jdphqevryx()
            return True
        self.xwrhpebfn += 1
        self.vxsrkfddz = max(0.0, self.vxsrkfddz - self.kqyosprvc)
        self.rgxlnsrafr()
        if self.xwrhpebfn < self.gdamdvokm:
            return True
        if self.ksuxajatq:
            self.jdphqevryx()
            return True
        self.jdphqevryx()
        return False

    def sgmsqapcxe(self) -> None:
        ygvuhhknqx = self.knkahdczsl()
        if self.ksuxajatq:
            self.luwexfjhwl()
        if self.yghzqxumz:
            wbqkmjcnbs: list[Sprite] = []
            for anemzlanjq, funzeszzzn in self.yghzqxumz.items():
                if funzeszzzn > 0:
                    self.yghzqxumz[anemzlanjq] = funzeszzzn - 1
                if self.yghzqxumz[anemzlanjq] <= 0:
                    wbqkmjcnbs.append(anemzlanjq)
            for anemzlanjq in wbqkmjcnbs:
                del self.yghzqxumz[anemzlanjq]
        if self.xwrhpebfn >= self.gdamdvokm:
            return
        if not self.fezhhzhih:
            return
        if not self.lkujttxgs:
            return
        if ygvuhhknqx:
            return
        nblujelyki = set(self.tmfwtfcyv)
        mdmdopkprx = set(self.yghzqxumz.keys())
        for anemzlanjq in self.fezhhzhih:
            if anemzlanjq in nblujelyki:
                continue
            if anemzlanjq in mdmdopkprx:
                continue
            raurpyopqy = False
            for vqfzoppoqx in self.lkujttxgs:
                if vqfzoppoqx not in self.ksuxajatq:
                    raurpyopqy = True
                    break
            if not raurpyopqy:
                break
            kpyftizzu, cbabrshqb = self.jdeyppambj(anemzlanjq)
            alwfabveaa: Sprite | None = None
            kedldpfgvf: int | None = None
            for vqfzoppoqx in self.lkujttxgs:
                if vqfzoppoqx in self.ksuxajatq:
                    continue
                twvnsfeqq, hambxrjgh = self.jdeyppambj(vqfzoppoqx)
                dx = twvnsfeqq - kpyftizzu
                dy = hambxrjgh - cbabrshqb
                oxnygnotwd = dx * dx + dy * dy
                if kedldpfgvf is None or oxnygnotwd < kedldpfgvf:
                    kedldpfgvf = oxnygnotwd
                    alwfabveaa = vqfzoppoqx
            if alwfabveaa is None:
                continue
            target_center_x, target_center_y = self.jdeyppambj(alwfabveaa)
            rfugedgvat = self.kcuphgwar.get(anemzlanjq, hytiizjifk)
            skbnuhqexk = 2 if rfugedgvat == wvbbduitdw else 1
            wwlsjeavpw = 0
            mzievdmpvu = 0
            if target_center_x > kpyftizzu:
                wwlsjeavpw = skbnuhqexk
            elif target_center_x < kpyftizzu:
                wwlsjeavpw = -skbnuhqexk
            if target_center_y > cbabrshqb:
                mzievdmpvu = skbnuhqexk
            elif target_center_y < cbabrshqb:
                mzievdmpvu = -skbnuhqexk
            lswmtgatho = anemzlanjq.x + wwlsjeavpw
            fxxzdqxseh = anemzlanjq.y + mzievdmpvu
            if anemzlanjq.pixels is not None:
                ybnveypak_height, ybnveypak_width = anemzlanjq.pixels.shape
            else:
                ybnveypak_height, ybnveypak_width = (1, 1)
            if lswmtgatho < 0:
                lswmtgatho = 0
            max_x = self.ojzsjmpic - ybnveypak_width
            if lswmtgatho > max_x:
                lswmtgatho = max_x
            if fxxzdqxseh < gvvyzrusqq:
                fxxzdqxseh = gvvyzrusqq
            if fxxzdqxseh > qsqeqpepjy:
                fxxzdqxseh = qsqeqpepjy
            max_y = self.fchredntr - ybnveypak_height
            if fxxzdqxseh > max_y:
                fxxzdqxseh = max_y
            anemzlanjq.set_position(lswmtgatho, fxxzdqxseh)
        if not self.lkujttxgs:
            return
        for anemzlanjq in self.fezhhzhih:
            if anemzlanjq in mdmdopkprx:
                continue
            if anemzlanjq in nblujelyki:
                continue
            for vqfzoppoqx in self.lkujttxgs:
                if vqfzoppoqx in self.ksuxajatq:
                    continue
                if not self.nbfpjkxrnp(anemzlanjq, vqfzoppoqx):
                    continue
                self.wwvumwkgbn(anemzlanjq, vqfzoppoqx)
        self.zmcyxbptrw()
        self.qzquneuehr()
        if self.qygchysnh == "ivqtcpakv":
            return

    def knkahdczsl(self) -> bool:
        if not self.ksuxajatq:
            return False
        if self.dgpsayght <= 0:
            return False
        for vqfzoppoqx in self.ksuxajatq:
            if vqfzoppoqx in self.idbgnpolc:
                continue
            neqewdesmz = self.tsepktxda.get(vqfzoppoqx, 0)
            if neqewdesmz >= self.rmziewkdi:
                orolhjloqv = self.rmziewkdi + self.dgpsayght
                if neqewdesmz < orolhjloqv:
                    return True
        return False

    def wwvumwkgbn(self, anemzlanjq: Sprite, vqfzoppoqx: Sprite) -> None:
        if vqfzoppoqx not in self.lkujttxgs:
            return
        if vqfzoppoqx in self.ksuxajatq:
            return
        kqywaxhmsb = self.kqywaxhmsb.get(vqfzoppoqx, 0)
        hgdggqongh = kqywaxhmsb <= 0
        if not hgdggqongh:
            tsqyqgiwlh = kqywaxhmsb - 1
            self.ppvvgaayv[vqfzoppoqx] = tsqyqgiwlh
        fruit_center_x, fruit_center_y = self.jdeyppambj(vqfzoppoqx)
        ybnveypak_center_x, ybnveypak_center_y = self.jdeyppambj(anemzlanjq)
        cznadydpzu = float(fruit_center_x - ybnveypak_center_x)
        iikhmkaafd = float(fruit_center_y - ybnveypak_center_y)
        rkgmfvqbjv = cznadydpzu * cznadydpzu + iikhmkaafd * iikhmkaafd
        if rkgmfvqbjv > 0.0:
            rnivijjyic = rkgmfvqbjv**0.5
            cznadydpzu /= rnivijjyic
            iikhmkaafd /= rnivijjyic
        else:
            cznadydpzu = 0.0
            iikhmkaafd = -1.0
        if cznadydpzu == 0.0 and iikhmkaafd == 0.0:
            iikhmkaafd = -1.0
        self.ksuxajatq.add(vqfzoppoqx)
        self.tsepktxda[vqfzoppoqx] = 0
        jhlnuaroik = float(vqfzoppoqx.x)
        tnhddbgxex = float(vqfzoppoqx.y)
        self.wqkwfwgny[vqfzoppoqx] = (jhlnuaroik, tnhddbgxex)
        self.xydvujvak[vqfzoppoqx] = (cznadydpzu, iikhmkaafd)
        self.lvpppoehd[vqfzoppoqx] = (jhlnuaroik, tnhddbgxex)
        if hgdggqongh:
            self.idbgnpolc.add(vqfzoppoqx)
        orolhjloqv = self.rmziewkdi + self.dgpsayght + 1
        self.yghzqxumz[anemzlanjq] = orolhjloqv

    def luwexfjhwl(self) -> None:
        if not self.ksuxajatq:
            return
        oalpjmidgc: list[Sprite] = []
        orolhjloqv = self.rmziewkdi + self.dgpsayght
        for vqfzoppoqx in list(self.ksuxajatq):
            if vqfzoppoqx not in self.tsepktxda:
                oalpjmidgc.append(vqfzoppoqx)
                continue
            neqewdesmz = self.tsepktxda[vqfzoppoqx]
            dqwcyxxvbh = self.wqkwfwgny.get(vqfzoppoqx)
            xuubxrwgkw = self.xydvujvak.get(vqfzoppoqx)
            ilndajskvn = self.lvpppoehd.get(vqfzoppoqx)
            if dqwcyxxvbh is None or xuubxrwgkw is None or ilndajskvn is None:
                oalpjmidgc.append(vqfzoppoqx)
                continue
            dfyvbkepij = orolhjloqv
            if vqfzoppoqx in self.idbgnpolc:
                dfyvbkepij = self.rmziewkdi
            jhlnuaroik, tnhddbgxex = dqwcyxxvbh
            cznadydpzu, iikhmkaafd = xuubxrwgkw
            hsopfzmdrz, fhrepqlzmy = ilndajskvn
            if neqewdesmz < self.rmziewkdi:
                qvmgcmqzjo = neqewdesmz % 4
                qbelyscyqo = 0.0
                if qvmgcmqzjo == 1:
                    qbelyscyqo = -1.0
                elif qvmgcmqzjo == 3:
                    qbelyscyqo = 1.0
                hsopfzmdrz = jhlnuaroik
                fhrepqlzmy = tnhddbgxex + qbelyscyqo
                if self.dgpsayght == 0 and neqewdesmz + 1 == self.rmziewkdi and (vqfzoppoqx in self.ppvvgaayv):
                    tsqyqgiwlh = self.ppvvgaayv[vqfzoppoqx]
                    self.kqywaxhmsb[vqfzoppoqx] = tsqyqgiwlh
                    lbwxpvpmok = pqxlzdqwbo[tsqyqgiwlh]
                    trlnaqwkjs = sprites[lbwxpvpmok]
                    if trlnaqwkjs.pixels is not None:
                        vqfzoppoqx.pixels = trlnaqwkjs.pixels.copy()
                    del self.ppvvgaayv[vqfzoppoqx]
            else:
                if vqfzoppoqx in self.ppvvgaayv:
                    tsqyqgiwlh = self.ppvvgaayv[vqfzoppoqx]
                    self.kqywaxhmsb[vqfzoppoqx] = tsqyqgiwlh
                    lbwxpvpmok = pqxlzdqwbo[tsqyqgiwlh]
                    trlnaqwkjs = sprites[lbwxpvpmok]
                    if trlnaqwkjs.pixels is not None:
                        vqfzoppoqx.pixels = trlnaqwkjs.pixels.copy()
                    del self.ppvvgaayv[vqfzoppoqx]
                if self.dgpsayght > 0:
                    xkotgrqwjl = self.ttwugcsth / float(self.dgpsayght)
                else:
                    xkotgrqwjl = self.ttwugcsth
                hsopfzmdrz += cznadydpzu * xkotgrqwjl
                fhrepqlzmy += iikhmkaafd * xkotgrqwjl
                self.lvpppoehd[vqfzoppoqx] = (hsopfzmdrz, fhrepqlzmy)
            lswmtgatho = int(round(hsopfzmdrz))
            fxxzdqxseh = int(round(fhrepqlzmy))
            if vqfzoppoqx.pixels is not None:
                fruit_height, fruit_width = vqfzoppoqx.pixels.shape
            else:
                fruit_height, fruit_width = (1, 1)
            if lswmtgatho < 0:
                lswmtgatho = 0
            max_x = self.ojzsjmpic - fruit_width
            if lswmtgatho > max_x:
                lswmtgatho = max_x
            if fxxzdqxseh < gvvyzrusqq:
                fxxzdqxseh = gvvyzrusqq
            if fxxzdqxseh > qsqeqpepjy:
                fxxzdqxseh = qsqeqpepjy
            max_y = self.fchredntr - fruit_height
            if fxxzdqxseh > max_y:
                fxxzdqxseh = max_y
            vqfzoppoqx.set_position(lswmtgatho, fxxzdqxseh)
            neqewdesmz += 1
            self.tsepktxda[vqfzoppoqx] = neqewdesmz
            if neqewdesmz >= dfyvbkepij:
                oalpjmidgc.append(vqfzoppoqx)
        if not oalpjmidgc:
            return
        for vqfzoppoqx in oalpjmidgc:
            self.ksuxajatq.discard(vqfzoppoqx)
            if vqfzoppoqx in self.tsepktxda:
                del self.tsepktxda[vqfzoppoqx]
            if vqfzoppoqx in self.wqkwfwgny:
                del self.wqkwfwgny[vqfzoppoqx]
            if vqfzoppoqx in self.xydvujvak:
                del self.xydvujvak[vqfzoppoqx]
            if vqfzoppoqx in self.lvpppoehd:
                del self.lvpppoehd[vqfzoppoqx]
            if vqfzoppoqx in self.ppvvgaayv:
                del self.ppvvgaayv[vqfzoppoqx]
            if vqfzoppoqx in self.idbgnpolc:
                self.idbgnpolc.discard(vqfzoppoqx)
                self.current_level.remove_sprite(vqfzoppoqx)
                if vqfzoppoqx in self.lkujttxgs:
                    self.lkujttxgs.remove(vqfzoppoqx)
                if vqfzoppoqx in self.kqywaxhmsb:
                    del self.kqywaxhmsb[vqfzoppoqx]
                if vqfzoppoqx in self.xxkedcuzq:
                    self.xxkedcuzq.remove(vqfzoppoqx)

    def btfgzectsd(self, sprite: Sprite) -> int:
        for tag in sprite.tags:
            if tag == "zmlxwcvwb":
                continue
            return int(tag)
        return 0

    def zmcyxbptrw(self) -> None:
        xihyciztqg = len(self.lkujttxgs)
        pdopxwnypp = np.zeros((xihyciztqg, 2), dtype=np.int64)
        vqqhofowim = np.zeros((xihyciztqg,), dtype=np.int64)
        for i, sprite in enumerate(self.lkujttxgs):
            japluzaoug, umozkwcyky = self.jdeyppambj(sprite)
            pdopxwnypp[i, 0] = japluzaoug
            pdopxwnypp[i, 1] = umozkwcyky
            vqqhofowim[i] = self.kqywaxhmsb.get(sprite, 0)
        self.yxpvimvli = pdopxwnypp
        self.oxgxfichu = vqqhofowim

    def jdeyppambj(self, sprite: Sprite) -> tuple[int, int]:
        if sprite.pixels is not None:
            sprite_height, sprite_width = sprite.pixels.shape
        else:
            sprite_height, sprite_width = (1, 1)
        japluzaoug = sprite.x + sprite_width // 2
        umozkwcyky = sprite.y + sprite_height // 2
        return (japluzaoug, umozkwcyky)

    def nbfpjkxrnp(self, hspentbnhg: Sprite, mjiosbwmpx: Sprite) -> bool:
        if hspentbnhg.pixels is not None:
            height_a, width_a = hspentbnhg.pixels.shape
        else:
            height_a, width_a = (1, 1)
        if mjiosbwmpx.pixels is not None:
            height_b, width_b = mjiosbwmpx.pixels.shape
        else:
            height_b, width_b = (1, 1)
        haipnqeehx = hspentbnhg.x
        jgdgcdqygw = hspentbnhg.y
        cuquuajdin = hspentbnhg.x + width_a
        bwxlacesto = hspentbnhg.y + height_a
        ieqvaqcwdc = mjiosbwmpx.x
        rzqkstsufc = mjiosbwmpx.y
        nezsmlbyvn = mjiosbwmpx.x + width_b
        edwmywzozq = mjiosbwmpx.y + height_b
        if cuquuajdin <= ieqvaqcwdc:
            return False
        if nezsmlbyvn <= haipnqeehx:
            return False
        if bwxlacesto <= rzqkstsufc:
            return False
        if edwmywzozq <= jgdgcdqygw:
            return False
        return True

    def kcqeohsztd(self, japluzaoug: int, umozkwcyky: int, gftsvpxuiq: int, sprite: Sprite) -> bool:
        if sprite.pixels is not None:
            sprite_height, sprite_width = sprite.pixels.shape
        else:
            sprite_height, sprite_width = (1, 1)
        qxtfiachpk = sprite.x
        harvxppezu = sprite.y
        miktvfoidv = sprite.x + sprite_width
        obxlmjemte = sprite.y + sprite_height
        if japluzaoug < qxtfiachpk:
            wcpnjdkxii = qxtfiachpk
        elif japluzaoug > miktvfoidv - 1:
            wcpnjdkxii = miktvfoidv - 1
        else:
            wcpnjdkxii = japluzaoug
        if umozkwcyky < harvxppezu:
            gvspqqluva = harvxppezu
        elif umozkwcyky > obxlmjemte - 1:
            gvspqqluva = obxlmjemte - 1
        else:
            gvspqqluva = umozkwcyky
        dx = japluzaoug - wcpnjdkxii
        dy = umozkwcyky - gvspqqluva
        return dx * dx + dy * dy <= gftsvpxuiq * gftsvpxuiq

    def dfqhmningy(self, rfugedgvat: str) -> int:
        if rfugedgvat == hytiizjifk:
            return 1
        if rfugedgvat == uzyoevbukk:
            return 2
        if rfugedgvat == wvbbduitdw:
            return 3
        return 1

    def wkwqpjaqpc(self, level: int) -> str:
        if level <= 1:
            return hytiizjifk
        if level == 2:
            return uzyoevbukk
        return wvbbduitdw

    def caaczjajzu(self, rfugedgvat: str) -> str | None:
        if rfugedgvat == hytiizjifk:
            return uzyoevbukk
        if rfugedgvat == uzyoevbukk:
            return wvbbduitdw
        return None

    def rhziiktjfu(self, rfugedgvat: str) -> Sprite:
        if rfugedgvat == hytiizjifk:
            return sprites[ieyrpvflsf]
        if rfugedgvat == uzyoevbukk:
            return sprites[fmrxwztzmt]
        if rfugedgvat == wvbbduitdw:
            return sprites[jzfqlydkvt]
        return sprites[ieyrpvflsf]

    def cnbyleshjj(self, anemzlanjq: Sprite) -> None:
        self.current_level.remove_sprite(anemzlanjq)
        if anemzlanjq in self.fezhhzhih:
            self.fezhhzhih.remove(anemzlanjq)
        if anemzlanjq in self.kcuphgwar:
            del self.kcuphgwar[anemzlanjq]
        if anemzlanjq in self.tmfwtfcyv:
            self.tmfwtfcyv.remove(anemzlanjq)
        if anemzlanjq in self.yghzqxumz:
            del self.yghzqxumz[anemzlanjq]
        if anemzlanjq in self.vdgmwvrhd:
            del self.vdgmwvrhd[anemzlanjq]
        if anemzlanjq in self.lphwskxbh:
            del self.lphwskxbh[anemzlanjq]

    def xuiddmbsef(self) -> bool:
        if not self.powykypsm:
            return False
        if self.dsqlbvwaj is None:
            return False
        jeachvehyd = self.dsqlbvwaj
        nzyywetyls = jeachvehyd[0]
        dojgglksgz: list[tuple[str, int]]
        if isinstance(nzyywetyls, (list, tuple)):
            dojgglksgz = []
            for tcjvlwirsq, wiucezgggs in jeachvehyd:
                dojgglksgz.append((str(tcjvlwirsq), int(wiucezgggs)))
        else:
            tcjvlwirsq = str(jeachvehyd[0])
            wiucezgggs = int(jeachvehyd[1])
            dojgglksgz = [(tcjvlwirsq, wiucezgggs)]
        yuubfwnqiq: dict[int, int] = {}
        ekjzmwqudr: dict[str, int] = {}
        for vqfzoppoqx in self.lkujttxgs:
            midmuqkgtg = False
            for rjgqffkspv in self.powykypsm:
                if self.nbfpjkxrnp(rjgqffkspv, vqfzoppoqx):
                    midmuqkgtg = True
                    break
            if not midmuqkgtg:
                continue
            vhbnknppud = self.kqywaxhmsb.get(vqfzoppoqx, 0)
            if vhbnknppud in yuubfwnqiq:
                yuubfwnqiq[vhbnknppud] += 1
            else:
                yuubfwnqiq[vhbnknppud] = 1
        for anemzlanjq in self.fezhhzhih:
            midmuqkgtg = False
            for rjgqffkspv in self.powykypsm:
                if self.nbfpjkxrnp(rjgqffkspv, anemzlanjq):
                    midmuqkgtg = True
                    break
            if not midmuqkgtg:
                continue
            rfugedgvat = self.kcuphgwar.get(anemzlanjq, hytiizjifk)
            if rfugedgvat in ekjzmwqudr and ekjzmwqudr is not None:
                ekjzmwqudr[rfugedgvat] += 1
            else:
                ekjzmwqudr[rfugedgvat] = 1
        for mfbbiuqkuu, wiucezgggs in dojgglksgz:
            if mfbbiuqkuu in (hytiizjifk, uzyoevbukk, wvbbduitdw):
                if ekjzmwqudr.get(mfbbiuqkuu, 0) != wiucezgggs:
                    return False
            else:
                vhbnknppud = int(mfbbiuqkuu)
                if yuubfwnqiq.get(vhbnknppud, 0) != wiucezgggs:
                    return False
        return True

    def jnieciwfsv(self, x: int, y: int, sprite: Sprite) -> bool:
        if sprite.pixels is not None:
            sprite_height, sprite_width = sprite.pixels.shape
        else:
            sprite_height, sprite_width = (1, 1)
        qxtfiachpk = sprite.x
        harvxppezu = sprite.y
        miktvfoidv = sprite.x + sprite_width
        obxlmjemte = sprite.y + sprite_height
        if x < qxtfiachpk:
            return False
        if x >= miktvfoidv:
            return False
        if y < harvxppezu:
            return False
        if y >= obxlmjemte:
            return False
        return True

    def cbdhpcilgb(self) -> bool:
        if not self.powykypsm:
            return False
        if self.dsqlbvwaj is None:
            return False
        jeachvehyd = self.dsqlbvwaj
        nzyywetyls = jeachvehyd[0]
        dojgglksgz: list[tuple[str, int]]
        if isinstance(nzyywetyls, (list, tuple)):
            dojgglksgz = []
            for tcjvlwirsq, wiucezgggs in jeachvehyd:
                dojgglksgz.append((str(tcjvlwirsq), int(wiucezgggs)))
        else:
            tcjvlwirsq = str(jeachvehyd[0])
            wiucezgggs = int(jeachvehyd[1])
            dojgglksgz = [(tcjvlwirsq, wiucezgggs)]
        yuubfwnqiq: dict[int, int] = {}
        ekjzmwqudr: dict[str, int] = {}
        for vqfzoppoqx in self.lkujttxgs:
            japluzaoug, umozkwcyky = self.jdeyppambj(vqfzoppoqx)
            midmuqkgtg = False
            for rjgqffkspv in self.powykypsm:
                if self.jnieciwfsv(japluzaoug, umozkwcyky, rjgqffkspv):
                    midmuqkgtg = True
                    break
            if not midmuqkgtg:
                continue
            vhbnknppud = self.kqywaxhmsb.get(vqfzoppoqx, 0)
            yuubfwnqiq[vhbnknppud] = yuubfwnqiq.get(vhbnknppud, 0) + 1
        for anemzlanjq in self.fezhhzhih:
            japluzaoug, umozkwcyky = self.jdeyppambj(anemzlanjq)
            midmuqkgtg = False
            for rjgqffkspv in self.powykypsm:
                if self.jnieciwfsv(japluzaoug, umozkwcyky, rjgqffkspv):
                    midmuqkgtg = True
                    break
            if not midmuqkgtg:
                continue
            rfugedgvat = self.kcuphgwar.get(anemzlanjq, hytiizjifk)
            ekjzmwqudr[rfugedgvat] = ekjzmwqudr.get(rfugedgvat, 0) + 1
        for mfbbiuqkuu, wiucezgggs in dojgglksgz:
            if mfbbiuqkuu in (hytiizjifk, uzyoevbukk, wvbbduitdw):
                if ekjzmwqudr.get(mfbbiuqkuu, 0) != wiucezgggs:
                    return False
            else:
                vhbnknppud = int(mfbbiuqkuu)
                if yuubfwnqiq.get(vhbnknppud, 0) != wiucezgggs:
                    return False
        return True

    def hlsimbcfgc(self) -> None:
        sxzjltytzx: list[tuple[str, int, int, int]] = []
        for vqfzoppoqx in self.lkujttxgs:
            pkjjooafkc = self.kqywaxhmsb.get(vqfzoppoqx, 0)
            sxzjltytzx.append(("zmlxwcvwb", int(pkjjooafkc), int(vqfzoppoqx.x), int(vqfzoppoqx.y)))
        for anemzlanjq in self.fezhhzhih:
            evxbijhefm = self.kcuphgwar.get(anemzlanjq, hytiizjifk)
            level = self.dfqhmningy(evxbijhefm)
            sxzjltytzx.append(("ybnveypak", int(level), int(anemzlanjq.x), int(anemzlanjq.y)))
        self.nscnqkkvg.append(sxzjltytzx)

    def vczehveskr(self) -> None:
        self.jdphqevryx()
        if not self.nscnqkkvg:
            return
        jjvntbrkkq = self.nscnqkkvg.pop()
        for vqfzoppoqx in list(self.lkujttxgs):
            self.current_level.remove_sprite(vqfzoppoqx)
        self.lkujttxgs = []
        self.kqywaxhmsb = {}
        for anemzlanjq in list(self.fezhhzhih):
            self.cnbyleshjj(anemzlanjq)
        self.fezhhzhih = []
        self.kcuphgwar = {}
        for eqscvnddnt, vornqmlxku, x, y in jjvntbrkkq:
            if eqscvnddnt == "zmlxwcvwb":
                vhbnknppud = vornqmlxku
                if vhbnknppud < 0:
                    vhbnknppud = 0
                if vhbnknppud >= len(pqxlzdqwbo):
                    vhbnknppud = len(pqxlzdqwbo) - 1
                lbwxpvpmok = pqxlzdqwbo[vhbnknppud]
                trlnaqwkjs = sprites[lbwxpvpmok]
                vqfzoppoqx = trlnaqwkjs.clone()
                vqfzoppoqx.set_position(x, y)
                self.current_level.add_sprite(vqfzoppoqx)
                self.lkujttxgs.append(vqfzoppoqx)
                self.kqywaxhmsb[vqfzoppoqx] = vhbnknppud
            elif eqscvnddnt == "ybnveypak":
                bxbzzazmbh = vornqmlxku
                rfugedgvat = self.wkwqpjaqpc(bxbzzazmbh)
                qjzanqzagz = self.rhziiktjfu(rfugedgvat)
                anemzlanjq = qjzanqzagz.clone()
                anemzlanjq.set_position(x, y)
                self.current_level.add_sprite(anemzlanjq)
                self.fezhhzhih.append(anemzlanjq)
                self.kcuphgwar[anemzlanjq] = rfugedgvat
        self.zmcyxbptrw()
        if self.oicctzexh and self.xspiwkmfbs():
            self.oicctzexh = False
            for k in self.qbykqfzrj:
                k.pixels = sprites[k.name].pixels.copy()
            for ucjbljdyjj in self.powykypsm:
                ucjbljdyjj.pixels = sprites[ucjbljdyjj.name].pixels.copy()

    def jrorxxkwlk(self, vhbnknppud: int) -> int:
        if vhbnknppud < 0:
            vhbnknppud = 0
        return 1 << vhbnknppud

    def xspiwkmfbs(self) -> bool:
        if self.dsqlbvwaj is None:
            return False
        jeachvehyd = self.dsqlbvwaj
        nzyywetyls = jeachvehyd[0]
        zmnaavrezr: list[tuple[int, int]] = []
        if isinstance(nzyywetyls, (list, tuple)):
            for tcjvlwirsq, wiucezgggs in jeachvehyd:
                mfbbiuqkuu = str(tcjvlwirsq)
                if mfbbiuqkuu in (hytiizjifk, uzyoevbukk, wvbbduitdw):
                    continue
                zmnaavrezr.append((int(mfbbiuqkuu), int(wiucezgggs)))
        else:
            tcjvlwirsq = jeachvehyd[0]
            wiucezgggs = jeachvehyd[1]
            mfbbiuqkuu = str(tcjvlwirsq)
            if mfbbiuqkuu not in (hytiizjifk, uzyoevbukk, wvbbduitdw):
                zmnaavrezr.append((int(mfbbiuqkuu), int(wiucezgggs)))
        if not zmnaavrezr:
            return True
        flwpmitbry: int = 0
        for vhbnknppud, abbcbreupi in zmnaavrezr:
            whnxafslns = self.jrorxxkwlk(vhbnknppud)
            flwpmitbry += whnxafslns * abbcbreupi
        wfvpkzeooz: int = 0
        for vqfzoppoqx in self.lkujttxgs:
            vhbnknppud = self.kqywaxhmsb.get(vqfzoppoqx, 0)
            value = self.jrorxxkwlk(vhbnknppud)
            wfvpkzeooz += value
        return wfvpkzeooz >= flwpmitbry


# -- held-out copycat layer (TEST ONLY -- NEVER TRAIN) ---------------------------------------
# Colour assignment: displayed colour = _CC_PALETTE[engine colour], applied to the camera's final
# 64x64 output only, so rules that read sprite colours are untouched. Works for any camera class.
_CC_PALETTE = np.array([12, 15, 2, 0, 13, 1, 14, 11, 6, 7, 5, 8, 10, 9, 4, 3], dtype=np.int8)
_CC_CAMERAS = {}


def _cc_render(self, sprites):
    frame = np.asarray(super(type(self), self).render(sprites))
    out = frame.copy()
    mask = (frame >= 0) & (frame <= 15)
    out[mask] = _CC_PALETTE[frame[mask].astype(np.int64)]
    return out


def _cc_camera_class(base):
    if base not in _CC_CAMERAS:
        _CC_CAMERAS[base] = type("_CcCamera_" + base.__name__, (base,), {"render": _cc_render})
    return _CC_CAMERAS[base]


class Sh15(_Sh15Rules):
    def __init__(self) -> None:
        super().__init__()
        self._camera.__class__ = _cc_camera_class(type(self._camera))
        self._game_id = 'sh15'

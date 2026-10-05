# Copycat ly20: rules of public ARC-AGI-3 game ls20, new maps, colours and art.
# Built and verified by autoresearch-arena arc3games/copycats/cc_ls20.py.
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

import math
from typing import List, Optional, Set, Tuple

import numpy as np
from arcengine import (
    InteractionMode,
    ARCBaseGame,
    BlockingMode,
    Camera,
    GameAction,
    Level,
    RenderableUserDisplay,
    Sprite,
)

"."
sprites = {
    'ajdspzphhd': Sprite(
        pixels=[
        [14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14],
    ],
        name='ajdspzphhd',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.INVISIBLE,
        tags=['xfmluydglp'],
    ),
    'eqatonpohu': Sprite(
        pixels=[
        [5, 5, 5, 5, 5, 5, 5, 5, 5, 5],
        [5, 5, 5, 5, 5, 5, 5, 5, 5, 5],
        [5, 5, 5, 5, 5, 5, 5, 5, 5, 5],
        [5, 5, 5, 5, 5, 5, 5, 5, 5, 5],
        [5, 5, 5, 5, 5, 5, 5, 5, 5, 5],
        [5, 5, 5, 5, 5, 5, 5, 5, 5, 5],
        [5, 5, 5, 5, 5, 5, 5, 5, 5, 5],
        [5, 5, 5, 5, 5, 5, 5, 5, 5, 5],
        [5, 5, 5, 5, 5, 5, 5, 5, 5, 5],
        [5, 5, 5, 5, 5, 5, 5, 5, 5, 5],
    ],
        name='eqatonpohu',
        layer=1,
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['eqatonpohu'],
    ),
    'fesygzfqui': Sprite(
        pixels=[
        [-2, 4, 4, 4, 4],
        [-2, 4, 4, 4, 4],
        [-2, 4, 4, 4, 4],
        [-2, 4, 4, 4, 4],
        [-2, 4, 4, 4, 4],
    ],
        name='fesygzfqui',
        layer=-5,
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['ihdgageizm'],
    ),
    'fywfjzkxlm': Sprite(
        pixels=[
        [0, 0, 0],
        [-1, 0, -1],
        [-1, 0, -1],
    ],
        name='fywfjzkxlm',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
    ),
    'ghizzeqtoh': Sprite(
        pixels=[
        [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        [0, -1, -1, -1, -1, -1, -1, -1, -1, 0],
        [0, -1, -1, -1, -1, -1, -1, -1, -1, 0],
        [0, -1, -1, -1, -1, -1, -1, -1, -1, 0],
        [0, -1, -1, -1, -1, -1, -1, -1, -1, 0],
        [0, -1, -1, -1, -1, -1, -1, -1, -1, 0],
        [0, -1, -1, -1, -1, -1, -1, -1, -1, 0],
        [0, -1, -1, -1, -1, -1, -1, -1, -1, 0],
        [0, -1, -1, -1, -1, -1, -1, -1, -1, 0],
        [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    ],
        name='ghizzeqtoh',
        layer=5,
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.INVISIBLE,
        tags=['ghizzeqtoh'],
    ),
    'gngifvjddu': Sprite(
        pixels=[
        [0, -1, 0],
        [0, 0, -1],
        [-1, 0, 0],
    ],
        name='gngifvjddu',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
    ),
    'grcpfuizfp': Sprite(
        pixels=[
        [0, 0, -1],
        [-1, 0, 0],
        [-1, 0, -1],
    ],
        name='grcpfuizfp',
        layer=1,
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
    ),
    'hahdypcdru': Sprite(
        pixels=[
        [14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14],
    ],
        name='hahdypcdru',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.INVISIBLE,
        tags=['xfmluydglp'],
    ),
    'hoswmpiqkw': Sprite(
        pixels=[
        [0, 0, 0, 0, 0, 0, 0],
        [0, -1, -1, -1, -1, -1, 0],
        [0, -1, -1, -1, -1, -1, 0],
        [0, -1, -1, -1, -1, -1, 0],
        [0, -1, -1, -1, -1, -1, 0],
        [0, -1, -1, -1, -1, -1, 0],
        [0, 0, 0, 0, 0, 0, 0],
    ],
        name='hoswmpiqkw',
        layer=-1,
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.INVISIBLE,
        tags=['hoswmpiqkw'],
    ),
    'ihdgageizm': Sprite(
        pixels=[
        [4, 4, 4, 4, 4],
        [4, 4, 4, 4, 4],
        [4, 4, 4, 4, 4],
        [4, 4, 4, 4, 4],
        [4, 4, 4, 4, 4],
    ],
        name='ihdgageizm',
        layer=-5,
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['ihdgageizm'],
    ),
    'irgjxweouz': Sprite(
        pixels=[
        [14],
        [14],
        [14],
        [14],
        [14],
        [14],
        [14],
        [14],
        [14],
        [14],
        [14],
        [14],
        [14],
        [14],
        [14],
        [14],
        [14],
        [14],
        [14],
        [14],
        [14],
        [14],
        [14],
        [14],
        [14],
        [14],
        [14],
        [14],
        [14],
    ],
        name='irgjxweouz',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.INVISIBLE,
        tags=['xfmluydglp'],
    ),
    'kapcaakvb_b': Sprite(
        pixels=[
        [-2, -2, -2, -2, -2],
        [-2, -2, -2, -2, -2],
        [-2, -2, -2, -2, -2],
        [-2, -2, -2, -2, -2],
        [1, 1, 1, 1, 1],
    ],
        name='kapcaakvb_b',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['gbvqrjtaqo'],
    ),
    'krdypjjivz': Sprite(
        pixels=[
        [4, 4, 4, 4, 4],
        [4, 4, 4, 4, 4],
        [4, 4, 4, 4, 4],
        [4, 4, 4, 4, 4],
        [-2, -2, -2, -2, -2],
    ],
        name='krdypjjivz',
        layer=-5,
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['ihdgageizm'],
    ),
    'kvynsvxbpi': Sprite(
        pixels=[
        [0, -1, -1],
        [-1, 0, -1],
        [-1, -1, 0],
    ],
        name='kvynsvxbpi',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['kvynsvxbpi'],
    ),
    'lujfinsby_t': Sprite(
        pixels=[
        [1, 1, 1, 1, 1],
        [-2, -2, -2, -2, -2],
        [-2, -2, -2, -2, -2],
        [-2, -2, -2, -2, -2],
        [-2, -2, -2, -2, -2],
    ],
        name='lujfinsby_t',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['gbvqrjtaqo'],
    ),
    'mkfbgalsbe': Sprite(
        pixels=[
        [0, 0, 0],
        [0, -1, 0],
        [0, -1, 0],
    ],
        name='mkfbgalsbe',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
    ),
    'mkjdaccuuf': Sprite(
        pixels=[
        [-2, -2, -2, -2, -2],
        [-2, 0, -2, 0, -2],
        [-2, -2, 0, -2, -2],
        [-2, 0, -2, 0, -2],
        [-2, -2, -2, -2, -2],
    ],
        name='mkjdaccuuf',
        layer=-1,
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.INTANGIBLE,
        tags=['ttfwljgohq'],
    ),
    'mxfhnkdzvf': Sprite(
        pixels=[
        [-2, -2, -2, -2, -2],
        [4, 4, 4, 4, 4],
        [4, 4, 4, 4, 4],
        [4, 4, 4, 4, 4],
        [4, 4, 4, 4, 4],
    ],
        name='mxfhnkdzvf',
        layer=-5,
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['ihdgageizm'],
    ),
    'neltxxziap': Sprite(
        pixels=[
        [14],
        [14],
        [14],
        [14],
        [14],
        [14],
        [14],
        [14],
        [14],
        [14],
        [14],
    ],
        name='neltxxziap',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.INVISIBLE,
        tags=['xfmluydglp'],
    ),
    'njpewhmtfd': Sprite(
        pixels=[
        [5, 5, 5, 5, 5, 5, 5],
        [5, -1, -1, -1, -1, -1, 5],
        [5, -1, -1, -1, -1, -1, 5],
        [5, -1, -1, -1, -1, -1, 5],
        [5, -1, -1, -1, -1, -1, 5],
        [5, -1, -1, -1, -1, -1, 5],
        [5, 5, 5, 5, 5, 5, 5],
    ],
        name='njpewhmtfd',
        layer=-3,
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['vjotnebuqo', 'vfkkzdgxzx'],
    ),
    'nnjhdcanjk': Sprite(
        pixels=[
        [-1, 0, -1],
        [0, -1, 0],
        [0, 0, -1],
    ],
        name='nnjhdcanjk',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
    ),
    'npxgalaybz': Sprite(
        pixels=[
        [-1, 11, -1],
        [11, 11, 11],
        [-1, 11, -1],
    ],
        name='npxgalaybz',
        layer=-1,
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.INTANGIBLE,
        tags=['npxgalaybz'],
    ),
    'nszegiawib': Sprite(
        pixels=[
        [3, 3, 3, 3, 3, 3, 3, 3, 3],
        [3, 3, 3, 3, 3, 3, 3, 3, 3],
        [3, 3, 3, 3, 3, 3, 3, 3, 3],
        [3, 3, 3, 3, 3, 3, 3, 3, 3],
        [3, 3, 3, 3, 3, 3, 3, 3, 3],
        [3, 3, 3, 3, 3, 3, 3, 3, 3],
        [3, 3, 3, 3, 3, 3, 3, 3, 3],
        [3, 3, 3, 3, 3, 3, 3, 3, 3],
        [3, 3, -1, -1, -1, -1, -1, 3, 3],
    ],
        name='nszegiawib',
        layer=-4,
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
    ),
    'rhsxkxzdjz': Sprite(
        pixels=[
        [-2, -2, -2, -2, -2],
        [-2, 0, 0, 0, -2],
        [-2, -2, -2, 1, -2],
        [-2, 1, -2, 1, -2],
        [-2, -2, -2, -2, -2],
    ],
        name='rhsxkxzdjz',
        layer=-1,
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['rhsxkxzdjz'],
    ),
    'rjlbuycveu': Sprite(
        pixels=[
        [5, 5, 5, 5, 5],
        [5, 5, 5, 5, 5],
        [5, 5, 5, 5, 5],
        [5, 5, 5, 5, 5],
        [5, 5, 5, 5, 5],
    ],
        name='rjlbuycveu',
        layer=-3,
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.INTANGIBLE,
        tags=['rjlbuycveu'],
    ),
    'sfqyzhzkij': Sprite(
        pixels=[
        [9, 9, 9, 9, 9],
        [9, 12, 12, 12, 9],
        [9, 12, 9, 12, 9],
        [9, 12, 12, 12, 9],
        [9, 9, 9, 9, 9],
    ],
        name='sfqyzhzkij',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['sfqyzhzkij'],
    ),
    'soyhouuebz': Sprite(
        pixels=[
        [-2, -2, -2, -2, -2],
        [-2, 9, 9, 14, -2],
        [-2, 12, -2, 14, -2],
        [-2, 12, 8, 8, -2],
        [-2, -2, -2, -2, -2],
    ],
        name='soyhouuebz',
        layer=-1,
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.INTANGIBLE,
        tags=['soyhouuebz'],
    ),
    'sqpmiygfvh': Sprite(
        pixels=[
        [11],
    ],
        name='sqpmiygfvh',
        layer=3,
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
    ),
    'tihiodtoj_l': Sprite(
        pixels=[
        [1, -2, -2, -2, -2],
        [1, -2, -2, -2, -2],
        [1, -2, -2, -2, -2],
        [1, -2, -2, -2, -2],
        [1, -2, -2, -2, -2],
    ],
        name='tihiodtoj_l',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['gbvqrjtaqo'],
    ),
    'ubspnhafvq': Sprite(
        pixels=[
        [0, -1, 0],
        [0, -1, -1],
        [0, 0, 0],
    ],
        name='ubspnhafvq',
        layer=-2,
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.INTANGIBLE,
    ),
    'ubyunwkbpx': Sprite(
        pixels=[
        [4, 4, 4, 4, -2],
        [4, 4, 4, 4, -2],
        [4, 4, 4, 4, -2],
        [4, 4, 4, 4, -2],
        [4, 4, 4, 4, -2],
    ],
        name='ubyunwkbpx',
        layer=-5,
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['ihdgageizm'],
    ),
    'vjotnebuqo': Sprite(
        pixels=[
        [5, 5, 5, 5, 5, 5, 5],
        [5, -1, -1, -1, -1, -1, 5],
        [5, -1, -1, -1, -1, -1, 5],
        [5, -1, -1, -1, -1, -1, 5],
        [5, -1, -1, -1, -1, -1, 5],
        [5, -1, -1, -1, -1, -1, 5],
        [5, 5, 5, 5, 5, 5, 5],
    ],
        name='vjotnebuqo',
        layer=-3,
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['vjotnebuqo'],
    ),
    'wgmbtyhvbc': Sprite(
        pixels=[
        [0, -1, 0],
        [-1, 0, -1],
        [0, -1, 0],
    ],
        name='wgmbtyhvbc',
        layer=10,
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['wgmbtyhvbc'],
    ),
    'xfmluydglp': Sprite(
        pixels=[
        [14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14],
        [14, -1, -1, -1, -1, -1, -1, -1, -1, -1, 14],
        [14, -1, -1, -1, -1, -1, -1, -1, -1, -1, 14],
        [14, -1, -1, -1, -1, -1, -1, -1, -1, -1, 14],
        [14, -1, -1, -1, -1, -1, -1, -1, -1, -1, 14],
        [14, -1, -1, -1, -1, -1, -1, -1, -1, -1, 14],
        [14, -1, -1, -1, -1, -1, -1, -1, -1, -1, 14],
        [14, -1, -1, -1, -1, -1, -1, -1, -1, -1, 14],
        [14, -1, -1, -1, -1, -1, -1, -1, -1, -1, 14],
        [14, -1, -1, -1, -1, -1, -1, -1, -1, -1, 14],
        [14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14],
    ],
        name='xfmluydglp',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.INVISIBLE,
        tags=['xfmluydglp'],
    ),
    'xvrpzkggig': Sprite(
        pixels=[
        [5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4],
        [5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 4, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 4],
        [5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 4, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 4],
        [5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 4, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 4],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 4, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 4],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 4, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 4],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 4, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 4],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 4, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 4],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 4, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 4],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 4, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 4],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 4, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 4],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 5, 5, 5, 5],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 5, 5, 5, 5],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 5, 5, 5, 5],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 5, 5, 5, 5],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 5, 5, 5, 5],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 5, 5, 5, 5],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 5, 5, 5, 5],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 5, 5, 5, 5],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 5, 5, 5, 5],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 5, 5, 5, 5],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 5, 5, 5, 5],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 5, 5, 5, 5],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 5, 5, 5, 5],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 5, 5, 5, 5],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 5, 5, 5, 5],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 5, 5, 5, 5],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 5, 5, 5, 5],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 5, 5, 5, 5],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 5, 5, 5, 5],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 5, 5, 5, 5],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 5, 5, 5, 5],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 5, 5, 5, 5],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 5, 5, 5, 5],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 5, 5, 5, 5],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 5, 5, 5, 5],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 5, 5, 5, 5],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 5, 5, 5, 5],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 5, 5, 5, 5],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 5, 5, 5, 5],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 5, 5, 5, 5],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 5, 5, 5, 5],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 5, 5, 5, 5],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 5, 5, 5, 5],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 5, 5, 5, 5],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 5, 5, 5, 5],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 5, 5, 5, 5],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 5, 5, 5, 5],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 5, 5, 5, 5],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 5, 5, 5, 5],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 5, 5, 5, 5],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 5, 5, 5, 5],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 5, 5, 5, 5],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 5, 5, 5, 5],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 5, 5, 5, 5],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 5, 5, 5, 5],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 5, 5, 5, 5],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 5, 5, 5, 5],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 5, 5, 5, 5],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 5, 5, 5, 5],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 5, 5, 5, 5],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 5, 5, 5, 5],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 5, 5, 5, 5],
    ],
        name='xvrpzkggig',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
    ),
    'yjgargdic_r': Sprite(
        pixels=[
        [-2, -2, -2, -2, 1],
        [-2, -2, -2, -2, 1],
        [-2, -2, -2, -2, 1],
        [-2, -2, -2, -2, 1],
        [-2, -2, -2, -2, 1],
    ],
        name='yjgargdic_r',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['gbvqrjtaqo'],
    ),
}
levels = [
    # Level 1
    Level(
        sprites=[
            sprites['eqatonpohu'].clone().set_position(53, 1),
            sprites['ghizzeqtoh'].clone().set_position(53, 1),
            sprites['hoswmpiqkw'].clone().set_position(24, 48),
            sprites['ihdgageizm'].clone().set_position(55, 59),
            sprites['ihdgageizm'].clone().set_position(50, 59),
            sprites['ihdgageizm'].clone().set_position(55, 54),
            sprites['ihdgageizm'].clone().set_position(45, 59),
            sprites['ihdgageizm'].clone().set_position(40, 59),
            sprites['ihdgageizm'].clone().set_position(35, 59),
            sprites['ihdgageizm'].clone().set_position(30, 59),
            sprites['ihdgageizm'].clone().set_position(20, 59),
            sprites['ihdgageizm'].clone().set_position(15, 59),
            sprites['ihdgageizm'].clone().set_position(10, 59),
            sprites['ihdgageizm'].clone().set_position(5, 59),
            sprites['ihdgageizm'].clone().set_position(0, 59),
            sprites['ihdgageizm'].clone().set_position(55, 49),
            sprites['ihdgageizm'].clone().set_position(55, 44),
            sprites['ihdgageizm'].clone().set_position(55, 39),
            sprites['ihdgageizm'].clone().set_position(55, 34),
            sprites['ihdgageizm'].clone().set_position(0, 44),
            sprites['ihdgageizm'].clone().set_position(0, 39),
            sprites['ihdgageizm'].clone().set_position(0, 34),
            sprites['ihdgageizm'].clone().set_position(0, 29),
            sprites['ihdgageizm'].clone().set_position(0, 39),
            sprites['ihdgageizm'].clone().set_position(0, 34),
            sprites['ihdgageizm'].clone().set_position(0, 29),
            sprites['ihdgageizm'].clone().set_position(0, 24),
            sprites['ihdgageizm'].clone().set_position(0, 19),
            sprites['ihdgageizm'].clone().set_position(0, 14),
            sprites['ihdgageizm'].clone().set_position(0, 24),
            sprites['ihdgageizm'].clone().set_position(0, 19),
            sprites['ihdgageizm'].clone().set_position(0, 14),
            sprites['ihdgageizm'].clone().set_position(0, 9),
            sprites['ihdgageizm'].clone().set_position(0, 4),
            sprites['ihdgageizm'].clone().set_position(0, 9),
            sprites['ihdgageizm'].clone().set_position(0, 4),
            sprites['ihdgageizm'].clone().set_position(5, 4),
            sprites['ihdgageizm'].clone().set_position(10, 4),
            sprites['ihdgageizm'].clone().set_position(15, 4),
            sprites['ihdgageizm'].clone().set_position(20, 4),
            sprites['ihdgageizm'].clone().set_position(25, 4),
            sprites['ihdgageizm'].clone().set_position(30, 4),
            sprites['ihdgageizm'].clone().set_position(35, 4),
            sprites['ihdgageizm'].clone().set_position(40, 4),
            sprites['ihdgageizm'].clone().set_position(55, 19),
            sprites['ihdgageizm'].clone().set_position(55, 14),
            sprites['ihdgageizm'].clone().set_position(55, 9),
            sprites['ihdgageizm'].clone().set_position(55, 4),
            sprites['ihdgageizm'].clone().set_position(50, 4),
            sprites['ihdgageizm'].clone().set_position(45, 4),
            sprites['ihdgageizm'].clone().set_position(55, 14),
            sprites['ihdgageizm'].clone().set_position(25, 59),
            sprites['ihdgageizm'].clone().set_position(0, 49),
            sprites['ihdgageizm'].clone().set_position(0, 54),
            sprites['ihdgageizm'].clone().set_position(55, 29),
            sprites['ihdgageizm'].clone().set_position(55, 24),
            sprites['kvynsvxbpi'].clone().set_position(26, 50),
            Sprite(
                pixels=[
                [3, 3, 3, 3, 3, 3, 3, 3, 3],
                [3, 3, 3, 3, 3, 3, 3, 3, 3],
                [3, 3, 3, 3, 3, 3, 3, 3, 3],
                [3, 3, 3, 3, 3, 3, 3, 3, 3],
                [3, 3, 3, 3, 3, 3, 3, 3, 3],
                [3, 3, 3, 3, 3, 3, 3, 3, 3],
                [3, 3, 3, 3, 3, 3, 3, 3, 3],
                [3, 3, 3, 3, 3, 3, 3, 3, 3],
                [3, 3, -1, -1, -1, -1, -1, 3, 3],
            ],
                name='nszegiawib',
                x=23,
                y=47,
                layer=-4,
                rotation=180,
                blocking=BlockingMode.PIXEL_PERFECT,
                interaction=InteractionMode.TANGIBLE,
            ),
            sprites['rhsxkxzdjz'].clone().set_position(40, 29),
            sprites['rjlbuycveu'].clone().set_position(25, 49),
            sprites['sfqyzhzkij'].clone().set_position(25, 14),
            sprites['vjotnebuqo'].clone().set_position(24, 48),
            Sprite(
                pixels=[
                [0, -1, 0],
                [-1, 0, -1],
                [0, -1, 0],
            ],
                name='wgmbtyhvbc',
                x=55,
                y=3,
                layer=10,
                scale=2,
                blocking=BlockingMode.PIXEL_PERFECT,
                interaction=InteractionMode.TANGIBLE,
                tags=['wgmbtyhvbc'],
            ),
            sprites['xvrpzkggig'].clone().set_position(0, 0),
            sprites['ihdgageizm'].clone().set_position(5, 9),
            sprites['ihdgageizm'].clone().set_position(5, 14),
            sprites['ihdgageizm'].clone().set_position(5, 19),
            sprites['ihdgageizm'].clone().set_position(5, 24),
            sprites['ihdgageizm'].clone().set_position(5, 29),
            sprites['ihdgageizm'].clone().set_position(5, 34),
            sprites['ihdgageizm'].clone().set_position(5, 39),
            sprites['ihdgageizm'].clone().set_position(5, 44),
            sprites['ihdgageizm'].clone().set_position(5, 49),
            sprites['ihdgageizm'].clone().set_position(5, 54),
            sprites['ihdgageizm'].clone().set_position(10, 9),
            sprites['ihdgageizm'].clone().set_position(10, 14),
            sprites['ihdgageizm'].clone().set_position(10, 19),
            sprites['ihdgageizm'].clone().set_position(10, 24),
            sprites['ihdgageizm'].clone().set_position(10, 29),
            sprites['ihdgageizm'].clone().set_position(10, 34),
            sprites['ihdgageizm'].clone().set_position(10, 39),
            sprites['ihdgageizm'].clone().set_position(10, 44),
            sprites['ihdgageizm'].clone().set_position(10, 49),
            sprites['ihdgageizm'].clone().set_position(10, 54),
            sprites['ihdgageizm'].clone().set_position(15, 9),
            sprites['ihdgageizm'].clone().set_position(15, 14),
            sprites['ihdgageizm'].clone().set_position(15, 19),
            sprites['ihdgageizm'].clone().set_position(15, 24),
            sprites['ihdgageizm'].clone().set_position(15, 29),
            sprites['ihdgageizm'].clone().set_position(15, 34),
            sprites['ihdgageizm'].clone().set_position(15, 39),
            sprites['ihdgageizm'].clone().set_position(15, 44),
            sprites['ihdgageizm'].clone().set_position(15, 49),
            sprites['ihdgageizm'].clone().set_position(15, 54),
            sprites['ihdgageizm'].clone().set_position(20, 9),
            sprites['ihdgageizm'].clone().set_position(20, 19),
            sprites['ihdgageizm'].clone().set_position(20, 29),
            sprites['ihdgageizm'].clone().set_position(20, 34),
            sprites['ihdgageizm'].clone().set_position(20, 39),
            sprites['ihdgageizm'].clone().set_position(20, 44),
            sprites['ihdgageizm'].clone().set_position(20, 49),
            sprites['ihdgageizm'].clone().set_position(20, 54),
            sprites['ihdgageizm'].clone().set_position(25, 9),
            sprites['ihdgageizm'].clone().set_position(25, 54),
            sprites['ihdgageizm'].clone().set_position(30, 19),
            sprites['ihdgageizm'].clone().set_position(30, 29),
            sprites['ihdgageizm'].clone().set_position(30, 39),
            sprites['ihdgageizm'].clone().set_position(30, 44),
            sprites['ihdgageizm'].clone().set_position(30, 49),
            sprites['ihdgageizm'].clone().set_position(30, 54),
            sprites['ihdgageizm'].clone().set_position(35, 9),
            sprites['ihdgageizm'].clone().set_position(35, 19),
            sprites['ihdgageizm'].clone().set_position(35, 29),
            sprites['ihdgageizm'].clone().set_position(40, 39),
            sprites['ihdgageizm'].clone().set_position(40, 44),
            sprites['ihdgageizm'].clone().set_position(40, 49),
            sprites['ihdgageizm'].clone().set_position(40, 54),
            sprites['ihdgageizm'].clone().set_position(45, 9),
            sprites['ihdgageizm'].clone().set_position(45, 19),
            sprites['ihdgageizm'].clone().set_position(45, 24),
            sprites['ihdgageizm'].clone().set_position(45, 29),
            sprites['ihdgageizm'].clone().set_position(45, 34),
            sprites['ihdgageizm'].clone().set_position(45, 39),
            sprites['ihdgageizm'].clone().set_position(45, 44),
            sprites['ihdgageizm'].clone().set_position(45, 49),
            sprites['ihdgageizm'].clone().set_position(45, 54),
            sprites['ihdgageizm'].clone().set_position(50, 9),
            sprites['ihdgageizm'].clone().set_position(50, 19),
            sprites['ihdgageizm'].clone().set_position(50, 24),
            sprites['ihdgageizm'].clone().set_position(50, 29),
            sprites['ihdgageizm'].clone().set_position(50, 34),
            sprites['ihdgageizm'].clone().set_position(50, 39),
            sprites['ihdgageizm'].clone().set_position(50, 44),
            sprites['ihdgageizm'].clone().set_position(50, 49),
            sprites['ihdgageizm'].clone().set_position(50, 54),
        ],
        grid_size=(64, 64),
        data={'StepCounter': 42, 'kvynsvxbpi': 5, 'GoalColor': 9, 'GoalRotation': 0, 'StartShape': 5, 'StartColor': 9, 'StartRotation': 270, 'Fog': False, 'StepsDecrement': 1},
    ),
    # Level 2
    Level(
        sprites=[
            sprites['eqatonpohu'].clone().set_position(53, 1),
            sprites['ghizzeqtoh'].clone().set_position(53, 1),
            sprites['hoswmpiqkw'].clone().set_position(44, 18),
            sprites['ihdgageizm'].clone().set_position(55, 59),
            sprites['ihdgageizm'].clone().set_position(50, 59),
            sprites['ihdgageizm'].clone().set_position(55, 54),
            sprites['ihdgageizm'].clone().set_position(45, 59),
            sprites['ihdgageizm'].clone().set_position(40, 59),
            sprites['ihdgageizm'].clone().set_position(35, 59),
            sprites['ihdgageizm'].clone().set_position(30, 59),
            sprites['ihdgageizm'].clone().set_position(20, 59),
            sprites['ihdgageizm'].clone().set_position(15, 59),
            sprites['ihdgageizm'].clone().set_position(10, 59),
            sprites['ihdgageizm'].clone().set_position(5, 59),
            sprites['ihdgageizm'].clone().set_position(0, 59),
            sprites['ihdgageizm'].clone().set_position(55, 49),
            sprites['ihdgageizm'].clone().set_position(55, 44),
            sprites['ihdgageizm'].clone().set_position(55, 39),
            sprites['ihdgageizm'].clone().set_position(55, 34),
            sprites['ihdgageizm'].clone().set_position(55, 29),
            sprites['ihdgageizm'].clone().set_position(55, 24),
            sprites['ihdgageizm'].clone().set_position(0, 44),
            sprites['ihdgageizm'].clone().set_position(0, 39),
            sprites['ihdgageizm'].clone().set_position(0, 34),
            sprites['ihdgageizm'].clone().set_position(0, 29),
            sprites['ihdgageizm'].clone().set_position(0, 39),
            sprites['ihdgageizm'].clone().set_position(0, 34),
            sprites['ihdgageizm'].clone().set_position(0, 29),
            sprites['ihdgageizm'].clone().set_position(0, 24),
            sprites['ihdgageizm'].clone().set_position(0, 19),
            sprites['ihdgageizm'].clone().set_position(0, 14),
            sprites['ihdgageizm'].clone().set_position(0, 24),
            sprites['ihdgageizm'].clone().set_position(0, 19),
            sprites['ihdgageizm'].clone().set_position(0, 14),
            sprites['ihdgageizm'].clone().set_position(0, 9),
            sprites['ihdgageizm'].clone().set_position(0, 4),
            sprites['ihdgageizm'].clone().set_position(0, 9),
            sprites['ihdgageizm'].clone().set_position(0, 4),
            sprites['ihdgageizm'].clone().set_position(5, 4),
            sprites['ihdgageizm'].clone().set_position(10, 4),
            sprites['ihdgageizm'].clone().set_position(15, 4),
            sprites['ihdgageizm'].clone().set_position(20, 4),
            sprites['ihdgageizm'].clone().set_position(25, 4),
            sprites['ihdgageizm'].clone().set_position(30, 4),
            sprites['ihdgageizm'].clone().set_position(35, 4),
            sprites['ihdgageizm'].clone().set_position(40, 4),
            sprites['ihdgageizm'].clone().set_position(55, 19),
            sprites['ihdgageizm'].clone().set_position(55, 14),
            sprites['ihdgageizm'].clone().set_position(55, 9),
            sprites['ihdgageizm'].clone().set_position(55, 4),
            sprites['ihdgageizm'].clone().set_position(50, 4),
            sprites['ihdgageizm'].clone().set_position(45, 4),
            sprites['ihdgageizm'].clone().set_position(55, 14),
            sprites['ihdgageizm'].clone().set_position(25, 59),
            sprites['ihdgageizm'].clone().set_position(0, 49),
            sprites['ihdgageizm'].clone().set_position(0, 54),
            sprites['ihdgageizm'].clone().set_position(5, 25),
            sprites['kvynsvxbpi'].clone().set_position(46, 20),
            sprites['npxgalaybz'].clone().set_position(46, 45),
            sprites['npxgalaybz'].clone().set_position(21, 10),
            sprites['nszegiawib'].clone().set_position(43, 17),
            sprites['rhsxkxzdjz'].clone().set_position(10, 14),
            sprites['rjlbuycveu'].clone().set_position(45, 19),
            sprites['sfqyzhzkij'].clone().set_position(30, 19),
            sprites['vjotnebuqo'].clone().set_position(44, 18),
            Sprite(
                pixels=[
                [0, -1, 0],
                [-1, 0, -1],
                [0, -1, 0],
            ],
                name='wgmbtyhvbc',
                x=55,
                y=3,
                layer=10,
                scale=2,
                blocking=BlockingMode.PIXEL_PERFECT,
                interaction=InteractionMode.TANGIBLE,
                tags=['wgmbtyhvbc'],
            ),
            sprites['xvrpzkggig'].clone().set_position(0, 0),
            sprites['ihdgageizm'].clone().set_position(5, 14),
            sprites['ihdgageizm'].clone().set_position(5, 19),
            sprites['ihdgageizm'].clone().set_position(5, 24),
            sprites['ihdgageizm'].clone().set_position(5, 29),
            sprites['ihdgageizm'].clone().set_position(5, 39),
            sprites['ihdgageizm'].clone().set_position(5, 44),
            sprites['ihdgageizm'].clone().set_position(5, 49),
            sprites['ihdgageizm'].clone().set_position(5, 54),
            sprites['ihdgageizm'].clone().set_position(10, 54),
            sprites['ihdgageizm'].clone().set_position(15, 19),
            sprites['ihdgageizm'].clone().set_position(15, 29),
            sprites['ihdgageizm'].clone().set_position(15, 34),
            sprites['ihdgageizm'].clone().set_position(15, 44),
            sprites['ihdgageizm'].clone().set_position(15, 54),
            sprites['ihdgageizm'].clone().set_position(20, 14),
            sprites['ihdgageizm'].clone().set_position(20, 19),
            sprites['ihdgageizm'].clone().set_position(20, 29),
            sprites['ihdgageizm'].clone().set_position(20, 34),
            sprites['ihdgageizm'].clone().set_position(20, 44),
            sprites['ihdgageizm'].clone().set_position(20, 54),
            sprites['ihdgageizm'].clone().set_position(25, 9),
            sprites['ihdgageizm'].clone().set_position(25, 14),
            sprites['ihdgageizm'].clone().set_position(25, 54),
            sprites['ihdgageizm'].clone().set_position(30, 9),
            sprites['ihdgageizm'].clone().set_position(30, 14),
            sprites['ihdgageizm'].clone().set_position(30, 24),
            sprites['ihdgageizm'].clone().set_position(30, 29),
            sprites['ihdgageizm'].clone().set_position(30, 39),
            sprites['ihdgageizm'].clone().set_position(30, 44),
            sprites['ihdgageizm'].clone().set_position(30, 54),
            sprites['ihdgageizm'].clone().set_position(35, 9),
            sprites['ihdgageizm'].clone().set_position(35, 14),
            sprites['ihdgageizm'].clone().set_position(35, 19),
            sprites['ihdgageizm'].clone().set_position(35, 24),
            sprites['ihdgageizm'].clone().set_position(40, 9),
            sprites['ihdgageizm'].clone().set_position(40, 14),
            sprites['ihdgageizm'].clone().set_position(40, 19),
            sprites['ihdgageizm'].clone().set_position(40, 24),
            sprites['ihdgageizm'].clone().set_position(40, 29),
            sprites['ihdgageizm'].clone().set_position(40, 34),
            sprites['ihdgageizm'].clone().set_position(40, 44),
            sprites['ihdgageizm'].clone().set_position(40, 54),
            sprites['ihdgageizm'].clone().set_position(45, 9),
            sprites['ihdgageizm'].clone().set_position(45, 14),
            sprites['ihdgageizm'].clone().set_position(50, 9),
            sprites['ihdgageizm'].clone().set_position(50, 14),
            sprites['ihdgageizm'].clone().set_position(50, 19),
            sprites['ihdgageizm'].clone().set_position(50, 24),
            sprites['ihdgageizm'].clone().set_position(50, 29),
            sprites['ihdgageizm'].clone().set_position(50, 34),
            sprites['ihdgageizm'].clone().set_position(50, 39),
            sprites['ihdgageizm'].clone().set_position(50, 44),
            sprites['ihdgageizm'].clone().set_position(50, 49),
            sprites['ihdgageizm'].clone().set_position(50, 54),
        ],
        grid_size=(64, 64),
        data={'StepCounter': 42, 'kvynsvxbpi': 5, 'GoalColor': 9, 'GoalRotation': 270, 'StartShape': 5, 'StartColor': 9, 'StartRotation': 0, 'Fog': False},
    ),
    # Level 3
    Level(
        sprites=[
            sprites['eqatonpohu'].clone().set_position(53, 1),
            sprites['fesygzfqui'].clone().set_position(55, 54),
            sprites['ghizzeqtoh'].clone().set_position(53, 1),
            sprites['hoswmpiqkw'].clone().set_position(4, 8),
            sprites['ihdgageizm'].clone().set_position(55, 59),
            sprites['ihdgageizm'].clone().set_position(50, 59),
            sprites['ihdgageizm'].clone().set_position(45, 59),
            sprites['ihdgageizm'].clone().set_position(40, 59),
            sprites['ihdgageizm'].clone().set_position(35, 59),
            sprites['ihdgageizm'].clone().set_position(30, 59),
            sprites['ihdgageizm'].clone().set_position(20, 59),
            sprites['ihdgageizm'].clone().set_position(15, 59),
            sprites['ihdgageizm'].clone().set_position(10, 59),
            sprites['ihdgageizm'].clone().set_position(0, 59),
            sprites['ihdgageizm'].clone().set_position(55, 49),
            sprites['ihdgageizm'].clone().set_position(55, 44),
            sprites['ihdgageizm'].clone().set_position(55, 39),
            sprites['ihdgageizm'].clone().set_position(55, 34),
            sprites['ihdgageizm'].clone().set_position(55, 29),
            sprites['ihdgageizm'].clone().set_position(55, 24),
            sprites['ihdgageizm'].clone().set_position(0, 39),
            sprites['ihdgageizm'].clone().set_position(0, 34),
            sprites['ihdgageizm'].clone().set_position(0, 29),
            sprites['ihdgageizm'].clone().set_position(0, 24),
            sprites['ihdgageizm'].clone().set_position(0, 19),
            sprites['ihdgageizm'].clone().set_position(0, 14),
            sprites['ihdgageizm'].clone().set_position(0, 9),
            sprites['ihdgageizm'].clone().set_position(0, 4),
            sprites['ihdgageizm'].clone().set_position(10, 4),
            sprites['ihdgageizm'].clone().set_position(15, 4),
            sprites['ihdgageizm'].clone().set_position(20, 4),
            sprites['ihdgageizm'].clone().set_position(25, 4),
            sprites['ihdgageizm'].clone().set_position(30, 4),
            sprites['ihdgageizm'].clone().set_position(35, 4),
            sprites['ihdgageizm'].clone().set_position(40, 4),
            sprites['ihdgageizm'].clone().set_position(55, 19),
            sprites['ihdgageizm'].clone().set_position(55, 14),
            sprites['ihdgageizm'].clone().set_position(55, 9),
            sprites['ihdgageizm'].clone().set_position(55, 4),
            sprites['ihdgageizm'].clone().set_position(50, 4),
            sprites['ihdgageizm'].clone().set_position(45, 4),
            sprites['ihdgageizm'].clone().set_position(55, 14),
            sprites['ihdgageizm'].clone().set_position(25, 59),
            sprites['ihdgageizm'].clone().set_position(0, 49),
            sprites['ihdgageizm'].clone().set_position(0, 54),
            sprites['ihdgageizm'].clone().set_position(0, 44),
            sprites['ihdgageizm'].clone().set_position(5, 4),
            sprites['kapcaakvb_b'].clone().set_position(5, 55),
            sprites['kvynsvxbpi'].clone().set_position(6, 10),
            sprites['mxfhnkdzvf'].clone().set_position(5, 59),
            sprites['npxgalaybz'].clone().set_position(26, 45),
            sprites['npxgalaybz'].clone().set_position(41, 30),
            sprites['nszegiawib'].clone().set_position(3, 7),
            sprites['rhsxkxzdjz'].clone().set_position(10, 49),
            sprites['rjlbuycveu'].clone().set_position(5, 9),
            sprites['sfqyzhzkij'].clone().set_position(50, 14),
            sprites['soyhouuebz'].clone().set_position(30, 14),
            sprites['vjotnebuqo'].clone().set_position(4, 8),
            Sprite(
                pixels=[
                [0, -1, 0],
                [-1, 0, -1],
                [0, -1, 0],
            ],
                name='wgmbtyhvbc',
                x=55,
                y=3,
                layer=10,
                scale=2,
                blocking=BlockingMode.PIXEL_PERFECT,
                interaction=InteractionMode.TANGIBLE,
                tags=['wgmbtyhvbc'],
            ),
            sprites['xvrpzkggig'].clone().set_position(0, 0),
            sprites['yjgargdic_r'].clone().set_position(51, 54),
            sprites['ihdgageizm'].clone().set_position(10, 9),
            sprites['ihdgageizm'].clone().set_position(10, 14),
            sprites['ihdgageizm'].clone().set_position(10, 19),
            sprites['ihdgageizm'].clone().set_position(10, 24),
            sprites['ihdgageizm'].clone().set_position(10, 29),
            sprites['ihdgageizm'].clone().set_position(10, 39),
            sprites['ihdgageizm'].clone().set_position(10, 44),
            sprites['ihdgageizm'].clone().set_position(15, 9),
            sprites['ihdgageizm'].clone().set_position(15, 39),
            sprites['ihdgageizm'].clone().set_position(15, 44),
            sprites['ihdgageizm'].clone().set_position(15, 49),
            sprites['ihdgageizm'].clone().set_position(20, 9),
            sprites['ihdgageizm'].clone().set_position(20, 14),
            sprites['ihdgageizm'].clone().set_position(20, 19),
            sprites['ihdgageizm'].clone().set_position(20, 24),
            sprites['ihdgageizm'].clone().set_position(20, 29),
            sprites['ihdgageizm'].clone().set_position(20, 39),
            sprites['ihdgageizm'].clone().set_position(20, 44),
            sprites['ihdgageizm'].clone().set_position(20, 49),
            sprites['ihdgageizm'].clone().set_position(20, 54),
            sprites['ihdgageizm'].clone().set_position(25, 9),
            sprites['ihdgageizm'].clone().set_position(25, 14),
            sprites['ihdgageizm'].clone().set_position(25, 24),
            sprites['ihdgageizm'].clone().set_position(25, 49),
            sprites['ihdgageizm'].clone().set_position(30, 9),
            sprites['ihdgageizm'].clone().set_position(35, 9),
            sprites['ihdgageizm'].clone().set_position(35, 14),
            sprites['ihdgageizm'].clone().set_position(35, 19),
            sprites['ihdgageizm'].clone().set_position(35, 24),
            sprites['ihdgageizm'].clone().set_position(35, 34),
            sprites['ihdgageizm'].clone().set_position(35, 39),
            sprites['ihdgageizm'].clone().set_position(35, 49),
            sprites['ihdgageizm'].clone().set_position(40, 9),
            sprites['ihdgageizm'].clone().set_position(40, 14),
            sprites['ihdgageizm'].clone().set_position(40, 19),
            sprites['ihdgageizm'].clone().set_position(40, 24),
            sprites['ihdgageizm'].clone().set_position(40, 49),
            sprites['ihdgageizm'].clone().set_position(45, 9),
            sprites['ihdgageizm'].clone().set_position(45, 14),
            sprites['ihdgageizm'].clone().set_position(45, 19),
            sprites['ihdgageizm'].clone().set_position(45, 24),
            sprites['ihdgageizm'].clone().set_position(45, 29),
            sprites['ihdgageizm'].clone().set_position(45, 34),
            sprites['ihdgageizm'].clone().set_position(45, 39),
            sprites['ihdgageizm'].clone().set_position(45, 49),
            sprites['ihdgageizm'].clone().set_position(50, 9),
        ],
        grid_size=(64, 64),
        data={'StepCounter': 42, 'kvynsvxbpi': 5, 'GoalColor': 9, 'GoalRotation': 180, 'StartShape': 5, 'StartColor': 12, 'StartRotation': 0, 'Fog': False},
    ),
    # Level 4
    Level(
        sprites=[
            sprites['eqatonpohu'].clone().set_position(53, 1),
            sprites['fesygzfqui'].clone().set_position(30, 39),
            sprites['fesygzfqui'].clone().set_position(55, 24),
            sprites['ghizzeqtoh'].clone().set_position(53, 1),
            sprites['hoswmpiqkw'].clone().set_position(49, 53),
            sprites['ihdgageizm'].clone().set_position(55, 59),
            sprites['ihdgageizm'].clone().set_position(50, 59),
            sprites['ihdgageizm'].clone().set_position(55, 54),
            sprites['ihdgageizm'].clone().set_position(45, 59),
            sprites['ihdgageizm'].clone().set_position(40, 59),
            sprites['ihdgageizm'].clone().set_position(35, 59),
            sprites['ihdgageizm'].clone().set_position(30, 59),
            sprites['ihdgageizm'].clone().set_position(20, 59),
            sprites['ihdgageizm'].clone().set_position(15, 59),
            sprites['ihdgageizm'].clone().set_position(10, 59),
            sprites['ihdgageizm'].clone().set_position(5, 59),
            sprites['ihdgageizm'].clone().set_position(0, 59),
            sprites['ihdgageizm'].clone().set_position(55, 49),
            sprites['ihdgageizm'].clone().set_position(55, 44),
            sprites['ihdgageizm'].clone().set_position(55, 39),
            sprites['ihdgageizm'].clone().set_position(55, 34),
            sprites['ihdgageizm'].clone().set_position(55, 29),
            sprites['ihdgageizm'].clone().set_position(0, 44),
            sprites['ihdgageizm'].clone().set_position(0, 39),
            sprites['ihdgageizm'].clone().set_position(0, 34),
            sprites['ihdgageizm'].clone().set_position(0, 29),
            sprites['ihdgageizm'].clone().set_position(0, 39),
            sprites['ihdgageizm'].clone().set_position(0, 34),
            sprites['ihdgageizm'].clone().set_position(0, 29),
            sprites['ihdgageizm'].clone().set_position(0, 24),
            sprites['ihdgageizm'].clone().set_position(0, 19),
            sprites['ihdgageizm'].clone().set_position(0, 14),
            sprites['ihdgageizm'].clone().set_position(0, 24),
            sprites['ihdgageizm'].clone().set_position(0, 19),
            sprites['ihdgageizm'].clone().set_position(0, 14),
            sprites['ihdgageizm'].clone().set_position(0, 9),
            sprites['ihdgageizm'].clone().set_position(0, 4),
            sprites['ihdgageizm'].clone().set_position(0, 9),
            sprites['ihdgageizm'].clone().set_position(0, 4),
            sprites['ihdgageizm'].clone().set_position(5, 4),
            sprites['ihdgageizm'].clone().set_position(10, 4),
            sprites['ihdgageizm'].clone().set_position(15, 4),
            sprites['ihdgageizm'].clone().set_position(20, 4),
            sprites['ihdgageizm'].clone().set_position(25, 4),
            sprites['ihdgageizm'].clone().set_position(30, 4),
            sprites['ihdgageizm'].clone().set_position(35, 4),
            sprites['ihdgageizm'].clone().set_position(40, 4),
            sprites['ihdgageizm'].clone().set_position(55, 19),
            sprites['ihdgageizm'].clone().set_position(55, 14),
            sprites['ihdgageizm'].clone().set_position(55, 9),
            sprites['ihdgageizm'].clone().set_position(55, 4),
            sprites['ihdgageizm'].clone().set_position(50, 4),
            sprites['ihdgageizm'].clone().set_position(45, 4),
            sprites['ihdgageizm'].clone().set_position(55, 14),
            sprites['ihdgageizm'].clone().set_position(0, 49),
            sprites['ihdgageizm'].clone().set_position(0, 54),
            sprites['ihdgageizm'].clone().set_position(25, 59),
            sprites['kapcaakvb_b'].clone().set_position(40, 25),
            sprites['kapcaakvb_b'].clone().set_position(15, 40),
            sprites['krdypjjivz'].clone().set_position(20, 29),
            sprites['kvynsvxbpi'].clone().set_position(51, 55),
            sprites['lujfinsby_t'].clone().set_position(20, 33),
            sprites['mkjdaccuuf'].clone().set_position(35, 29),
            sprites['mxfhnkdzvf'].clone().set_position(40, 29),
            sprites['mxfhnkdzvf'].clone().set_position(15, 44),
            sprites['npxgalaybz'].clone().set_position(26, 10),
            sprites['npxgalaybz'].clone().set_position(41, 45),
            Sprite(
                pixels=[
                [3, 3, 3, 3, 3, 3, 3, 3, 3],
                [3, 3, 3, 3, 3, 3, 3, 3, 3],
                [3, 3, 3, 3, 3, 3, 3, 3, 3],
                [3, 3, 3, 3, 3, 3, 3, 3, 3],
                [3, 3, 3, 3, 3, 3, 3, 3, 3],
                [3, 3, 3, 3, 3, 3, 3, 3, 3],
                [3, 3, 3, 3, 3, 3, 3, 3, 3],
                [3, 3, 3, 3, 3, 3, 3, 3, 3],
                [3, 3, -1, -1, -1, -1, -1, 3, 3],
            ],
                name='nszegiawib',
                x=48,
                y=52,
                layer=-4,
                rotation=90,
                blocking=BlockingMode.PIXEL_PERFECT,
                interaction=InteractionMode.TANGIBLE,
            ),
            sprites['rjlbuycveu'].clone().set_position(50, 54),
            sprites['sfqyzhzkij'].clone().set_position(5, 54),
            sprites['soyhouuebz'].clone().set_position(25, 29),
            sprites['tihiodtoj_l'].clone().set_position(14, 34),
            sprites['tihiodtoj_l'].clone().set_position(34, 19),
            sprites['tihiodtoj_l'].clone().set_position(14, 19),
            sprites['ubyunwkbpx'].clone().set_position(10, 34),
            sprites['ubyunwkbpx'].clone().set_position(30, 19),
            sprites['ubyunwkbpx'].clone().set_position(10, 19),
            sprites['vjotnebuqo'].clone().set_position(49, 53),
            Sprite(
                pixels=[
                [0, -1, 0],
                [-1, 0, -1],
                [0, -1, 0],
            ],
                name='wgmbtyhvbc',
                x=55,
                y=3,
                layer=10,
                scale=2,
                blocking=BlockingMode.PIXEL_PERFECT,
                interaction=InteractionMode.TANGIBLE,
                tags=['wgmbtyhvbc'],
            ),
            sprites['xvrpzkggig'].clone().set_position(0, 0),
            sprites['yjgargdic_r'].clone().set_position(26, 39),
            sprites['yjgargdic_r'].clone().set_position(51, 24),
            sprites['ihdgageizm'].clone().set_position(5, 9),
            sprites['ihdgageizm'].clone().set_position(10, 9),
            sprites['ihdgageizm'].clone().set_position(10, 44),
            sprites['ihdgageizm'].clone().set_position(10, 49),
            sprites['ihdgageizm'].clone().set_position(15, 9),
            sprites['ihdgageizm'].clone().set_position(15, 49),
            sprites['ihdgageizm'].clone().set_position(20, 9),
            sprites['ihdgageizm'].clone().set_position(20, 14),
            sprites['ihdgageizm'].clone().set_position(20, 24),
            sprites['ihdgageizm'].clone().set_position(25, 24),
            sprites['ihdgageizm'].clone().set_position(25, 44),
            sprites['ihdgageizm'].clone().set_position(25, 49),
            sprites['ihdgageizm'].clone().set_position(30, 14),
            sprites['ihdgageizm'].clone().set_position(30, 24),
            sprites['ihdgageizm'].clone().set_position(30, 34),
            sprites['ihdgageizm'].clone().set_position(30, 44),
            sprites['ihdgageizm'].clone().set_position(30, 49),
            sprites['ihdgageizm'].clone().set_position(35, 34),
            sprites['ihdgageizm'].clone().set_position(40, 9),
            sprites['ihdgageizm'].clone().set_position(40, 34),
            sprites['ihdgageizm'].clone().set_position(40, 49),
            sprites['ihdgageizm'].clone().set_position(45, 9),
            sprites['ihdgageizm'].clone().set_position(45, 14),
            sprites['ihdgageizm'].clone().set_position(45, 44),
            sprites['ihdgageizm'].clone().set_position(45, 49),
            sprites['ihdgageizm'].clone().set_position(50, 9),
            sprites['ihdgageizm'].clone().set_position(50, 29),
            sprites['ihdgageizm'].clone().set_position(50, 39),
            sprites['ihdgageizm'].clone().set_position(50, 44),
            sprites['ihdgageizm'].clone().set_position(50, 49),
        ],
        grid_size=(64, 64),
        data={'StepCounter': 42, 'kvynsvxbpi': 5, 'GoalColor': 9, 'GoalRotation': 0, 'StartShape': 4, 'StartColor': 14, 'StartRotation': 0, 'Fog': False, 'StepsDecrement': 1},
    ),
    # Level 5
    Level(
        sprites=[
            sprites['ajdspzphhd'].clone().set_position(35, 24),
            sprites['eqatonpohu'].clone().set_position(53, 1),
            sprites['fesygzfqui'].clone().set_position(30, 39),
            sprites['fesygzfqui'].clone().set_position(20, 19),
            sprites['ghizzeqtoh'].clone().set_position(53, 1),
            sprites['hoswmpiqkw'].clone().set_position(4, 53),
            sprites['ihdgageizm'].clone().set_position(55, 59),
            sprites['ihdgageizm'].clone().set_position(50, 59),
            sprites['ihdgageizm'].clone().set_position(55, 54),
            sprites['ihdgageizm'].clone().set_position(40, 59),
            sprites['ihdgageizm'].clone().set_position(35, 59),
            sprites['ihdgageizm'].clone().set_position(30, 59),
            sprites['ihdgageizm'].clone().set_position(20, 59),
            sprites['ihdgageizm'].clone().set_position(15, 59),
            sprites['ihdgageizm'].clone().set_position(10, 59),
            sprites['ihdgageizm'].clone().set_position(5, 59),
            sprites['ihdgageizm'].clone().set_position(0, 59),
            sprites['ihdgageizm'].clone().set_position(55, 49),
            sprites['ihdgageizm'].clone().set_position(55, 44),
            sprites['ihdgageizm'].clone().set_position(55, 39),
            sprites['ihdgageizm'].clone().set_position(55, 34),
            sprites['ihdgageizm'].clone().set_position(55, 29),
            sprites['ihdgageizm'].clone().set_position(55, 24),
            sprites['ihdgageizm'].clone().set_position(0, 9),
            sprites['ihdgageizm'].clone().set_position(0, 4),
            sprites['ihdgageizm'].clone().set_position(20, 4),
            sprites['ihdgageizm'].clone().set_position(25, 4),
            sprites['ihdgageizm'].clone().set_position(30, 4),
            sprites['ihdgageizm'].clone().set_position(35, 4),
            sprites['ihdgageizm'].clone().set_position(40, 4),
            sprites['ihdgageizm'].clone().set_position(55, 19),
            sprites['ihdgageizm'].clone().set_position(55, 14),
            sprites['ihdgageizm'].clone().set_position(55, 9),
            sprites['ihdgageizm'].clone().set_position(55, 4),
            sprites['ihdgageizm'].clone().set_position(50, 4),
            sprites['ihdgageizm'].clone().set_position(45, 4),
            sprites['ihdgageizm'].clone().set_position(55, 14),
            sprites['ihdgageizm'].clone().set_position(0, 54),
            sprites['ihdgageizm'].clone().set_position(15, 4),
            sprites['ihdgageizm'].clone().set_position(10, 4),
            sprites['ihdgageizm'].clone().set_position(0, 49),
            sprites['ihdgageizm'].clone().set_position(0, 39),
            sprites['ihdgageizm'].clone().set_position(0, 34),
            sprites['ihdgageizm'].clone().set_position(0, 24),
            sprites['ihdgageizm'].clone().set_position(0, 19),
            sprites['ihdgageizm'].clone().set_position(0, 14),
            sprites['ihdgageizm'].clone().set_position(45, 59),
            sprites['ihdgageizm'].clone().set_position(0, 44),
            sprites['kapcaakvb_b'].clone().set_position(25, 55),
            sprites['kapcaakvb_b'].clone().set_position(10, 30),
            sprites['krdypjjivz'].clone().set_position(5, 4),
            sprites['krdypjjivz'].clone().set_position(20, 29),
            sprites['kvynsvxbpi'].clone().set_position(6, 55),
            sprites['lujfinsby_t'].clone().set_position(5, 8),
            sprites['lujfinsby_t'].clone().set_position(20, 33),
            sprites['mkjdaccuuf'].clone().set_position(40, 49),
            sprites['mxfhnkdzvf'].clone().set_position(25, 59),
            sprites['mxfhnkdzvf'].clone().set_position(10, 34),
            sprites['npxgalaybz'].clone().set_position(46, 15),
            sprites['npxgalaybz'].clone().set_position(16, 55),
            sprites['npxgalaybz'].clone().set_position(51, 50),
            Sprite(
                pixels=[
                [3, 3, 3, 3, 3, 3, 3, 3, 3],
                [3, 3, 3, 3, 3, 3, 3, 3, 3],
                [3, 3, 3, 3, 3, 3, 3, 3, 3],
                [3, 3, 3, 3, 3, 3, 3, 3, 3],
                [3, 3, 3, 3, 3, 3, 3, 3, 3],
                [3, 3, 3, 3, 3, 3, 3, 3, 3],
                [3, 3, 3, 3, 3, 3, 3, 3, 3],
                [3, 3, 3, 3, 3, 3, 3, 3, 3],
                [3, 3, -1, -1, -1, -1, -1, 3, 3],
            ],
                name='nszegiawib',
                x=3,
                y=52,
                layer=-4,
                rotation=180,
                blocking=BlockingMode.PIXEL_PERFECT,
                interaction=InteractionMode.TANGIBLE,
            ),
            sprites['rhsxkxzdjz'].clone().set_position(45, 24),
            sprites['rjlbuycveu'].clone().set_position(5, 54),
            sprites['sfqyzhzkij'].clone().set_position(10, 19),
            sprites['soyhouuebz'].clone().set_position(30, 34),
            sprites['tihiodtoj_l'].clone().set_position(4, 29),
            sprites['tihiodtoj_l'].clone().set_position(39, 34),
            sprites['ubyunwkbpx'].clone().set_position(0, 29),
            sprites['ubyunwkbpx'].clone().set_position(35, 34),
            sprites['vjotnebuqo'].clone().set_position(4, 53),
            Sprite(
                pixels=[
                [0, -1, 0],
                [-1, 0, -1],
                [0, -1, 0],
            ],
                name='wgmbtyhvbc',
                x=55,
                y=3,
                layer=10,
                scale=2,
                blocking=BlockingMode.PIXEL_PERFECT,
                interaction=InteractionMode.TANGIBLE,
                tags=['wgmbtyhvbc'],
            ),
            sprites['xvrpzkggig'].clone().set_position(0, 0),
            sprites['yjgargdic_r'].clone().set_position(26, 39),
            sprites['yjgargdic_r'].clone().set_position(16, 19),
            sprites['ihdgageizm'].clone().set_position(10, 14),
            sprites['ihdgageizm'].clone().set_position(10, 39),
            sprites['ihdgageizm'].clone().set_position(10, 44),
            sprites['ihdgageizm'].clone().set_position(10, 49),
            sprites['ihdgageizm'].clone().set_position(10, 54),
            sprites['ihdgageizm'].clone().set_position(15, 44),
            sprites['ihdgageizm'].clone().set_position(15, 49),
            sprites['ihdgageizm'].clone().set_position(20, 14),
            sprites['ihdgageizm'].clone().set_position(25, 14),
            sprites['ihdgageizm'].clone().set_position(25, 29),
            sprites['ihdgageizm'].clone().set_position(30, 24),
            sprites['ihdgageizm'].clone().set_position(30, 29),
            sprites['ihdgageizm'].clone().set_position(30, 49),
            sprites['ihdgageizm'].clone().set_position(35, 14),
            sprites['ihdgageizm'].clone().set_position(35, 29),
            sprites['ihdgageizm'].clone().set_position(35, 39),
            sprites['ihdgageizm'].clone().set_position(35, 49),
            sprites['ihdgageizm'].clone().set_position(40, 29),
            sprites['ihdgageizm'].clone().set_position(45, 9),
            sprites['ihdgageizm'].clone().set_position(45, 29),
            sprites['ihdgageizm'].clone().set_position(45, 39),
            sprites['ihdgageizm'].clone().set_position(45, 54),
            sprites['ihdgageizm'].clone().set_position(50, 9),
            sprites['ihdgageizm'].clone().set_position(50, 14),
            sprites['ihdgageizm'].clone().set_position(50, 39),
            sprites['ihdgageizm'].clone().set_position(50, 44),
        ],
        grid_size=(64, 64),
        data={'StepCounter': 42, 'kvynsvxbpi': 0, 'GoalColor': 8, 'GoalRotation': 180, 'StartShape': 4, 'StartColor': 12, 'StartRotation': 0, 'Fog': False},
    ),
    # Level 6
    Level(
        sprites=[
            sprites['eqatonpohu'].clone().set_position(53, 1),
            sprites['ghizzeqtoh'].clone().set_position(53, 1),
            sprites['hahdypcdru'].clone().set_position(25, 19),
            sprites['hahdypcdru'].clone().set_position(25, 49),
            sprites['hoswmpiqkw'].clone().set_position(4, 23),
            sprites['hoswmpiqkw'].clone().set_position(4, 8),
            sprites['ihdgageizm'].clone().set_position(55, 59),
            sprites['ihdgageizm'].clone().set_position(50, 59),
            sprites['ihdgageizm'].clone().set_position(55, 54),
            sprites['ihdgageizm'].clone().set_position(45, 59),
            sprites['ihdgageizm'].clone().set_position(40, 59),
            sprites['ihdgageizm'].clone().set_position(35, 59),
            sprites['ihdgageizm'].clone().set_position(30, 59),
            sprites['ihdgageizm'].clone().set_position(20, 59),
            sprites['ihdgageizm'].clone().set_position(0, 59),
            sprites['ihdgageizm'].clone().set_position(55, 49),
            sprites['ihdgageizm'].clone().set_position(55, 44),
            sprites['ihdgageizm'].clone().set_position(55, 39),
            sprites['ihdgageizm'].clone().set_position(55, 34),
            sprites['ihdgageizm'].clone().set_position(55, 29),
            sprites['ihdgageizm'].clone().set_position(55, 24),
            sprites['ihdgageizm'].clone().set_position(0, 34),
            sprites['ihdgageizm'].clone().set_position(0, 29),
            sprites['ihdgageizm'].clone().set_position(0, 24),
            sprites['ihdgageizm'].clone().set_position(0, 19),
            sprites['ihdgageizm'].clone().set_position(0, 14),
            sprites['ihdgageizm'].clone().set_position(0, 9),
            sprites['ihdgageizm'].clone().set_position(0, 4),
            sprites['ihdgageizm'].clone().set_position(10, 4),
            sprites['ihdgageizm'].clone().set_position(15, 4),
            sprites['ihdgageizm'].clone().set_position(20, 4),
            sprites['ihdgageizm'].clone().set_position(25, 4),
            sprites['ihdgageizm'].clone().set_position(30, 4),
            sprites['ihdgageizm'].clone().set_position(35, 4),
            sprites['ihdgageizm'].clone().set_position(40, 4),
            sprites['ihdgageizm'].clone().set_position(55, 19),
            sprites['ihdgageizm'].clone().set_position(55, 14),
            sprites['ihdgageizm'].clone().set_position(55, 9),
            sprites['ihdgageizm'].clone().set_position(55, 4),
            sprites['ihdgageizm'].clone().set_position(50, 4),
            sprites['ihdgageizm'].clone().set_position(45, 4),
            sprites['ihdgageizm'].clone().set_position(55, 14),
            sprites['ihdgageizm'].clone().set_position(25, 59),
            sprites['ihdgageizm'].clone().set_position(0, 49),
            sprites['ihdgageizm'].clone().set_position(0, 54),
            sprites['ihdgageizm'].clone().set_position(5, 4),
            sprites['ihdgageizm'].clone().set_position(15, 59),
            sprites['ihdgageizm'].clone().set_position(5, 59),
            sprites['ihdgageizm'].clone().set_position(0, 44),
            sprites['ihdgageizm'].clone().set_position(0, 39),
            sprites['kapcaakvb_b'].clone().set_position(10, 55),
            sprites['kvynsvxbpi'].clone().set_position(6, 10),
            sprites['kvynsvxbpi'].clone().set_position(6, 25),
            sprites['mkjdaccuuf'].clone().set_position(45, 49),
            sprites['mxfhnkdzvf'].clone().set_position(10, 59),
            sprites['njpewhmtfd'].clone().set_position(4, 23),
            sprites['npxgalaybz'].clone().set_position(21, 55),
            sprites['npxgalaybz'].clone().set_position(51, 15),
            sprites['npxgalaybz'].clone().set_position(51, 55),
            sprites['nszegiawib'].clone().set_position(3, 7),
            sprites['nszegiawib'].clone().set_position(3, 22),
            sprites['rhsxkxzdjz'].clone().set_position(25, 19),
            sprites['rjlbuycveu'].clone().set_position(5, 9),
            sprites['rjlbuycveu'].clone().set_position(5, 24),
            sprites['sfqyzhzkij'].clone().set_position(35, 9),
            sprites['soyhouuebz'].clone().set_position(35, 29),
            sprites['tihiodtoj_l'].clone().set_position(9, 39),
            sprites['ubyunwkbpx'].clone().set_position(5, 39),
            sprites['vjotnebuqo'].clone().set_position(4, 8),
            Sprite(
                pixels=[
                [0, -1, 0],
                [-1, 0, -1],
                [0, -1, 0],
            ],
                name='wgmbtyhvbc',
                x=55,
                y=3,
                layer=10,
                scale=2,
                blocking=BlockingMode.PIXEL_PERFECT,
                interaction=InteractionMode.TANGIBLE,
                tags=['wgmbtyhvbc'],
            ),
            sprites['xfmluydglp'].clone().set_position(30, 29),
            sprites['xvrpzkggig'].clone().set_position(0, 0),
            sprites['ihdgageizm'].clone().set_position(5, 44),
            sprites['ihdgageizm'].clone().set_position(5, 54),
            sprites['ihdgageizm'].clone().set_position(10, 9),
            sprites['ihdgageizm'].clone().set_position(10, 14),
            sprites['ihdgageizm'].clone().set_position(10, 19),
            sprites['ihdgageizm'].clone().set_position(10, 24),
            sprites['ihdgageizm'].clone().set_position(10, 29),
            sprites['ihdgageizm'].clone().set_position(15, 9),
            sprites['ihdgageizm'].clone().set_position(15, 14),
            sprites['ihdgageizm'].clone().set_position(15, 19),
            sprites['ihdgageizm'].clone().set_position(15, 24),
            sprites['ihdgageizm'].clone().set_position(15, 29),
            sprites['ihdgageizm'].clone().set_position(15, 34),
            sprites['ihdgageizm'].clone().set_position(15, 49),
            sprites['ihdgageizm'].clone().set_position(15, 54),
            sprites['ihdgageizm'].clone().set_position(25, 9),
            sprites['ihdgageizm'].clone().set_position(25, 24),
            sprites['ihdgageizm'].clone().set_position(25, 29),
            sprites['ihdgageizm'].clone().set_position(25, 39),
            sprites['ihdgageizm'].clone().set_position(25, 44),
            sprites['ihdgageizm'].clone().set_position(25, 54),
            sprites['ihdgageizm'].clone().set_position(30, 9),
            sprites['ihdgageizm'].clone().set_position(30, 44),
            sprites['ihdgageizm'].clone().set_position(35, 24),
            sprites['ihdgageizm'].clone().set_position(35, 44),
            sprites['ihdgageizm'].clone().set_position(35, 54),
            sprites['ihdgageizm'].clone().set_position(40, 9),
            sprites['ihdgageizm'].clone().set_position(45, 9),
            sprites['ihdgageizm'].clone().set_position(45, 24),
            sprites['ihdgageizm'].clone().set_position(45, 29),
            sprites['ihdgageizm'].clone().set_position(45, 39),
            sprites['ihdgageizm'].clone().set_position(45, 44),
            sprites['ihdgageizm'].clone().set_position(50, 9),
        ],
        grid_size=(64, 64),
        data={'StepCounter': 42, 'kvynsvxbpi': [5, 0], 'GoalColor': [9, 8], 'GoalRotation': [90, 180], 'StartShape': 0, 'StartColor': 14, 'StartRotation': 0, 'Fog': False, 'StepsDecrement': 1},
    ),
    # Level 7
    Level(
        sprites=[
            sprites['eqatonpohu'].clone().set_position(53, 1),
            sprites['ghizzeqtoh'].clone().set_position(53, 1),
            sprites['hoswmpiqkw'].clone().set_position(29, 8),
            sprites['ihdgageizm'].clone().set_position(55, 59),
            sprites['ihdgageizm'].clone().set_position(50, 59),
            sprites['ihdgageizm'].clone().set_position(55, 54),
            sprites['ihdgageizm'].clone().set_position(45, 59),
            sprites['ihdgageizm'].clone().set_position(40, 59),
            sprites['ihdgageizm'].clone().set_position(35, 59),
            sprites['ihdgageizm'].clone().set_position(30, 59),
            sprites['ihdgageizm'].clone().set_position(20, 59),
            sprites['ihdgageizm'].clone().set_position(15, 59),
            sprites['ihdgageizm'].clone().set_position(10, 59),
            sprites['ihdgageizm'].clone().set_position(5, 59),
            sprites['ihdgageizm'].clone().set_position(0, 59),
            sprites['ihdgageizm'].clone().set_position(55, 49),
            sprites['ihdgageizm'].clone().set_position(55, 44),
            sprites['ihdgageizm'].clone().set_position(55, 39),
            sprites['ihdgageizm'].clone().set_position(55, 34),
            sprites['ihdgageizm'].clone().set_position(55, 29),
            sprites['ihdgageizm'].clone().set_position(55, 24),
            sprites['ihdgageizm'].clone().set_position(0, 39),
            sprites['ihdgageizm'].clone().set_position(0, 29),
            sprites['ihdgageizm'].clone().set_position(0, 14),
            sprites['ihdgageizm'].clone().set_position(0, 9),
            sprites['ihdgageizm'].clone().set_position(0, 4),
            sprites['ihdgageizm'].clone().set_position(0, 4),
            sprites['ihdgageizm'].clone().set_position(5, 4),
            sprites['ihdgageizm'].clone().set_position(10, 4),
            sprites['ihdgageizm'].clone().set_position(15, 4),
            sprites['ihdgageizm'].clone().set_position(20, 4),
            sprites['ihdgageizm'].clone().set_position(25, 4),
            sprites['ihdgageizm'].clone().set_position(30, 4),
            sprites['ihdgageizm'].clone().set_position(35, 4),
            sprites['ihdgageizm'].clone().set_position(40, 4),
            sprites['ihdgageizm'].clone().set_position(55, 19),
            sprites['ihdgageizm'].clone().set_position(55, 14),
            sprites['ihdgageizm'].clone().set_position(55, 9),
            sprites['ihdgageizm'].clone().set_position(55, 4),
            sprites['ihdgageizm'].clone().set_position(50, 4),
            sprites['ihdgageizm'].clone().set_position(45, 4),
            sprites['ihdgageizm'].clone().set_position(55, 14),
            sprites['ihdgageizm'].clone().set_position(25, 59),
            sprites['ihdgageizm'].clone().set_position(0, 49),
            sprites['ihdgageizm'].clone().set_position(0, 54),
            sprites['ihdgageizm'].clone().set_position(0, 44),
            sprites['ihdgageizm'].clone().set_position(0, 34),
            sprites['ihdgageizm'].clone().set_position(0, 24),
            sprites['ihdgageizm'].clone().set_position(0, 19),
            sprites['irgjxweouz'].clone().set_position(5, 26),
            sprites['kapcaakvb_b'].clone().set_position(20, 40),
            sprites['krdypjjivz'].clone().set_position(25, 24),
            sprites['kvynsvxbpi'].clone().set_position(31, 10),
            sprites['lujfinsby_t'].clone().set_position(25, 28),
            sprites['mkjdaccuuf'].clone().set_position(40, 19),
            sprites['mxfhnkdzvf'].clone().set_position(20, 44),
            sprites['npxgalaybz'].clone().set_position(31, 40),
            sprites['npxgalaybz'].clone().set_position(11, 55),
            sprites['npxgalaybz'].clone().set_position(46, 15),
            sprites['npxgalaybz'].clone().set_position(21, 55),
            sprites['npxgalaybz'].clone().set_position(6, 10),
            sprites['npxgalaybz'].clone().set_position(51, 55),
            sprites['nszegiawib'].clone().set_position(28, 7),
            sprites['rhsxkxzdjz'].clone().set_position(5, 49),
            sprites['rjlbuycveu'].clone().set_position(30, 9),
            sprites['sfqyzhzkij'].clone().set_position(40, 44),
            sprites['soyhouuebz'].clone().set_position(50, 19),
            sprites['tihiodtoj_l'].clone().set_position(19, 29),
            sprites['ubyunwkbpx'].clone().set_position(15, 29),
            sprites['vjotnebuqo'].clone().set_position(29, 8),
            Sprite(
                pixels=[
                [0, -1, 0],
                [-1, 0, -1],
                [0, -1, 0],
            ],
                name='wgmbtyhvbc',
                x=55,
                y=3,
                layer=10,
                scale=2,
                blocking=BlockingMode.PIXEL_PERFECT,
                interaction=InteractionMode.TANGIBLE,
                tags=['wgmbtyhvbc'],
            ),
            sprites['xvrpzkggig'].clone().set_position(0, 0),
            sprites['ihdgageizm'].clone().set_position(5, 14),
            sprites['ihdgageizm'].clone().set_position(5, 19),
            sprites['ihdgageizm'].clone().set_position(10, 9),
            sprites['ihdgageizm'].clone().set_position(10, 14),
            sprites['ihdgageizm'].clone().set_position(15, 9),
            sprites['ihdgageizm'].clone().set_position(15, 14),
            sprites['ihdgageizm'].clone().set_position(15, 34),
            sprites['ihdgageizm'].clone().set_position(15, 44),
            sprites['ihdgageizm'].clone().set_position(15, 49),
            sprites['ihdgageizm'].clone().set_position(20, 9),
            sprites['ihdgageizm'].clone().set_position(20, 14),
            sprites['ihdgageizm'].clone().set_position(25, 9),
            sprites['ihdgageizm'].clone().set_position(25, 14),
            sprites['ihdgageizm'].clone().set_position(25, 19),
            sprites['ihdgageizm'].clone().set_position(25, 54),
            sprites['ihdgageizm'].clone().set_position(30, 44),
            sprites['ihdgageizm'].clone().set_position(35, 9),
            sprites['ihdgageizm'].clone().set_position(35, 14),
            sprites['ihdgageizm'].clone().set_position(35, 24),
            sprites['ihdgageizm'].clone().set_position(35, 29),
            sprites['ihdgageizm'].clone().set_position(35, 39),
            sprites['ihdgageizm'].clone().set_position(35, 49),
            sprites['ihdgageizm'].clone().set_position(40, 9),
            sprites['ihdgageizm'].clone().set_position(40, 14),
            sprites['ihdgageizm'].clone().set_position(40, 24),
            sprites['ihdgageizm'].clone().set_position(40, 29),
            sprites['ihdgageizm'].clone().set_position(45, 9),
            sprites['ihdgageizm'].clone().set_position(45, 24),
            sprites['ihdgageizm'].clone().set_position(45, 29),
            sprites['ihdgageizm'].clone().set_position(45, 39),
            sprites['ihdgageizm'].clone().set_position(45, 49),
            sprites['ihdgageizm'].clone().set_position(50, 9),
            sprites['ihdgageizm'].clone().set_position(50, 14),
        ],
        grid_size=(64, 64),
        data={'StepCounter': 42, 'kvynsvxbpi': 0, 'GoalColor': 8, 'GoalRotation': 180, 'StartShape': 1, 'StartColor': 12, 'StartRotation': 0, 'Fog': True},
    ),
]
BACKGROUND_COLOR = 3
PADDING_COLOR = 3
ubupgomgin = -1
epeqflmtfc = 0
dqifgqaxrg = 1
oazrnhzatr = 2
iisukudgvu = 3
kacnekcwsp = 4
avbdwkmqcy = 5
ijbilzmvdl = 6
yffnqoouus = 7
tqogkgimes = 8
jninpsotet = 9
vgcsccvckt = 10
dhxmtlewyv = 11
epqvqkpffo = 12
qqkmepheqb = 13
bejggpjowv = 14
eqvdisyxbr = 15
zoghkczvvt = 5
xvzyzqolqz = 5


class hbuhvkxlhc(RenderableUserDisplay):
    """."""

    bfdcztirdu: List[Tuple[int, int]]

    def __init__(self, vjhajnbdzr: "_Ly20Rules", osgviligwp: int):
        self.vjhajnbdzr = vjhajnbdzr
        self.osgviligwp = osgviligwp
        self.current_steps = osgviligwp
        self.efipnixsvl = 1

    def kbkdzqocik(self, kapizhweba: int) -> None:
        self.current_steps = max(0, min(kapizhweba, self.osgviligwp))

    def vytykscvhe(self, efipnixsvl: int) -> None:
        self.efipnixsvl = efipnixsvl

    def mfyzdfvxsm(self) -> bool:
        if self.current_steps >= 0:
            self.current_steps -= self.efipnixsvl
        return self.current_steps >= 0

    def nzukewekzr(self) -> None:
        self.current_steps = self.osgviligwp

    def render_interface(self, frame: np.ndarray) -> np.ndarray:
        if self.osgviligwp == 0 or self.vjhajnbdzr.ebfuxzbvn:
            return frame
        yydgfgfvvh = 1.5
        if self.vjhajnbdzr.oeuabekjf:
            for i in range(64):
                for fbklvtfnjh in range(64):
                    if (
                        math.dist(
                            (i, fbklvtfnjh),
                            (
                                self.vjhajnbdzr.gudziatsk.y + yydgfgfvvh,
                                self.vjhajnbdzr.gudziatsk.x + yydgfgfvvh,
                            ),
                        )
                        > 20.0
                    ):
                        frame[i, fbklvtfnjh] = avbdwkmqcy
            if self.vjhajnbdzr.htkmubhry and self.vjhajnbdzr.htkmubhry.is_visible:
                sprite = self.vjhajnbdzr.htkmubhry.render()
                wmdkkxqkw = 64 - 3 - self.vjhajnbdzr.htkmubhry.width
                toxqhfsju = 64 - 55 - self.vjhajnbdzr.htkmubhry.height
                for i in range(self.vjhajnbdzr.htkmubhry.height):
                    for rejdvlfhdv in range(self.vjhajnbdzr.htkmubhry.width):
                        if sprite[i][rejdvlfhdv] != -1:
                            frame[toxqhfsju + i, wmdkkxqkw + rejdvlfhdv] = sprite[i][rejdvlfhdv]
        for i in range(self.osgviligwp):
            wmdkkxqkw = 63 - 13 - i
            toxqhfsju = 1
            frame[toxqhfsju : toxqhfsju + 2, wmdkkxqkw] = dhxmtlewyv if self.osgviligwp - i - 1 < self.current_steps else iisukudgvu
        for bsyrmrqsrq in range(3):
            wmdkkxqkw = 63 - 56 - 3 * bsyrmrqsrq - 1
            toxqhfsju = 1
            for x in range(2):
                frame[toxqhfsju : toxqhfsju + 2, wmdkkxqkw + x] = tqogkgimes if self.vjhajnbdzr.aqygnziho > bsyrmrqsrq else iisukudgvu
        return frame


class xajlyftlyn:
    def wgxrzqzazj(self) -> bool:
        return False


class twkzhcfelv(xajlyftlyn):
    qeekhxkoad = 8
    boafatmkhi = 6

    def __init__(self, sprite: Sprite, fjzuynaokm: Set[Tuple[int, int]]) -> None:
        self.fjzuynaokm = fjzuynaokm
        self.sprite = sprite
        self.sprite.set_blocking(BlockingMode.BOUNDING_BOX)
        self.width = self.sprite.width
        self.height = self.sprite.height
        self.start_x = self.sprite.x
        self.start_y = self.sprite.y
        self.dx = 0
        self.dy = 0
        if sprite.name.endswith("t"):
            self.dx, self.dy = 0, 1
        elif sprite.name.endswith("b"):
            self.dx, self.dy = 0, -1
        elif sprite.name.endswith("r"):
            self.dx, self.dy = -1, 0
        elif sprite.name.endswith("l"):
            self.dx, self.dy = 1, 0
        self.target_x = self.sprite.x
        self.target_y = self.sprite.y
        self.is_pushing = False
        self.aqxtoxeino: Optional[Sprite] = None
        self._anim_elapsed = 0
        self._anim_duration = 1
        self._anim_from_x = float(self.sprite.x)
        self._anim_from_y = float(self.sprite.y)
        self._anim_to_x = float(self.sprite.x)
        self._anim_to_y = float(self.sprite.y)
        self._carry_x = 0.0
        self._carry_y = 0.0

    def ullzqnksoj(self, aqxtoxeino: Sprite) -> int:
        wall_cx, wall_cy = (self.sprite.x + 1 * self.dx, self.sprite.y + 1 * self.dy)
        xwjnqmqiaz = None
        for acdeadlbzx in range(1, 12):
            nskortmtde = wall_cx + self.dx * self.width * acdeadlbzx
            wsotwbexvh = wall_cy + self.dy * self.height * acdeadlbzx
            if (nskortmtde, wsotwbexvh) in self.fjzuynaokm:
                xwjnqmqiaz = acdeadlbzx
                break
        if xwjnqmqiaz is None:
            return 0
        return max(0, xwjnqmqiaz - 1)

    def mfnyvivrar(self, dxegqdlzda: float) -> float:
        if dxegqdlzda < 0.5:
            return 4 * dxegqdlzda * dxegqdlzda * dxegqdlzda
        return 1 - (-2 * dxegqdlzda + 2) ** 3 / 2

    def monctmxmpp(self, dutvzjyvok: int, xxnitqxuds: int, ilzothrych: int) -> None:
        self._anim_elapsed = 0
        self._anim_duration = max(1, int(ilzothrych))
        self._anim_from_x = float(self.sprite.x)
        self._anim_from_y = float(self.sprite.y)
        self._anim_to_x = float(dutvzjyvok)
        self._anim_to_y = float(xxnitqxuds)
        self._carry_x = 0.0
        self._carry_y = 0.0

    def qeoitwygzm(self, srkcilioyp: bool) -> bool:
        if self._anim_elapsed >= self._anim_duration:
            dx = int(round(self._anim_to_x - self.sprite.x))
            dy = int(round(self._anim_to_y - self.sprite.y))
            if dx or dy:
                self.sprite.move(dx, dy)
                if srkcilioyp and self.aqxtoxeino is not None:
                    self.aqxtoxeino.move(dx, dy)
            return False
        self._anim_elapsed += 1
        dxegqdlzda = self._anim_elapsed / self._anim_duration
        hpaysqkbgh = self.mfnyvivrar(dxegqdlzda)
        enzdcdjnzt = self._anim_from_x + (self._anim_to_x - self._anim_from_x) * hpaysqkbgh
        kyaecjvpph = self._anim_from_y + (self._anim_to_y - self._anim_from_y) * hpaysqkbgh
        kdsuujxuag = enzdcdjnzt - float(self.sprite.x) + self._carry_x
        sihdbliheu = kyaecjvpph - float(self.sprite.y) + self._carry_y
        vzkxmdfnba = int(kdsuujxuag)
        acjrijfisx = int(sihdbliheu)
        self._carry_x = kdsuujxuag - vzkxmdfnba
        self._carry_y = sihdbliheu - acjrijfisx
        if vzkxmdfnba or acjrijfisx:
            self.sprite.move(vzkxmdfnba, acjrijfisx)
            if srkcilioyp and self.aqxtoxeino is not None:
                self.aqxtoxeino.move(vzkxmdfnba, acjrijfisx)
        return True

    def prpxgfxlcm(self, aqxtoxeino: Sprite) -> bool:
        if not self.sprite.collides_with(aqxtoxeino):
            return False
        gguyvrkohc = self.ullzqnksoj(aqxtoxeino)
        if gguyvrkohc <= 0:
            return False
        self.aqxtoxeino = aqxtoxeino
        self.is_pushing = True
        self.target_x = self.start_x + self.dx * self.width * gguyvrkohc
        self.target_y = self.start_y + self.dy * self.height * gguyvrkohc
        self.monctmxmpp(self.target_x, self.target_y, self.qeekhxkoad)
        return True

    def wgxrzqzazj(self) -> bool:
        if self.is_pushing:
            if self.qeoitwygzm(srkcilioyp=True):
                return True
            self.target_x = self.start_x
            self.target_y = self.start_y
            self.is_pushing = False
            self.monctmxmpp(self.target_x, self.target_y, self.boafatmkhi)
            return True
        return self.qeoitwygzm(srkcilioyp=False)


class dboxixicic:
    def __init__(self, oypxsalqjo: Sprite, sprite: Sprite, pawjyrnadt: int = 5) -> None:
        self.bfdcztirdu = oypxsalqjo
        self._sprite = sprite
        self._cell = pawjyrnadt
        self._start_x = sprite.x
        self._start_y = sprite.y
        self._dir = 0
        self._undo_x: Optional[int] = None
        self._undo_y: Optional[int] = None
        self._undo_dir: Optional[int] = None

    def bkuguqrpvq(self) -> None:
        self._dir = 0
        self._sprite.set_position(self._start_x, self._start_y)
        self._undo_x = None
        self._undo_y = None
        self._undo_dir = None

    def qrttfzbifu(self) -> None:
        self._dir = (self._dir + 2) % 4

    def npdjlrkhsg(self) -> Tuple[int, int]:
        if not self.bfdcztirdu:
            return (0, 0)
        msmljuaejl = (
            self._dir,
            (self._dir - 1) % 4,
            (self._dir + 1) % 4,
            (self._dir + 2) % 4,
        )
        for acdeadlbzx in msmljuaejl:
            dx, dy = self.nakogfhyus(acdeadlbzx)
            rbaqncskoi = self._sprite.x + dx * self._cell
            uodlwwyprt = self._sprite.y + dy * self._cell
            if self.iiosonyanc(rbaqncskoi, uodlwwyprt):
                self._dir = acdeadlbzx
                return (dx, dy)
        return (0, 0)

    def step(self) -> bool:
        folqexnjmf = self._sprite.x
        yxlpsejtoh = self._sprite.y
        wsdeleuewc = self._dir
        dx, dy = self.npdjlrkhsg()
        if dx == 0 and dy == 0:
            self._undo_x = None
            self._undo_y = None
            self._undo_dir = None
            return False
        self._undo_x = folqexnjmf
        self._undo_y = yxlpsejtoh
        self._undo_dir = wsdeleuewc
        self._sprite.set_position(folqexnjmf + dx * self._cell, yxlpsejtoh + dy * self._cell)
        return True

    def fwtnsrvkrz(self) -> bool:
        if self._undo_x is None or self._undo_y is None or self._undo_dir is None:
            return False
        self._sprite.set_position(self._undo_x, self._undo_y)
        self._dir = self._undo_dir
        self._undo_x = None
        self._undo_y = None
        self._undo_dir = None
        return True

    def iiosonyanc(self, x: int, y: int) -> bool:
        if not self.bfdcztirdu:
            return False
        return self.vtfcqjvbeo(x, y) and self.uczkzlpcwg(x, y) >= 0

    def vtfcqjvbeo(self, x: int, y: int) -> bool:
        return x >= self.bfdcztirdu.x and y >= self.bfdcztirdu.y and (x < self.bfdcztirdu.x + self.bfdcztirdu.width) and (y < self.bfdcztirdu.y + self.bfdcztirdu.height)

    def uczkzlpcwg(self, x: int, y: int) -> int:
        akcoyirktv = x - self.bfdcztirdu.x
        cgpwxobidt = y - self.bfdcztirdu.y
        if akcoyirktv < 0 or akcoyirktv >= self.bfdcztirdu.width or cgpwxobidt < 0 or (cgpwxobidt >= self.bfdcztirdu.height):
            return -1
        return int(self.bfdcztirdu.pixels[cgpwxobidt, akcoyirktv])

    def nakogfhyus(self, acdeadlbzx: int) -> Tuple[int, int]:
        if acdeadlbzx == 0:
            return (0, -1)
        if acdeadlbzx == 1:
            return (-1, 0)
        if acdeadlbzx == 2:
            return (0, 1)
        return (1, 0)


class _Ly20Rules(ARCBaseGame):
    def __init__(self) -> None:
        shumwqpzsq = levels[0].get_data("StepCounter") if levels else 0
        osgviligwp = shumwqpzsq if shumwqpzsq else 0
        self._step_counter_ui = hbuhvkxlhc(self, osgviligwp)
        self.ijessuuig = []
        self.tnkekoeuk = [epqvqkpffo, jninpsotet, bejggpjowv, tqogkgimes]
        self.dhksvilbb = [0, 90, 180, 270]
        self.ijessuuig.append(sprites["gngifvjddu"])
        self.ijessuuig.append(sprites["fywfjzkxlm"])
        self.ijessuuig.append(sprites["mkfbgalsbe"])
        self.ijessuuig.append(sprites["nnjhdcanjk"])
        self.ijessuuig.append(sprites["grcpfuizfp"])
        self.ijessuuig.append(sprites["ubspnhafvq"])
        self.oeuabekjf = False
        xngzmcbxu = Camera(
            width=16,
            height=16,
            background=BACKGROUND_COLOR,
            letter_box=PADDING_COLOR,
            interfaces=[self._step_counter_ui],
        )
        super().__init__(game_id="ls20", levels=levels, camera=xngzmcbxu, available_actions=[1, 2, 3, 4])
        self.wbcenorpju()

    def wbcenorpju(self) -> None:
        """."""
        hgkhqetaxy = self.current_level.get_data("StepsDecrement")
        efipnixsvl = 2 if hgkhqetaxy is None else hgkhqetaxy
        self._step_counter_ui.vytykscvhe(efipnixsvl)
        rnaomksehd = self.current_level.get_data("StepCounter")
        if rnaomksehd:
            self._step_counter_ui.osgviligwp = rnaomksehd
            self._step_counter_ui.nzukewekzr()

    def on_set_level(self, level: Level) -> None:
        """."""
        self._levels[self._current_level_index] = self._clean_levels[self._current_level_index].clone()
        self.gudziatsk = self.current_level.get_sprites_by_tag("sfqyzhzkij")[0]
        self.gudziatsk.set_blocking(BlockingMode.BOUNDING_BOX)
        self.gisrhqpee = self.gudziatsk.width
        self.tbwnoxqgc = self.gudziatsk.height
        self.htkmubhry = self.current_level.get_sprites_by_tag("wgmbtyhvbc")[0]
        self.htkmubhry_2 = self.current_level.get_sprites_by_tag("eqatonpohu")[0]
        self.tsynhckng = self.current_level.get_sprites_by_tag("ghizzeqtoh")[0]
        self.srgbthxut = self.current_level.get_sprites_by_tag("kvynsvxbpi")
        self.plrpelhym = self.current_level.get_sprites_by_tag("rjlbuycveu")
        self.lvrnuajbl = [False] * len(self.srgbthxut)
        self.fwckfzsyc = 0
        self.hiaauhahz = 0
        self.cklxociuu = 0
        self.wbcenorpju()
        ezhluetmc = self.current_level.grid_size
        if ezhluetmc is not None:
            self.drtdqwdbc = ezhluetmc[0]
            self.qlgmdayuo = ezhluetmc[1]
        self.ehwheiwsk = []
        self.yjdexjsoa = []
        self.oeuabekjf = self.current_level.get_data("Fog")
        self.ldxlnycps = self.current_level.get_data("kvynsvxbpi")
        if isinstance(self.ldxlnycps, int):
            self.ldxlnycps = [self.ldxlnycps]
        ldgzgjdsrf = self.current_level.get_data("GoalRotation")
        if isinstance(ldgzgjdsrf, int):
            ldgzgjdsrf = [ldgzgjdsrf]
        lbgtuaplev = self.current_level.get_data("GoalColor")
        if isinstance(lbgtuaplev, int):
            lbgtuaplev = [lbgtuaplev]
        for dinyecvyq in range(len(self.plrpelhym)):
            self.ehwheiwsk.append(self.dhksvilbb.index(ldgzgjdsrf[dinyecvyq]))
            self.yjdexjsoa.append(self.tnkekoeuk.index(lbgtuaplev[dinyecvyq]))
            self.srgbthxut[dinyecvyq].pixels = self.ijessuuig[self.ldxlnycps[dinyecvyq]].pixels.copy()
            self.srgbthxut[dinyecvyq].color_remap(epeqflmtfc, self.tnkekoeuk[self.yjdexjsoa[dinyecvyq]])
            self.srgbthxut[dinyecvyq].set_rotation(self.dhksvilbb[self.ehwheiwsk[dinyecvyq]])
        self.qetwzqzzik()
        self.aqdxgoyvu = sprites["sqpmiygfvh"].clone()
        self.current_level.add_sprite(self.aqdxgoyvu)
        self.aqdxgoyvu.set_visible(False)
        self.aqygnziho = 3
        self.ofoahudlo: List[Sprite] = []
        self.byotxmvkt: List[Sprite] = []
        self.alsxlhizr: List[Sprite] = []
        self.ebfuxzbvn = 0
        self.akoadfsur = 0
        self.ltwrkifkx = self.gudziatsk.x
        self.zyoimjaei = self.gudziatsk.y
        self.wsoslqeku: List[dboxixicic] = []
        for uedjpektbg in self.current_level.get_sprites_by_tag("xfmluydglp"):
            for ocajwvfus in ("ttfwljgohq", "soyhouuebz", "rhsxkxzdjz"):
                for hasivfwip in self.current_level.get_sprites_by_tag(ocajwvfus):
                    if uedjpektbg.collides_with(hasivfwip, ignoreMode=True):
                        self.wsoslqeku.append(dboxixicic(uedjpektbg, hasivfwip))
        fjzuynaokm: Set[Tuple[int, int]] = set()
        for qoceexndvw in self.current_level.get_sprites_by_tag("ihdgageizm"):
            fjzuynaokm.add((qoceexndvw.x, qoceexndvw.y))
        for grbudvkafa in self.current_level.get_sprites_by_tag("rjlbuycveu"):
            fjzuynaokm.add((grbudvkafa.x, grbudvkafa.y))
        self.hasivfwip: List[twkzhcfelv] = []
        for ojwauijaoq in self.current_level.get_sprites_by_tag("gbvqrjtaqo"):
            self.hasivfwip.append(twkzhcfelv(ojwauijaoq, fjzuynaokm))
        self.euemavvxz: List[xajlyftlyn] = []

    def mrznumynfe(self, zccgflmau: int, qoxqcbqfp: int, xzejejszi: int, eutrvdkbx: int) -> List[Sprite]:
        """."""
        ehiovmywu = self.current_level._sprites
        return [xfemxgpuj for xfemxgpuj in ehiovmywu if xfemxgpuj.x >= zccgflmau and xfemxgpuj.x < zccgflmau + xzejejszi and (xfemxgpuj.y >= qoxqcbqfp) and (xfemxgpuj.y < qoxqcbqfp + eutrvdkbx)]

    def txnfzvzetn(self, juldcpkjse: int, ullicjtklz: int) -> Tuple[bool, bool]:
        ttiyzlpkgh = self.mrznumynfe(juldcpkjse, ullicjtklz, self.gisrhqpee, self.tbwnoxqgc)
        bwdzgjttjp = False
        yubyobdoss = False
        for mvcsnkcqz in ttiyzlpkgh:
            if mvcsnkcqz.tags is None:
                break
            elif "ihdgageizm" in mvcsnkcqz.tags:
                bwdzgjttjp = True
                break
            elif "rjlbuycveu" in mvcsnkcqz.tags:
                wyhfvzxukh = self.plrpelhym.index(mvcsnkcqz)
                if not self.bejndxqqzf(wyhfvzxukh):
                    self.htkmubhry_2.color_remap(None, epeqflmtfc)
                    self.akoadfsur = zoghkczvvt
                    bwdzgjttjp = True
            elif "npxgalaybz" in mvcsnkcqz.tags:
                yubyobdoss = True
                self._step_counter_ui.kbkdzqocik(self._step_counter_ui.osgviligwp)
                self.ofoahudlo.append(mvcsnkcqz)
                self.current_level.remove_sprite(mvcsnkcqz)
            elif "ttfwljgohq" in mvcsnkcqz.tags:
                self.fwckfzsyc = (self.fwckfzsyc + 1) % len(self.ijessuuig)
                self.htkmubhry.pixels = self.ijessuuig[self.fwckfzsyc].pixels.copy()
                self.htkmubhry.color_remap(epeqflmtfc, self.tnkekoeuk[self.hiaauhahz])
                if self.vqfjzzkhid():
                    self.akoadfsur = zoghkczvvt
            elif "soyhouuebz" in mvcsnkcqz.tags:
                lwphyolnjb = (self.hiaauhahz + 1) % len(self.tnkekoeuk)
                self.htkmubhry.color_remap(self.tnkekoeuk[self.hiaauhahz], self.tnkekoeuk[lwphyolnjb])
                self.hiaauhahz = lwphyolnjb
                if self.vqfjzzkhid():
                    self.akoadfsur = zoghkczvvt
            elif "rhsxkxzdjz" in mvcsnkcqz.tags:
                self.cklxociuu = (self.cklxociuu + 1) % 4
                self.htkmubhry.set_rotation(self.dhksvilbb[self.cklxociuu])
                if self.vqfjzzkhid():
                    self.akoadfsur = zoghkczvvt
        return (bwdzgjttjp, yubyobdoss)

    def step(self) -> None:
        if self.euemavvxz:
            for i in range(len(self.euemavvxz) - 1, -1, -1):
                kgppvertad = self.euemavvxz[i]
                if not kgppvertad.wgxrzqzazj():
                    del self.euemavvxz[i]
            if not self.euemavvxz:
                self.txnfzvzetn(self.gudziatsk.x, self.gudziatsk.y)
                self.complete_action()
            return
        if self.ebfuxzbvn > 0:
            self.ebfuxzbvn -= 1
            if self.ebfuxzbvn > 0:
                return
            self.aqdxgoyvu.set_visible(False)
            self.htkmubhry.set_visible(True)
            self.complete_action()
            return
        if self.akoadfsur > 0:
            self.akoadfsur -= 1
            if self.akoadfsur > 0:
                return
            self.htkmubhry_2.color_remap(None, avbdwkmqcy)
            self.tsynhckng.set_visible(False)
            for pidqulszaw in self.current_level.get_sprites_by_tag("hoswmpiqkw"):
                pidqulszaw.set_visible(False)
            self.complete_action()
            return
        hnrvmfooc = 0
        feyjbrwyb = 0
        etvjlacrau = False
        if self.action.id == GameAction.ACTION1:
            feyjbrwyb = -1
            etvjlacrau = True
        elif self.action.id == GameAction.ACTION2:
            feyjbrwyb = 1
            etvjlacrau = True
        elif self.action.id == GameAction.ACTION3:
            hnrvmfooc = -1
            etvjlacrau = True
        elif self.action.id == GameAction.ACTION4:
            hnrvmfooc = 1
            etvjlacrau = True
        if not etvjlacrau:
            self.complete_action()
            return
        for arilbvrrme in self.wsoslqeku:
            arilbvrrme.step()
        juldcpkjse, ullicjtklz = (
            self.gudziatsk.x + hnrvmfooc * self.gisrhqpee,
            self.gudziatsk.y + feyjbrwyb * self.tbwnoxqgc,
        )
        bwdzgjttjp, yubyobdoss = self.txnfzvzetn(juldcpkjse, ullicjtklz)
        if not bwdzgjttjp:
            self.gudziatsk.set_position(juldcpkjse, ullicjtklz)
        else:
            for arilbvrrme in self.wsoslqeku:
                arilbvrrme.fwtnsrvkrz()
        if self.akoadfsur:
            return
        bkuguqrpvq = not yubyobdoss and (not self._step_counter_ui.mfyzdfvxsm())
        if not bkuguqrpvq:
            for shdkimnqse in self.hasivfwip:
                if shdkimnqse.prpxgfxlcm(self.gudziatsk):
                    self.euemavvxz.append(shdkimnqse)
                    return
        if self.pbznecvnfr():
            self.next_level()
            self.complete_action()
            return
        if bkuguqrpvq:
            self.aqygnziho -= 1
            if self.aqygnziho == 0:
                self.lose()
                self.complete_action()
                return
            self.aqdxgoyvu.set_visible(True)
            self.aqdxgoyvu.set_scale(64)
            self.aqdxgoyvu.set_position(0, 0)
            self.htkmubhry.set_visible(False)
            self.ebfuxzbvn = xvzyzqolqz
            self.lvrnuajbl = [False] * len(self.plrpelhym)
            self.gudziatsk.set_position(self.ltwrkifkx, self.zyoimjaei)
            self.qetwzqzzik()
            for iybkldaxol in self.ofoahudlo:
                self.current_level.add_sprite(iybkldaxol)
            for spssohsnbq in self.byotxmvkt:
                self.current_level.add_sprite(spssohsnbq)
            for lztoedneuu in self.alsxlhizr:
                self.current_level.add_sprite(lztoedneuu)
            self.ofoahudlo = []
            self.byotxmvkt = []
            self.alsxlhizr = []
            self._step_counter_ui.kbkdzqocik(self._step_counter_ui.osgviligwp)
            self.tsynhckng.set_visible(False)
            for pidqulszaw in self.current_level.get_sprites_by_tag("hoswmpiqkw"):
                pidqulszaw.set_visible(False)
            for opdsmckaqo in self.current_level.get_sprites_by_tag("vjotnebuqo"):
                opdsmckaqo.set_visible(True)
            for arilbvrrme in self.wsoslqeku:
                arilbvrrme.bkuguqrpvq()
            return
        self.complete_action()

    def qetwzqzzik(self) -> None:
        self.cklxociuu = self.dhksvilbb.index(self.current_level.get_data("StartRotation"))
        self.hiaauhahz = self.tnkekoeuk.index(self.current_level.get_data("StartColor"))
        self.fwckfzsyc = self.current_level.get_data("StartShape")
        self.htkmubhry.pixels = self.ijessuuig[self.fwckfzsyc].pixels.copy()
        self.htkmubhry.color_remap(epeqflmtfc, self.tnkekoeuk[self.hiaauhahz])
        self.htkmubhry.set_rotation(self.dhksvilbb[self.cklxociuu])

    def vqfjzzkhid(self) -> bool:
        if self.level_index > 0:
            return False
        uhftkonsvn = False
        for wyhfvzxukh, spssohsnbq in enumerate(self.plrpelhym):
            pidqulszaw = self.current_level.get_sprite_at(spssohsnbq.x - 1, spssohsnbq.y - 1, "hoswmpiqkw")
            if self.bejndxqqzf(wyhfvzxukh) and (not self.lvrnuajbl[wyhfvzxukh]):
                uhftkonsvn = True
                if pidqulszaw:
                    pidqulszaw.set_visible(True)
            elif pidqulszaw:
                pidqulszaw.set_visible(False)
        self.tsynhckng.set_visible(uhftkonsvn)
        return uhftkonsvn

    def bejndxqqzf(self, wyhfvzxukh: int) -> bool:
        return self.fwckfzsyc == self.ldxlnycps[wyhfvzxukh] and self.hiaauhahz == self.yjdexjsoa[wyhfvzxukh] and (self.cklxociuu == self.ehwheiwsk[wyhfvzxukh])

    def pbznecvnfr(self) -> bool:
        for i, spssohsnbq in enumerate(self.plrpelhym):
            if not self.lvrnuajbl[i] and self.gudziatsk.x == spssohsnbq.x and (self.gudziatsk.y == spssohsnbq.y) and self.bejndxqqzf(i):
                self.lvrnuajbl[i] = True
                self.byotxmvkt.append(self.plrpelhym[i])
                self.alsxlhizr.append(self.srgbthxut[i])
                self.current_level.remove_sprite(self.plrpelhym[i])
                self.current_level.remove_sprite(self.srgbthxut[i])
                opdsmckaqo = self.current_level.get_sprite_at(spssohsnbq.x - 1, spssohsnbq.y - 1, "vjotnebuqo")
                if opdsmckaqo and "vfkkzdgxzx" in opdsmckaqo.tags:
                    opdsmckaqo.set_visible(False)
                    pidqulszaw = self.current_level.get_sprite_at(spssohsnbq.x - 1, spssohsnbq.y - 1, "hoswmpiqkw")
                    if pidqulszaw:
                        pidqulszaw.set_visible(False)
                    self.tsynhckng.set_visible(False)
        for i in range(len(self.lvrnuajbl)):
            if not self.lvrnuajbl[i]:
                return False
        return True


# ── copycat layer ───────────────────────────────────────────────────────────────
# Colour assignment for this copycat: displayed colour = _CC_PALETTE[engine colour].
# Applied to the camera's final 64x64 output only, so the game's own rules (some of which
# read sprite colours) are untouched.
_CC_PALETTE = np.array([11, 9, 8, 10, 5, 3, 15, 4, 6, 7, 0, 2, 13, 1, 12, 14], dtype=np.int8)


class _CcCamera(Camera):
    def render(self, sprites):
        frame = super().render(sprites)
        frame = np.asarray(frame)
        out = frame.copy()
        mask = (frame >= 0) & (frame <= 15)
        out[mask] = _CC_PALETTE[frame[mask].astype(np.int64)]
        return out


class Ly20(_Ly20Rules):
    def __init__(self) -> None:
        super().__init__()
        if type(self._camera) is Camera:
            self._camera.__class__ = _CcCamera
        if not isinstance(self._camera, _CcCamera):
            raise RuntimeError("copycat palette camera not installed")
        self._game_id = 'ly20'

# Copycat mxr0: rules of public ARC-AGI-3 game m0r0, new maps, colours and art.
# Built and verified by autoresearch-arena arc3games/copycats/cc_m0r0.py.
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

import numpy as np
from arcengine import (
    BlockingMode,
    ARCBaseGame,
    Camera,
    GameAction,
    InteractionMode,
    Level,
    RenderableUserDisplay,
    Sprite,
)

sprites = {
    'gayktr-grwjuk': Sprite(
        pixels=[
        [14],
        [14],
        [14],
    ],
        name='gayktr-grwjuk',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
    ),
    'gayktr-orfrpe': Sprite(
        pixels=[
        [12],
        [12],
        [12],
    ],
        name='gayktr-orfrpe',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
    ),
    'gayktr-puvdux': Sprite(
        pixels=[
        [15],
        [15],
        [15],
    ],
        name='gayktr-puvdux',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
    ),
    'mosdlc': Sprite(
        pixels=[
        [9],
    ],
        name='mosdlc',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['sys_click', 'xbso'],
    ),
    'pikgci-boweok-leklkn': Sprite(
        pixels=[
        [10],
    ],
        name='pikgci-boweok-leklkn',
        layer=2,
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['sys_click'],
    ),
    'pikgci-boweok-rivmdg': Sprite(
        pixels=[
        [10],
    ],
        name='pikgci-boweok-rivmdg',
        layer=2,
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['sys_click'],
    ),
    'pikgci-toljda-leklkn': Sprite(
        pixels=[
        [10],
    ],
        name='pikgci-toljda-leklkn',
        layer=2,
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['sys_click', 'fucr'],
    ),
    'pikgci-toljda-rivmdg': Sprite(
        pixels=[
        [10],
    ],
        name='pikgci-toljda-rivmdg',
        layer=2,
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['sys_click', 'fucr'],
    ),
    'spswjz': Sprite(
        pixels=[
        [8],
    ],
        name='spswjz',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['spswjz'],
    ),
    'unobxw-grwjuk': Sprite(
        pixels=[
        [14],
    ],
        name='unobxw-grwjuk',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
    ),
    'unobxw-orfrpe': Sprite(
        pixels=[
        [12],
    ],
        name='unobxw-orfrpe',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
    ),
    'unobxw-puvdux': Sprite(
        pixels=[
        [15],
    ],
        name='unobxw-puvdux',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
    ),
}
levels = [
    # Level 1
    Level(
        sprites=[
            sprites['pikgci-toljda-leklkn'].clone().set_position(5, 3),
            sprites['pikgci-toljda-rivmdg'].clone().set_position(9, 3),
            Sprite(
                pixels=[
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                [0, 0, 0, 0, -1, 0, -1, 0, 0, 0, -1, 0, 0, 0, 0],
                [0, 0, -1, 0, 0, 0, -1, 0, 0, -1, 0, 0, 0, 0, 0],
                [0, 0, 0, -1, 0, -1, -1, 0, -1, -1, 0, 0, -1, 0, 0],
                [0, 0, 0, -1, -1, -1, -1, 0, 0, -1, -1, -1, -1, 0, 0],
                [0, 0, 0, -1, 0, 0, -1, 0, -1, 0, -1, -1, 0, 0, 0],
                [0, 0, 0, -1, -1, 0, 0, 0, 0, 0, 0, -1, -1, 0, 0],
                [0, 0, -1, 0, -1, 0, 0, 0, 0, 0, -1, -1, -1, 0, 0],
                [0, 0, 0, -1, -1, 0, -1, 0, 0, 0, -1, -1, 0, 0, 0],
                [0, 0, -1, -1, -1, -1, -1, -1, 0, -1, -1, -1, 0, 0, 0],
                [0, 0, 0, 0, -1, -1, -1, 0, -1, 0, -1, 0, -1, 0, 0],
                [0, 0, 0, -1, 0, -1, -1, -1, -1, -1, -1, 0, 0, 0, 0],
                [0, 0, 0, 0, -1, 0, 0, 0, 0, -1, 0, -1, 0, 0, 0],
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            ],
                name='wahtyt-Level1',
                blocking=BlockingMode.PIXEL_PERFECT,
                interaction=InteractionMode.TANGIBLE,
                tags=['wahtyt'],
            ),
        ],
        grid_size=(15, 15),
        data={'psqw': [11, 12]},
    ),
    # Level 2
    Level(
        sprites=[
            sprites['pikgci-toljda-leklkn'].clone().set_position(6, 13),
            sprites['pikgci-toljda-rivmdg'].clone().set_position(10, 13),
            sprites['spswjz'].clone().set_position(2, 2),
            sprites['spswjz'].clone().set_position(2, 6),
            sprites['spswjz'].clone().set_position(3, 2),
            sprites['spswjz'].clone().set_position(3, 6),
            sprites['spswjz'].clone().set_position(4, 2),
            sprites['spswjz'].clone().set_position(4, 6),
            sprites['spswjz'].clone().set_position(5, 2),
            sprites['spswjz'].clone().set_position(6, 2),
            sprites['spswjz'].clone().set_position(6, 6),
            sprites['spswjz'].clone().set_position(7, 2),
            sprites['spswjz'].clone().set_position(7, 6),
            sprites['spswjz'].clone().set_position(7, 7),
            sprites['spswjz'].clone().set_position(7, 8),
            sprites['spswjz'].clone().set_position(7, 9),
            sprites['spswjz'].clone().set_position(8, 2),
            sprites['spswjz'].clone().set_position(9, 2),
            sprites['spswjz'].clone().set_position(10, 2),
            sprites['spswjz'].clone().set_position(10, 6),
            sprites['spswjz'].clone().set_position(11, 2),
            sprites['spswjz'].clone().set_position(11, 6),
            sprites['spswjz'].clone().set_position(12, 2),
            sprites['spswjz'].clone().set_position(12, 6),
            sprites['spswjz'].clone().set_position(13, 2),
            sprites['spswjz'].clone().set_position(13, 6),
            sprites['spswjz'].clone().set_position(14, 2),
            sprites['spswjz'].clone().set_position(14, 6),
            Sprite(
                pixels=[
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                [0, -1, -1, 0, -1, 0, 0, 0, 0, 0, -1, 0, -1, 0, -1, 0, 0],
                [0, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, 0],
                [0, 0, -1, -1, 0, 0, 0, -1, -1, 0, -1, -1, -1, -1, -1, 0, 0],
                [0, -1, -1, 0, -1, -1, 0, -1, -1, -1, -1, -1, 0, 0, -1, -1, 0],
                [0, 0, 0, -1, -1, -1, -1, -1, 0, -1, -1, -1, 0, 0, -1, 0, 0],
                [0, 0, -1, -1, -1, -1, -1, -1, 0, -1, -1, -1, -1, -1, -1, 0, 0],
                [0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, 0, 0],
                [0, 0, -1, -1, -1, -1, -1, -1, 0, -1, -1, -1, -1, -1, -1, 0, 0],
                [0, 0, -1, -1, 0, -1, -1, -1, -1, -1, 0, -1, -1, 0, -1, 0, 0],
                [0, 0, -1, -1, -1, -1, -1, 0, 0, -1, 0, -1, 0, -1, -1, -1, 0],
                [0, -1, -1, -1, -1, 0, 0, -1, -1, 0, 0, 0, 0, -1, -1, 0, 0],
                [0, -1, 0, -1, -1, -1, -1, -1, 0, -1, -1, -1, 0, 0, -1, 0, 0],
                [0, -1, -1, -1, 0, -1, -1, -1, 0, 0, -1, -1, 0, -1, -1, -1, 0],
                [0, -1, 0, 0, -1, -1, 0, -1, 0, 0, 0, -1, -1, -1, 0, -1, 0],
                [0, 0, -1, 0, 0, -1, 0, -1, -1, 0, -1, 0, -1, 0, 0, -1, 0],
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            ],
                name='wahtyt-Level2',
                blocking=BlockingMode.PIXEL_PERFECT,
                interaction=InteractionMode.TANGIBLE,
                tags=['wahtyt'],
            ),
        ],
        grid_size=(17, 17),
        data={'psqw': [6, 15]},
    ),
    # Level 3
    Level(
        sprites=[
            sprites['mosdlc'].clone().set_position(3, 11),
            sprites['mosdlc'].clone().set_position(8, 12),
            sprites['mosdlc'].clone().set_position(10, 8),
            sprites['pikgci-toljda-leklkn'].clone().set_position(6, 4),
            sprites['pikgci-toljda-rivmdg'].clone().set_position(10, 4),
            Sprite(
                pixels=[
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                [0, 0, 0, 0, -1, 0, -1, 0, -1, -1, 0, 0, 0, 0, -1, 0, 0],
                [0, 0, 0, 0, -1, -1, -1, -1, 0, -1, -1, -1, -1, -1, -1, 0, 0],
                [0, 0, 0, 0, -1, -1, -1, -1, 0, -1, -1, -1, -1, -1, 0, 0, 0],
                [0, 0, 0, -1, -1, -1, -1, -1, 0, -1, -1, -1, -1, -1, 0, 0, 0],
                [0, 0, 0, 0, 0, 0, 0, -1, 0, -1, -1, 0, -1, 0, 0, 0, 0],
                [0, 0, -1, -1, -1, -1, -1, -1, 0, 0, 0, 0, -1, -1, 0, 0, 0],
                [0, 0, 0, -1, 0, 0, 0, 0, 0, -1, -1, -1, -1, -1, 0, 0, 0],
                [0, 0, 0, -1, 0, -1, -1, -1, 0, -1, 0, 0, 0, 0, 0, 0, 0],
                [0, 0, 0, -1, 0, -1, 0, -1, 0, -1, -1, -1, -1, -1, 0, 0, 0],
                [0, 0, 0, -1, 0, -1, 0, -1, 0, 0, 0, -1, 0, -1, 0, 0, 0],
                [0, 0, 0, -1, -1, -1, 0, -1, -1, -1, 0, 0, 0, -1, 0, 0, 0],
                [0, 0, 0, 0, -1, 0, 0, 0, 0, -1, -1, -1, -1, -1, 0, 0, 0],
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            ],
                name='wahtyt-Level3',
                blocking=BlockingMode.PIXEL_PERFECT,
                interaction=InteractionMode.TANGIBLE,
                tags=['wahtyt'],
            ),
        ],
        grid_size=(17, 17),
        data={'psqw': [15, 8]},
    ),
    # Level 4
    Level(
        sprites=[
            sprites['mosdlc'].clone().set_position(7, 7),
            sprites['pikgci-toljda-leklkn'].clone().set_position(4, 6),
            sprites['pikgci-toljda-rivmdg'].clone().set_position(10, 8),
            sprites['spswjz'].clone().set_position(3, 3),
            sprites['spswjz'].clone().set_position(3, 11),
            sprites['spswjz'].clone().set_position(4, 3),
            sprites['spswjz'].clone().set_position(4, 11),
            sprites['spswjz'].clone().set_position(5, 3),
            sprites['spswjz'].clone().set_position(5, 11),
            sprites['spswjz'].clone().set_position(6, 6),
            sprites['spswjz'].clone().set_position(6, 8),
            sprites['spswjz'].clone().set_position(7, 6),
            sprites['spswjz'].clone().set_position(7, 8),
            sprites['spswjz'].clone().set_position(8, 6),
            sprites['spswjz'].clone().set_position(8, 8),
            sprites['spswjz'].clone().set_position(9, 3),
            sprites['spswjz'].clone().set_position(9, 11),
            sprites['spswjz'].clone().set_position(10, 3),
            sprites['spswjz'].clone().set_position(10, 11),
            sprites['spswjz'].clone().set_position(11, 3),
            sprites['spswjz'].clone().set_position(11, 11),
            Sprite(
                pixels=[
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, -1, 0, 0, 0, 0],
                [0, 0, 0, -1, -1, -1, -1, 0, -1, -1, -1, -1, -1, 0, 0],
                [0, 0, 0, -1, -1, -1, -1, 0, -1, -1, 0, -1, 0, 0, 0],
                [0, 0, 0, 0, -1, -1, -1, 0, -1, 0, 0, -1, 0, 0, 0],
                [0, 0, 0, -1, -1, -1, -1, -1, -1, 0, -1, -1, -1, 0, 0],
                [0, 0, 0, -1, -1, -1, -1, -1, -1, -1, 0, 0, 0, 0, 0],
                [0, 0, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, 0],
                [0, 0, -1, 0, 0, -1, 0, 0, -1, -1, -1, -1, 0, 0, 0],
                [0, 0, 0, -1, -1, -1, -1, 0, 0, 0, -1, 0, -1, 0, 0],
                [0, 0, 0, -1, -1, -1, 0, 0, 0, -1, -1, -1, 0, 0, 0],
                [0, 0, 0, -1, -1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            ],
                name='wahtyt-Level4',
                blocking=BlockingMode.PIXEL_PERFECT,
                interaction=InteractionMode.TANGIBLE,
                tags=['wahtyt'],
            ),
        ],
        grid_size=(15, 15),
        data={'psqw': [11, 15]},
    ),
    # Level 5
    Level(
        sprites=[
            sprites['pikgci-toljda-leklkn'].clone().set_position(15, 4),
            sprites['pikgci-toljda-rivmdg'].clone().set_position(3, 4),
            Sprite(
                pixels=[
                [14, 14, 14],
            ],
                name='gayktr-grwjuk',
                x=5,
                y=11,
                blocking=BlockingMode.PIXEL_PERFECT,
                interaction=InteractionMode.TANGIBLE,
            ),
            Sprite(
                pixels=[
                [12, 12, 12],
            ],
                name='gayktr-orfrpe',
                x=4,
                y=7,
                blocking=BlockingMode.PIXEL_PERFECT,
                interaction=InteractionMode.TANGIBLE,
            ),
            Sprite(
                pixels=[
                [15, 15, 15],
            ],
                name='gayktr-puvdux',
                x=12,
                y=7,
                blocking=BlockingMode.PIXEL_PERFECT,
                interaction=InteractionMode.TANGIBLE,
            ),
            Sprite(
                pixels=[
                [15, 15, 15],
            ],
                name='gayktr-puvdux',
                x=12,
                y=11,
                blocking=BlockingMode.PIXEL_PERFECT,
                interaction=InteractionMode.TANGIBLE,
            ),
            sprites['unobxw-grwjuk'].clone().set_position(10, 10),
            sprites['unobxw-orfrpe'].clone().set_position(16, 10),
            sprites['unobxw-puvdux'].clone().set_position(5, 4),
            sprites['unobxw-puvdux'].clone().set_position(5, 15),
            Sprite(
                pixels=[
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                [0, 0, -1, 0, 0, 0, 0, -1, -1, -1, 0, 0, 0, -1, 0, -1, -1, -1, 0],
                [0, 0, -1, 0, 0, 0, -1, -1, -1, 0, -1, -1, -1, -1, -1, -1, 0, 0, 0],
                [0, -1, 0, -1, 0, -1, -1, -1, -1, 0, -1, -1, -1, -1, -1, -1, -1, 0, 0],
                [0, 0, -1, -1, -1, -1, -1, 0, -1, 0, 0, -1, -1, -1, -1, -1, -1, -1, 0],
                [0, 0, 0, 0, -1, -1, -1, -1, 0, -1, 0, -1, 0, -1, 0, -1, 0, -1, 0],
                [0, -1, 0, 0, -1, -1, -1, 0, 0, -1, -1, 0, -1, -1, -1, 0, -1, -1, 0],
                [0, -1, -1, 0, -1, -1, -1, 0, -1, 0, -1, 0, -1, -1, 0, 0, -1, -1, 0],
                [0, -1, -1, -1, 0, -1, -1, -1, -1, -1, 0, -1, -1, -1, 0, -1, 0, 0, 0],
                [0, 0, 0, -1, -1, 0, -1, 0, -1, 0, -1, -1, -1, -1, -1, -1, -1, 0, 0],
                [0, 0, 0, 0, 0, -1, -1, -1, -1, -1, 0, 0, -1, -1, -1, 0, 0, 0, 0],
                [0, 0, 0, -1, -1, -1, 0, 0, 0, 0, -1, -1, -1, -1, -1, -1, -1, 0, 0],
                [0, 0, 0, 0, 0, -1, -1, -1, -1, -1, -1, 0, -1, -1, -1, -1, -1, 0, 0],
                [0, 0, -1, -1, -1, -1, -1, -1, -1, 0, 0, -1, -1, -1, -1, -1, -1, 0, 0],
                [0, 0, -1, 0, -1, -1, -1, 0, -1, -1, -1, -1, -1, 0, 0, -1, -1, -1, 0],
                [0, 0, 0, 0, 0, -1, 0, -1, 0, 0, -1, -1, 0, -1, -1, 0, 0, 0, 0],
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            ],
                name='wahtyt-Level5',
                blocking=BlockingMode.PIXEL_PERFECT,
                interaction=InteractionMode.TANGIBLE,
                tags=['wahtyt'],
            ),
        ],
        grid_size=(19, 19),
        data={'psqw': [6, 7]},
    ),
    # Level 6
    Level(
        sprites=[
            sprites['mosdlc'].clone().set_position(8, 5),
            sprites['pikgci-toljda-leklkn'].clone().set_position(5, 10),
            sprites['pikgci-toljda-rivmdg'].clone().set_position(11, 10),
            sprites['spswjz'].clone().set_position(2, 2),
            sprites['spswjz'].clone().set_position(2, 3),
            sprites['spswjz'].clone().set_position(2, 4),
            sprites['spswjz'].clone().set_position(2, 5),
            sprites['spswjz'].clone().set_position(2, 6),
            sprites['spswjz'].clone().set_position(2, 7),
            sprites['spswjz'].clone().set_position(2, 8),
            sprites['spswjz'].clone().set_position(2, 9),
            sprites['spswjz'].clone().set_position(2, 10),
            sprites['spswjz'].clone().set_position(2, 11),
            sprites['spswjz'].clone().set_position(2, 12),
            sprites['spswjz'].clone().set_position(2, 13),
            sprites['spswjz'].clone().set_position(2, 14),
            sprites['spswjz'].clone().set_position(3, 2),
            sprites['spswjz'].clone().set_position(3, 8),
            sprites['spswjz'].clone().set_position(3, 14),
            sprites['spswjz'].clone().set_position(4, 2),
            sprites['spswjz'].clone().set_position(4, 14),
            sprites['spswjz'].clone().set_position(5, 2),
            sprites['spswjz'].clone().set_position(5, 14),
            sprites['spswjz'].clone().set_position(6, 2),
            sprites['spswjz'].clone().set_position(6, 14),
            sprites['spswjz'].clone().set_position(7, 2),
            sprites['spswjz'].clone().set_position(7, 8),
            sprites['spswjz'].clone().set_position(7, 14),
            sprites['spswjz'].clone().set_position(8, 2),
            sprites['spswjz'].clone().set_position(8, 3),
            sprites['spswjz'].clone().set_position(8, 4),
            sprites['spswjz'].clone().set_position(8, 6),
            sprites['spswjz'].clone().set_position(8, 7),
            sprites['spswjz'].clone().set_position(8, 8),
            sprites['spswjz'].clone().set_position(8, 9),
            sprites['spswjz'].clone().set_position(8, 10),
            sprites['spswjz'].clone().set_position(8, 11),
            sprites['spswjz'].clone().set_position(8, 12),
            sprites['spswjz'].clone().set_position(8, 13),
            sprites['spswjz'].clone().set_position(8, 14),
            sprites['spswjz'].clone().set_position(9, 2),
            sprites['spswjz'].clone().set_position(9, 8),
            sprites['spswjz'].clone().set_position(9, 14),
            sprites['spswjz'].clone().set_position(10, 2),
            sprites['spswjz'].clone().set_position(10, 14),
            sprites['spswjz'].clone().set_position(11, 2),
            sprites['spswjz'].clone().set_position(11, 14),
            sprites['spswjz'].clone().set_position(12, 2),
            sprites['spswjz'].clone().set_position(12, 14),
            sprites['spswjz'].clone().set_position(13, 2),
            sprites['spswjz'].clone().set_position(13, 8),
            sprites['spswjz'].clone().set_position(13, 14),
            sprites['spswjz'].clone().set_position(14, 2),
            sprites['spswjz'].clone().set_position(14, 3),
            sprites['spswjz'].clone().set_position(14, 4),
            sprites['spswjz'].clone().set_position(14, 5),
            sprites['spswjz'].clone().set_position(14, 6),
            sprites['spswjz'].clone().set_position(14, 7),
            sprites['spswjz'].clone().set_position(14, 8),
            sprites['spswjz'].clone().set_position(14, 9),
            sprites['spswjz'].clone().set_position(14, 10),
            sprites['spswjz'].clone().set_position(14, 11),
            sprites['spswjz'].clone().set_position(14, 12),
            sprites['spswjz'].clone().set_position(14, 13),
            sprites['spswjz'].clone().set_position(14, 14),
            Sprite(
                pixels=[
                [14, 14, 14],
            ],
                name='gayktr-grwjuk',
                x=4,
                y=8,
                blocking=BlockingMode.PIXEL_PERFECT,
                interaction=InteractionMode.TANGIBLE,
            ),
            Sprite(
                pixels=[
                [12, 12, 12],
            ],
                name='gayktr-orfrpe',
                x=10,
                y=8,
                blocking=BlockingMode.PIXEL_PERFECT,
                interaction=InteractionMode.TANGIBLE,
            ),
            sprites['unobxw-grwjuk'].clone().set_position(11, 12),
            sprites['unobxw-grwjuk'].clone().set_position(5, 5),
            sprites['unobxw-orfrpe'].clone().set_position(5, 12),
            Sprite(
                pixels=[
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                [0, 0, 0, -1, -1, 0, 0, -1, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                [0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, 0],
                [0, 0, -1, -1, -1, -1, 0, -1, -1, -1, -1, 0, -1, 0, -1, 0, 0],
                [0, 0, -1, -1, -1, -1, -1, -1, -1, -1, 0, -1, 0, 0, -1, -1, 0],
                [0, 0, -1, -1, -1, -1, -1, -1, -1, -1, 0, 0, -1, 0, -1, 0, 0],
                [0, -1, -1, 0, -1, -1, 0, -1, -1, -1, -1, 0, -1, -1, -1, 0, 0],
                [0, -1, -1, -1, 0, -1, -1, -1, -1, -1, -1, -1, 0, 0, -1, -1, 0],
                [0, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0],
                [0, -1, -1, 0, -1, 0, -1, -1, -1, -1, -1, 0, -1, 0, -1, 0, 0],
                [0, 0, -1, 0, 0, -1, -1, -1, -1, -1, -1, -1, 0, -1, -1, 0, 0],
                [0, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, -1, 0, 0],
                [0, 0, -1, -1, -1, -1, -1, -1, -1, -1, 0, -1, -1, -1, -1, 0, 0],
                [0, 0, -1, -1, -1, 0, 0, -1, -1, -1, 0, 0, -1, -1, -1, 0, 0],
                [0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0],
                [0, 0, -1, 0, 0, 0, -1, -1, -1, 0, 0, 0, 0, 0, 0, -1, 0],
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            ],
                name='wahtyt-Level6',
                blocking=BlockingMode.PIXEL_PERFECT,
                interaction=InteractionMode.TANGIBLE,
                tags=['wahtyt'],
            ),
        ],
        grid_size=(17, 17),
        data={'psqw': [6, 7]},
    ),
]
BACKGROUND_COLOR = 5
PADDING_COLOR = 0


class ckpxigfdkg(RenderableUserDisplay):
    """."""

    def __init__(self, fmdcmwxxau: int):
        """."""
        self.fmdcmwxxau = fmdcmwxxau
        self.current_steps = fmdcmwxxau

    def uzcyzamlne(self, gxeeoevgfl: int) -> None:
        """."""
        self.current_steps = max(0, min(gxeeoevgfl, self.fmdcmwxxau))

    def render_interface(self, frame: np.ndarray) -> np.ndarray:
        """."""
        if self.fmdcmwxxau == 0:
            return frame
        okyxymlaxu = self.current_steps / self.fmdcmwxxau
        ugmolyjptb = round(64 * okyxymlaxu)
        ugmolyjptb = min(ugmolyjptb, 64)
        for x in range(64):
            if x < ugmolyjptb:
                frame[x, 0] = 5
            else:
                frame[x, 0] = 0
        for x in range(64):
            if 63 - x < ugmolyjptb:
                frame[x, 63] = 5
            else:
                frame[x, 63] = 0
        return frame


class uuyjjjqcvy(RenderableUserDisplay):
    """."""

    def __init__(self, nbisasgkdo: "_Mxr0Rules") -> None:
        self.nbisasgkdo = nbisasgkdo

    def render_interface(self, frame: np.ndarray) -> np.ndarray:
        """."""
        rhvrjrsria = self.nbisasgkdo.current_level.get_data("psqw")
        if rhvrjrsria and len(rhvrjrsria) >= 2:
            color1, color2 = (rhvrjrsria[0], rhvrjrsria[1])
            moypuorxop = frame == 0
            if np.any(moypuorxop):
                zyulynzacx = 0
                for kpaxgykyfg in [
                    "pikgci-toljda-leklkn",
                    "pikgci-toljda-rivmdg",
                    "pikgci-boweok-leklkn",
                    "pikgci-boweok-rivmdg",
                ]:
                    if kpaxgykyfg not in self.nbisasgkdo.okpvcjupabr:
                        sprites = self.nbisasgkdo.current_level.get_sprites_by_name(kpaxgykyfg)
                        if sprites and sprites[0].interaction != InteractionMode.REMOVED:
                            zyulynzacx += 1
                pvrabjchrn = np.zeros((64, 64), dtype=np.int8)
                if zyulynzacx == 4:
                    pvrabjchrn[:32, :32] = color1
                    pvrabjchrn[:32, 32:] = color2
                    pvrabjchrn[32:, :32] = color2
                    pvrabjchrn[32:, 32:] = color1
                else:
                    pvrabjchrn[:, :32] = color1
                    pvrabjchrn[:, 32:] = color2
                frame[moypuorxop] = pvrabjchrn[moypuorxop]
        grid_width, grid_height = self.nbisasgkdo.current_level.grid_size or (64, 64)
        scale_x = 64 // grid_width
        scale_y = 64 // grid_height
        scale = min(scale_x, scale_y)
        scaled_width = grid_width * scale
        scaled_height = grid_height * scale
        x_offset = (64 - scaled_width) // 2
        y_offset = (64 - scaled_height) // 2
        qdwysrswtv = self.nbisasgkdo.current_level.get_sprites_by_name("mosdlc")
        for ctdsrzzyik in qdwysrswtv:
            if ctdsrzzyik.is_visible:
                xstekntyoi = ctdsrzzyik.x * scale + x_offset
                ibhmkpzcys = ctdsrzzyik.y * scale + y_offset
                for y in range(ibhmkpzcys, min(ibhmkpzcys + scale, 64)):
                    for x in range(xstekntyoi, min(xstekntyoi + scale, 64)):
                        if (y == ibhmkpzcys or y == ibhmkpzcys + scale - 1) and (x == xstekntyoi or x == xstekntyoi + scale - 1):
                            frame[y, x] = 5
        for naligxzjuh in self.nbisasgkdo.current_level.get_sprites_by_name("spswjz"):
            if self.nbisasgkdo.current_level.get_sprite_at(naligxzjuh.x, naligxzjuh.y, "fucr"):
                continue
            xstekntyoi, ibhmkpzcys = (
                naligxzjuh.x * scale + x_offset,
                naligxzjuh.y * scale + y_offset,
            )
            for y in range(ibhmkpzcys, min(ibhmkpzcys + scale, 64)):
                for x in range(xstekntyoi, min(xstekntyoi + scale, 64)):
                    if (x + y) % 3 == 0:
                        frame[y, x] = 5
        return frame


class _Mxr0Rules(ARCBaseGame):
    def __init__(self) -> None:
        dekehcqgaao = Camera(background=BACKGROUND_COLOR, letter_box=PADDING_COLOR)
        self.ddjekzihkbc: dict[str, tuple[int, int]] = {}
        self.okpvcjupabr: set[str] = set()
        self.xjtmzsltgjl = uuyjjjqcvy(self)
        self.vtivsqjblkm = ckpxigfdkg(fmdcmwxxau=150)
        self.jnyxgyktgcv: Sprite | None = None
        self.pyhtlpzlmnr = True
        super().__init__(
            game_id="m0r0",
            levels=levels,
            camera=dekehcqgaao,
            available_actions=[1, 2, 3, 4, 5, 6],
        )
        self._camera.replace_interface([self.xjtmzsltgjl, self.vtivsqjblkm])

    def on_set_level(self, level: Level) -> None:
        """."""
        self.ddjekzihkbc = {}
        self.okpvcjupabr = set()
        self.vtivsqjblkm.uzcyzamlne(150)
        for lcbpdmntevr in self.current_level.get_sprites_by_name("mosdlc"):
            lcbpdmntevr.color_remap(None, 9)
        self.jnyxgyktgcv = None
        self.pyhtlpzlmnr = True
        self.anfcrclwoac: list[Sprite] = []
        self.ukempikfmtm = -1
        self.yzihzkijgmp = [(s, s.x, s.y) for s in self.current_level.get_sprites_by_tag("sys_click")]

    def step(self) -> None:
        """."""
        if self.ukempikfmtm >= 0:
            vdolerwhik = self.ukempikfmtm % 2 == 0 and self.ukempikfmtm < 5
            for frbrtmyepc in self.anfcrclwoac:
                frbrtmyepc.color_remap(None, 11 if vdolerwhik else 10)
            self.ukempikfmtm += 1
            if self.ukempikfmtm > 6:
                for ssebydbziot, nuyjtkhbyuu, hrzpyhhngsf in self.yzihzkijgmp:
                    ssebydbziot.set_position(nuyjtkhbyuu, hrzpyhhngsf)
                self.ukempikfmtm = -1
                self.anfcrclwoac = []
                self.complete_action()
            return
        fjsdpbazki = 150 - self._action_count
        self.vtivsqjblkm.uzcyzamlne(fjsdpbazki)
        if self._action_count > 150:
            self.lose()
            self.complete_action()
            return
        if self.action.id == GameAction.ACTION6:
            nuyjtkhbyuu = self.action.data["x"]
            hrzpyhhngsf = self.action.data["y"]
            lonzrrktea = self.camera.display_to_grid(nuyjtkhbyuu, hrzpyhhngsf)
            if lonzrrktea:
                jamhialqflz, zjgkkciavka = lonzrrktea
                gyetnvemfz = self.current_level.get_sprite_at(jamhialqflz, zjgkkciavka, tag="sys_click")
                if gyetnvemfz and gyetnvemfz.name == "mosdlc":
                    self.pyhtlpzlmnr = False
                    for kpaxgykyfg in [
                        "pikgci-toljda-leklkn",
                        "pikgci-toljda-rivmdg",
                        "pikgci-boweok-leklkn",
                        "pikgci-boweok-rivmdg",
                    ]:
                        cmrfmxkgsyp = self.current_level.get_sprites_by_name(kpaxgykyfg)
                        if cmrfmxkgsyp and kpaxgykyfg not in self.okpvcjupabr:
                            cmrfmxkgsyp[0].color_remap(None, 1)
                    if self.jnyxgyktgcv:
                        self.jnyxgyktgcv.color_remap(None, 9)
                    self.jnyxgyktgcv = gyetnvemfz
                    self.set_placeable_sprite(self.jnyxgyktgcv)
                    self.jnyxgyktgcv.color_remap(None, 11)
                else:
                    self.pyhtlpzlmnr = True
                    for kpaxgykyfg in [
                        "pikgci-toljda-leklkn",
                        "pikgci-toljda-rivmdg",
                        "pikgci-boweok-leklkn",
                        "pikgci-boweok-rivmdg",
                    ]:
                        cmrfmxkgsyp = self.current_level.get_sprites_by_name(kpaxgykyfg)
                        if cmrfmxkgsyp and kpaxgykyfg not in self.okpvcjupabr:
                            cmrfmxkgsyp[0].color_remap(None, 10)
                    if self.jnyxgyktgcv:
                        self.jnyxgyktgcv.color_remap(None, 9)
                        self.jnyxgyktgcv = None
                        self.set_placeable_sprite(self.jnyxgyktgcv)
            self.complete_action()
            return
        tbbgvkvoptv = 0
        rjcrgldrrqz = 0
        if self.action.id == GameAction.ACTION1:
            rjcrgldrrqz = -1
            self.set_placeable_sprite(None)
        elif self.action.id == GameAction.ACTION2:
            rjcrgldrrqz = 1
            self.set_placeable_sprite(None)
        elif self.action.id == GameAction.ACTION3:
            tbbgvkvoptv = -1
            self.set_placeable_sprite(None)
        elif self.action.id == GameAction.ACTION4:
            tbbgvkvoptv = 1
            self.set_placeable_sprite(None)
        if self.jnyxgyktgcv and (not self.pyhtlpzlmnr):
            grid_width, grid_height = self.current_level.grid_size or (64, 64)
            ucnlheamiu = self.jnyxgyktgcv.x + tbbgvkvoptv
            qgwjdnmhnp = self.jnyxgyktgcv.y + rjcrgldrrqz
            if ucnlheamiu < 0 or ucnlheamiu >= grid_width or qgwjdnmhnp < 0 or (qgwjdnmhnp >= grid_height):
                self.complete_action()
                return
            self.try_move_sprite(self.jnyxgyktgcv, tbbgvkvoptv, rjcrgldrrqz)
            self.xxlavvheeu()
            self.complete_action()
            return
        if self.pyhtlpzlmnr:
            yjopaxfnag = []
            for kpaxgykyfg in [
                "pikgci-toljda-leklkn",
                "pikgci-toljda-rivmdg",
                "pikgci-boweok-leklkn",
                "pikgci-boweok-rivmdg",
            ]:
                cmrfmxkgsyp = self.current_level.get_sprites_by_name(kpaxgykyfg)
                if cmrfmxkgsyp and kpaxgykyfg not in self.okpvcjupabr:
                    yjopaxfnag.append((kpaxgykyfg, cmrfmxkgsyp[0]))
            for dtktmyjjtsa, ssebydbziot in yjopaxfnag:
                self.ddjekzihkbc[dtktmyjjtsa] = (ssebydbziot.x, ssebydbziot.y)
            urouxrqoiz = []
            for dtktmyjjtsa, ssebydbziot in yjopaxfnag:
                if "toljda-leklkn" in dtktmyjjtsa:
                    urouxrqoiz.append((ssebydbziot, tbbgvkvoptv, rjcrgldrrqz))
                elif "toljda-rivmdg" in dtktmyjjtsa:
                    urouxrqoiz.append((ssebydbziot, -tbbgvkvoptv, rjcrgldrrqz))
                elif "boweok-leklkn" in dtktmyjjtsa:
                    urouxrqoiz.append((ssebydbziot, tbbgvkvoptv, -rjcrgldrrqz))
                elif "boweok-rivmdg" in dtktmyjjtsa:
                    urouxrqoiz.append((ssebydbziot, -tbbgvkvoptv, -rjcrgldrrqz))
            for ssebydbziot, nvujraomgw, uamkpsisme in urouxrqoiz:
                if nvujraomgw != 0 or uamkpsisme != 0:
                    self.jpwxcqabja(ssebydbziot, nvujraomgw, uamkpsisme)
            for yfdzkmrhwn, bworgnodum in yjopaxfnag:
                if self.current_level.get_sprite_at(bworgnodum.x, bworgnodum.y, "spswjz"):
                    self.anfcrclwoac.append(bworgnodum)
            if self.anfcrclwoac:
                self.ukempikfmtm = 0
                return
            zszudehkps = [(name, sprite) for name, sprite in yjopaxfnag if name not in self.okpvcjupabr and sprite.interaction != InteractionMode.REMOVED]
            for i, (mxadgeakbw, bzoyarwevo) in enumerate(zszudehkps):
                if mxadgeakbw in self.okpvcjupabr:
                    continue
                for jasevsxheb, ofjzhesrvy in zszudehkps[i + 1 :]:
                    if jasevsxheb in self.okpvcjupabr:
                        continue
                    if mxadgeakbw in self.ddjekzihkbc and jasevsxheb in self.ddjekzihkbc:
                        loemvbfdsjc, vislabrdyds = self.ddjekzihkbc[mxadgeakbw]
                        zntvhzbkrco, ivmkrssvkbx = self.ddjekzihkbc[jasevsxheb]
                        if abs(loemvbfdsjc - zntvhzbkrco) == 1 and vislabrdyds == ivmkrssvkbx:
                            if bzoyarwevo.x == zntvhzbkrco and bzoyarwevo.y == ivmkrssvkbx or (ofjzhesrvy.x == loemvbfdsjc and ofjzhesrvy.y == vislabrdyds):
                                jrkwvtxkvm = (bzoyarwevo.x + ofjzhesrvy.x) // 2
                                ojqneywevf = (bzoyarwevo.y + ofjzhesrvy.y) // 2
                                bzoyarwevo.set_position(jrkwvtxkvm, ojqneywevf)
                                ofjzhesrvy.set_position(jrkwvtxkvm, ojqneywevf)
            fvqnbtefro: dict[tuple[int, int], list[tuple[str, Sprite]]] = {}
            for dtktmyjjtsa, ssebydbziot in zszudehkps:
                igdddytrcd = (ssebydbziot.x, ssebydbziot.y)
                if igdddytrcd not in fvqnbtefro:
                    fvqnbtefro[igdddytrcd] = []
                fvqnbtefro[igdddytrcd].append((dtktmyjjtsa, ssebydbziot))
            for igdddytrcd, scppkacdme in fvqnbtefro.items():
                if len(scppkacdme) == 2:
                    for dtktmyjjtsa, ssebydbziot in scppkacdme:
                        self.okpvcjupabr.add(dtktmyjjtsa)
                        ssebydbziot.set_interaction(InteractionMode.INTANGIBLE)
                elif len(scppkacdme) > 2:
                    for dtktmyjjtsa, ssebydbziot in scppkacdme[:2]:
                        self.okpvcjupabr.add(dtktmyjjtsa)
                        ssebydbziot.set_interaction(InteractionMode.INTANGIBLE)
                    for dtktmyjjtsa, ssebydbziot in scppkacdme[2:]:
                        if dtktmyjjtsa in self.ddjekzihkbc:
                            prev_x, prev_y = self.ddjekzihkbc[dtktmyjjtsa]
                            ssebydbziot.set_position(prev_x, prev_y)
            self.xxlavvheeu()
            piznjwrdhn = sum((1 for atdohiedatw, sqctczantrh in yjopaxfnag if atdohiedatw not in self.okpvcjupabr and sqctczantrh.interaction != InteractionMode.INTANGIBLE))
            if piznjwrdhn == 0:
                self.next_level()
        self.complete_action()

    def jpwxcqabja(self, bflgaukfzcq: Sprite, vzkllxtmkgj: int, lejrjfmlsoz: int) -> None:
        """."""
        mvhdcywqsbe, iqxplnerngk = self.current_level.grid_size or (64, 64)
        ucnlheamiu = bflgaukfzcq.x + vzkllxtmkgj
        qgwjdnmhnp = bflgaukfzcq.y + lejrjfmlsoz
        if ucnlheamiu < 0 or ucnlheamiu >= mvhdcywqsbe or qgwjdnmhnp < 0 or (qgwjdnmhnp >= iqxplnerngk):
            return
        wbjvyyrjbll, wrbpicczsnl = (bflgaukfzcq.x, bflgaukfzcq.y)
        bflgaukfzcq.move(vzkllxtmkgj, lejrjfmlsoz)
        tnymtunyiz = self.current_level.get_sprites_by_tag("wahtyt")
        for rxjyuzkgxa in tnymtunyiz:
            if bflgaukfzcq.collides_with(rxjyuzkgxa):
                bflgaukfzcq.set_position(wbjvyyrjbll, wrbpicczsnl)
                return
        jbzjjcoeiv = self.current_level.get_sprites_by_tag("xbso")
        for ctdsrzzyik in jbzjjcoeiv:
            if bflgaukfzcq.collides_with(ctdsrzzyik):
                bflgaukfzcq.set_position(wbjvyyrjbll, wrbpicczsnl)
                return
        for ltjqbdbqsw in ["grwjuk", "orfrpe", "puvdux"]:
            iuqsenyddz = self.current_level.get_sprites_by_name(f"gayktr-{ltjqbdbqsw}")
            for xaskewqzny in iuqsenyddz:
                if xaskewqzny.is_collidable and bflgaukfzcq.collides_with(xaskewqzny):
                    bflgaukfzcq.set_position(wbjvyyrjbll, wrbpicczsnl)
                    return

    def xxlavvheeu(self) -> None:
        """."""
        zszudehkps = []
        for kpaxgykyfg in [
            "pikgci-toljda-leklkn",
            "pikgci-toljda-rivmdg",
            "pikgci-boweok-leklkn",
            "pikgci-boweok-rivmdg",
        ]:
            if kpaxgykyfg not in self.okpvcjupabr:
                sprites = self.current_level.get_sprites_by_name(kpaxgykyfg)
                if sprites:
                    zszudehkps.append(sprites[0])
        for ltjqbdbqsw in ["grwjuk", "orfrpe", "puvdux"]:
            xcaqymmdkg = self.current_level.get_sprites_by_name(f"unobxw-{ltjqbdbqsw}")
            iuqsenyddz = self.current_level.get_sprites_by_name(f"gayktr-{ltjqbdbqsw}")
            if not xcaqymmdkg or not iuqsenyddz:
                continue
            sgltbhmlte = False
            for qhgxwetdxw in xcaqymmdkg:
                for bworgnodum in zszudehkps:
                    if bworgnodum.x == qhgxwetdxw.x and bworgnodum.y == qhgxwetdxw.y:
                        sgltbhmlte = True
                        break
                if sgltbhmlte:
                    break
            for xaskewqzny in iuqsenyddz:
                if sgltbhmlte:
                    xaskewqzny.set_interaction(InteractionMode.REMOVED)
                else:
                    xaskewqzny.set_interaction(InteractionMode.TANGIBLE)


# ── copycat layer ───────────────────────────────────────────────────────────────
# Colour assignment for this copycat: displayed colour = _CC_PALETTE[engine colour].
# Applied to the camera's final 64x64 output only, so the game's own rules (some of which
# read sprite colours) are untouched.
_CC_PALETTE = np.array([3, 4, 11, 12, 1, 0, 10, 5, 2, 6, 13, 9, 15, 7, 8, 14], dtype=np.int8)


class _CcCamera(Camera):
    def render(self, sprites):
        frame = super().render(sprites)
        frame = np.asarray(frame)
        out = frame.copy()
        mask = (frame >= 0) & (frame <= 15)
        out[mask] = _CC_PALETTE[frame[mask].astype(np.int64)]
        return out


class Mxr0(_Mxr0Rules):
    def __init__(self) -> None:
        super().__init__()
        if type(self._camera) is Camera:
            self._camera.__class__ = _CcCamera
        if not isinstance(self._camera, _CcCamera):
            raise RuntimeError("copycat palette camera not installed")
        self._game_id = 'mxr0'

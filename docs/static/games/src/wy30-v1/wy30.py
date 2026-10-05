# Copycat wy30: rules of public ARC-AGI-3 game wa30, new maps, colours and art.
# Built and verified by autoresearch-arena arc3games/copycats/cc_wa30.py.
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
    'aidclcbjcv': Sprite(
        pixels=[
        [4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4],
        [4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4],
        [4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4],
        [4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4],
        [4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4],
        [4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4],
        [4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4],
        [4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4],
        [4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4],
        [4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4],
        [4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4],
        [4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4],
        [4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4],
        [4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4],
        [4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4],
        [4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4],
        [4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4],
        [4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4],
        [4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4],
        [4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4],
    ],
        name='aidclcbjcv',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
    ),
    'byigobxzpg': Sprite(
        pixels=[
        [12, 8, 8, 12],
        [8, 12, 12, 8],
        [8, 12, 12, 8],
        [12, 8, 8, 12],
    ],
        name='byigobxzpg',
        layer=1,
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['kdweefinfi'],
    ),
    'cwefnfvjhr': Sprite(
        pixels=[
        [4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4],
        [4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4],
        [4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4],
        [4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4],
        [4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4],
        [4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4],
        [4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4],
        [4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4],
        [4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4],
        [4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4],
        [4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4],
        [4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4],
        [4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4],
        [4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4],
        [4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4, 4, 4, 13, 4],
        [4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4],
    ],
        name='cwefnfvjhr',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
    ),
    'doijajrgdi': Sprite(
        pixels=[
        [8, 9, 9, 9, 9, 9, 9, 8],
        [9, 2, 2, 2, 2, 2, 2, 9],
        [9, 2, 2, 2, 2, 2, 2, 9],
        [9, 2, 2, 2, 2, 2, 2, 9],
        [9, 2, 2, 2, 2, 2, 2, 9],
        [9, 2, 2, 2, 2, 2, 2, 9],
        [9, 2, 2, 2, 2, 2, 2, 9],
        [9, 2, 2, 2, 2, 2, 2, 9],
        [9, 2, 2, 2, 2, 2, 2, 9],
        [9, 2, 2, 2, 2, 2, 2, 9],
        [9, 2, 2, 2, 2, 2, 2, 9],
        [8, 9, 9, 9, 9, 9, 9, 8],
    ],
        name='doijajrgdi',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.INTANGIBLE,
        tags=['fsjjayjoeg'],
    ),
    'geffskzhqq': Sprite(
        pixels=[
        [2, 2, 13, 2],
        [2, 13, 2, 2],
        [13, 2, 2, 13],
        [2, 2, 13, 2],
        [2, 13, 2, 2],
        [13, 2, 2, 13],
        [2, 2, 13, 2],
        [2, 13, 2, 2],
    ],
        name='geffskzhqq',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.INTANGIBLE,
        tags=['zqxwgacnue'],
    ),
    'ghklglzjuf': Sprite(
        pixels=[
        [8, 9, 9, 9, 9, 9, 9, 8],
        [9, 2, 2, 2, 2, 2, 2, 9],
        [9, 2, 2, 2, 2, 2, 2, 9],
        [9, 2, 2, 2, 2, 2, 2, 9],
        [9, 2, 2, 2, 2, 2, 2, 9],
        [9, 2, 2, 2, 2, 2, 2, 9],
        [9, 2, 2, 2, 2, 2, 2, 9],
        [8, 9, 9, 9, 9, 9, 9, 8],
    ],
        name='ghklglzjuf',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.INTANGIBLE,
        tags=['fsjjayjoeg'],
    ),
    'jigtxgzhwt': Sprite(
        pixels=[
        [8, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 8],
        [9, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 9],
        [9, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 9],
        [8, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 8],
    ],
        name='jigtxgzhwt',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.INTANGIBLE,
        tags=['fsjjayjoeg'],
    ),
    'jqzhxgbmtz': Sprite(
        pixels=[
        [15, 15, 15, 15],
        [15, 6, 15, 15],
        [15, 15, 6, 15],
        [15, 15, 15, 15],
    ],
        name='jqzhxgbmtz',
        layer=1,
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['ysysltqlke'],
    ),
    'ktghqrydvd': Sprite(
        pixels=[
        [8, 9, 9, 9, 9, 9, 9, 8],
        [9, 2, 2, 2, 2, 2, 2, 9],
        [9, 2, 2, 2, 2, 2, 2, 9],
        [9, 2, 2, 2, 2, 2, 2, 9],
        [9, 2, 2, 2, 2, 2, 2, 9],
        [9, 2, 2, 2, 2, 2, 2, 9],
        [9, 2, 2, 2, 2, 2, 2, 9],
        [9, 2, 2, 2, 2, 2, 2, 9],
        [9, 2, 2, 2, 2, 2, 2, 9],
        [9, 2, 2, 2, 2, 2, 2, 9],
        [9, 2, 2, 2, 2, 2, 2, 9],
        [9, 2, 2, 2, 2, 2, 2, 9],
        [9, 2, 2, 2, 2, 2, 2, 9],
        [9, 2, 2, 2, 2, 2, 2, 9],
        [9, 2, 2, 2, 2, 2, 2, 9],
        [8, 9, 9, 9, 9, 9, 9, 8],
    ],
        name='ktghqrydvd',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.INTANGIBLE,
        tags=['fsjjayjoeg'],
    ),
    'ofwegeqknn': Sprite(
        pixels=[
        [8, 9, 9, 8],
        [9, 2, 2, 9],
        [9, 2, 2, 9],
        [9, 2, 2, 9],
        [9, 2, 2, 9],
        [9, 2, 2, 9],
        [9, 2, 2, 9],
        [8, 9, 9, 8],
    ],
        name='ofwegeqknn',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.INTANGIBLE,
        tags=['fsjjayjoeg'],
    ),
    'ooaamfpvqr': Sprite(
        pixels=[
        [2, 2, 13, 2, 2, 13, 2, 2],
        [2, 13, 2, 2, 13, 2, 2, 13],
        [13, 2, 2, 13, 2, 2, 13, 2],
        [2, 2, 13, 2, 2, 13, 2, 2],
        [2, 13, 2, 2, 13, 2, 2, 13],
        [13, 2, 2, 13, 2, 2, 13, 2],
        [2, 2, 13, 2, 2, 13, 2, 2],
        [2, 13, 2, 2, 13, 2, 2, 13],
    ],
        name='ooaamfpvqr',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.INTANGIBLE,
        tags=['zqxwgacnue'],
    ),
    'peimznrlqd': Sprite(
        pixels=[
        [8, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 8],
        [9, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 9],
        [9, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 9],
        [9, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 9],
        [9, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 9],
        [9, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 9],
        [9, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 9],
        [9, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 9],
        [9, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 9],
        [9, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 9],
        [9, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 9],
        [8, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 8],
    ],
        name='peimznrlqd',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.INTANGIBLE,
        tags=['fsjjayjoeg'],
    ),
    'pktgsotzmw': Sprite(
        pixels=[
        [4, 4, 4, 4],
        [4, 9, 10, 4],
        [4, 10, 9, 4],
        [4, 4, 4, 4],
    ],
        name='pktgsotzmw',
        layer=1,
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['geezpjgiyd'],
    ),
    'pmargquscu': Sprite(
        pixels=[
        [-2, 2, 2, -2],
        [2, 2, 3, 2],
        [2, 3, 2, 2],
        [-2, 2, 2, -2],
    ],
        name='pmargquscu',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.INTANGIBLE,
        tags=['bnzklblgdk'],
    ),
    'uasmnkbzmm': Sprite(
        pixels=[
        [5, 13, 5, 5],
        [5, 5, 13, 5],
        [5, 5, 5, 13],
        [13, 5, 5, 5],
    ],
        name='uasmnkbzmm',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['debyzcmtnr'],
    ),
    'vikkhnsrzd': Sprite(
        pixels=[
        [8, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 8],
        [9, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 9],
        [9, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 9],
        [9, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 9],
        [9, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 9],
        [9, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 9],
        [9, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 9],
        [8, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 8],
    ],
        name='vikkhnsrzd',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.INTANGIBLE,
        tags=['fsjjayjoeg'],
    ),
    'wkmuwhjqyo': Sprite(
        pixels=[
        [8, 9, 9, 9, 9, 9, 9, 8],
        [9, 2, 2, 2, 2, 2, 2, 9],
        [9, 2, 2, 2, 2, 2, 2, 9],
        [8, 9, 9, 9, 9, 9, 9, 8],
    ],
        name='wkmuwhjqyo',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.INTANGIBLE,
        tags=['fsjjayjoeg'],
    ),
    'wppuejnwhl': Sprite(
        pixels=[
        [14, 0, 0, 14],
        [14, 0, 0, 14],
        [14, 14, 14, 14],
        [14, 14, 14, 14],
    ],
        name='wppuejnwhl',
        layer=1,
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['wbmdvjhthc'],
    ),
    'xqaqifquaw': Sprite(
        pixels=[
        [2, 2, 13, 2, 2, 13, 2, 2, 13, 2, 2, 13],
        [2, 13, 2, 2, 13, 2, 2, 13, 2, 2, 13, 2],
        [13, 2, 2, 13, 2, 2, 13, 2, 2, 13, 2, 2],
        [2, 2, 13, 2, 2, 13, 2, 2, 13, 2, 2, 13],
        [2, 13, 2, 2, 13, 2, 2, 13, 2, 2, 13, 2],
        [13, 2, 2, 13, 2, 2, 13, 2, 2, 13, 2, 2],
        [2, 2, 13, 2, 2, 13, 2, 2, 13, 2, 2, 13],
        [2, 13, 2, 2, 13, 2, 2, 13, 2, 2, 13, 2],
        [13, 2, 2, 13, 2, 2, 13, 2, 2, 13, 2, 2],
        [2, 2, 13, 2, 2, 13, 2, 2, 13, 2, 2, 13],
        [2, 13, 2, 2, 13, 2, 2, 13, 2, 2, 13, 2],
        [13, 2, 2, 13, 2, 2, 13, 2, 2, 13, 2, 2],
    ],
        name='xqaqifquaw',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.INTANGIBLE,
        tags=['zqxwgacnue'],
    ),
    'xxmzyqktqy': Sprite(
        pixels=[
        [8, 9, 9, 8],
        [9, 2, 2, 9],
        [9, 2, 2, 9],
        [8, 9, 9, 8],
    ],
        name='xxmzyqktqy',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.INTANGIBLE,
        tags=['fsjjayjoeg'],
    ),
}
levels = [
    # Level 1
    Level(
        sprites=[
            sprites['jigtxgzhwt'].clone().set_position(24, 28),
            sprites['pktgsotzmw'].clone().set_position(16, 24),
            sprites['pktgsotzmw'].clone().set_position(44, 28),
            sprites['pktgsotzmw'].clone().set_position(28, 36),
            sprites['wppuejnwhl'].clone().set_position(28, 48),
            sprites['uasmnkbzmm'].clone().set_position(0, 12),
            sprites['uasmnkbzmm'].clone().set_position(0, 20),
            sprites['uasmnkbzmm'].clone().set_position(0, 24),
            sprites['uasmnkbzmm'].clone().set_position(0, 28),
            sprites['uasmnkbzmm'].clone().set_position(0, 32),
            sprites['uasmnkbzmm'].clone().set_position(0, 44),
            sprites['uasmnkbzmm'].clone().set_position(0, 48),
            sprites['uasmnkbzmm'].clone().set_position(0, 52),
            sprites['uasmnkbzmm'].clone().set_position(0, 56),
            sprites['uasmnkbzmm'].clone().set_position(4, 12),
            sprites['uasmnkbzmm'].clone().set_position(4, 20),
            sprites['uasmnkbzmm'].clone().set_position(4, 24),
            sprites['uasmnkbzmm'].clone().set_position(4, 28),
            sprites['uasmnkbzmm'].clone().set_position(4, 32),
            sprites['uasmnkbzmm'].clone().set_position(8, 0),
            sprites['uasmnkbzmm'].clone().set_position(8, 20),
            sprites['uasmnkbzmm'].clone().set_position(8, 28),
            sprites['uasmnkbzmm'].clone().set_position(8, 36),
            sprites['uasmnkbzmm'].clone().set_position(12, 28),
            sprites['uasmnkbzmm'].clone().set_position(12, 36),
            sprites['uasmnkbzmm'].clone().set_position(12, 44),
            sprites['uasmnkbzmm'].clone().set_position(12, 48),
            sprites['uasmnkbzmm'].clone().set_position(12, 52),
            sprites['uasmnkbzmm'].clone().set_position(16, 8),
            sprites['uasmnkbzmm'].clone().set_position(16, 12),
            sprites['uasmnkbzmm'].clone().set_position(16, 16),
            sprites['uasmnkbzmm'].clone().set_position(16, 40),
            sprites['uasmnkbzmm'].clone().set_position(16, 44),
            sprites['uasmnkbzmm'].clone().set_position(16, 48),
            sprites['uasmnkbzmm'].clone().set_position(16, 52),
            sprites['uasmnkbzmm'].clone().set_position(16, 56),
            sprites['uasmnkbzmm'].clone().set_position(20, 0),
            sprites['uasmnkbzmm'].clone().set_position(20, 16),
            sprites['uasmnkbzmm'].clone().set_position(20, 40),
            sprites['uasmnkbzmm'].clone().set_position(20, 44),
            sprites['uasmnkbzmm'].clone().set_position(20, 52),
            sprites['uasmnkbzmm'].clone().set_position(24, 52),
            sprites['uasmnkbzmm'].clone().set_position(28, 8),
            sprites['uasmnkbzmm'].clone().set_position(28, 12),
            sprites['uasmnkbzmm'].clone().set_position(32, 8),
            sprites['uasmnkbzmm'].clone().set_position(32, 44),
            sprites['uasmnkbzmm'].clone().set_position(32, 48),
            sprites['uasmnkbzmm'].clone().set_position(32, 52),
            sprites['uasmnkbzmm'].clone().set_position(36, 52),
            sprites['uasmnkbzmm'].clone().set_position(40, 48),
            sprites['uasmnkbzmm'].clone().set_position(40, 52),
            sprites['uasmnkbzmm'].clone().set_position(44, 0),
            sprites['uasmnkbzmm'].clone().set_position(44, 4),
            sprites['uasmnkbzmm'].clone().set_position(44, 8),
            sprites['uasmnkbzmm'].clone().set_position(44, 48),
            sprites['uasmnkbzmm'].clone().set_position(44, 52),
            sprites['uasmnkbzmm'].clone().set_position(44, 56),
            sprites['uasmnkbzmm'].clone().set_position(44, 60),
            sprites['uasmnkbzmm'].clone().set_position(48, 0),
            sprites['uasmnkbzmm'].clone().set_position(48, 40),
            sprites['uasmnkbzmm'].clone().set_position(48, 44),
            sprites['uasmnkbzmm'].clone().set_position(48, 48),
            sprites['uasmnkbzmm'].clone().set_position(52, 0),
            sprites['uasmnkbzmm'].clone().set_position(52, 4),
            sprites['uasmnkbzmm'].clone().set_position(52, 8),
            sprites['uasmnkbzmm'].clone().set_position(52, 32),
            sprites['uasmnkbzmm'].clone().set_position(52, 44),
            sprites['uasmnkbzmm'].clone().set_position(52, 48),
            sprites['uasmnkbzmm'].clone().set_position(56, 32),
            sprites['uasmnkbzmm'].clone().set_position(56, 36),
            sprites['uasmnkbzmm'].clone().set_position(56, 40),
            sprites['uasmnkbzmm'].clone().set_position(56, 44),
            sprites['uasmnkbzmm'].clone().set_position(60, 24),
            sprites['uasmnkbzmm'].clone().set_position(60, 28),
            sprites['uasmnkbzmm'].clone().set_position(60, 32),
            sprites['uasmnkbzmm'].clone().set_position(60, 40),
            sprites['uasmnkbzmm'].clone().set_position(60, 44),
        ],
        grid_size=(64, 64),
        data={'StepCounter': 200},
    ),
    # Level 2
    Level(
        sprites=[
            sprites['byigobxzpg'].clone().set_position(36, 36),
            sprites['doijajrgdi'].clone().set_position(44, 28),
            sprites['pktgsotzmw'].clone().set_position(12, 32),
            sprites['pktgsotzmw'].clone().set_position(24, 28),
            sprites['pktgsotzmw'].clone().set_position(20, 20),
            sprites['pktgsotzmw'].clone().set_position(12, 24),
            sprites['pktgsotzmw'].clone().set_position(16, 40),
            sprites['wppuejnwhl'].clone().set_position(48, 8),
            sprites['uasmnkbzmm'].clone().set_position(0, 4),
            sprites['uasmnkbzmm'].clone().set_position(0, 8),
            sprites['uasmnkbzmm'].clone().set_position(0, 12),
            sprites['uasmnkbzmm'].clone().set_position(0, 28),
            sprites['uasmnkbzmm'].clone().set_position(0, 52),
            sprites['uasmnkbzmm'].clone().set_position(0, 56),
            sprites['uasmnkbzmm'].clone().set_position(4, 12),
            sprites['uasmnkbzmm'].clone().set_position(4, 20),
            sprites['uasmnkbzmm'].clone().set_position(4, 24),
            sprites['uasmnkbzmm'].clone().set_position(4, 28),
            sprites['uasmnkbzmm'].clone().set_position(4, 40),
            sprites['uasmnkbzmm'].clone().set_position(4, 52),
            sprites['uasmnkbzmm'].clone().set_position(8, 28),
            sprites['uasmnkbzmm'].clone().set_position(8, 40),
            sprites['uasmnkbzmm'].clone().set_position(8, 52),
            sprites['uasmnkbzmm'].clone().set_position(12, 0),
            sprites['uasmnkbzmm'].clone().set_position(12, 4),
            sprites['uasmnkbzmm'].clone().set_position(12, 8),
            sprites['uasmnkbzmm'].clone().set_position(12, 40),
            sprites['uasmnkbzmm'].clone().set_position(12, 52),
            sprites['uasmnkbzmm'].clone().set_position(12, 56),
            sprites['uasmnkbzmm'].clone().set_position(16, 52),
            sprites['uasmnkbzmm'].clone().set_position(16, 56),
            sprites['uasmnkbzmm'].clone().set_position(20, 44),
            sprites['uasmnkbzmm'].clone().set_position(20, 52),
            sprites['uasmnkbzmm'].clone().set_position(20, 56),
            sprites['uasmnkbzmm'].clone().set_position(24, 44),
            sprites['uasmnkbzmm'].clone().set_position(32, 8),
            sprites['uasmnkbzmm'].clone().set_position(36, 0),
            sprites['uasmnkbzmm'].clone().set_position(36, 8),
            sprites['uasmnkbzmm'].clone().set_position(36, 12),
            sprites['uasmnkbzmm'].clone().set_position(36, 16),
            sprites['uasmnkbzmm'].clone().set_position(40, 0),
            sprites['uasmnkbzmm'].clone().set_position(40, 4),
            sprites['uasmnkbzmm'].clone().set_position(40, 16),
            sprites['uasmnkbzmm'].clone().set_position(40, 48),
            sprites['uasmnkbzmm'].clone().set_position(40, 52),
            sprites['uasmnkbzmm'].clone().set_position(44, 4),
            sprites['uasmnkbzmm'].clone().set_position(44, 8),
            sprites['uasmnkbzmm'].clone().set_position(44, 12),
            sprites['uasmnkbzmm'].clone().set_position(44, 16),
            sprites['uasmnkbzmm'].clone().set_position(48, 48),
            sprites['uasmnkbzmm'].clone().set_position(48, 52),
            sprites['uasmnkbzmm'].clone().set_position(48, 56),
            sprites['uasmnkbzmm'].clone().set_position(48, 60),
            sprites['uasmnkbzmm'].clone().set_position(52, 48),
            sprites['uasmnkbzmm'].clone().set_position(52, 56),
            sprites['uasmnkbzmm'].clone().set_position(56, 0),
            sprites['uasmnkbzmm'].clone().set_position(56, 4),
            sprites['uasmnkbzmm'].clone().set_position(56, 8),
            sprites['uasmnkbzmm'].clone().set_position(56, 48),
            sprites['uasmnkbzmm'].clone().set_position(56, 56),
            sprites['uasmnkbzmm'].clone().set_position(60, 0),
            sprites['uasmnkbzmm'].clone().set_position(60, 8),
            sprites['uasmnkbzmm'].clone().set_position(60, 48),
            sprites['uasmnkbzmm'].clone().set_position(60, 56),
            sprites['uasmnkbzmm'].clone().set_position(60, 60),
        ],
        grid_size=(64, 64),
        data={'StepCounter': 70},
    ),
    # Level 3
    Level(
        sprites=[
            sprites['byigobxzpg'].clone().set_position(12, 12),
            sprites['ktghqrydvd'].clone().set_position(4, 24),
            sprites['pktgsotzmw'].clone().set_position(28, 32),
            sprites['pktgsotzmw'].clone().set_position(40, 20),
            sprites['pktgsotzmw'].clone().set_position(48, 44),
            sprites['pktgsotzmw'].clone().set_position(52, 16),
            sprites['pktgsotzmw'].clone().set_position(28, 12),
            sprites['pmargquscu'].clone().set_position(28, 0),
            sprites['pmargquscu'].clone().set_position(28, 4),
            sprites['pmargquscu'].clone().set_position(28, 8),
            sprites['pmargquscu'].clone().set_position(28, 12),
            sprites['pmargquscu'].clone().set_position(28, 16),
            sprites['pmargquscu'].clone().set_position(28, 20),
            sprites['pmargquscu'].clone().set_position(28, 24),
            sprites['pmargquscu'].clone().set_position(28, 28),
            sprites['pmargquscu'].clone().set_position(28, 32),
            sprites['pmargquscu'].clone().set_position(28, 36),
            sprites['pmargquscu'].clone().set_position(28, 40),
            sprites['pmargquscu'].clone().set_position(28, 44),
            sprites['pmargquscu'].clone().set_position(28, 48),
            sprites['pmargquscu'].clone().set_position(28, 52),
            sprites['pmargquscu'].clone().set_position(28, 56),
            sprites['pmargquscu'].clone().set_position(28, 60),
            sprites['wppuejnwhl'].clone().set_position(44, 36),
            sprites['uasmnkbzmm'].clone().set_position(0, 8),
            sprites['uasmnkbzmm'].clone().set_position(0, 32),
            sprites['uasmnkbzmm'].clone().set_position(0, 36),
            sprites['uasmnkbzmm'].clone().set_position(0, 40),
            sprites['uasmnkbzmm'].clone().set_position(0, 44),
            sprites['uasmnkbzmm'].clone().set_position(4, 0),
            sprites['uasmnkbzmm'].clone().set_position(4, 4),
            sprites['uasmnkbzmm'].clone().set_position(4, 40),
            sprites['uasmnkbzmm'].clone().set_position(4, 44),
            sprites['uasmnkbzmm'].clone().set_position(8, 0),
            sprites['uasmnkbzmm'].clone().set_position(8, 4),
            sprites['uasmnkbzmm'].clone().set_position(8, 44),
            sprites['uasmnkbzmm'].clone().set_position(8, 48),
            sprites['uasmnkbzmm'].clone().set_position(12, 0),
            sprites['uasmnkbzmm'].clone().set_position(12, 4),
            sprites['uasmnkbzmm'].clone().set_position(12, 8),
            sprites['uasmnkbzmm'].clone().set_position(12, 48),
            sprites['uasmnkbzmm'].clone().set_position(16, 48),
            sprites['uasmnkbzmm'].clone().set_position(16, 52),
            sprites['uasmnkbzmm'].clone().set_position(24, 4),
            sprites['uasmnkbzmm'].clone().set_position(24, 8),
            sprites['uasmnkbzmm'].clone().set_position(24, 52),
            sprites['uasmnkbzmm'].clone().set_position(32, 48),
            sprites['uasmnkbzmm'].clone().set_position(32, 52),
            sprites['uasmnkbzmm'].clone().set_position(40, 24),
            sprites['uasmnkbzmm'].clone().set_position(40, 56),
            sprites['uasmnkbzmm'].clone().set_position(44, 0),
            sprites['uasmnkbzmm'].clone().set_position(44, 12),
            sprites['uasmnkbzmm'].clone().set_position(44, 56),
            sprites['uasmnkbzmm'].clone().set_position(44, 60),
            sprites['uasmnkbzmm'].clone().set_position(48, 0),
            sprites['uasmnkbzmm'].clone().set_position(48, 4),
            sprites['uasmnkbzmm'].clone().set_position(48, 36),
            sprites['uasmnkbzmm'].clone().set_position(48, 40),
            sprites['uasmnkbzmm'].clone().set_position(52, 0),
            sprites['uasmnkbzmm'].clone().set_position(56, 0),
            sprites['uasmnkbzmm'].clone().set_position(56, 4),
            sprites['uasmnkbzmm'].clone().set_position(56, 8),
            sprites['uasmnkbzmm'].clone().set_position(56, 12),
            sprites['uasmnkbzmm'].clone().set_position(56, 28),
            sprites['uasmnkbzmm'].clone().set_position(56, 40),
            sprites['uasmnkbzmm'].clone().set_position(56, 44),
            sprites['uasmnkbzmm'].clone().set_position(56, 48),
            sprites['uasmnkbzmm'].clone().set_position(56, 52),
            sprites['uasmnkbzmm'].clone().set_position(56, 56),
            sprites['uasmnkbzmm'].clone().set_position(60, 4),
            sprites['uasmnkbzmm'].clone().set_position(60, 12),
            sprites['uasmnkbzmm'].clone().set_position(60, 28),
            sprites['uasmnkbzmm'].clone().set_position(60, 32),
        ],
        grid_size=(64, 64),
        data={'StepCounter': 100},
    ),
    # Level 4
    Level(
        sprites=[
            sprites['byigobxzpg'].clone().set_position(4, 4),
            sprites['byigobxzpg'].clone().set_position(52, 12),
            sprites['byigobxzpg'].clone().set_position(36, 56),
            sprites['ofwegeqknn'].clone().set_position(56, 24),
            sprites['pktgsotzmw'].clone().set_position(28, 36),
            sprites['pktgsotzmw'].clone().set_position(36, 24),
            sprites['pktgsotzmw'].clone().set_position(24, 40),
            sprites['pktgsotzmw'].clone().set_position(36, 40),
            sprites['pktgsotzmw'].clone().set_position(28, 24),
            sprites['pktgsotzmw'].clone().set_position(24, 24),
            sprites['pktgsotzmw'].clone().set_position(36, 4),
            sprites['pmargquscu'].clone().set_position(32, 20),
            sprites['pmargquscu'].clone().set_position(36, 20),
            sprites['pmargquscu'].clone().set_position(40, 20),
            sprites['pmargquscu'].clone().set_position(40, 24),
            sprites['pmargquscu'].clone().set_position(40, 28),
            sprites['pmargquscu'].clone().set_position(40, 32),
            sprites['pmargquscu'].clone().set_position(40, 36),
            sprites['pmargquscu'].clone().set_position(40, 40),
            sprites['pmargquscu'].clone().set_position(40, 44),
            sprites['pmargquscu'].clone().set_position(28, 20),
            sprites['pmargquscu'].clone().set_position(24, 20),
            sprites['pmargquscu'].clone().set_position(20, 20),
            sprites['pmargquscu'].clone().set_position(20, 24),
            sprites['pmargquscu'].clone().set_position(36, 44),
            sprites['pmargquscu'].clone().set_position(32, 44),
            sprites['pmargquscu'].clone().set_position(28, 44),
            sprites['pmargquscu'].clone().set_position(24, 44),
            sprites['pmargquscu'].clone().set_position(20, 44),
            sprites['pmargquscu'].clone().set_position(20, 40),
            sprites['pmargquscu'].clone().set_position(20, 36),
            sprites['pmargquscu'].clone().set_position(20, 32),
            sprites['pmargquscu'].clone().set_position(20, 28),
            sprites['uasmnkbzmm'].clone().set_position(44, 48),
            sprites['uasmnkbzmm'].clone().set_position(48, 52),
            sprites['uasmnkbzmm'].clone().set_position(52, 56),
            sprites['uasmnkbzmm'].clone().set_position(56, 60),
            sprites['uasmnkbzmm'].clone().set_position(16, 48),
            sprites['uasmnkbzmm'].clone().set_position(12, 52),
            sprites['uasmnkbzmm'].clone().set_position(8, 56),
            sprites['uasmnkbzmm'].clone().set_position(4, 60),
            sprites['uasmnkbzmm'].clone().set_position(32, 4),
            sprites['uasmnkbzmm'].clone().set_position(32, 0),
            sprites['uasmnkbzmm'].clone().set_position(32, 8),
            sprites['uasmnkbzmm'].clone().set_position(32, 12),
            sprites['uasmnkbzmm'].clone().set_position(32, 16),
            sprites['wkmuwhjqyo'].clone().set_position(20, 56),
            sprites['wppuejnwhl'].clone().set_position(32, 32),
            sprites['xxmzyqktqy'].clone().set_position(52, 36),
            sprites['xxmzyqktqy'].clone().set_position(8, 28),
            sprites['xxmzyqktqy'].clone().set_position(4, 20),
            sprites['uasmnkbzmm'].clone().set_position(0, 8),
            sprites['uasmnkbzmm'].clone().set_position(0, 40),
            sprites['uasmnkbzmm'].clone().set_position(0, 44),
            sprites['uasmnkbzmm'].clone().set_position(4, 0),
            sprites['uasmnkbzmm'].clone().set_position(4, 8),
            sprites['uasmnkbzmm'].clone().set_position(4, 44),
            sprites['uasmnkbzmm'].clone().set_position(8, 0),
            sprites['uasmnkbzmm'].clone().set_position(8, 8),
            sprites['uasmnkbzmm'].clone().set_position(8, 32),
            sprites['uasmnkbzmm'].clone().set_position(8, 44),
            sprites['uasmnkbzmm'].clone().set_position(12, 8),
            sprites['uasmnkbzmm'].clone().set_position(12, 12),
            sprites['uasmnkbzmm'].clone().set_position(12, 16),
            sprites['uasmnkbzmm'].clone().set_position(12, 20),
            sprites['uasmnkbzmm'].clone().set_position(12, 32),
            sprites['uasmnkbzmm'].clone().set_position(12, 40),
            sprites['uasmnkbzmm'].clone().set_position(12, 44),
            sprites['uasmnkbzmm'].clone().set_position(12, 56),
            sprites['uasmnkbzmm'].clone().set_position(12, 60),
            sprites['uasmnkbzmm'].clone().set_position(16, 0),
            sprites['uasmnkbzmm'].clone().set_position(16, 32),
            sprites['uasmnkbzmm'].clone().set_position(20, 0),
            sprites['uasmnkbzmm'].clone().set_position(20, 16),
            sprites['uasmnkbzmm'].clone().set_position(24, 0),
            sprites['uasmnkbzmm'].clone().set_position(24, 16),
            sprites['uasmnkbzmm'].clone().set_position(28, 0),
            sprites['uasmnkbzmm'].clone().set_position(32, 60),
            sprites['uasmnkbzmm'].clone().set_position(40, 56),
            sprites['uasmnkbzmm'].clone().set_position(44, 0),
            sprites['uasmnkbzmm'].clone().set_position(44, 56),
            sprites['uasmnkbzmm'].clone().set_position(44, 60),
            sprites['uasmnkbzmm'].clone().set_position(48, 0),
            sprites['uasmnkbzmm'].clone().set_position(52, 0),
            sprites['uasmnkbzmm'].clone().set_position(52, 44),
            sprites['uasmnkbzmm'].clone().set_position(56, 0),
            sprites['uasmnkbzmm'].clone().set_position(56, 40),
            sprites['uasmnkbzmm'].clone().set_position(56, 44),
            sprites['uasmnkbzmm'].clone().set_position(56, 56),
            sprites['uasmnkbzmm'].clone().set_position(60, 44),
            sprites['uasmnkbzmm'].clone().set_position(60, 56),
        ],
        grid_size=(64, 64),
        data={'StepCounter': 100},
    ),
    # Level 5
    Level(
        sprites=[
            sprites['byigobxzpg'].clone().set_position(40, 28),
            sprites['ktghqrydvd'].clone().set_position(48, 24),
            sprites['pktgsotzmw'].clone().set_position(8, 48),
            sprites['pktgsotzmw'].clone().set_position(0, 52),
            sprites['pktgsotzmw'].clone().set_position(12, 4),
            sprites['pktgsotzmw'].clone().set_position(4, 8),
            sprites['pktgsotzmw'].clone().set_position(16, 56),
            sprites['pktgsotzmw'].clone().set_position(16, 28),
            sprites['uasmnkbzmm'].clone().set_position(36, 24),
            sprites['uasmnkbzmm'].clone().set_position(32, 24),
            sprites['uasmnkbzmm'].clone().set_position(28, 24),
            sprites['uasmnkbzmm'].clone().set_position(24, 24),
            sprites['uasmnkbzmm'].clone().set_position(24, 20),
            sprites['uasmnkbzmm'].clone().set_position(24, 16),
            sprites['uasmnkbzmm'].clone().set_position(24, 12),
            sprites['uasmnkbzmm'].clone().set_position(24, 8),
            sprites['uasmnkbzmm'].clone().set_position(24, 4),
            sprites['uasmnkbzmm'].clone().set_position(24, 0),
            sprites['uasmnkbzmm'].clone().set_position(24, 60),
            sprites['uasmnkbzmm'].clone().set_position(24, 56),
            sprites['uasmnkbzmm'].clone().set_position(24, 52),
            sprites['uasmnkbzmm'].clone().set_position(24, 48),
            sprites['uasmnkbzmm'].clone().set_position(24, 44),
            sprites['uasmnkbzmm'].clone().set_position(24, 40),
            sprites['uasmnkbzmm'].clone().set_position(24, 36),
            sprites['uasmnkbzmm'].clone().set_position(36, 36),
            sprites['uasmnkbzmm'].clone().set_position(32, 36),
            sprites['uasmnkbzmm'].clone().set_position(28, 36),
            sprites['wppuejnwhl'].clone().set_position(16, 36),
            sprites['uasmnkbzmm'].clone().set_position(0, 4),
            sprites['uasmnkbzmm'].clone().set_position(0, 8),
            sprites['uasmnkbzmm'].clone().set_position(0, 12),
            sprites['uasmnkbzmm'].clone().set_position(0, 16),
            sprites['uasmnkbzmm'].clone().set_position(0, 20),
            sprites['uasmnkbzmm'].clone().set_position(0, 24),
            sprites['uasmnkbzmm'].clone().set_position(0, 56),
            sprites['uasmnkbzmm'].clone().set_position(0, 60),
            sprites['uasmnkbzmm'].clone().set_position(4, 36),
            sprites['uasmnkbzmm'].clone().set_position(4, 40),
            sprites['uasmnkbzmm'].clone().set_position(4, 60),
            sprites['uasmnkbzmm'].clone().set_position(8, 16),
            sprites['uasmnkbzmm'].clone().set_position(8, 60),
            sprites['uasmnkbzmm'].clone().set_position(12, 48),
            sprites['uasmnkbzmm'].clone().set_position(12, 52),
            sprites['uasmnkbzmm'].clone().set_position(12, 56),
            sprites['uasmnkbzmm'].clone().set_position(12, 60),
            sprites['uasmnkbzmm'].clone().set_position(16, 16),
            sprites['uasmnkbzmm'].clone().set_position(16, 20),
            sprites['uasmnkbzmm'].clone().set_position(16, 60),
            sprites['uasmnkbzmm'].clone().set_position(20, 20),
            sprites['uasmnkbzmm'].clone().set_position(20, 24),
            sprites['uasmnkbzmm'].clone().set_position(20, 60),
            sprites['uasmnkbzmm'].clone().set_position(28, 52),
            sprites['uasmnkbzmm'].clone().set_position(32, 4),
            sprites['uasmnkbzmm'].clone().set_position(32, 16),
            sprites['uasmnkbzmm'].clone().set_position(32, 52),
            sprites['uasmnkbzmm'].clone().set_position(32, 56),
            sprites['uasmnkbzmm'].clone().set_position(32, 60),
            sprites['uasmnkbzmm'].clone().set_position(36, 4),
            sprites['uasmnkbzmm'].clone().set_position(36, 16),
            sprites['uasmnkbzmm'].clone().set_position(36, 52),
            sprites['uasmnkbzmm'].clone().set_position(40, 4),
            sprites['uasmnkbzmm'].clone().set_position(40, 52),
            sprites['uasmnkbzmm'].clone().set_position(44, 8),
            sprites['uasmnkbzmm'].clone().set_position(44, 12),
            sprites['uasmnkbzmm'].clone().set_position(44, 52),
            sprites['uasmnkbzmm'].clone().set_position(48, 8),
            sprites['uasmnkbzmm'].clone().set_position(48, 12),
            sprites['uasmnkbzmm'].clone().set_position(52, 8),
            sprites['uasmnkbzmm'].clone().set_position(52, 12),
            sprites['uasmnkbzmm'].clone().set_position(56, 8),
            sprites['uasmnkbzmm'].clone().set_position(56, 12),
            sprites['uasmnkbzmm'].clone().set_position(56, 52),
            sprites['uasmnkbzmm'].clone().set_position(56, 56),
            sprites['uasmnkbzmm'].clone().set_position(56, 60),
            sprites['uasmnkbzmm'].clone().set_position(60, 36),
            sprites['uasmnkbzmm'].clone().set_position(60, 52),
        ],
        grid_size=(64, 64),
        data={'StepCounter': 125},
    ),
    # Level 6
    Level(
        sprites=[
            sprites['ghklglzjuf'].clone().set_position(28, 12),
            sprites['jqzhxgbmtz'].clone().set_position(44, 16),
            sprites['ooaamfpvqr'].clone().set_position(4, 24),
            sprites['pktgsotzmw'].clone().set_position(4, 28),
            sprites['pktgsotzmw'].clone().set_position(32, 16),
            sprites['uasmnkbzmm'].clone().set_position(16, 0),
            sprites['uasmnkbzmm'].clone().set_position(16, 4),
            sprites['uasmnkbzmm'].clone().set_position(16, 8),
            sprites['uasmnkbzmm'].clone().set_position(16, 12),
            sprites['uasmnkbzmm'].clone().set_position(16, 16),
            sprites['uasmnkbzmm'].clone().set_position(16, 20),
            sprites['uasmnkbzmm'].clone().set_position(12, 0),
            sprites['uasmnkbzmm'].clone().set_position(12, 4),
            sprites['uasmnkbzmm'].clone().set_position(12, 8),
            sprites['uasmnkbzmm'].clone().set_position(12, 12),
            sprites['uasmnkbzmm'].clone().set_position(12, 16),
            sprites['uasmnkbzmm'].clone().set_position(12, 20),
            sprites['uasmnkbzmm'].clone().set_position(16, 28),
            sprites['uasmnkbzmm'].clone().set_position(16, 32),
            sprites['uasmnkbzmm'].clone().set_position(16, 36),
            sprites['uasmnkbzmm'].clone().set_position(16, 40),
            sprites['uasmnkbzmm'].clone().set_position(16, 44),
            sprites['uasmnkbzmm'].clone().set_position(16, 48),
            sprites['uasmnkbzmm'].clone().set_position(12, 28),
            sprites['uasmnkbzmm'].clone().set_position(12, 32),
            sprites['uasmnkbzmm'].clone().set_position(12, 36),
            sprites['uasmnkbzmm'].clone().set_position(12, 40),
            sprites['uasmnkbzmm'].clone().set_position(12, 44),
            sprites['uasmnkbzmm'].clone().set_position(12, 48),
            sprites['uasmnkbzmm'].clone().set_position(16, 52),
            sprites['uasmnkbzmm'].clone().set_position(16, 56),
            sprites['uasmnkbzmm'].clone().set_position(12, 52),
            sprites['uasmnkbzmm'].clone().set_position(12, 56),
            sprites['uasmnkbzmm'].clone().set_position(16, 60),
            sprites['uasmnkbzmm'].clone().set_position(12, 60),
            sprites['wppuejnwhl'].clone().set_position(40, 52),
            sprites['uasmnkbzmm'].clone().set_position(0, 0),
            sprites['uasmnkbzmm'].clone().set_position(0, 4),
            sprites['uasmnkbzmm'].clone().set_position(0, 8),
            sprites['uasmnkbzmm'].clone().set_position(0, 12),
            sprites['uasmnkbzmm'].clone().set_position(0, 16),
            sprites['uasmnkbzmm'].clone().set_position(0, 40),
            sprites['uasmnkbzmm'].clone().set_position(0, 44),
            sprites['uasmnkbzmm'].clone().set_position(0, 48),
            sprites['uasmnkbzmm'].clone().set_position(0, 52),
            sprites['uasmnkbzmm'].clone().set_position(0, 56),
            sprites['uasmnkbzmm'].clone().set_position(0, 60),
            sprites['uasmnkbzmm'].clone().set_position(4, 0),
            sprites['uasmnkbzmm'].clone().set_position(4, 4),
            sprites['uasmnkbzmm'].clone().set_position(4, 8),
            sprites['uasmnkbzmm'].clone().set_position(4, 44),
            sprites['uasmnkbzmm'].clone().set_position(4, 48),
            sprites['uasmnkbzmm'].clone().set_position(4, 52),
            sprites['uasmnkbzmm'].clone().set_position(4, 56),
            sprites['uasmnkbzmm'].clone().set_position(4, 60),
            sprites['uasmnkbzmm'].clone().set_position(8, 0),
            sprites['uasmnkbzmm'].clone().set_position(8, 4),
            sprites['uasmnkbzmm'].clone().set_position(8, 8),
            sprites['uasmnkbzmm'].clone().set_position(8, 12),
            sprites['uasmnkbzmm'].clone().set_position(8, 16),
            sprites['uasmnkbzmm'].clone().set_position(8, 20),
            sprites['uasmnkbzmm'].clone().set_position(8, 56),
            sprites['uasmnkbzmm'].clone().set_position(8, 60),
            sprites['uasmnkbzmm'].clone().set_position(20, 0),
            sprites['uasmnkbzmm'].clone().set_position(20, 4),
            sprites['uasmnkbzmm'].clone().set_position(20, 8),
            sprites['uasmnkbzmm'].clone().set_position(20, 12),
            sprites['uasmnkbzmm'].clone().set_position(20, 52),
            sprites['uasmnkbzmm'].clone().set_position(20, 56),
            sprites['uasmnkbzmm'].clone().set_position(20, 60),
            sprites['uasmnkbzmm'].clone().set_position(24, 0),
            sprites['uasmnkbzmm'].clone().set_position(24, 4),
            sprites['uasmnkbzmm'].clone().set_position(24, 8),
            sprites['uasmnkbzmm'].clone().set_position(24, 56),
            sprites['uasmnkbzmm'].clone().set_position(24, 60),
            sprites['uasmnkbzmm'].clone().set_position(28, 0),
            sprites['uasmnkbzmm'].clone().set_position(32, 0),
            sprites['uasmnkbzmm'].clone().set_position(36, 0),
            sprites['uasmnkbzmm'].clone().set_position(52, 0),
            sprites['uasmnkbzmm'].clone().set_position(52, 4),
            sprites['uasmnkbzmm'].clone().set_position(56, 0),
            sprites['uasmnkbzmm'].clone().set_position(56, 4),
            sprites['uasmnkbzmm'].clone().set_position(60, 0),
            sprites['uasmnkbzmm'].clone().set_position(60, 4),
            sprites['uasmnkbzmm'].clone().set_position(60, 8),
            sprites['uasmnkbzmm'].clone().set_position(60, 12),
            sprites['uasmnkbzmm'].clone().set_position(60, 52),
            sprites['uasmnkbzmm'].clone().set_position(60, 56),
            sprites['uasmnkbzmm'].clone().set_position(60, 60),
        ],
        grid_size=(64, 64),
        data={'StepCounter': 75},
    ),
    # Level 7
    Level(
        sprites=[
            sprites['aidclcbjcv'].clone().set_position(0, 44),
            sprites['cwefnfvjhr'].clone().set_position(0, 0),
            sprites['geffskzhqq'].clone().set_position(12, 28),
            sprites['jqzhxgbmtz'].clone().set_position(20, 32),
            sprites['ofwegeqknn'].clone().set_position(48, 28),
            sprites['pktgsotzmw'].clone().set_position(28, 24),
            sprites['pktgsotzmw'].clone().set_position(32, 32),
            sprites['uasmnkbzmm'].clone().set_position(60, 16),
            sprites['uasmnkbzmm'].clone().set_position(56, 16),
            sprites['uasmnkbzmm'].clone().set_position(52, 16),
            sprites['uasmnkbzmm'].clone().set_position(48, 16),
            sprites['uasmnkbzmm'].clone().set_position(44, 16),
            sprites['uasmnkbzmm'].clone().set_position(40, 16),
            sprites['uasmnkbzmm'].clone().set_position(36, 16),
            sprites['uasmnkbzmm'].clone().set_position(32, 16),
            sprites['uasmnkbzmm'].clone().set_position(28, 16),
            sprites['uasmnkbzmm'].clone().set_position(24, 16),
            sprites['uasmnkbzmm'].clone().set_position(20, 16),
            sprites['uasmnkbzmm'].clone().set_position(16, 16),
            sprites['uasmnkbzmm'].clone().set_position(12, 16),
            sprites['uasmnkbzmm'].clone().set_position(8, 16),
            sprites['uasmnkbzmm'].clone().set_position(4, 16),
            sprites['uasmnkbzmm'].clone().set_position(0, 16),
            sprites['uasmnkbzmm'].clone().set_position(60, 40),
            sprites['uasmnkbzmm'].clone().set_position(56, 40),
            sprites['uasmnkbzmm'].clone().set_position(52, 40),
            sprites['uasmnkbzmm'].clone().set_position(48, 40),
            sprites['uasmnkbzmm'].clone().set_position(44, 40),
            sprites['uasmnkbzmm'].clone().set_position(40, 40),
            sprites['uasmnkbzmm'].clone().set_position(36, 40),
            sprites['uasmnkbzmm'].clone().set_position(32, 40),
            sprites['uasmnkbzmm'].clone().set_position(28, 40),
            sprites['uasmnkbzmm'].clone().set_position(24, 40),
            sprites['uasmnkbzmm'].clone().set_position(20, 40),
            sprites['uasmnkbzmm'].clone().set_position(16, 40),
            sprites['uasmnkbzmm'].clone().set_position(12, 40),
            sprites['uasmnkbzmm'].clone().set_position(8, 40),
            sprites['uasmnkbzmm'].clone().set_position(4, 40),
            sprites['uasmnkbzmm'].clone().set_position(0, 40),
            sprites['wppuejnwhl'].clone().set_position(40, 32),
            sprites['uasmnkbzmm'].clone().set_position(0, 20),
            sprites['uasmnkbzmm'].clone().set_position(0, 24),
            sprites['uasmnkbzmm'].clone().set_position(0, 28),
            sprites['uasmnkbzmm'].clone().set_position(0, 32),
            sprites['uasmnkbzmm'].clone().set_position(0, 36),
            sprites['uasmnkbzmm'].clone().set_position(4, 20),
            sprites['uasmnkbzmm'].clone().set_position(4, 32),
            sprites['uasmnkbzmm'].clone().set_position(4, 36),
            sprites['uasmnkbzmm'].clone().set_position(8, 20),
            sprites['uasmnkbzmm'].clone().set_position(8, 36),
            sprites['uasmnkbzmm'].clone().set_position(12, 20),
            sprites['uasmnkbzmm'].clone().set_position(16, 20),
            sprites['uasmnkbzmm'].clone().set_position(20, 20),
            sprites['uasmnkbzmm'].clone().set_position(24, 20),
            sprites['uasmnkbzmm'].clone().set_position(28, 20),
        ],
        grid_size=(64, 64),
        data={'StepCounter': 125},
    ),
    # Level 8
    Level(
        sprites=[
            sprites['byigobxzpg'].clone().set_position(32, 4),
            sprites['byigobxzpg'].clone().set_position(24, 44),
            sprites['jqzhxgbmtz'].clone().set_position(28, 16),
            sprites['jqzhxgbmtz'].clone().set_position(28, 56),
            sprites['peimznrlqd'].clone().set_position(4, 48),
            sprites['pktgsotzmw'].clone().set_position(28, 12),
            sprites['pktgsotzmw'].clone().set_position(32, 8),
            sprites['pktgsotzmw'].clone().set_position(20, 52),
            sprites['pktgsotzmw'].clone().set_position(24, 48),
            sprites['pktgsotzmw'].clone().set_position(32, 52),
            sprites['pktgsotzmw'].clone().set_position(28, 52),
            sprites['pktgsotzmw'].clone().set_position(24, 8),
            sprites['pktgsotzmw'].clone().set_position(36, 12),
            sprites['pktgsotzmw'].clone().set_position(56, 8),
            sprites['pktgsotzmw'].clone().set_position(52, 12),
            sprites['pktgsotzmw'].clone().set_position(52, 8),
            sprites['pktgsotzmw'].clone().set_position(56, 12),
            sprites['pktgsotzmw'].clone().set_position(36, 44),
            sprites['uasmnkbzmm'].clone().set_position(36, 24),
            sprites['uasmnkbzmm'].clone().set_position(32, 24),
            sprites['uasmnkbzmm'].clone().set_position(52, 24),
            sprites['uasmnkbzmm'].clone().set_position(48, 24),
            sprites['uasmnkbzmm'].clone().set_position(60, 24),
            sprites['uasmnkbzmm'].clone().set_position(56, 24),
            sprites['uasmnkbzmm'].clone().set_position(28, 24),
            sprites['uasmnkbzmm'].clone().set_position(24, 24),
            sprites['uasmnkbzmm'].clone().set_position(20, 24),
            sprites['uasmnkbzmm'].clone().set_position(16, 24),
            sprites['uasmnkbzmm'].clone().set_position(12, 24),
            sprites['uasmnkbzmm'].clone().set_position(8, 24),
            sprites['uasmnkbzmm'].clone().set_position(4, 24),
            sprites['uasmnkbzmm'].clone().set_position(0, 24),
            sprites['uasmnkbzmm'].clone().set_position(16, 36),
            sprites['uasmnkbzmm'].clone().set_position(12, 36),
            sprites['uasmnkbzmm'].clone().set_position(8, 36),
            sprites['uasmnkbzmm'].clone().set_position(4, 36),
            sprites['uasmnkbzmm'].clone().set_position(0, 36),
            sprites['uasmnkbzmm'].clone().set_position(60, 36),
            sprites['uasmnkbzmm'].clone().set_position(56, 36),
            sprites['uasmnkbzmm'].clone().set_position(52, 36),
            sprites['uasmnkbzmm'].clone().set_position(48, 36),
            sprites['uasmnkbzmm'].clone().set_position(44, 36),
            sprites['uasmnkbzmm'].clone().set_position(40, 36),
            sprites['uasmnkbzmm'].clone().set_position(36, 36),
            sprites['uasmnkbzmm'].clone().set_position(32, 36),
            sprites['uasmnkbzmm'].clone().set_position(28, 36),
            sprites['vikkhnsrzd'].clone().set_position(4, 8),
            sprites['wppuejnwhl'].clone().set_position(56, 32),
            sprites['xqaqifquaw'].clone().set_position(48, 8),
            sprites['xqaqifquaw'].clone().set_position(40, 48),
            sprites['uasmnkbzmm'].clone().set_position(0, 0),
            sprites['uasmnkbzmm'].clone().set_position(0, 4),
            sprites['uasmnkbzmm'].clone().set_position(0, 28),
            sprites['uasmnkbzmm'].clone().set_position(0, 32),
            sprites['uasmnkbzmm'].clone().set_position(0, 56),
            sprites['uasmnkbzmm'].clone().set_position(0, 60),
            sprites['uasmnkbzmm'].clone().set_position(4, 32),
            sprites['uasmnkbzmm'].clone().set_position(4, 60),
            sprites['uasmnkbzmm'].clone().set_position(8, 32),
            sprites['uasmnkbzmm'].clone().set_position(48, 28),
            sprites['uasmnkbzmm'].clone().set_position(52, 28),
            sprites['uasmnkbzmm'].clone().set_position(56, 0),
            sprites['uasmnkbzmm'].clone().set_position(56, 28),
            sprites['uasmnkbzmm'].clone().set_position(56, 40),
            sprites['uasmnkbzmm'].clone().set_position(60, 0),
            sprites['uasmnkbzmm'].clone().set_position(60, 28),
            sprites['uasmnkbzmm'].clone().set_position(60, 40),
            sprites['uasmnkbzmm'].clone().set_position(60, 44),
            sprites['uasmnkbzmm'].clone().set_position(60, 48),
            sprites['uasmnkbzmm'].clone().set_position(60, 52),
            sprites['uasmnkbzmm'].clone().set_position(60, 56),
            sprites['uasmnkbzmm'].clone().set_position(60, 60),
        ],
        grid_size=(64, 64),
        data={'StepCounter': 150},
    ),
    # Level 9
    Level(
        sprites=[
            sprites['byigobxzpg'].clone().set_position(44, 28),
            sprites['byigobxzpg'].clone().set_position(16, 4),
            sprites['jqzhxgbmtz'].clone().set_position(0, 56),
            sprites['ooaamfpvqr'].clone().set_position(52, 28),
            sprites['peimznrlqd'].clone().set_position(32, 12),
            sprites['pktgsotzmw'].clone().set_position(48, 20),
            sprites['pktgsotzmw'].clone().set_position(52, 28),
            sprites['pktgsotzmw'].clone().set_position(56, 20),
            sprites['pktgsotzmw'].clone().set_position(56, 32),
            sprites['pktgsotzmw'].clone().set_position(4, 32),
            sprites['pktgsotzmw'].clone().set_position(16, 20),
            sprites['pktgsotzmw'].clone().set_position(52, 12),
            sprites['pktgsotzmw'].clone().set_position(12, 28),
            sprites['pktgsotzmw'].clone().set_position(56, 28),
            sprites['pmargquscu'].clone().set_position(8, 12),
            sprites['pmargquscu'].clone().set_position(20, 12),
            sprites['pmargquscu'].clone().set_position(4, 12),
            sprites['pmargquscu'].clone().set_position(0, 12),
            sprites['pmargquscu'].clone().set_position(12, 12),
            sprites['pmargquscu'].clone().set_position(16, 12),
            sprites['uasmnkbzmm'].clone().set_position(20, 40),
            sprites['uasmnkbzmm'].clone().set_position(24, 40),
            sprites['uasmnkbzmm'].clone().set_position(28, 40),
            sprites['uasmnkbzmm'].clone().set_position(4, 40),
            sprites['uasmnkbzmm'].clone().set_position(8, 40),
            sprites['uasmnkbzmm'].clone().set_position(12, 40),
            sprites['uasmnkbzmm'].clone().set_position(16, 40),
            sprites['uasmnkbzmm'].clone().set_position(0, 40),
            sprites['uasmnkbzmm'].clone().set_position(28, 44),
            sprites['uasmnkbzmm'].clone().set_position(28, 48),
            sprites['uasmnkbzmm'].clone().set_position(20, 56),
            sprites['uasmnkbzmm'].clone().set_position(20, 60),
            sprites['uasmnkbzmm'].clone().set_position(12, 44),
            sprites['uasmnkbzmm'].clone().set_position(12, 48),
            sprites['uasmnkbzmm'].clone().set_position(4, 48),
            sprites['uasmnkbzmm'].clone().set_position(4, 52),
            sprites['uasmnkbzmm'].clone().set_position(36, 56),
            sprites['uasmnkbzmm'].clone().set_position(36, 60),
            sprites['uasmnkbzmm'].clone().set_position(36, 52),
            sprites['uasmnkbzmm'].clone().set_position(36, 48),
            sprites['uasmnkbzmm'].clone().set_position(4, 56),
            sprites['uasmnkbzmm'].clone().set_position(4, 60),
            sprites['uasmnkbzmm'].clone().set_position(12, 52),
            sprites['uasmnkbzmm'].clone().set_position(12, 56),
            sprites['uasmnkbzmm'].clone().set_position(20, 48),
            sprites['uasmnkbzmm'].clone().set_position(20, 52),
            sprites['uasmnkbzmm'].clone().set_position(28, 56),
            sprites['uasmnkbzmm'].clone().set_position(28, 52),
            sprites['uasmnkbzmm'].clone().set_position(36, 40),
            sprites['uasmnkbzmm'].clone().set_position(32, 40),
            sprites['uasmnkbzmm'].clone().set_position(44, 40),
            sprites['uasmnkbzmm'].clone().set_position(40, 40),
            sprites['uasmnkbzmm'].clone().set_position(44, 44),
            sprites['uasmnkbzmm'].clone().set_position(44, 48),
            sprites['uasmnkbzmm'].clone().set_position(44, 56),
            sprites['uasmnkbzmm'].clone().set_position(44, 52),
            sprites['uasmnkbzmm'].clone().set_position(24, 0),
            sprites['uasmnkbzmm'].clone().set_position(24, 4),
            sprites['uasmnkbzmm'].clone().set_position(24, 8),
            sprites['uasmnkbzmm'].clone().set_position(24, 16),
            sprites['uasmnkbzmm'].clone().set_position(24, 12),
            sprites['uasmnkbzmm'].clone().set_position(24, 20),
            sprites['uasmnkbzmm'].clone().set_position(24, 24),
            sprites['uasmnkbzmm'].clone().set_position(24, 28),
            sprites['uasmnkbzmm'].clone().set_position(52, 60),
            sprites['uasmnkbzmm'].clone().set_position(52, 56),
            sprites['uasmnkbzmm'].clone().set_position(52, 52),
            sprites['uasmnkbzmm'].clone().set_position(52, 48),
            sprites['uasmnkbzmm'].clone().set_position(52, 44),
            sprites['uasmnkbzmm'].clone().set_position(52, 40),
            sprites['wkmuwhjqyo'].clone().set_position(4, 24),
            sprites['wkmuwhjqyo'].clone().set_position(4, 8),
            sprites['wppuejnwhl'].clone().set_position(28, 32),
            sprites['uasmnkbzmm'].clone().set_position(0, 0),
            sprites['uasmnkbzmm'].clone().set_position(0, 4),
            sprites['uasmnkbzmm'].clone().set_position(0, 8),
            sprites['uasmnkbzmm'].clone().set_position(4, 0),
            sprites['uasmnkbzmm'].clone().set_position(4, 4),
            sprites['uasmnkbzmm'].clone().set_position(8, 0),
            sprites['uasmnkbzmm'].clone().set_position(12, 0),
            sprites['uasmnkbzmm'].clone().set_position(16, 0),
            sprites['uasmnkbzmm'].clone().set_position(20, 0),
            sprites['uasmnkbzmm'].clone().set_position(20, 4),
            sprites['uasmnkbzmm'].clone().set_position(20, 8),
            sprites['uasmnkbzmm'].clone().set_position(20, 16),
            sprites['uasmnkbzmm'].clone().set_position(28, 0),
            sprites['uasmnkbzmm'].clone().set_position(44, 0),
            sprites['uasmnkbzmm'].clone().set_position(48, 0),
            sprites['uasmnkbzmm'].clone().set_position(52, 0),
            sprites['uasmnkbzmm'].clone().set_position(56, 0),
            sprites['uasmnkbzmm'].clone().set_position(60, 0),
            sprites['uasmnkbzmm'].clone().set_position(60, 4),
            sprites['uasmnkbzmm'].clone().set_position(60, 8),
            sprites['uasmnkbzmm'].clone().set_position(60, 52),
            sprites['uasmnkbzmm'].clone().set_position(60, 56),
            sprites['uasmnkbzmm'].clone().set_position(60, 60),
        ],
        grid_size=(64, 64),
        data={'StepCounter': 70},
    ),
]
BACKGROUND_COLOR = 1
PADDING_COLOR = 0
celomdfhbh = 4
wvrpthjfsv = 4
vlzkmytlgh = 3
hgqlwjikqr = 0
qrmfayeqpo = 5
ansrsmsvzs = 15
lajjveeqzb = 11


class etuniyewsy(RenderableUserDisplay):
    """."""

    def __init__(self, dbdarsgrbj: int):
        """."""
        self.dbdarsgrbj = dbdarsgrbj
        self.current_steps = dbdarsgrbj

    def uwwwedmhqv(self, yfgynsqzmu: int) -> None:
        """."""
        self.current_steps = max(0, min(yfgynsqzmu, self.dbdarsgrbj))

    def pfakmupgbr(self) -> bool:
        """."""
        if self.current_steps > 0:
            self.current_steps -= 1
        return self.current_steps > 0

    def ububboesmh(self) -> None:
        """."""
        self.current_steps = self.dbdarsgrbj

    def render_interface(self, frame: np.ndarray) -> np.ndarray:
        """."""
        if self.dbdarsgrbj == 0:
            return frame
        icsbqzymhf = self.current_steps / self.dbdarsgrbj
        eagwaqduxs = round(64 * icsbqzymhf)
        for x in range(64):
            if x < eagwaqduxs:
                frame[0, 63 - x] = 7
            else:
                frame[0, 63 - x] = 4
        return frame


class wjdpciselr(Camera):
    """."""

    def _raw_render(self, sprites: list[Sprite]) -> np.ndarray:
        output = np.full((self._height, self._width), self._background, dtype=np.int8)
        for sprite in sprites:
            sprite_pixels = sprite.pixels
            sprite_height, sprite_width = sprite_pixels.shape
            rel_x = sprite._x - self._x
            rel_y = sprite._y - self._y
            dest_x_start = max(0, rel_x)
            dest_x_end = min(self._width, rel_x + sprite_width)
            dest_y_start = max(0, rel_y)
            dest_y_end = min(self._height, rel_y + sprite_height)
            if dest_x_end <= dest_x_start or dest_y_end <= dest_y_start:
                continue
            sprite_x_start = max(0, -rel_x)
            sprite_x_end = sprite_width - max(0, rel_x + sprite_width - self._width)
            sprite_y_start = max(0, -rel_y)
            sprite_y_end = sprite_height - max(0, rel_y + sprite_height - self._height)
            sprite_region = sprite_pixels[sprite_y_start:sprite_y_end, sprite_x_start:sprite_x_end]
            visible_mask = sprite_region >= 0
            output[dest_y_start:dest_y_end, dest_x_start:dest_x_end][visible_mask] = sprite_region[visible_mask]
        return output


def hbipqrhvbm(rfwebuoepa: tuple[int, int], ixzwlkvsbs: tuple[int, int]) -> int:
    return abs(rfwebuoepa[0] - ixzwlkvsbs[0]) + abs(rfwebuoepa[1] - ixzwlkvsbs[1])


def mdbwmdaxuu(rfwebuoepa: tuple[int, int], ixzwlkvsbs: tuple[int, int]) -> bool:
    return hbipqrhvbm(rfwebuoepa, ixzwlkvsbs) == celomdfhbh


def vwiozbtqgi(fqdniajpfh: Sprite, sprite: Sprite) -> bool:
    if fqdniajpfh.rotation == 0:
        return fqdniajpfh.x == sprite.x and fqdniajpfh.y - celomdfhbh == sprite.y
    elif fqdniajpfh.rotation == 180:
        return fqdniajpfh.x == sprite.x and fqdniajpfh.y + celomdfhbh == sprite.y
    elif fqdniajpfh.rotation == 90:
        return fqdniajpfh.x + celomdfhbh == sprite.x and fqdniajpfh.y == sprite.y
    else:
        return fqdniajpfh.x - celomdfhbh == sprite.x and fqdniajpfh.y == sprite.y


def uxricavavq(sprite: Sprite, clhazarisu: int) -> None:
    sprite.pixels[:, 0] = clhazarisu
    sprite.pixels[:, 3] = clhazarisu
    sprite.pixels[0, :] = clhazarisu
    sprite.pixels[3, :] = clhazarisu


def pjedoipwee(dx: int, dy: int) -> int:
    if dy < 0:
        return 0
    elif dx > 0:
        return 90
    elif dy > 0:
        return 180
    return 270


def anojofkynf(v: tuple[int, int], sprite: Sprite) -> bool:
    return v[0] >= sprite.x and v[0] < sprite.x + sprite.width and (v[1] >= sprite.y) and (v[1] < sprite.y + sprite.height)


class _Wy30Rules(ARCBaseGame):
    kuncbnslnm: etuniyewsy
    nsevyuople: dict[Sprite, Sprite]
    zmqreragji: dict[Sprite, Sprite]
    pkbufziase: set[tuple[int, int]]
    wyzquhjerd: set[tuple[int, int]]
    lqctaojiby: set[tuple[int, int]]
    qthdiggudy: set[tuple[int, int]]
    lkvghqfwan: set[tuple[int, int]]
    uuorgjazmj: set[tuple[int, int]]

    def __init__(self) -> None:
        self.kuncbnslnm = etuniyewsy(0)
        sfahrdviv = Camera(
            background=BACKGROUND_COLOR,
            letter_box=PADDING_COLOR,
            interfaces=[self.kuncbnslnm],
        )
        super().__init__(
            game_id="wa30",
            levels=levels,
            camera=sfahrdviv,
            available_actions=[1, 2, 3, 4, 5],
        )

    def on_set_level(self, level: Level) -> None:
        self.xcuqvqnmiu()
        self.nsevyuople = dict()
        self.zmqreragji = dict()
        self.pkbufziase = set()
        self.wyzquhjerd = set()
        self.lqctaojiby = set()
        self.qthdiggudy = set()
        self.lkvghqfwan = set()
        self.uuorgjazmj = set()
        xdatcqhbr = self.current_level.get_sprites()
        for wunpnzavk in xdatcqhbr:
            if wunpnzavk.is_collidable:
                self.pkbufziase.add((wunpnzavk.x, wunpnzavk.y))
        for i in range(0, 64, celomdfhbh):
            self.pkbufziase.add((-celomdfhbh, i))
            self.pkbufziase.add((64, i))
            self.pkbufziase.add((i, -celomdfhbh))
            self.pkbufziase.add((i, 64))
        qiitczxxug = self.current_level.get_sprites_by_tag("fsjjayjoeg")
        for yotccnlopr in qiitczxxug:
            for i in range(yotccnlopr.height):
                for iiffofdbmb in range(yotccnlopr.width):
                    self.wyzquhjerd.add((yotccnlopr.x + iiffofdbmb, yotccnlopr.y + i))
        djpjnippwv = self.current_level.get_sprites_by_tag("zqxwgacnue")
        for tsrsytlfgb in djpjnippwv:
            for i in range(tsrsytlfgb.height):
                for iiffofdbmb in range(tsrsytlfgb.width):
                    self.lqctaojiby.add((tsrsytlfgb.x + iiffofdbmb, tsrsytlfgb.y + i))
        gflnevqmdv = self.current_level.get_sprites_by_tag("bnzklblgdk")
        for adxrpmucwx in gflnevqmdv:
            self.qthdiggudy.add((adxrpmucwx.x, adxrpmucwx.y))
        self.vyltpasvhc()
        self.lgirylubbp()

    def vyltpasvhc(self) -> None:
        """."""
        self.lkvghqfwan = set()
        fyfxmnwzhp = self.current_level.get_sprites_by_tag("geezpjgiyd")
        for ijudbtgsll in fyfxmnwzhp:
            if ijudbtgsll not in self.zmqreragji and (not self.shbxbhnhjc((ijudbtgsll.x, ijudbtgsll.y))):
                qrcmkiozlr = [
                    (ijudbtgsll.x - celomdfhbh, ijudbtgsll.y),
                    (ijudbtgsll.x + celomdfhbh, ijudbtgsll.y),
                    (ijudbtgsll.x, ijudbtgsll.y - celomdfhbh),
                    (ijudbtgsll.x, ijudbtgsll.y + celomdfhbh),
                ]
                for v in qrcmkiozlr:
                    self.lkvghqfwan.add(v)

    def lgirylubbp(self) -> None:
        """."""
        self.uuorgjazmj = set()
        fyfxmnwzhp = self.current_level.get_sprites_by_tag("geezpjgiyd")
        for ijudbtgsll in fyfxmnwzhp:
            if not self.jrrltylxpp(ijudbtgsll) and (not self.ahzqkfjpsc((ijudbtgsll.x, ijudbtgsll.y))):
                qrcmkiozlr = [
                    (ijudbtgsll.x - celomdfhbh, ijudbtgsll.y),
                    (ijudbtgsll.x + celomdfhbh, ijudbtgsll.y),
                    (ijudbtgsll.x, ijudbtgsll.y - celomdfhbh),
                    (ijudbtgsll.x, ijudbtgsll.y + celomdfhbh),
                ]
                for v in qrcmkiozlr:
                    self.uuorgjazmj.add(v)

    def xcuqvqnmiu(self) -> None:
        """."""
        drogceccgh = self.current_level.get_data("StepCounter")
        self.kuncbnslnm.dbdarsgrbj = drogceccgh
        self.kuncbnslnm.ububboesmh()

    def wqwsvmhhzj(self, fqdniajpfh: Sprite, x: int, y: int) -> None:
        if fqdniajpfh in self.nsevyuople:
            tkrlgpoppf = self.nsevyuople[fqdniajpfh]
            if self.fuykgiiwit(fqdniajpfh, tkrlgpoppf, (x, y)):
                dx, dy = (tkrlgpoppf.x - fqdniajpfh.x, tkrlgpoppf.y - fqdniajpfh.y)
                self.pkbufziase.remove((fqdniajpfh.x, fqdniajpfh.y))
                self.pkbufziase.remove((tkrlgpoppf.x, tkrlgpoppf.y))
                fqdniajpfh.set_position(x, y)
                tkrlgpoppf.set_position(x + dx, y + dy)
                self.pkbufziase.add((fqdniajpfh.x, fqdniajpfh.y))
                self.pkbufziase.add((tkrlgpoppf.x, tkrlgpoppf.y))
                self.lgirylubbp()
        elif self.kblzhbvysd((x, y)):
            self.pkbufziase.remove((fqdniajpfh.x, fqdniajpfh.y))
            fqdniajpfh.set_position(x, y)
            self.pkbufziase.add((fqdniajpfh.x, fqdniajpfh.y))

    def qnmfimgpwc(self, fqdniajpfh: Sprite, dx: int, dy: int) -> None:
        if fqdniajpfh not in self.nsevyuople:
            rotation = pjedoipwee(dx, dy)
            fqdniajpfh.set_rotation(rotation)
        self.wqwsvmhhzj(fqdniajpfh, fqdniajpfh.x + dx, fqdniajpfh.y + dy)

    def kblzhbvysd(self, v: tuple[int, int]) -> bool:
        return v not in self.pkbufziase and v not in self.qthdiggudy

    def fuykgiiwit(self, fqdniajpfh: Sprite, tkrlgpoppf: Sprite, v: tuple[int, int]) -> bool:
        dx = tkrlgpoppf.x - fqdniajpfh.x
        dy = tkrlgpoppf.y - fqdniajpfh.y
        tsvynrmpmm = (v[0] + dx, v[1] + dy)
        vouzrxjshl = (v not in self.pkbufziase or v == (tkrlgpoppf.x, tkrlgpoppf.y)) and v not in self.qthdiggudy and (tsvynrmpmm not in self.pkbufziase or tsvynrmpmm == (fqdniajpfh.x, fqdniajpfh.y))
        return vouzrxjshl

    def shbxbhnhjc(self, v: tuple[int, int]) -> bool:
        return v in self.wyzquhjerd

    def ahzqkfjpsc(self, v: tuple[int, int]) -> bool:
        return v in self.lqctaojiby

    def czrprbohhe(self, fqdniajpfh: Sprite) -> list[tuple[int, int]] | None:
        kpiyvjksem = (fqdniajpfh.x, fqdniajpfh.y)
        qkmekaxaqf = set()
        qkmekaxaqf.add(kpiyvjksem)
        mbkpalarob = [[kpiyvjksem]]
        while mbkpalarob:
            sfivrisylh = mbkpalarob.pop(0)
            omhkabyvpg = sfivrisylh[-1]
            if omhkabyvpg in self.lkvghqfwan:
                return sfivrisylh
            qrcmkiozlr = [
                (omhkabyvpg[0] + celomdfhbh, omhkabyvpg[1]),
                (omhkabyvpg[0] - celomdfhbh, omhkabyvpg[1]),
                (omhkabyvpg[0], omhkabyvpg[1] - celomdfhbh),
                (omhkabyvpg[0], omhkabyvpg[1] + celomdfhbh),
            ]
            for yweobqdxhg in qrcmkiozlr:
                if yweobqdxhg not in qkmekaxaqf and self.kblzhbvysd(yweobqdxhg):
                    qkmekaxaqf.add(yweobqdxhg)
                    mbkpalarob.append(sfivrisylh + [yweobqdxhg])
        return None

    def cyjrduhzmz(self, fqdniajpfh: Sprite) -> list[tuple[int, int]] | None:
        kpiyvjksem = (fqdniajpfh.x, fqdniajpfh.y)
        qkmekaxaqf = set()
        qkmekaxaqf.add(kpiyvjksem)
        mbkpalarob = [[kpiyvjksem]]
        tkrlgpoppf = self.nsevyuople[fqdniajpfh]
        dx = tkrlgpoppf.x - fqdniajpfh.x
        dy = tkrlgpoppf.y - fqdniajpfh.y
        while mbkpalarob:
            sfivrisylh = mbkpalarob.pop(0)
            omhkabyvpg = sfivrisylh[-1]
            if self.shbxbhnhjc((omhkabyvpg[0] + dx, omhkabyvpg[1] + dy)):
                return sfivrisylh
            qrcmkiozlr = [
                (omhkabyvpg[0] + celomdfhbh, omhkabyvpg[1]),
                (omhkabyvpg[0] - celomdfhbh, omhkabyvpg[1]),
                (omhkabyvpg[0], omhkabyvpg[1] - celomdfhbh),
                (omhkabyvpg[0], omhkabyvpg[1] + celomdfhbh),
            ]
            for yweobqdxhg in qrcmkiozlr:
                if yweobqdxhg not in qkmekaxaqf and self.fuykgiiwit(fqdniajpfh, tkrlgpoppf, yweobqdxhg):
                    qkmekaxaqf.add(yweobqdxhg)
                    mbkpalarob.append(sfivrisylh + [yweobqdxhg])
        return None

    def zauouvdhta(self, fqdniajpfh: Sprite) -> list[tuple[int, int]] | None:
        kpiyvjksem = (fqdniajpfh.x, fqdniajpfh.y)
        qkmekaxaqf = set()
        qkmekaxaqf.add(kpiyvjksem)
        mbkpalarob = [[kpiyvjksem]]
        while mbkpalarob:
            sfivrisylh = mbkpalarob.pop(0)
            omhkabyvpg = sfivrisylh[-1]
            if omhkabyvpg in self.uuorgjazmj:
                return sfivrisylh
            qrcmkiozlr = [
                (omhkabyvpg[0] + celomdfhbh, omhkabyvpg[1]),
                (omhkabyvpg[0] - celomdfhbh, omhkabyvpg[1]),
                (omhkabyvpg[0], omhkabyvpg[1] - celomdfhbh),
                (omhkabyvpg[0], omhkabyvpg[1] + celomdfhbh),
            ]
            for yweobqdxhg in qrcmkiozlr:
                if yweobqdxhg not in qkmekaxaqf and self.kblzhbvysd(yweobqdxhg):
                    qkmekaxaqf.add(yweobqdxhg)
                    mbkpalarob.append(sfivrisylh + [yweobqdxhg])
        return None

    def egqayvffim(self, fqdniajpfh: Sprite) -> list[tuple[int, int]] | None:
        kpiyvjksem = (fqdniajpfh.x, fqdniajpfh.y)
        qkmekaxaqf = set()
        qkmekaxaqf.add(kpiyvjksem)
        mbkpalarob = [[kpiyvjksem]]
        tkrlgpoppf = self.nsevyuople[fqdniajpfh]
        dx = tkrlgpoppf.x - fqdniajpfh.x
        dy = tkrlgpoppf.y - fqdniajpfh.y
        while mbkpalarob:
            sfivrisylh = mbkpalarob.pop(0)
            omhkabyvpg = sfivrisylh[-1]
            if self.ahzqkfjpsc((omhkabyvpg[0] + dx, omhkabyvpg[1] + dy)):
                return sfivrisylh
            qrcmkiozlr = [
                (omhkabyvpg[0] + celomdfhbh, omhkabyvpg[1]),
                (omhkabyvpg[0] - celomdfhbh, omhkabyvpg[1]),
                (omhkabyvpg[0], omhkabyvpg[1] - celomdfhbh),
                (omhkabyvpg[0], omhkabyvpg[1] + celomdfhbh),
            ]
            for yweobqdxhg in qrcmkiozlr:
                if yweobqdxhg not in qkmekaxaqf and self.fuykgiiwit(fqdniajpfh, tkrlgpoppf, yweobqdxhg):
                    qkmekaxaqf.add(yweobqdxhg)
                    mbkpalarob.append(sfivrisylh + [yweobqdxhg])
        return None

    def xpcvspllwr(self, fqdniajpfh: Sprite, sprite: Sprite) -> None:
        if sprite in self.zmqreragji:
            self.kqrtstlzkg(self.zmqreragji[sprite])
        self.nsevyuople[fqdniajpfh] = sprite
        self.zmqreragji[sprite] = fqdniajpfh
        self.vyltpasvhc()
        self.lgirylubbp()

    def kqrtstlzkg(self, fqdniajpfh: Sprite) -> None:
        if fqdniajpfh in self.nsevyuople:
            sprite = self.nsevyuople[fqdniajpfh]
            del self.zmqreragji[sprite]
            del self.nsevyuople[fqdniajpfh]
            self.vyltpasvhc()
            self.lgirylubbp()

    def zzppkjnqgk(self) -> None:
        xfkkaooadb = self.current_level.get_sprites_by_tag("wbmdvjhthc")
        fyfxmnwzhp = self.current_level.get_sprites_by_tag("geezpjgiyd")
        for ijudbtgsll in fyfxmnwzhp:
            if ijudbtgsll in self.zmqreragji:
                fqdniajpfh = self.zmqreragji[ijudbtgsll]
                if fqdniajpfh in xfkkaooadb:
                    uxricavavq(ijudbtgsll, hgqlwjikqr)
                elif any([vwiozbtqgi(olxydpaqfn, ijudbtgsll) for olxydpaqfn in xfkkaooadb]):
                    uxricavavq(ijudbtgsll, vlzkmytlgh)
                else:
                    uxricavavq(ijudbtgsll, qrmfayeqpo)
            elif any([vwiozbtqgi(olxydpaqfn, ijudbtgsll) for olxydpaqfn in xfkkaooadb]):
                uxricavavq(ijudbtgsll, vlzkmytlgh)
            else:
                uxricavavq(ijudbtgsll, wvrpthjfsv)
        zyjsukrrpd = self.current_level.get_sprites_by_tag("ysysltqlke")
        for kkkwtxdnov in zyjsukrrpd:
            if any([vwiozbtqgi(olxydpaqfn, kkkwtxdnov) for olxydpaqfn in xfkkaooadb]):
                uxricavavq(kkkwtxdnov, lajjveeqzb)
            else:
                uxricavavq(kkkwtxdnov, ansrsmsvzs)

    def ynmgxjqkgh(self) -> None:
        makxrwhhlc = self.current_level.get_sprites_by_tag("kdweefinfi")
        for dhptvmzfpx in makxrwhhlc:
            if dhptvmzfpx in self.nsevyuople:
                tkrlgpoppf = self.nsevyuople[dhptvmzfpx]
                if self.shbxbhnhjc((tkrlgpoppf.x, tkrlgpoppf.y)):
                    self.kqrtstlzkg(dhptvmzfpx)
                else:
                    sfivrisylh = self.cyjrduhzmz(dhptvmzfpx)
                    if sfivrisylh and len(sfivrisylh) > 1:
                        czvpytgvaw = sfivrisylh[1]
                        self.wqwsvmhhzj(dhptvmzfpx, czvpytgvaw[0], czvpytgvaw[1])
            else:
                fyfxmnwzhp = self.current_level.get_sprites_by_tag("geezpjgiyd")
                for ijudbtgsll in fyfxmnwzhp:
                    if mdbwmdaxuu((dhptvmzfpx.x, dhptvmzfpx.y), (ijudbtgsll.x, ijudbtgsll.y)) and ijudbtgsll not in self.zmqreragji and (not self.shbxbhnhjc((ijudbtgsll.x, ijudbtgsll.y))):
                        self.xpcvspllwr(dhptvmzfpx, ijudbtgsll)
                        return
                sfivrisylh = self.czrprbohhe(dhptvmzfpx)
                if sfivrisylh:
                    czvpytgvaw = sfivrisylh[1]
                    self.wqwsvmhhzj(dhptvmzfpx, czvpytgvaw[0], czvpytgvaw[1])

    def jrrltylxpp(self, sprite: Sprite) -> bool:
        if sprite in self.zmqreragji:
            fqdniajpfh = self.zmqreragji[sprite]
            return "ysysltqlke" in fqdniajpfh.tags
        return False

    def aoeyzovteg(self) -> None:
        zyjsukrrpd = self.current_level.get_sprites_by_tag("ysysltqlke")
        for kkkwtxdnov in zyjsukrrpd:
            if kkkwtxdnov in self.nsevyuople:
                tkrlgpoppf = self.nsevyuople[kkkwtxdnov]
                if self.ahzqkfjpsc((tkrlgpoppf.x, tkrlgpoppf.y)):
                    self.kqrtstlzkg(kkkwtxdnov)
                else:
                    sfivrisylh = self.egqayvffim(kkkwtxdnov)
                    if sfivrisylh and len(sfivrisylh) > 1:
                        czvpytgvaw = sfivrisylh[1]
                        self.wqwsvmhhzj(kkkwtxdnov, czvpytgvaw[0], czvpytgvaw[1])
            else:
                fyfxmnwzhp = self.current_level.get_sprites_by_tag("geezpjgiyd")
                for ijudbtgsll in fyfxmnwzhp:
                    if mdbwmdaxuu((kkkwtxdnov.x, kkkwtxdnov.y), (ijudbtgsll.x, ijudbtgsll.y)) and (not self.jrrltylxpp(ijudbtgsll)) and (not self.ahzqkfjpsc((ijudbtgsll.x, ijudbtgsll.y))):
                        self.xpcvspllwr(kkkwtxdnov, ijudbtgsll)
                        return
                sfivrisylh = self.zauouvdhta(kkkwtxdnov)
                if sfivrisylh:
                    czvpytgvaw = sfivrisylh[1]
                    self.wqwsvmhhzj(kkkwtxdnov, czvpytgvaw[0], czvpytgvaw[1])

    def ymzfopzgbq(self) -> bool:
        fyfxmnwzhp = self.current_level.get_sprites_by_tag("geezpjgiyd")
        return all([self.shbxbhnhjc((ijudbtgsll.x, ijudbtgsll.y)) and ijudbtgsll not in self.zmqreragji for ijudbtgsll in fyfxmnwzhp])

    def dhrikuybfo(self) -> None:
        self.ynmgxjqkgh()
        self.aoeyzovteg()
        self.zzppkjnqgk()

    def yygfcvqoyx(self, action: ActionInput) -> None:
        olxydpaqfn = self.current_level.get_sprites_by_tag("wbmdvjhthc")[0]
        if action.id == GameAction.ACTION1:
            self.kuncbnslnm.pfakmupgbr()
            dx = 0
            dy = -celomdfhbh
            self.qnmfimgpwc(olxydpaqfn, dx, dy)
            self.dhrikuybfo()
        elif action.id == GameAction.ACTION2:
            self.kuncbnslnm.pfakmupgbr()
            dx = 0
            dy = celomdfhbh
            self.qnmfimgpwc(olxydpaqfn, dx, dy)
            self.dhrikuybfo()
        elif action.id == GameAction.ACTION3:
            self.kuncbnslnm.pfakmupgbr()
            dx = -celomdfhbh
            dy = 0
            self.qnmfimgpwc(olxydpaqfn, dx, dy)
            self.dhrikuybfo()
        elif action.id == GameAction.ACTION4:
            self.kuncbnslnm.pfakmupgbr()
            dx = celomdfhbh
            dy = 0
            self.qnmfimgpwc(olxydpaqfn, dx, dy)
            self.dhrikuybfo()
        elif action.id == GameAction.ACTION5:
            self.kuncbnslnm.pfakmupgbr()
            if olxydpaqfn in self.nsevyuople:
                self.kqrtstlzkg(olxydpaqfn)
            else:
                fyfxmnwzhp = self.current_level.get_sprites_by_tag("geezpjgiyd")
                for ijudbtgsll in fyfxmnwzhp:
                    if vwiozbtqgi(olxydpaqfn, ijudbtgsll):
                        self.xpcvspllwr(olxydpaqfn, ijudbtgsll)
                        break
                zyjsukrrpd = self.current_level.get_sprites_by_tag("ysysltqlke")
                for kkkwtxdnov in zyjsukrrpd:
                    if vwiozbtqgi(olxydpaqfn, kkkwtxdnov):
                        self.kqrtstlzkg(kkkwtxdnov)
                        self.pkbufziase.remove((kkkwtxdnov.x, kkkwtxdnov.y))
                        self.current_level.remove_sprite(kkkwtxdnov)
                        break
            self.dhrikuybfo()

    def step(self) -> None:
        self.yygfcvqoyx(self.action)
        if self.ymzfopzgbq():
            self.next_level()
        elif not self.kuncbnslnm.current_steps:
            self.lose()
        self.complete_action()


# ── copycat layer ───────────────────────────────────────────────────────────────
# Colour assignment for this copycat: displayed colour = _CC_PALETTE[engine colour].
# Applied to the camera's final 64x64 output only, so the game's own rules (some of which
# read sprite colours) are untouched.
_CC_PALETTE = np.array([12, 10, 1, 13, 15, 3, 14, 9, 11, 7, 4, 2, 6, 0, 5, 8], dtype=np.int8)


class _CcCamera(Camera):
    def render(self, sprites):
        frame = super().render(sprites)
        frame = np.asarray(frame)
        out = frame.copy()
        mask = (frame >= 0) & (frame <= 15)
        out[mask] = _CC_PALETTE[frame[mask].astype(np.int64)]
        return out


class Wy30(_Wy30Rules):
    def __init__(self) -> None:
        super().__init__()
        if type(self._camera) is Camera:
            self._camera.__class__ = _CcCamera
        if not isinstance(self._camera, _CcCamera):
            raise RuntimeError("copycat palette camera not installed")
        self._game_id = 'wy30'

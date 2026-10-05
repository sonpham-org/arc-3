# Copycat fy09: rules of public ARC-AGI-3 game ft09, new maps, colours and art.
# Built and verified by autoresearch-arena arc3games/copycats/cc_ft09.py.
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
    'AcT': Sprite(
        pixels=[
        [12, 12],
        [12, 12],
    ],
        name='AcT',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
    ),
    'aIV': Sprite(
        pixels=[
        [14, 0],
        [0, 0],
    ],
        name='aIV',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
    ),
    'ajm': Sprite(
        pixels=[
        [0, 2, 2],
        [2, 15, 2],
        [2, 2, 2],
    ],
        name='ajm',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['bsT'],
    ),
    'aPM': Sprite(
        pixels=[
        [3, 3, 3],
        [0, 11, 3],
        [2, 0, 3],
    ],
        name='aPM',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['bsT'],
    ),
    'APy': Sprite(
        pixels=[
        [0, 0, 2],
        [2, 8, 0],
        [2, 0, 2],
    ],
        name='APy',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['bsT'],
    ),
    'AQG': Sprite(
        pixels=[
        [3, 3, 0],
        [3, 15, 2],
        [0, 2, 0],
    ],
        name='AQG',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['bsT'],
    ),
    'aRa': Sprite(
        pixels=[
        [2, 0, 2],
        [2, 9, 2],
        [0, 2, 2],
    ],
        name='aRa',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['bsT'],
    ),
    'ASc': Sprite(
        pixels=[
        [0, 0, 2],
        [2, 14, 3],
        [3, 3, 3],
    ],
        name='ASc',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.INTANGIBLE,
        tags=['bsT'],
    ),
    'AzN': Sprite(
        pixels=[
        [15, 15],
        [15, 15],
    ],
        name='AzN',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
    ),
    'Bbi': Sprite(
        pixels=[
        [3, 0, 3],
        [2, 11, 2],
        [3, 0, 3],
    ],
        name='Bbi',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.INTANGIBLE,
        tags=['bsT'],
    ),
    'bdj': Sprite(
        pixels=[
        [12, 12],
        [12, 12],
    ],
        name='bdj',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
    ),
    'bqV': Sprite(
        pixels=[
        [0, -1, 0, -1, 0],
    ],
        name='bqV',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
    ),
    'BvX': Sprite(
        pixels=[
        [2, 0, 2],
        [0, 14, 3],
        [3, 3, 3],
    ],
        name='BvX',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['bsT'],
    ),
    'bzH': Sprite(
        pixels=[
        [-1, -1, 6, -1, -1],
        [-1, -1, -1, -1, -1],
        [6, -1, -1, -1, 6],
        [-1, -1, -1, -1, -1],
        [-1, -1, 6, -1, -1],
        [-1, -1, -1, -1, -1],
        [6, -1, -1, -1, 6],
        [-1, -1, -1, -1, -1],
        [-1, -1, 6, -1, -1],
    ],
        name='bzH',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
    ),
    'cgN': Sprite(
        pixels=[
        [5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5],
        [5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5],
        [5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5],
        [5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5],
        [5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5],
        [5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5],
        [5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5],
        [5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5],
        [5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5],
        [5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5],
        [5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5],
        [5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5],
        [5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5],
        [5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5],
        [5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5],
        [5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5],
        [5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5],
        [5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5],
    ],
        name='cgN',
        layer=-2,
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.INTANGIBLE,
    ),
    'ciC': Sprite(
        pixels=[
        [6, 7, 6],
        [7, 10, 7],
        [6, 7, 6],
    ],
        name='ciC',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['NTi'],
    ),
    'CKH': Sprite(
        pixels=[
        [2, 0, 3],
        [0, 8, 0],
        [2, 2, 0],
    ],
        name='CKH',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['bsT'],
    ),
    'cWS': Sprite(
        pixels=[
        [2, 2, 2],
        [0, 9, 0],
        [0, 2, 0],
    ],
        name='cWS',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['bsT'],
    ),
    'dhm': Sprite(
        pixels=[
        [6, 6, 6],
        [6, 7, 6],
        [6, 7, 6],
    ],
        name='dhm',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
    ),
    'dta': Sprite(
        pixels=[
        [2, 0, 2],
        [2, 12, 0],
        [0, 0, 0],
    ],
        name='dta',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['bsT'],
    ),
    'dvQ': Sprite(
        pixels=[
        [5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5],
        [5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5],
        [5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5],
        [5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5],
        [5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5],
        [5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5],
        [5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5],
        [5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5],
        [5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5],
        [5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5],
        [5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5],
        [5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5],
        [5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5],
        [5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5],
        [5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5],
        [5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5],
    ],
        name='dvQ',
        layer=-2,
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.INTANGIBLE,
    ),
    'dwp': Sprite(
        pixels=[
        [3, 3, 3],
        [3, 10, 0],
        [3, 0, 0],
    ],
        name='dwp',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['bsT'],
    ),
    'DYr': Sprite(
        pixels=[
        [2],
        [2],
    ],
        name='DYr',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
    ),
    'EEB': Sprite(
        pixels=[
        [8, 8],
        [8, 8],
        [9, 9],
        [9, 9],
    ],
        name='EEB',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
    ),
    'Eev': Sprite(
        pixels=[
        [2, 2, 2],
        [2, 2, 2],
        [2, 2, 2],
    ],
        name='Eev',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['bsT'],
    ),
    'ejV': Sprite(
        pixels=[
        [8, 8],
        [8, 8],
    ],
        name='ejV',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
    ),
    'EQX': Sprite(
        pixels=[
        [0, 2, 0],
        [2, 12, 2],
        [2, 0, 0],
    ],
        name='EQX',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['bsT'],
    ),
    'ewB': Sprite(
        pixels=[
        [6, 6, 6],
        [6, 7, 6],
        [6, 6, 6],
    ],
        name='ewB',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
    ),
    'ewH': Sprite(
        pixels=[
        [6, 7, 6],
        [7, 7, 7],
        [6, 7, 6],
    ],
        name='ewH',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
    ),
    'Ewx': Sprite(
        pixels=[
        [2, 0, 2],
        [0, 8, 0],
        [2, 0, 2],
    ],
        name='Ewx',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['bsT'],
    ),
    'fBi': Sprite(
        pixels=[
        [8, 8],
        [8, 8],
        [12, 12],
        [12, 12],
    ],
        name='fBi',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
    ),
    'FfJ': Sprite(
        pixels=[
        [0, 0, 3],
        [0, 12, 3],
        [2, 0, 3],
    ],
        name='FfJ',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['bsT'],
    ),
    'fjN': Sprite(
        pixels=[
        [0, 0, 0],
        [2, 8, 2],
        [2, 2, 2],
    ],
        name='fjN',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['bsT'],
    ),
    'FLH': Sprite(
        pixels=[
        [2, 2, 2],
        [3, 15, 0],
        [3, 3, 3],
    ],
        name='FLH',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['bsT'],
    ),
    'fPj': Sprite(
        pixels=[
        [0, 2, 0],
        [2, 14, 2],
        [0, 3, 0],
    ],
        name='fPj',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['bsT'],
    ),
    'Fpw': Sprite(
        pixels=[
        [6, 7, 6],
        [7, 7, 7],
        [6, 7, 6],
    ],
        name='Fpw',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
    ),
    'FRs': Sprite(
        pixels=[
        [2, 2, 3],
        [0, 11, 0],
        [3, 2, 3],
    ],
        name='FRs',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['bsT'],
    ),
    'fsp': Sprite(
        pixels=[
        [6, 7, 7],
        [7, 10, 7],
        [7, 7, 6],
    ],
        name='fsp',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['NTi', 'gOi'],
    ),
    'fTG': Sprite(
        pixels=[
        [6, 6, 6],
        [7, 6, 7],
        [6, 6, 6],
    ],
        name='fTG',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
    ),
    'FvN': Sprite(
        pixels=[
        [0, 0, 3],
        [2, 9, 2],
        [0, 0, 3],
    ],
        name='FvN',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['bsT'],
    ),
    'gdG': Sprite(
        pixels=[
        [2, 2, 0],
        [2, 8, 2],
        [2, 2, 2],
    ],
        name='gdG',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['bsT'],
    ),
    'gFd': Sprite(
        pixels=[
        [14, 14],
        [14, 14],
    ],
        name='gFd',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
    ),
    'guB': Sprite(
        pixels=[
        [3, 2, 3],
        [0, 11, 0],
        [3, 2, 3],
    ],
        name='guB',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['bsT'],
    ),
    'gYF': Sprite(
        pixels=[
        [12, 12],
        [12, 12],
    ],
        name='gYF',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
    ),
    'GYn': Sprite(
        pixels=[
        [2, 2, 0],
        [2, 9, 2],
        [2, 2, 0],
    ],
        name='GYn',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['bsT'],
    ),
    'hGV': Sprite(
        pixels=[
        [2, 3, 3],
        [0, 12, 3],
        [2, 0, 2],
    ],
        name='hGV',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['bsT'],
    ),
    'hIX': Sprite(
        pixels=[
        [0, 0, 0],
        [0, 14, 3],
        [3, 3, 3],
    ],
        name='hIX',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['bsT'],
    ),
    'Hkx': Sprite(
        pixels=[
        [9, 9, 9],
        [9, 9, 9],
        [9, 9, 9],
    ],
        name='Hkx',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['Hkx', 'gOi'],
    ),
    'htK': Sprite(
        pixels=[
        [8, 8],
        [8, 8],
    ],
        name='htK',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
    ),
    'IFI': Sprite(
        pixels=[
        [0, 2, 3],
        [2, 15, 3],
        [0, 2, 3],
    ],
        name='IFI',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['bsT'],
    ),
    'ImU': Sprite(
        pixels=[
        [7, 7, 6],
        [7, 10, 7],
        [7, 7, 7],
    ],
        name='ImU',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['NTi', 'gOi'],
    ),
    'iSM': Sprite(
        pixels=[
        [2, 2, 2],
        [2, 2, 2],
        [2, 2, 2],
    ],
        name='iSM',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['bsT'],
    ),
    'iTO': Sprite(
        pixels=[
        [6, 6, 6],
        [6, 7, 6],
        [7, 6, 6],
    ],
        name='iTO',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
    ),
    'iVf': Sprite(
        pixels=[
        [3, 3, 3],
        [2, 9, 3],
        [2, 0, 3],
    ],
        name='iVf',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['bsT'],
    ),
    'jGI': Sprite(
        pixels=[
        [2, 2, 0],
        [0, 12, 0],
        [0, 2, 0],
    ],
        name='jGI',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['bsT'],
    ),
    'Jir': Sprite(
        pixels=[
        [9, 9],
        [9, 9],
    ],
        name='Jir',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
    ),
    'jqz': Sprite(
        pixels=[
        [0, 0, 2],
        [2, 12, 3],
        [3, 3, 3],
    ],
        name='jqz',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['bsT'],
    ),
    'jRD': Sprite(
        pixels=[
        [3, 2, 3],
        [0, 11, 0],
        [3, 2, 3],
    ],
        name='jRD',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['bsT'],
    ),
    'jsT': Sprite(
        pixels=[
        [14, 14],
        [14, 14],
    ],
        name='jsT',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
    ),
    'KBg': Sprite(
        pixels=[
        [3, 2, 2],
        [0, 8, 0],
        [3, 2, 2],
    ],
        name='KBg',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['bsT'],
    ),
    'kEq': Sprite(
        pixels=[
        [2, 0, 0],
        [2, 9, 2],
        [2, 2, 2],
    ],
        name='kEq',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['bsT'],
    ),
    'kJY': Sprite(
        pixels=[
        [9, 9],
        [9, 9],
    ],
        name='kJY',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
    ),
    'KOm': Sprite(
        pixels=[
        [3, 0, 2],
        [3, 9, 0],
        [3, 0, 2],
    ],
        name='KOm',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['bsT'],
    ),
    'KpR': Sprite(
        pixels=[
        [3, 0, 3],
        [2, 11, 3],
        [3, 0, 3],
    ],
        name='KpR',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['bsT'],
    ),
    'KrW': Sprite(
        pixels=[
        [2, 0, 2],
        [2, 12, 2],
        [2, 2, 2],
    ],
        name='KrW',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['bsT'],
    ),
    'kUt': Sprite(
        pixels=[
        [9, 9],
        [9, 9],
    ],
        name='kUt',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
    ),
    'kvt': Sprite(
        pixels=[
        [0, 0, 2],
        [0, 14, 0],
        [2, 0, 2],
    ],
        name='kvt',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.INTANGIBLE,
        tags=['bsT'],
    ),
    'kyg': Sprite(
        pixels=[
        [3, 0, 3],
        [2, 11, 2],
        [3, 0, 3],
    ],
        name='kyg',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.INTANGIBLE,
        tags=['bsT'],
    ),
    'KYk': Sprite(
        pixels=[
        [0, 0, 0],
        [2, 12, 0],
        [2, 0, 2],
    ],
        name='KYk',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['bsT'],
    ),
    'LDC': Sprite(
        pixels=[
        [2, 2, 2],
        [2, 12, 2],
        [2, 0, 2],
    ],
        name='LDC',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['bsT'],
    ),
    'LfP': Sprite(
        pixels=[
        [2, 0, 2],
        [0, 8, 2],
        [2, 2, 2],
    ],
        name='LfP',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['bsT'],
    ),
    'LgL': Sprite(
        pixels=[
        [12, 12],
        [12, 12],
        [9, 9],
        [9, 9],
    ],
        name='LgL',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
    ),
    'LIx': Sprite(
        pixels=[
        [3, 0, 3],
        [2, 11, 0],
        [3, 2, 3],
    ],
        name='LIx',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['bsT'],
    ),
    'lMN': Sprite(
        pixels=[
        [2, 0, 2],
        [2, 12, 2],
        [2, 0, 2],
    ],
        name='lMN',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['bsT'],
    ),
    'LRU': Sprite(
        pixels=[
        [15, 15],
        [15, 15],
    ],
        name='LRU',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
    ),
    'Lua': Sprite(
        pixels=[
        [3, 0, 0],
        [3, 14, 2],
        [3, 2, 0],
    ],
        name='Lua',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['bsT'],
    ),
    'lVU': Sprite(
        pixels=[
        [0, -1, 0, -1, 0],
    ],
        name='lVU',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
    ),
    'Lzf': Sprite(
        pixels=[
        [0, 2, 2],
        [2, 9, 2],
        [2, 2, 2],
    ],
        name='Lzf',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['bsT'],
    ),
    'MEF': Sprite(
        pixels=[
        [2, 0, 2],
        [0, 8, 0],
        [2, 0, 2],
    ],
        name='MEF',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
    ),
    'mnE': Sprite(
        pixels=[
        [3, 3, 3],
        [0, 12, 3],
        [3, 2, 2],
    ],
        name='mnE',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['bsT'],
    ),
    'mrc': Sprite(
        pixels=[
        [2, 0, 2],
        [2, 9, 2],
        [2, 2, 2],
    ],
        name='mrc',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['bsT'],
    ),
    'mTg': Sprite(
        pixels=[
        [0, 0, 2],
        [2, 9, 2],
        [2, 2, 2],
    ],
        name='mTg',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['bsT'],
    ),
    'MTx': Sprite(
        pixels=[
        [8, 8],
        [8, 8],
    ],
        name='MTx',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
    ),
    'ndN': Sprite(
        pixels=[
        [2, 0, 2],
        [0, 8, 0],
        [2, 2, 2],
    ],
        name='ndN',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['bsT'],
    ),
    'NGA': Sprite(
        pixels=[
        [3, 3, 3],
        [0, 15, 3],
        [0, 2, 2],
    ],
        name='NGA',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['bsT'],
    ),
    'nGy': Sprite(
        pixels=[
        [12, 12],
        [12, 12],
        [8, 8],
        [8, 8],
    ],
        name='nGy',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
    ),
    'nkM': Sprite(
        pixels=[
        [3, 2, 3],
        [2, 11, 2],
        [3, 2, 3],
    ],
        name='nkM',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['bsT'],
    ),
    'Nod': Sprite(
        pixels=[
        [2],
    ],
        name='Nod',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
    ),
    'NTi': Sprite(
        pixels=[
        [7, 6, 7],
        [6, 10, 6],
        [7, 6, 7],
    ],
        name='NTi',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['NTi', 'gOi'],
    ),
    'Nul': Sprite(
        pixels=[
        [3, 3, 3],
        [0, 14, 3],
        [2, 0, 3],
    ],
        name='Nul',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['bsT'],
    ),
    'OFC': Sprite(
        pixels=[
        [12, 12],
        [12, 12],
    ],
        name='OFC',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
    ),
    'oif': Sprite(
        pixels=[
        [0, 0, 0],
        [3, 10, 3],
        [3, 3, 3],
    ],
        name='oif',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['bsT'],
    ),
    'OqR': Sprite(
        pixels=[
        [3, 0, 2],
        [3, 8, 0],
        [3, 0, 2],
    ],
        name='OqR',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['bsT'],
    ),
    'OZL': Sprite(
        pixels=[
        [0, 2, 0],
        [2, 12, 2],
        [0, 2, 0],
    ],
        name='OZL',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['bsT'],
    ),
    'PjS': Sprite(
        pixels=[
        [2, 0, 2],
        [0, 14, 0],
        [2, 0, 0],
    ],
        name='PjS',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.INTANGIBLE,
        tags=['bsT'],
    ),
    'PmE': Sprite(
        pixels=[
        [3, 0, 2],
        [3, 14, 0],
        [3, 3, 3],
    ],
        name='PmE',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['bsT'],
    ),
    'PrU': Sprite(
        pixels=[
        [8, 8],
        [8, 8],
    ],
        name='PrU',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
    ),
    'PRx': Sprite(
        pixels=[
        [0, 0, 0],
        [0, -1, 0],
        [0, 0, 0],
    ],
        name='PRx',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['bsT'],
    ),
    'pvc': Sprite(
        pixels=[
        [0, 0, 0],
        [0, 8, 0],
        [0, 0, 0],
    ],
        name='pvc',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['bsT'],
    ),
    'QBc': Sprite(
        pixels=[
        [2, 2, 0],
        [2, 9, 2],
        [2, 0, 0],
    ],
        name='QBc',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['bsT'],
    ),
    'QpB': Sprite(
        pixels=[
        [9, 9],
        [9, 9],
    ],
        name='QpB',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
    ),
    'qpe': Sprite(
        pixels=[
        [9, 9],
        [9, 9],
    ],
        name='qpe',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
    ),
    'qqM': Sprite(
        pixels=[
        [2, 3, 2],
        [0, 14, 0],
        [2, 0, 2],
    ],
        name='qqM',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['bsT'],
    ),
    'qqX': Sprite(
        pixels=[
        [2, 2, 0],
        [0, 8, 0],
        [0, 2, 2],
    ],
        name='qqX',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
    ),
    'RBv': Sprite(
        pixels=[
        [2, 0, 0],
        [0, 14, 0],
        [3, 3, 3],
    ],
        name='RBv',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['bsT'],
    ),
    'REY': Sprite(
        pixels=[
        [10, 10],
        [10, 10],
    ],
        name='REY',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
    ),
    'RjR': Sprite(
        pixels=[
        [2, 0, 2],
        [2, 9, 0],
        [0, 2, 0],
    ],
        name='RjR',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['bsT'],
    ),
    'rKF': Sprite(
        pixels=[
        [2, 0, 2],
        [2, 8, 2],
        [2, 2, 2],
    ],
        name='rKF',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['bsT'],
    ),
    'rni': Sprite(
        pixels=[
        [-1, -1, -1, -1, -1, -1, -1, -1, 10, -1, -1, -1, 15, -1, -1, -1, -1],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
        [-1, -1, -1, -1, -1, -1, -1, -1, 15, -1, -1, -1, 14, -1, -1, -1, 10],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
        [-1, -1, -1, -1, 15, -1, -1, -1, 14, -1, -1, -1, 10, -1, -1, -1, 15],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
        [-1, -1, -1, -1, 14, -1, -1, -1, 10, -1, -1, -1, 15, -1, -1, -1, -1],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
        [14, -1, -1, -1, 10, -1, -1, -1, 15, -1, -1, -1, 14, -1, -1, -1, -1],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
        [10, -1, -1, -1, 15, -1, -1, -1, 14, -1, -1, -1, -1, -1, -1, -1, -1],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
        [-1, -1, -1, -1, 14, -1, -1, -1, 10, -1, -1, -1, -1, -1, -1, -1, -1],
    ],
        name='rni',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
    ),
    'ROc': Sprite(
        pixels=[
        [2, 0, 3],
        [0, 9, 3],
        [3, 3, 3],
    ],
        name='ROc',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['bsT'],
    ),
    'RZR': Sprite(
        pixels=[
        [2],
    ],
        name='RZR',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
    ),
    'seE': Sprite(
        pixels=[
        [5, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
        [5, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
        [5, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
        [5, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
        [5, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
        [5, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
        [5, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
        [5, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
        [5, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
        [5, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
        [5, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
        [5, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
        [5, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
        [5, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
        [5, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
        [5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5],
    ],
        name='seE',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.INTANGIBLE,
    ),
    'SfD': Sprite(
        pixels=[
        [3, 0, 2],
        [3, 14, 0],
        [3, 0, 2],
    ],
        name='SfD',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['bsT'],
    ),
    'SJP': Sprite(
        pixels=[
        [0, 2, 0],
        [2, 8, 0],
        [2, 0, 2],
    ],
        name='SJP',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['bsT'],
    ),
    'sPz': Sprite(
        pixels=[
        [2, 0, 0],
        [2, 8, 2],
        [2, 2, 2],
    ],
        name='sPz',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['bsT'],
    ),
    'srH': Sprite(
        pixels=[
        [3, 0, 3],
        [2, 11, 0],
        [3, 2, 3],
    ],
        name='srH',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['bsT'],
    ),
    'ssK': Sprite(
        pixels=[
        [3, 3, 3],
        [3, 14, 2],
        [2, 0, 0],
    ],
        name='ssK',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.INTANGIBLE,
        tags=['bsT'],
    ),
    'sTI': Sprite(
        pixels=[
        [2, 2, 2],
        [0, 9, 2],
        [2, 2, 2],
    ],
        name='sTI',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
    ),
    'sxj': Sprite(
        pixels=[
        [2, 0, 2],
        [2, 8, 0],
        [0, 0, 2],
    ],
        name='sxj',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
    ),
    'SXM': Sprite(
        pixels=[
        [2, 0, 2],
        [0, 8, 2],
        [2, 0, 0],
    ],
        name='SXM',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['bsT'],
    ),
    'tCT': Sprite(
        pixels=[
        [2, 0, 2],
        [2, 9, 0],
        [2, 2, 2],
    ],
        name='tCT',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['bsT'],
    ),
    'TOK': Sprite(
        pixels=[
        [9, 9, 9, -1, 8, 8, 8, -1, 9, 9, 9],
        [9, 9, 9, -1, 8, 8, 8, -1, 9, 9, 9],
        [9, 9, 9, -1, 8, 8, 8, -1, 9, 9, 9],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
        [8, 8, 8, -1, -1, -1, -1, -1, 8, 8, 8],
        [8, 8, 8, -1, -1, -1, -1, -1, 8, 8, 8],
        [8, 8, 8, -1, -1, -1, -1, -1, 8, 8, 8],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
        [9, 9, 9, -1, 8, 8, 8, -1, 9, 9, 9],
        [9, 9, 9, -1, 8, 8, 8, -1, 9, 9, 9],
        [9, 9, 9, -1, 8, 8, 8, -1, 9, 9, 9],
    ],
        name='TOK',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.INTANGIBLE,
    ),
    'TqS': Sprite(
        pixels=[
        [2, -1, 2],
    ],
        name='TqS',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
    ),
    'TqV': Sprite(
        pixels=[
        [2, 2, 0],
        [2, 8, 0],
        [2, 2, 2],
    ],
        name='TqV',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['bsT'],
    ),
    'TuS': Sprite(
        pixels=[
        [3, 3, 3],
        [2, 14, 0],
        [0, 0, 0],
    ],
        name='TuS',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['bsT'],
    ),
    'uaD': Sprite(
        pixels=[
        [3, 0, 3],
        [2, 11, 0],
        [3, 2, 3],
    ],
        name='uaD',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['bsT'],
    ),
    'UaS': Sprite(
        pixels=[
        [0, 2, 2],
        [2, 9, 2],
        [0, 0, 2],
    ],
        name='UaS',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['bsT'],
    ),
    'uCD': Sprite(
        pixels=[
        [6],
    ],
        name='uCD',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
    ),
    'uCe': Sprite(
        pixels=[
        [2, 2, 0],
        [2, 12, 2],
        [0, 0, 0],
    ],
        name='uCe',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['bsT'],
    ),
    'uDP': Sprite(
        pixels=[
        [2, 2, 2],
        [2, 9, 2],
        [2, 2, 0],
    ],
        name='uDP',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['bsT'],
    ),
    'uds': Sprite(
        pixels=[
        [2, 0, 2],
        [0, 12, 2],
        [2, 0, 2],
    ],
        name='uds',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['bsT'],
    ),
    'UdT': Sprite(
        pixels=[
        [0, 2, 2],
        [2, 8, 2],
        [2, 0, 0],
    ],
        name='UdT',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['bsT'],
    ),
    'UEq': Sprite(
        pixels=[
        [2, 2, 2, -1, -1, -1, -1, -1, -1, -1, -1, -1, 2, 2, 2],
        [2, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 2],
        [2, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 2],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
        [2, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 2],
        [2, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 2],
        [2, 2, 2, -1, -1, -1, -1, -1, -1, -1, -1, -1, 2, 2, 2],
    ],
        name='UEq',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.INTANGIBLE,
        tags=['Ycb'],
    ),
    'UEt': Sprite(
        pixels=[
        [7, 7, 7],
        [6, 7, 6],
        [6, 6, 6],
    ],
        name='UEt',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
    ),
    'uJY': Sprite(
        pixels=[
        [5],
    ],
        name='uJY',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
    ),
    'ukF': Sprite(
        pixels=[
        [2, 0, 3],
        [0, 12, 2],
        [0, 2, 2],
    ],
        name='ukF',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['bsT'],
    ),
    'ukY': Sprite(
        pixels=[
        [3, 2, 3],
        [0, 11, 0],
        [3, 2, 3],
    ],
        name='ukY',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.INTANGIBLE,
        tags=['bsT'],
    ),
    'UmB': Sprite(
        pixels=[
        [6, -1, 6],
    ],
        name='UmB',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
    ),
    'uPr': Sprite(
        pixels=[
        [11],
    ],
        name='uPr',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
    ),
    'UQj': Sprite(
        pixels=[
        [2, 2, 2],
        [2, 8, 0],
        [2, 0, 2],
    ],
        name='UQj',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['bsT'],
    ),
    'UsM': Sprite(
        pixels=[
        [0],
    ],
        name='UsM',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
    ),
    'UTh': Sprite(
        pixels=[
        [2, 2, 2],
        [0, 8, 2],
        [0, 2, 2],
    ],
        name='UTh',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['bsT'],
    ),
    'uvy': Sprite(
        pixels=[
        [2, 2, 2],
        [2, 2, 2],
        [2, 2, 2],
    ],
        name='uvy',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['bsT'],
    ),
    'Uxp': Sprite(
        pixels=[
        [2, 2, 2],
        [2, 8, 2],
        [2, 2, 0],
    ],
        name='Uxp',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['bsT'],
    ),
    'vAD': Sprite(
        pixels=[
        [-1, -1, 6, -1, -1],
        [-1, -1, -1, -1, -1],
        [6, -1, -1, -1, 6],
        [-1, -1, -1, -1, -1],
        [-1, -1, 6, -1, -1],
    ],
        name='vAD',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
    ),
    'van': Sprite(
        pixels=[
        [2, 2, 2],
        [2, 2, 2],
        [2, 2, 2],
    ],
        name='van',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['bsT'],
    ),
    'VdJ': Sprite(
        pixels=[
        [2, 2, 2],
        [2, 9, 0],
        [0, 2, 2],
    ],
        name='VdJ',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
    ),
    'vFj': Sprite(
        pixels=[
        [2, 0, 2],
        [2, 8, 2],
        [2, 2, 0],
    ],
        name='vFj',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['bsT'],
    ),
    'VHA': Sprite(
        pixels=[
        [11, 11],
        [11, 11],
    ],
        name='VHA',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
    ),
    'viw': Sprite(
        pixels=[
        [12, 12],
        [12, 12],
    ],
        name='viw',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
    ),
    'vSD': Sprite(
        pixels=[
        [2, 2, 2],
        [0, 8, 2],
        [0, 2, 0],
    ],
        name='vSD',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['bsT'],
    ),
    'Vuk': Sprite(
        pixels=[
        [6, 7, 7],
        [7, 10, 7],
        [7, 7, 7],
    ],
        name='Vuk',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['NTi', 'gOi'],
    ),
    'vxk': Sprite(
        pixels=[
        [9, 9, 9, -1, 9, 9, 9, -1, 8, 8, 8],
        [9, 9, 9, -1, 9, 9, 9, -1, 8, 8, 8],
        [9, 9, 9, -1, 9, 9, 9, -1, 8, 8, 8],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
        [8, 8, 8, -1, -1, -1, -1, -1, 8, 8, 8],
        [8, 8, 8, -1, -1, -1, -1, -1, 8, 8, 8],
        [8, 8, 8, -1, -1, -1, -1, -1, 8, 8, 8],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
        [8, 8, 8, -1, 9, 9, 9, -1, 9, 9, 9],
        [8, 8, 8, -1, 9, 9, 9, -1, 9, 9, 9],
        [8, 8, 8, -1, 9, 9, 9, -1, 9, 9, 9],
    ],
        name='vxk',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.INTANGIBLE,
    ),
    'VxQ': Sprite(
        pixels=[
        [7, 7, 7],
        [7, 10, 7],
        [6, 7, 6],
    ],
        name='VxQ',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['NTi', 'gOi'],
    ),
    'wai': Sprite(
        pixels=[
        [2, 2, 0],
        [3, 8, 2],
        [3, 3, 3],
    ],
        name='wai',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['bsT'],
    ),
    'WbH': Sprite(
        pixels=[
        [0, 2, 0],
        [3, 12, 3],
        [0, 3, 0],
    ],
        name='WbH',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['bsT'],
    ),
    'wCl': Sprite(
        pixels=[
        [9, 9, 9, -1, 8, 8, 8, -1, 9, 9, 9],
        [9, 9, 9, -1, 8, 8, 8, -1, 9, 9, 9],
        [9, 9, 9, -1, 8, 8, 8, -1, 9, 9, 9],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
        [9, 9, 9, -1, -1, -1, -1, -1, 8, 8, 8],
        [9, 9, 9, -1, -1, -1, -1, -1, 8, 8, 8],
        [9, 9, 9, -1, -1, -1, -1, -1, 8, 8, 8],
        [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
        [8, 8, 8, -1, 8, 8, 8, -1, 9, 9, 9],
        [8, 8, 8, -1, 8, 8, 8, -1, 9, 9, 9],
        [8, 8, 8, -1, 8, 8, 8, -1, 9, 9, 9],
    ],
        name='wCl',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.INTANGIBLE,
    ),
    'WDx': Sprite(
        pixels=[
        [2, 2, 2],
        [3, 8, 3],
        [3, 3, 3],
    ],
        name='WDx',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['bsT'],
    ),
    'wmW': Sprite(
        pixels=[
        [2, 2, 0],
        [0, 8, 0],
        [2, 2, 0],
    ],
        name='wmW',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['bsT'],
    ),
    'wmz': Sprite(
        pixels=[
        [0, 0, 3],
        [2, 11, 2],
        [2, 3, 3],
    ],
        name='wmz',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['bsT'],
    ),
    'Wnw': Sprite(
        pixels=[
        [9, 9],
        [9, 9],
        [8, 8],
        [8, 8],
    ],
        name='Wnw',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
    ),
    'Wpv': Sprite(
        pixels=[
        [2, 2, 3],
        [0, 11, 0],
        [3, 2, 3],
    ],
        name='Wpv',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['bsT'],
    ),
    'WQe': Sprite(
        pixels=[
        [0, 2, 2],
        [2, 9, 2],
        [0, 0, 0],
    ],
        name='WQe',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['bsT'],
    ),
    'xas': Sprite(
        pixels=[
        [2, 2, 2],
        [2, 12, 2],
        [0, 2, 0],
    ],
        name='xas',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['bsT'],
    ),
    'xeV': Sprite(
        pixels=[
        [6, 6, 6],
        [6, 7, 6],
        [6, 6, 6],
    ],
        name='xeV',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
    ),
    'xga': Sprite(
        pixels=[
        [3, 2, 3],
        [0, 11, 0],
        [3, 2, 3],
    ],
        name='xga',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.INTANGIBLE,
        tags=['bsT'],
    ),
    'XND': Sprite(
        pixels=[
        [6, 7, 6],
        [7, 10, 7],
        [7, 7, 7],
    ],
        name='XND',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['NTi'],
    ),
    'XWQ': Sprite(
        pixels=[
        [2, 2, 2],
        [2, 12, 2],
        [2, 0, 2],
    ],
        name='XWQ',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['bsT'],
    ),
    'Yid': Sprite(
        pixels=[
        [6, 6, 6],
        [7, 7, 7],
        [6, 6, 6],
    ],
        name='Yid',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
    ),
    'yKt': Sprite(
        pixels=[
        [3, 0, 3],
        [3, 11, 2],
        [3, 0, 3],
    ],
        name='yKt',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['bsT'],
    ),
    'yUG': Sprite(
        pixels=[
        [3, 2, 3],
        [0, 14, 0],
        [3, 2, 3],
    ],
        name='yUG',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['bsT'],
    ),
    'Ywn': Sprite(
        pixels=[
        [14, 14],
        [14, 14],
        [15, 15],
        [15, 15],
    ],
        name='Ywn',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
    ),
    'ywQ': Sprite(
        pixels=[
        [2, 2, 2],
        [2, 9, 2],
        [2, 2, 2],
    ],
        name='ywQ',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['bsT'],
    ),
    'yZg': Sprite(
        pixels=[
        [2, 0, 2],
        [0, 14, 0],
        [2, 0, 2],
    ],
        name='yZg',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['bsT'],
    ),
    'Zgh': Sprite(
        pixels=[
        [11, 11],
        [11, 11],
    ],
        name='Zgh',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
    ),
    'zhI': Sprite(
        pixels=[
        [2, 2, 2],
        [2, 9, 2],
        [2, 2, 2],
    ],
        name='zhI',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['bsT'],
    ),
    'zIu': Sprite(
        pixels=[
        [3, 2, 3],
        [0, 11, 0],
        [3, 2, 3],
    ],
        name='zIu',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.INTANGIBLE,
        tags=['bsT'],
    ),
    'ZkU': Sprite(
        pixels=[
        [7, 6, 7],
        [7, 10, 7],
        [7, 7, 7],
    ],
        name='ZkU',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['NTi', 'gOi'],
    ),
    'zmT': Sprite(
        pixels=[
        [3, 2, 0],
        [3, 12, 2],
        [3, 3, 3],
    ],
        name='zmT',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['bsT'],
    ),
    'zoT': Sprite(
        pixels=[
        [7, 7, 6],
        [7, 10, 7],
        [6, 7, 7],
    ],
        name='zoT',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['NTi', 'gOi'],
    ),
    'zvj': Sprite(
        pixels=[
        [0, 0, 2],
        [2, 8, 2],
        [2, 2, 2],
    ],
        name='zvj',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['bsT'],
    ),
}

levels = [
    # Level 1
    Level(
        sprites=[
            sprites['cgN'].clone().set_position(16, 14),
            sprites['dvQ'].clone().set_position(0, 0),
            sprites['Hkx'].clone().set_position(11, 18),
            sprites['Hkx'].clone().set_position(7, 18),
            sprites['Hkx'].clone().set_position(3, 18),
            sprites['Hkx'].clone().set_position(11, 22),
            sprites['Hkx'].clone().set_position(3, 22),
            sprites['Hkx'].clone().set_position(11, 26),
            sprites['Hkx'].clone().set_position(7, 26),
            sprites['Hkx'].clone().set_position(3, 26),
            sprites['MEF'].clone().set_position(6, 5),
            sprites['qqX'].clone().set_position(23, 22),
            sprites['seE'].clone().set_position(0, 16),
            sprites['sxj'].clone().set_position(23, 5),
            sprites['TOK'].clone().set_position(2, 1),
            sprites['UEq'].clone().set_position(1, 16),
            sprites['vxk'].clone().set_position(19, 18),
            sprites['wCl'].clone().set_position(19, 1),
            Sprite(
                pixels=[
                [2, 2, 0],
                [2, 8, 2],
                [0, 0, 0],
            ],
                name='wmW',
                x=7,
                y=22,
                blocking=BlockingMode.PIXEL_PERFECT,
                interaction=InteractionMode.TANGIBLE,
                tags=['bsT'],
            ),
        ],
        grid_size=(32, 32),
        data={'kCv': 32, 'cwU': [9, 8], 'elp': [[0, 0, 0], [0, 1, 0], [0, 0, 0]]},
        name='THR',
    ),
    # Level 2
    Level(
        sprites=[
            Sprite(
                pixels=[
                [0, 2, 2],
                [0, 12, 0],
                [0, 0, 2],
            ],
                name='EQX',
                x=15,
                y=19,
                blocking=BlockingMode.PIXEL_PERFECT,
                interaction=InteractionMode.TANGIBLE,
                tags=['bsT'],
            ),
            sprites['Hkx'].clone().set_position(19, 7),
            sprites['Hkx'].clone().set_position(15, 7),
            sprites['Hkx'].clone().set_position(11, 7),
            sprites['Hkx'].clone().set_position(19, 11),
            sprites['Hkx'].clone().set_position(11, 11),
            sprites['Hkx'].clone().set_position(19, 15),
            sprites['Hkx'].clone().set_position(15, 15),
            sprites['Hkx'].clone().set_position(11, 15),
            sprites['Hkx'].clone().set_position(11, 19),
            sprites['Hkx'].clone().set_position(15, 23),
            sprites['Hkx'].clone().set_position(19, 23),
            sprites['Hkx'].clone().set_position(19, 19),
            sprites['Hkx'].clone().set_position(11, 23),
            Sprite(
                pixels=[
                [2, 0, 2],
                [0, 12, 2],
                [0, 2, 2],
            ],
                name='jGI',
                x=15,
                y=11,
                blocking=BlockingMode.PIXEL_PERFECT,
                interaction=InteractionMode.TANGIBLE,
                tags=['bsT'],
            ),
            sprites['qpe'].clone().set_position(0, 0),
            sprites['viw'].clone().set_position(0, 2),
        ],
        grid_size=(32, 32),
        data={'kCv': 32, 'cwU': [9, 12], 'elp': [[0, 0, 0], [0, 1, 0], [0, 0, 0]]},
        name='hxv',
    ),
    # Level 3
    Level(
        sprites=[
            Sprite(
                pixels=[
                [2, 2, 0],
                [2, 8, 2],
                [0, 2, 2],
            ],
                name='APy',
                x=11,
                y=14,
                blocking=BlockingMode.PIXEL_PERFECT,
                interaction=InteractionMode.TANGIBLE,
                tags=['bsT'],
            ),
            Sprite(
                pixels=[
                [2, 2, 2],
                [2, 8, 2],
                [0, 2, 0],
            ],
                name='dta',
                x=15,
                y=22,
                blocking=BlockingMode.PIXEL_PERFECT,
                interaction=InteractionMode.TANGIBLE,
                tags=['bsT'],
            ),
            sprites['fBi'].clone().set_position(0, 0),
            sprites['Hkx'].clone().set_position(19, 2),
            sprites['Hkx'].clone().set_position(19, 6),
            sprites['Hkx'].clone().set_position(19, 10),
            sprites['Hkx'].clone().set_position(15, 10),
            sprites['Hkx'].clone().set_position(15, 14),
            sprites['Hkx'].clone().set_position(11, 10),
            sprites['Hkx'].clone().set_position(11, 6),
            sprites['Hkx'].clone().set_position(7, 10),
            sprites['Hkx'].clone().set_position(11, 2),
            sprites['Hkx'].clone().set_position(15, 2),
            sprites['Hkx'].clone().set_position(23, 14),
            sprites['Hkx'].clone().set_position(23, 10),
            sprites['Hkx'].clone().set_position(19, 18),
            sprites['Hkx'].clone().set_position(23, 18),
            sprites['Hkx'].clone().set_position(15, 18),
            sprites['Hkx'].clone().set_position(11, 18),
            sprites['Hkx'].clone().set_position(7, 18),
            sprites['Hkx'].clone().set_position(7, 14),
            sprites['Hkx'].clone().set_position(19, 22),
            sprites['Hkx'].clone().set_position(11, 22),
            sprites['Hkx'].clone().set_position(15, 26),
            sprites['Hkx'].clone().set_position(19, 26),
            sprites['Hkx'].clone().set_position(11, 26),
            Sprite(
                pixels=[
                [0, 0, 2],
                [0, 12, 0],
                [0, 2, 2],
            ],
                name='KYk',
                x=15,
                y=6,
                blocking=BlockingMode.PIXEL_PERFECT,
                interaction=InteractionMode.TANGIBLE,
                tags=['bsT'],
            ),
            Sprite(
                pixels=[
                [0, 0, 2],
                [2, 8, 0],
                [2, 2, 0],
            ],
                name='SXM',
                x=19,
                y=14,
                blocking=BlockingMode.PIXEL_PERFECT,
                interaction=InteractionMode.TANGIBLE,
                tags=['bsT'],
            ),
        ],
        grid_size=(32, 32),
        data={'kCv': 96, 'cwU': [8, 12], 'elp': [[0, 0, 0], [0, 1, 0], [0, 0, 0]]},
        name='Fmh',
    ),
    # Level 4
    Level(
        sprites=[
            Sprite(
                pixels=[
                [0, 2, 2],
                [0, 9, 2],
                [2, 0, 2],
            ],
                name='aRa',
                x=11,
                y=11,
                blocking=BlockingMode.PIXEL_PERFECT,
                interaction=InteractionMode.TANGIBLE,
                tags=['bsT'],
            ),
            sprites['gYF'].clone().set_position(0, 4),
            sprites['Hkx'].clone().set_position(19, 7),
            sprites['Hkx'].clone().set_position(15, 11),
            sprites['Hkx'].clone().set_position(15, 15),
            sprites['Hkx'].clone().set_position(7, 11),
            sprites['Hkx'].clone().set_position(7, 15),
            sprites['Hkx'].clone().set_position(11, 7),
            sprites['Hkx'].clone().set_position(15, 7),
            sprites['Hkx'].clone().set_position(23, 11),
            sprites['Hkx'].clone().set_position(19, 15),
            sprites['Hkx'].clone().set_position(11, 15),
            sprites['Hkx'].clone().set_position(23, 15),
            sprites['Hkx'].clone().set_position(23, 7),
            sprites['Hkx'].clone().set_position(7, 7),
            sprites['Hkx'].clone().set_position(19, 19),
            sprites['Hkx'].clone().set_position(11, 19),
            sprites['Hkx'].clone().set_position(19, 23),
            sprites['Hkx'].clone().set_position(15, 23),
            sprites['Hkx'].clone().set_position(11, 23),
            Sprite(
                pixels=[
                [2, 2, 2],
                [2, 9, 2],
                [2, 2, 2],
            ],
                name='lMN',
                x=19,
                y=11,
                blocking=BlockingMode.PIXEL_PERFECT,
                interaction=InteractionMode.TANGIBLE,
                tags=['bsT'],
            ),
            sprites['PrU'].clone().set_position(0, 2),
            sprites['QpB'].clone().set_position(0, 0),
            Sprite(
                pixels=[
                [2, 0, 0],
                [2, 12, 0],
                [0, 2, 2],
            ],
                name='uCe',
                x=15,
                y=19,
                blocking=BlockingMode.PIXEL_PERFECT,
                interaction=InteractionMode.TANGIBLE,
                tags=['bsT'],
            ),
        ],
        grid_size=(32, 32),
        data={'kCv': 96, 'cwU': [9, 8, 12], 'elp': [[0, 0, 0], [0, 1, 0], [0, 0, 0]]},
        name='oea',
    ),
    # Level 5
    Level(
        sprites=[
            Sprite(
                pixels=[
                [3, 3, 0],
                [3, 15, 2],
                [0, 0, 2],
            ],
                name='AQG',
                x=10,
                y=6,
                blocking=BlockingMode.PIXEL_PERFECT,
                interaction=InteractionMode.TANGIBLE,
                tags=['bsT'],
            ),
            Sprite(
                pixels=[
                [2, 0, 2],
                [0, 15, 2],
                [2, 3, 0],
            ],
                name='fPj',
                x=18,
                y=18,
                blocking=BlockingMode.PIXEL_PERFECT,
                interaction=InteractionMode.TANGIBLE,
                tags=['bsT'],
            ),
            sprites['Hkx'].clone().set_position(22, 6),
            sprites['Hkx'].clone().set_position(14, 18),
            sprites['Hkx'].clone().set_position(14, 6),
            sprites['Hkx'].clone().set_position(18, 10),
            sprites['Hkx'].clone().set_position(18, 2),
            sprites['Hkx'].clone().set_position(6, 14),
            sprites['Hkx'].clone().set_position(14, 10),
            sprites['Hkx'].clone().set_position(10, 18),
            sprites['Hkx'].clone().set_position(6, 22),
            sprites['Hkx'].clone().set_position(14, 22),
            sprites['Hkx'].clone().set_position(10, 26),
            sprites['Hkx'].clone().set_position(14, 26),
            sprites['Hkx'].clone().set_position(6, 18),
            sprites['Hkx'].clone().set_position(10, 10),
            sprites['Hkx'].clone().set_position(22, 10),
            sprites['Hkx'].clone().set_position(14, 2),
            sprites['Hkx'].clone().set_position(22, 18),
            sprites['Hkx'].clone().set_position(22, 22),
            sprites['Hkx'].clone().set_position(22, 26),
            sprites['Hkx'].clone().set_position(18, 26),
            sprites['Hkx'].clone().set_position(22, 14),
            sprites['Hkx'].clone().set_position(26, 10),
            sprites['Hkx'].clone().set_position(26, 18),
            sprites['Hkx'].clone().set_position(14, 14),
            sprites['Hkx'].clone().set_position(6, 10),
            sprites['Hkx'].clone().set_position(2, 18),
            sprites['Hkx'].clone().set_position(2, 10),
            Sprite(
                pixels=[
                [0, 0, 3],
                [0, 14, 3],
                [0, 2, 3],
            ],
                name='IFI',
                x=26,
                y=14,
                blocking=BlockingMode.PIXEL_PERFECT,
                interaction=InteractionMode.TANGIBLE,
                tags=['bsT'],
            ),
            sprites['NTi'].clone().set_position(18, 6),
            sprites['NTi'].clone().set_position(10, 22),
            sprites['NTi'].clone().set_position(18, 14),
            sprites['Nul'].clone().set_position(22, 2),
            sprites['PmE'].clone().set_position(6, 26),
            Sprite(
                pixels=[
                [2, 3, 0],
                [0, 14, 2],
                [2, 0, 2],
            ],
                name='qqM',
                x=18,
                y=22,
                blocking=BlockingMode.PIXEL_PERFECT,
                interaction=InteractionMode.TANGIBLE,
                tags=['bsT'],
            ),
            Sprite(
                pixels=[
                [3, 2, 2],
                [3, 14, 2],
                [3, 0, 2],
            ],
                name='SfD',
                x=2,
                y=14,
                blocking=BlockingMode.PIXEL_PERFECT,
                interaction=InteractionMode.TANGIBLE,
                tags=['bsT'],
            ),
            sprites['Ywn'].clone().set_position(3, 0),
            Sprite(
                pixels=[
                [0, 0, 2],
                [0, 15, 2],
                [0, 0, 0],
            ],
                name='yZg',
                x=10,
                y=14,
                blocking=BlockingMode.PIXEL_PERFECT,
                interaction=InteractionMode.TANGIBLE,
                tags=['bsT'],
            ),
        ],
        grid_size=(32, 32),
        data={'kCv': 128, 'cwU': [14, 15], 'elp': [[0, 0, 0], [0, 1, 0], [0, 0, 0]]},
        name='INW',
    ),
    # Level 6
    Level(
        sprites=[
            Sprite(
                pixels=[
                [2, 0, 2],
                [0, 14, 3],
                [3, 3, 3],
            ],
                name='ASc',
                x=7,
                y=23,
                blocking=BlockingMode.PIXEL_PERFECT,
                interaction=InteractionMode.INTANGIBLE,
                tags=['bsT'],
            ),
            sprites['gFd'].clone().set_position(0, 2),
            Sprite(
                pixels=[
                [0, 0, 2],
                [0, 14, 0],
                [0, 2, 2],
            ],
                name='kvt',
                x=19,
                y=15,
                blocking=BlockingMode.PIXEL_PERFECT,
                interaction=InteractionMode.INTANGIBLE,
                tags=['bsT'],
            ),
            Sprite(
                pixels=[
                [2, 2, 2],
                [2, 14, 0],
                [2, 2, 0],
            ],
                name='PjS',
                x=11,
                y=11,
                blocking=BlockingMode.PIXEL_PERFECT,
                interaction=InteractionMode.INTANGIBLE,
                tags=['bsT'],
            ),
            Sprite(
                pixels=[
                [3, 3, 3],
                [3, 14, 2],
                [0, 0, 0],
            ],
                name='ssK',
                x=23,
                y=3,
                blocking=BlockingMode.PIXEL_PERFECT,
                interaction=InteractionMode.INTANGIBLE,
                tags=['bsT'],
            ),
            sprites['Zgh'].clone().set_position(0, 0),
            sprites['ZkU'].clone().set_position(23, 7),
            sprites['ZkU'].clone().set_position(19, 7),
            sprites['ZkU'].clone().set_position(15, 7),
            sprites['ZkU'].clone().set_position(11, 7),
            sprites['ZkU'].clone().set_position(7, 7),
            sprites['ZkU'].clone().set_position(23, 11),
            sprites['ZkU'].clone().set_position(7, 11),
            sprites['ZkU'].clone().set_position(19, 11),
            sprites['ZkU'].clone().set_position(15, 11),
            sprites['ZkU'].clone().set_position(11, 15),
            sprites['ZkU'].clone().set_position(23, 15),
            sprites['ZkU'].clone().set_position(7, 15),
            sprites['ZkU'].clone().set_position(15, 15),
            sprites['ZkU'].clone().set_position(11, 19),
            sprites['ZkU'].clone().set_position(23, 19),
            sprites['ZkU'].clone().set_position(7, 19),
            sprites['ZkU'].clone().set_position(19, 19),
            sprites['ZkU'].clone().set_position(15, 19),
            sprites['ZkU'].clone().set_position(3, 19),
            sprites['ZkU'].clone().set_position(27, 7),
            sprites['ZkU'].clone().set_position(27, 3),
            sprites['ZkU'].clone().set_position(3, 23),
        ],
        grid_size=(32, 32),
        data={'kCv': 128, 'cwU': [11, 14], 'elp': [[0, 0, 0], [0, 1, 0], [0, 0, 0]]},
        name='DFx',
    ),
]

BACKGROUND_COLOR = 4
PADDING_COLOR = 4


class sve(RenderableUserDisplay):
    def __init__(self, sbb: int, vrr: "_Fy09Rules"):
        self.oro = sbb
        self.dzy = sbb
        self.vai = vrr

    def cab(self, shl: int) -> None:
        self.dzy = max(0, min(shl, self.oro))

    def lph(self) -> bool:
        if self.dzy > 0:
            self.dzy -= 1
        return self.dzy > 0

    def dsl(self) -> None:
        self.dzy = self.oro

    def render_interface(self, frame: np.ndarray) -> np.ndarray:
        if self.oro == 0:
            return frame

        slC = self.dzy / self.oro
        GoJ = round(64 * slC)
        for x in range(64):
            frame[0, 63 - x] = 12 if x < GoJ else 11

        return frame


class _Fy09Rules(ARCBaseGame):
    def __init__(self) -> None:
        ZnK = levels[0].get_data("kCv") if levels else 0
        bUg = ZnK if ZnK else 0
        self.lpw = sve(bUg, self)
        super().__init__("ft09", levels, Camera(0, 0, 16, 16, 4, 4, [self.lpw]), available_actions=[6])

    def olv(self) -> None:
        yTL = self.current_level.get_data("kCv")
        if yTL:
            self.lpw.oro = yTL
            self.lpw.dsl()

    def on_set_level(self, level: Level) -> None:
        self.olv()

        self.zth = None
        self.our = 0
        if self.level_index == 0:
            Uev = self.current_level.get_sprites_by_tag("Ycb")
            if Uev:
                self.zth = Uev[0]

        rKu = self.current_level.grid_size
        self.pdw = rKu[0]  # type: ignore
        self.zbh = rKu[1]  # type: ignore

        self.gig = self.current_level.get_sprites_by_tag("bsT")
        self.fhc = self.current_level.get_sprites_by_tag("Hkx")
        self.mou = self.current_level.get_sprites_by_tag("NTi")

        self.gqb = self.current_level.get_data("cwU")
        if self.gqb is None:
            self.gqb = [9, 8]

        self.irw = self.current_level.get_data("elp")

        if self.irw is None:
            self.irw = [[0, 0, 0], [0, 1, 0], [0, 0, 0]]

        for rmy, zge in enumerate(self.fhc):
            zge.color_remap(zge.pixels[0][0], self.gqb[0])

        for rmy, zge in enumerate(self.mou):
            for jon in range(3):
                for vlo in range(3):
                    if zge.pixels[jon][vlo] != 6:
                        zge.pixels[jon][vlo] = self.gqb[0]

    def step(self) -> None:
        if self.action.id.value == 0:
            self.complete_action()
            return

        if self.our > 0 and self.zth:
            self.our -= 1

            aIT = 0 if self.our % 2 == 1 else 2
            Ytt = self.zth.pixels > -1
            self.zth.pixels[Ytt] = aIT
            if self.our == 0:
                self.complete_action()
            return

        kMO = None
        ATn = False
        Hzf = None

        if self.action.id.value == 6:
            AfP = self.action.data.get("x", 0)
            Ywt = self.action.data.get("y", 0)

            Hzf = self.camera.display_to_grid(AfP, Ywt)
            if Hzf:
                ppb, tut = Hzf

                Wmr = self.current_level.get_sprite_at(ppb, tut, "Hkx")
                if not Wmr:
                    Wmr = self.current_level.get_sprite_at(ppb, tut, "NTi")
                    if Wmr:
                        ATn = True
                if Wmr:
                    self.blr = Wmr
                    kMO = 5

        if kMO is None and Hzf is not None:
            uTB = Hzf and self.current_level.get_sprite_at(Hzf[0], Hzf[1], "bsT")
            if self.level_index == 0 and self.zth and not uTB:
                self.our = 4
                return
            self.complete_action()
            return

        GBS = [
            [(-1, -1), (0, -1), (1, -1)],
            [(-1, 0), (0, 0), (1, 0)],
            [(-1, 1), (0, 1), (1, 1)],
        ]

        if ATn:
            eHl = [[0, 0, 0], [0, 1, 0], [0, 0, 0]]
            bBi = self.blr.pixels
            for j in range(3):
                for i in range(3):
                    if bBi[j][i] == 6:
                        eHl[j][i] = 1
        else:
            eHl = self.irw

        if kMO == 5:
            for i in range(3):
                for j in range(3):
                    if eHl[j][i] == 1:
                        ybc, lga = GBS[j][i]
                        cAw = (self.blr.x + (ybc * 4), self.blr.y + (lga * 4))

                        RfH = self.current_level.get_sprite_at(cAw[0], cAw[1], "Hkx")

                        if not RfH:
                            RfH = self.current_level.get_sprite_at(cAw[0], cAw[1], "NTi")
                        if RfH:
                            kNa = self.gqb.index(RfH.pixels[1][1])
                            kNa = (kNa + 1) % len(self.gqb)
                            RfH.color_remap(RfH.pixels[1][1], self.gqb[kNa])

        if self.cgj():
            self.next_level()
            self.complete_action()
            return

        if not self.lpw.lph():
            self.lose()

        self.complete_action()

    def cgj(self) -> bool:
        for etf in self.gig:
            nRq = etf.pixels[1][1]

            HJd = etf.pixels[0][0] == 0
            tx, ty = etf.x - 4, etf.y - 4
            PML = self.current_level.get_sprite_at(tx, ty, "Hkx")
            if not PML:
                PML = self.current_level.get_sprite_at(tx, ty, "NTi")

            if PML:
                pbA = (PML.pixels[1][1] == nRq) if HJd else (PML.pixels[1][1] != nRq)
                if not pbA:
                    return False

            HJd = etf.pixels[0][1] == 0
            tx, ty = etf.x, etf.y - 4
            PML = self.current_level.get_sprite_at(tx, ty, "Hkx")
            if not PML:
                PML = self.current_level.get_sprite_at(tx, ty, "NTi")
            if PML:
                pbA = (PML.pixels[1][1] == nRq) if HJd else (PML.pixels[1][1] != nRq)
                if not pbA:
                    return False

            HJd = etf.pixels[0][2] == 0
            tx, ty = etf.x + 4, etf.y - 4
            PML = self.current_level.get_sprite_at(tx, ty, "Hkx")
            if not PML:
                PML = self.current_level.get_sprite_at(tx, ty, "NTi")
            if PML:
                pbA = (PML.pixels[1][1] == nRq) if HJd else (PML.pixels[1][1] != nRq)
                if not pbA:
                    return False

            HJd = etf.pixels[1][0] == 0
            tx, ty = etf.x - 4, etf.y
            PML = self.current_level.get_sprite_at(tx, ty, "Hkx")
            if not PML:
                PML = self.current_level.get_sprite_at(tx, ty, "NTi")
            if PML:
                pbA = (PML.pixels[1][1] == nRq) if HJd else (PML.pixels[1][1] != nRq)
                if not pbA:
                    return False

            HJd = etf.pixels[1][2] == 0
            tx, ty = etf.x + 4, etf.y
            PML = self.current_level.get_sprite_at(tx, ty, "Hkx")
            if not PML:
                PML = self.current_level.get_sprite_at(tx, ty, "NTi")
            if PML:
                pbA = (PML.pixels[1][1] == nRq) if HJd else (PML.pixels[1][1] != nRq)
                if not pbA:
                    return False

            HJd = etf.pixels[2][0] == 0
            tx, ty = etf.x - 4, etf.y + 4
            PML = self.current_level.get_sprite_at(tx, ty, "Hkx")
            if not PML:
                PML = self.current_level.get_sprite_at(tx, ty, "NTi")
            if PML:
                pbA = (PML.pixels[1][1] == nRq) if HJd else (PML.pixels[1][1] != nRq)
                if not pbA:
                    return False

            HJd = etf.pixels[2][1] == 0
            tx, ty = etf.x, etf.y + 4
            PML = self.current_level.get_sprite_at(tx, ty, "Hkx")
            if not PML:
                PML = self.current_level.get_sprite_at(tx, ty, "NTi")
            if PML:
                pbA = (PML.pixels[1][1] == nRq) if HJd else (PML.pixels[1][1] != nRq)
                if not pbA:
                    return False

            HJd = etf.pixels[2][2] == 0
            tx, ty = etf.x + 4, etf.y + 4
            PML = self.current_level.get_sprite_at(tx, ty, "Hkx")
            if not PML:
                PML = self.current_level.get_sprite_at(tx, ty, "NTi")
            if PML:
                pbA = (PML.pixels[1][1] == nRq) if HJd else (PML.pixels[1][1] != nRq)
                if not pbA:
                    return False
        return True


# ── copycat layer ───────────────────────────────────────────────────────────────
# Colour assignment for this copycat: displayed colour = _CC_PALETTE[engine colour].
# Applied to the camera's final 64x64 output only, so the game's own rules (some of which
# read sprite colours) are untouched.
_CC_PALETTE = np.array([3, 8, 10, 14, 13, 4, 5, 9, 11, 6, 0, 12, 15, 2, 1, 7], dtype=np.int8)


class _CcCamera(Camera):
    def render(self, sprites):
        frame = super().render(sprites)
        frame = np.asarray(frame)
        out = frame.copy()
        mask = (frame >= 0) & (frame <= 15)
        out[mask] = _CC_PALETTE[frame[mask].astype(np.int64)]
        return out


class Fy09(_Fy09Rules):
    def __init__(self) -> None:
        super().__init__()
        if type(self._camera) is Camera:
            self._camera.__class__ = _CcCamera
        if not isinstance(self._camera, _CcCamera):
            raise RuntimeError("copycat palette camera not installed")
        self._game_id = 'fy09'

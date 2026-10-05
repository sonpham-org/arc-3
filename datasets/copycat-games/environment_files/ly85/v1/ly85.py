# Copycat ly85: rules of public ARC-AGI-3 game lp85, new maps, colours and art.
# Built and verified by autoresearch-arena arc3games/copycats/cc_lp85.py.
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

from typing import Dict, List, NamedTuple, Tuple, TypedDict

import numpy as np
from arcengine import (
    BlockingMode,
    InteractionMode,
    ARCBaseGame,
    Camera,
    GameAction,
    Level,
    RenderableUserDisplay,
    Sprite,
)

sprites = {
    'ahdesifykt': Sprite(
        pixels=[
        [8, 8, -1],
        [-1, 8, 8],
        [-1, 8, 8],
        [8, 8, -1],
    ],
        name='ahdesifykt',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['button_A_L', 'sys_click'],
    ),
    'aoibinevrm': Sprite(
        pixels=[
        [-1, 14, 14],
        [14, 14, -1],
        [14, 14, -1],
        [-1, 14, 14],
    ],
        name='aoibinevrm',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['button_13_R', 'sys_click'],
    ),
    'aqwhbtzcfg': Sprite(
        pixels=[
        [-1, 14, 14],
        [14, 14, -1],
        [14, 14, -1],
        [-1, 14, 14],
    ],
        name='aqwhbtzcfg',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['button_27_R', 'sys_click'],
    ),
    'auxglvwwep': Sprite(
        pixels=[
        [-1, 14, 14],
        [14, 14, -1],
        [14, 14, -1],
        [-1, 14, 14],
    ],
        name='auxglvwwep',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['button_23_R', 'sys_click'],
    ),
    'avazowxmej': Sprite(
        pixels=[
        [-1, 14, 14],
        [14, 14, -1],
        [14, 14, -1],
        [-1, 14, 14],
    ],
        name='avazowxmej',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['button_18_R', 'sys_click'],
    ),
    'aydooxtcli': Sprite(
        pixels=[
        [-1, 9],
        [9, -1],
    ],
        name='aydooxtcli',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['tile'],
    ),
    'azkpmswird': Sprite(
        pixels=[
        [-1, 14, 14],
        [14, 14, -1],
        [14, 14, -1],
        [-1, 14, 14],
    ],
        name='azkpmswird',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['button_8_R', 'sys_click'],
    ),
    'bbxrzomunc': Sprite(
        pixels=[
        [-1, 14, 14],
        [14, 14, -1],
        [14, 14, -1],
        [-1, 14, 14],
    ],
        name='bbxrzomunc',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['button_11_R', 'sys_click'],
    ),
    'bghvgbtwcb': Sprite(
        pixels=[
        [-1, 11, 11, -1],
        [11, -1, -1, 11],
        [11, -1, -1, 11],
        [-1, 11, 11, -1],
    ],
        name='bghvgbtwcb',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['bghvgbtwcb'],
    ),
    'cfhhkdewbs': Sprite(
        pixels=[
        [-1, 14, 14],
        [14, 14, -1],
        [14, 14, -1],
        [-1, 14, 14],
    ],
        name='cfhhkdewbs',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['button_3_R', 'sys_click'],
    ),
    'cgkbezvpdp': Sprite(
        pixels=[
        [-1, 14, 14],
        [14, 14, -1],
        [14, 14, -1],
        [-1, 14, 14],
    ],
        name='cgkbezvpdp',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['button_9_R', 'sys_click'],
    ),
    'chwujwypuk': Sprite(
        pixels=[
        [8, 8, -1],
        [-1, 8, 8],
        [-1, 8, 8],
        [8, 8, -1],
    ],
        name='chwujwypuk',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['button_2_L', 'sys_click'],
    ),
    'cjcssvobei': Sprite(
        pixels=[
        [-1, 14, 14],
        [14, 14, -1],
        [14, 14, -1],
        [-1, 14, 14],
    ],
        name='cjcssvobei',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['button_I_R', 'sys_click'],
    ),
    'ckkvkowlfm': Sprite(
        pixels=[
        [8, 8, -1],
        [-1, 8, 8],
        [-1, 8, 8],
        [8, 8, -1],
    ],
        name='ckkvkowlfm',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['button_26_L', 'sys_click'],
    ),
    'cyqncaekpb': Sprite(
        pixels=[
        [-1, 14, 14],
        [14, 14, -1],
        [14, 14, -1],
        [-1, 14, 14],
    ],
        name='cyqncaekpb',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['button_1_R', 'sys_click'],
    ),
    'djepopdkpm': Sprite(
        pixels=[
        [-1, 14, 14],
        [14, 14, -1],
        [14, 14, -1],
        [-1, 14, 14],
    ],
        name='djepopdkpm',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['button_4_R', 'sys_click'],
    ),
    'djqnpusomv': Sprite(
        pixels=[
        [8, 8, -1],
        [-1, 8, 8],
        [-1, 8, 8],
        [8, 8, -1],
    ],
        name='djqnpusomv',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['button_23_L', 'sys_click'],
    ),
    'dvvacwfchj': Sprite(
        pixels=[
        [-1, 14, 14],
        [14, 14, -1],
        [14, 14, -1],
        [-1, 14, 14],
    ],
        name='dvvacwfchj',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['button_B_R', 'sys_click'],
    ),
    'ekpijbeoel': Sprite(
        pixels=[
        [-1, 1],
        [1, -1],
    ],
        name='ekpijbeoel',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['tile'],
    ),
    'fdgmtkfrxl': Sprite(
        pixels=[
        [-1, 12, 12, -1],
        [12, -1, -1, 12],
        [12, -1, -1, 12],
        [-1, 12, 12, -1],
    ],
        name='fdgmtkfrxl',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['fdgmtkfrxl'],
    ),
    'fxtadqcoja': Sprite(
        pixels=[
        [8, 8, -1],
        [-1, 8, 8],
        [-1, 8, 8],
        [8, 8, -1],
    ],
        name='fxtadqcoja',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['button_14_L', 'sys_click'],
    ),
    'gknuimaglj': Sprite(
        pixels=[
        [-1, 14, 14],
        [14, 14, -1],
        [14, 14, -1],
        [-1, 14, 14],
    ],
        name='gknuimaglj',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['button_24_R', 'sys_click'],
    ),
    'gzfuxxfhxh': Sprite(
        pixels=[
        [-1, 14, 14],
        [14, 14, -1],
        [14, 14, -1],
        [-1, 14, 14],
    ],
        name='gzfuxxfhxh',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['button_L_R', 'sys_click'],
    ),
    'hfikqtizdo': Sprite(
        pixels=[
        [12, 12],
        [12, 12],
    ],
        name='hfikqtizdo',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['goal-o'],
    ),
    'hiictjojxg': Sprite(
        pixels=[
        [-1, 14, 14],
        [14, 14, -1],
        [14, 14, -1],
        [-1, 14, 14],
    ],
        name='hiictjojxg',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['button_5_R', 'sys_click'],
    ),
    'hlpgfhkhui': Sprite(
        pixels=[
        [8, 8, -1],
        [-1, 8, 8],
        [-1, 8, 8],
        [8, 8, -1],
    ],
        name='hlpgfhkhui',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['button_16_L', 'sys_click'],
    ),
    'hvgvgpuasf': Sprite(
        pixels=[
        [-1, 14, 14],
        [14, 14, -1],
        [14, 14, -1],
        [-1, 14, 14],
    ],
        name='hvgvgpuasf',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['button_D_R', 'sys_click'],
    ),
    'hyifvqmswy': Sprite(
        pixels=[
        [-1, 14, 14],
        [14, 14, -1],
        [14, 14, -1],
        [-1, 14, 14],
    ],
        name='hyifvqmswy',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['button_K_R', 'sys_click'],
    ),
    'icgyrqkqpc': Sprite(
        pixels=[
        [-1, 14, 14],
        [14, 14, -1],
        [14, 14, -1],
        [-1, 14, 14],
    ],
        name='icgyrqkqpc',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['button_16_R', 'sys_click'],
    ),
    'ikexwlluqt': Sprite(
        pixels=[
        [-1, 14, 14],
        [14, 14, -1],
        [14, 14, -1],
        [-1, 14, 14],
    ],
        name='ikexwlluqt',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['button_J_R', 'sys_click'],
    ),
    'ikgydmjteo': Sprite(
        pixels=[
        [-1, 14, 14],
        [14, 14, -1],
        [14, 14, -1],
        [-1, 14, 14],
    ],
        name='ikgydmjteo',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['button_10_R', 'sys_click'],
    ),
    'iozrrxaimm': Sprite(
        pixels=[
        [8, 8, -1],
        [-1, 8, 8],
        [-1, 8, 8],
        [8, 8, -1],
    ],
        name='iozrrxaimm',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['button_27_L', 'sys_click'],
    ),
    'isjrkszgff': Sprite(
        pixels=[
        [-1, 14, 14],
        [14, 14, -1],
        [14, 14, -1],
        [-1, 14, 14],
    ],
        name='isjrkszgff',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['button_22_R', 'sys_click'],
    ),
    'jxibbjkyqn': Sprite(
        pixels=[
        [-1, 14, 14],
        [14, 14, -1],
        [14, 14, -1],
        [-1, 14, 14],
    ],
        name='jxibbjkyqn',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['button_12_R', 'sys_click'],
    ),
    'kcuuamovad': Sprite(
        pixels=[
        [-1, 14, 14],
        [14, 14, -1],
        [14, 14, -1],
        [-1, 14, 14],
    ],
        name='kcuuamovad',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['button_17_R', 'sys_click'],
    ),
    'kisflvfvsy': Sprite(
        pixels=[
        [-1, 10],
        [10, -1],
    ],
        name='kisflvfvsy',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['tile'],
    ),
    'ksnvdjtrfm': Sprite(
        pixels=[
        [8, 8, -1],
        [-1, 8, 8],
        [-1, 8, 8],
        [8, 8, -1],
    ],
        name='ksnvdjtrfm',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['button_7_L', 'sys_click'],
    ),
    'kzjtnfvqjg': Sprite(
        pixels=[
        [8, 8, -1],
        [-1, 8, 8],
        [-1, 8, 8],
        [8, 8, -1],
    ],
        name='kzjtnfvqjg',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['button_4_L', 'sys_click'],
    ),
    'lfcynjbowf': Sprite(
        pixels=[
        [-1, 14, 14],
        [14, 14, -1],
        [14, 14, -1],
        [-1, 14, 14],
    ],
        name='lfcynjbowf',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['button_2_R', 'sys_click'],
    ),
    'lfimxyubtw': Sprite(
        pixels=[
        [8, 8, -1],
        [-1, 8, 8],
        [-1, 8, 8],
        [8, 8, -1],
    ],
        name='lfimxyubtw',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['button_E_L', 'sys_click'],
    ),
    'lnnponqnto': Sprite(
        pixels=[
        [-1, 14, 14],
        [14, 14, -1],
        [14, 14, -1],
        [-1, 14, 14],
    ],
        name='lnnponqnto',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['button_6_R', 'sys_click'],
    ),
    'lqtjzsqwtz': Sprite(
        pixels=[
        [-1, 14, 14],
        [14, 14, -1],
        [14, 14, -1],
        [-1, 14, 14],
    ],
        name='lqtjzsqwtz',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['button_20_R', 'sys_click'],
    ),
    'mchtsgjpjm': Sprite(
        pixels=[
        [8, 8, -1],
        [-1, 8, 8],
        [-1, 8, 8],
        [8, 8, -1],
    ],
        name='mchtsgjpjm',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['button_12_L', 'sys_click'],
    ),
    'msmalfqpgt': Sprite(
        pixels=[
        [8, 8, -1],
        [-1, 8, 8],
        [-1, 8, 8],
        [8, 8, -1],
    ],
        name='msmalfqpgt',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['button_10_L', 'sys_click'],
    ),
    'nidhkbeymj': Sprite(
        pixels=[
        [8, 8, -1],
        [-1, 8, 8],
        [-1, 8, 8],
        [8, 8, -1],
    ],
        name='nidhkbeymj',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['button_5_L', 'sys_click'],
    ),
    'npiudvzxms': Sprite(
        pixels=[
        [8, 8, -1],
        [-1, 8, 8],
        [-1, 8, 8],
        [8, 8, -1],
    ],
        name='npiudvzxms',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['button_3_L', 'sys_click'],
    ),
    'odkpvwbihk': Sprite(
        pixels=[
        [11, 11],
        [11, 11],
    ],
        name='odkpvwbihk',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['goal'],
    ),
    'olznmtqgqf': Sprite(
        pixels=[
        [8, 8, -1],
        [-1, 8, 8],
        [-1, 8, 8],
        [8, 8, -1],
    ],
        name='olznmtqgqf',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['button_20_L', 'sys_click'],
    ),
    'oqsumsdlyg': Sprite(
        pixels=[
        [8, 8, -1],
        [-1, 8, 8],
        [-1, 8, 8],
        [8, 8, -1],
    ],
        name='oqsumsdlyg',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['button_D_L', 'sys_click'],
    ),
    'peuddygayw': Sprite(
        pixels=[
        [8, 8, -1],
        [-1, 8, 8],
        [-1, 8, 8],
        [8, 8, -1],
    ],
        name='peuddygayw',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['button_B_L', 'sys_click'],
    ),
    'pispbshofi': Sprite(
        pixels=[
        [8, 8, -1],
        [-1, 8, 8],
        [-1, 8, 8],
        [8, 8, -1],
    ],
        name='pispbshofi',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['button_G_L', 'sys_click'],
    ),
    'qfmlfsmppb': Sprite(
        pixels=[
        [-1, 14, 14],
        [14, 14, -1],
        [14, 14, -1],
        [-1, 14, 14],
    ],
        name='qfmlfsmppb',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['button_14_R', 'sys_click'],
    ),
    'qiezkvylfa': Sprite(
        pixels=[
        [8, 8, -1],
        [-1, 8, 8],
        [-1, 8, 8],
        [8, 8, -1],
    ],
        name='qiezkvylfa',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['button_13_L', 'sys_click'],
    ),
    'qwjjziosdl': Sprite(
        pixels=[
        [8, 8, -1],
        [-1, 8, 8],
        [-1, 8, 8],
        [8, 8, -1],
    ],
        name='qwjjziosdl',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['button_21_L', 'sys_click'],
    ),
    'reafrgzfwk': Sprite(
        pixels=[
        [-1, 14, 14],
        [14, 14, -1],
        [14, 14, -1],
        [-1, 14, 14],
    ],
        name='reafrgzfwk',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['button_C_R', 'sys_click'],
    ),
    'rhyksubvjk': Sprite(
        pixels=[
        [-1, 14, 14],
        [14, 14, -1],
        [14, 14, -1],
        [-1, 14, 14],
    ],
        name='rhyksubvjk',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['button_19_R', 'sys_click'],
    ),
    'rltccsmmjh': Sprite(
        pixels=[
        [8, 8, -1],
        [-1, 8, 8],
        [-1, 8, 8],
        [8, 8, -1],
    ],
        name='rltccsmmjh',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['button_I_L', 'sys_click'],
    ),
    'rslwkirzds': Sprite(
        pixels=[
        [8, 8, -1],
        [-1, 8, 8],
        [-1, 8, 8],
        [8, 8, -1],
    ],
        name='rslwkirzds',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['button_19_L', 'sys_click'],
    ),
    'sbogwsxcvo': Sprite(
        pixels=[
        [-1, 14, 14],
        [14, 14, -1],
        [14, 14, -1],
        [-1, 14, 14],
    ],
        name='sbogwsxcvo',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['button_E_R', 'sys_click'],
    ),
    'sjummcsymu': Sprite(
        pixels=[
        [8, 8, -1],
        [-1, 8, 8],
        [-1, 8, 8],
        [8, 8, -1],
    ],
        name='sjummcsymu',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['button_F_L', 'sys_click'],
    ),
    'sklqiglcbh': Sprite(
        pixels=[
        [8, 8, -1],
        [-1, 8, 8],
        [-1, 8, 8],
        [8, 8, -1],
    ],
        name='sklqiglcbh',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['button_18_L', 'sys_click'],
    ),
    'slefrnjymo': Sprite(
        pixels=[
        [-1, 2],
        [2, -1],
    ],
        name='slefrnjymo',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['tile'],
    ),
    'squvkghyif': Sprite(
        pixels=[
        [8, 8, -1],
        [-1, 8, 8],
        [-1, 8, 8],
        [8, 8, -1],
    ],
        name='squvkghyif',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['button_H_L', 'sys_click'],
    ),
    'tcweaqkrko': Sprite(
        pixels=[
        [-1, 14, 14],
        [14, 14, -1],
        [14, 14, -1],
        [-1, 14, 14],
    ],
        name='tcweaqkrko',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['button_15_R', 'sys_click'],
    ),
    'tddzizwhzf': Sprite(
        pixels=[
        [-1, 15],
        [15, -1],
    ],
        name='tddzizwhzf',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['tile'],
    ),
    'tohldkeyto': Sprite(
        pixels=[
        [8, 8, -1],
        [-1, 8, 8],
        [-1, 8, 8],
        [8, 8, -1],
    ],
        name='tohldkeyto',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['button_1_L', 'sys_click'],
    ),
    'uqipjzobpp': Sprite(
        pixels=[
        [-1, 14, 14],
        [14, 14, -1],
        [14, 14, -1],
        [-1, 14, 14],
    ],
        name='uqipjzobpp',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['button_F_R', 'sys_click'],
    ),
    'uyqbibneuw': Sprite(
        pixels=[
        [8, 8, -1],
        [-1, 8, 8],
        [-1, 8, 8],
        [8, 8, -1],
    ],
        name='uyqbibneuw',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['button_15_L', 'sys_click'],
    ),
    'vdeasuthve': Sprite(
        pixels=[
        [8, 8, -1],
        [-1, 8, 8],
        [-1, 8, 8],
        [8, 8, -1],
    ],
        name='vdeasuthve',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['button_6_L', 'sys_click'],
    ),
    'vdjpajqpny': Sprite(
        pixels=[
        [-1, 14, 14],
        [14, 14, -1],
        [14, 14, -1],
        [-1, 14, 14],
    ],
        name='vdjpajqpny',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['button_21_R', 'sys_click'],
    ),
    'viyoficcma': Sprite(
        pixels=[
        [8, 8, -1],
        [-1, 8, 8],
        [-1, 8, 8],
        [8, 8, -1],
    ],
        name='viyoficcma',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['button_11_L', 'sys_click'],
    ),
    'vwassicppq': Sprite(
        pixels=[
        [8, 8, -1],
        [-1, 8, 8],
        [-1, 8, 8],
        [8, 8, -1],
    ],
        name='vwassicppq',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['button_L_L', 'sys_click'],
    ),
    'vwwnrphkjt': Sprite(
        pixels=[
        [-1, 14, 14],
        [14, 14, -1],
        [14, 14, -1],
        [-1, 14, 14],
    ],
        name='vwwnrphkjt',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['button_M_R', 'sys_click'],
    ),
    'wnmnhngnez': Sprite(
        pixels=[
        [8, 8, -1],
        [-1, 8, 8],
        [-1, 8, 8],
        [8, 8, -1],
    ],
        name='wnmnhngnez',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['button_K_L', 'sys_click'],
    ),
    'wonxgysgjx': Sprite(
        pixels=[
        [8, 8, -1],
        [-1, 8, 8],
        [-1, 8, 8],
        [8, 8, -1],
    ],
        name='wonxgysgjx',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['button_M_L', 'sys_click'],
    ),
    'wvgpslgvch': Sprite(
        pixels=[
        [8, 8, -1],
        [-1, 8, 8],
        [-1, 8, 8],
        [8, 8, -1],
    ],
        name='wvgpslgvch',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['button_22_L', 'sys_click'],
    ),
    'wxlzrpcmji': Sprite(
        pixels=[
        [8, 8, -1],
        [-1, 8, 8],
        [-1, 8, 8],
        [8, 8, -1],
    ],
        name='wxlzrpcmji',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['button_9_L', 'sys_click'],
    ),
    'xtxayxwyfn': Sprite(
        pixels=[
        [-1, 14, 14],
        [14, 14, -1],
        [14, 14, -1],
        [-1, 14, 14],
    ],
        name='xtxayxwyfn',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['button_G_R', 'sys_click'],
    ),
    'ycdtvcgsiu': Sprite(
        pixels=[
        [8, 8, -1],
        [-1, 8, 8],
        [-1, 8, 8],
        [8, 8, -1],
    ],
        name='ycdtvcgsiu',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['button_25_L', 'sys_click'],
    ),
    'yjdrfgspyl': Sprite(
        pixels=[
        [8, 8, -1],
        [-1, 8, 8],
        [-1, 8, 8],
        [8, 8, -1],
    ],
        name='yjdrfgspyl',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['button_8_L', 'sys_click'],
    ),
    'ymwkwkfxct': Sprite(
        pixels=[
        [8, 8, -1],
        [-1, 8, 8],
        [-1, 8, 8],
        [8, 8, -1],
    ],
        name='ymwkwkfxct',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['button_C_L', 'sys_click'],
    ),
    'ypbsjakojf': Sprite(
        pixels=[
        [-1, 14, 14],
        [14, 14, -1],
        [14, 14, -1],
        [-1, 14, 14],
    ],
        name='ypbsjakojf',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['button_7_R', 'sys_click'],
    ),
    'yqgkbwbeag': Sprite(
        pixels=[
        [8, 8, -1],
        [-1, 8, 8],
        [-1, 8, 8],
        [8, 8, -1],
    ],
        name='yqgkbwbeag',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['button_24_L', 'sys_click'],
    ),
    'yyxhanzsay': Sprite(
        pixels=[
        [8, 8, -1],
        [-1, 8, 8],
        [-1, 8, 8],
        [8, 8, -1],
    ],
        name='yyxhanzsay',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['button_17_L', 'sys_click'],
    ),
    'zapbjqjgij': Sprite(
        pixels=[
        [8, 8, -1],
        [-1, 8, 8],
        [-1, 8, 8],
        [8, 8, -1],
    ],
        name='zapbjqjgij',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['button_J_L', 'sys_click'],
    ),
    'zdlwfpeyyd': Sprite(
        pixels=[
        [-1, 14, 14],
        [14, 14, -1],
        [14, 14, -1],
        [-1, 14, 14],
    ],
        name='zdlwfpeyyd',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['button_H_R', 'sys_click'],
    ),
    'zpxgvxwdex': Sprite(
        pixels=[
        [-1, 14, 14],
        [14, 14, -1],
        [14, 14, -1],
        [-1, 14, 14],
    ],
        name='zpxgvxwdex',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['button_A_R', 'sys_click'],
    ),
    'zrzovwqbcx': Sprite(
        pixels=[
        [-1, 14, 14],
        [14, 14, -1],
        [14, 14, -1],
        [-1, 14, 14],
    ],
        name='zrzovwqbcx',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['button_25_R', 'sys_click'],
    ),
    'zseotqksli': Sprite(
        pixels=[
        [-1, 14, 14],
        [14, 14, -1],
        [14, 14, -1],
        [-1, 14, 14],
    ],
        name='zseotqksli',
        blocking=BlockingMode.PIXEL_PERFECT,
        interaction=InteractionMode.TANGIBLE,
        tags=['button_26_R', 'sys_click'],
    ),
}
levels = [
    # Level 1
    Level(
        sprites=[
            sprites['ahdesifykt'].clone().set_position(28, 8),
            sprites['aydooxtcli'].clone().set_position(6, 3),
            sprites['aydooxtcli'].clone().set_position(9, 3),
            sprites['aydooxtcli'].clone().set_position(21, 15),
            sprites['aydooxtcli'].clone().set_position(6, 12),
            sprites['bghvgbtwcb'].clone().set_position(23, 11),
            sprites['ekpijbeoel'].clone().set_position(18, 3),
            sprites['ekpijbeoel'].clone().set_position(24, 3),
            sprites['ekpijbeoel'].clone().set_position(6, 15),
            sprites['kisflvfvsy'].clone().set_position(6, 6),
            sprites['kisflvfvsy'].clone().set_position(24, 15),
            sprites['kisflvfvsy'].clone().set_position(6, 9),
            sprites['kisflvfvsy'].clone().set_position(12, 15),
            sprites['odkpvwbihk'].clone().set_position(9, 15),
            sprites['slefrnjymo'].clone().set_position(24, 9),
            sprites['slefrnjymo'].clone().set_position(12, 3),
            sprites['slefrnjymo'].clone().set_position(15, 3),
            sprites['slefrnjymo'].clone().set_position(24, 12),
            sprites['tddzizwhzf'].clone().set_position(15, 15),
            sprites['tddzizwhzf'].clone().set_position(21, 3),
            sprites['tddzizwhzf'].clone().set_position(24, 6),
            sprites['tddzizwhzf'].clone().set_position(18, 15),
            sprites['zpxgvxwdex'].clone().set_position(1, 8),
        ],
        grid_size=(32, 19),
        data={'StepCounter': 13, 'level_name': 'kdrsqrvpwb'},
    ),
    # Level 2
    Level(
        sprites=[
            sprites['ahdesifykt'].clone().set_position(30, 5),
            sprites['aydooxtcli'].clone().set_position(27, 27),
            sprites['aydooxtcli'].clone().set_position(27, 21),
            sprites['aydooxtcli'].clone().set_position(21, 24),
            sprites['aydooxtcli'].clone().set_position(27, 24),
            sprites['aydooxtcli'].clone().set_position(9, 15),
            sprites['aydooxtcli'].clone().set_position(27, 30),
            sprites['aydooxtcli'].clone().set_position(15, 33),
            sprites['aydooxtcli'].clone().set_position(6, 15),
            sprites['bghvgbtwcb'].clone().set_position(20, 23),
            sprites['bghvgbtwcb'].clone().set_position(14, 26),
            sprites['dvvacwfchj'].clone().set_position(2, 14),
            sprites['ekpijbeoel'].clone().set_position(15, 15),
            sprites['ekpijbeoel'].clone().set_position(12, 15),
            sprites['ekpijbeoel'].clone().set_position(33, 15),
            sprites['ekpijbeoel'].clone().set_position(21, 33),
            sprites['ekpijbeoel'].clone().set_position(30, 15),
            sprites['ekpijbeoel'].clone().set_position(18, 6),
            sprites['ekpijbeoel'].clone().set_position(18, 33),
            sprites['ekpijbeoel'].clone().set_position(15, 6),
            sprites['kisflvfvsy'].clone().set_position(15, 30),
            sprites['kisflvfvsy'].clone().set_position(15, 9),
            sprites['kisflvfvsy'].clone().set_position(15, 18),
            sprites['kisflvfvsy'].clone().set_position(15, 27),
            sprites['kisflvfvsy'].clone().set_position(12, 24),
            sprites['kisflvfvsy'].clone().set_position(27, 18),
            sprites['kisflvfvsy'].clone().set_position(18, 15),
            sprites['kisflvfvsy'].clone().set_position(24, 33),
            sprites['kisflvfvsy'].clone().set_position(15, 21),
            sprites['odkpvwbihk'].clone().set_position(21, 15),
            sprites['odkpvwbihk'].clone().set_position(27, 9),
            sprites['peuddygayw'].clone().set_position(36, 14),
            sprites['reafrgzfwk'].clone().set_position(2, 23),
            sprites['slefrnjymo'].clone().set_position(24, 15),
            sprites['slefrnjymo'].clone().set_position(27, 6),
            sprites['slefrnjymo'].clone().set_position(24, 24),
            sprites['slefrnjymo'].clone().set_position(27, 12),
            sprites['slefrnjymo'].clone().set_position(9, 24),
            sprites['slefrnjymo'].clone().set_position(15, 24),
            sprites['slefrnjymo'].clone().set_position(6, 24),
            sprites['slefrnjymo'].clone().set_position(21, 6),
            sprites['tddzizwhzf'].clone().set_position(27, 33),
            sprites['tddzizwhzf'].clone().set_position(24, 6),
            sprites['tddzizwhzf'].clone().set_position(33, 24),
            sprites['tddzizwhzf'].clone().set_position(27, 15),
            sprites['tddzizwhzf'].clone().set_position(30, 24),
            sprites['tddzizwhzf'].clone().set_position(18, 24),
            sprites['tddzizwhzf'].clone().set_position(15, 12),
            sprites['ymwkwkfxct'].clone().set_position(36, 23),
            sprites['zpxgvxwdex'].clone().set_position(11, 5),
        ],
        grid_size=(41, 41),
        data={'StepCounter': 60, 'level_name': 'cecdsipmha'},
    ),
    # Level 3
    Level(
        sprites=[
            sprites['ahdesifykt'].clone().set_position(13, 24),
            sprites['aydooxtcli'].clone().set_position(6, 6),
            sprites['aydooxtcli'].clone().set_position(33, 9),
            sprites['aydooxtcli'].clone().set_position(21, 21),
            sprites['aydooxtcli'].clone().set_position(3, 15),
            sprites['aydooxtcli'].clone().set_position(21, 12),
            sprites['aydooxtcli'].clone().set_position(24, 3),
            sprites['aydooxtcli'].clone().set_position(21, 3),
            sprites['aydooxtcli'].clone().set_position(15, 15),
            sprites['bghvgbtwcb'].clone().set_position(5, 5),
            sprites['dvvacwfchj'].clone().set_position(22, 24),
            sprites['ekpijbeoel'].clone().set_position(3, 12),
            sprites['ekpijbeoel'].clone().set_position(3, 9),
            sprites['ekpijbeoel'].clone().set_position(21, 9),
            sprites['ekpijbeoel'].clone().set_position(18, 18),
            sprites['ekpijbeoel'].clone().set_position(30, 6),
            sprites['ekpijbeoel'].clone().set_position(33, 12),
            sprites['fdgmtkfrxl'].clone().set_position(32, 14),
            sprites['hfikqtizdo'].clone().set_position(6, 18),
            sprites['kisflvfvsy'].clone().set_position(27, 3),
            sprites['kisflvfvsy'].clone().set_position(12, 3),
            sprites['kisflvfvsy'].clone().set_position(18, 6),
            sprites['kisflvfvsy'].clone().set_position(21, 15),
            sprites['odkpvwbihk'].clone().set_position(9, 21),
            sprites['peuddygayw'].clone().set_position(25, 24),
            sprites['slefrnjymo'].clone().set_position(15, 9),
            sprites['slefrnjymo'].clone().set_position(15, 12),
            sprites['slefrnjymo'].clone().set_position(9, 3),
            sprites['slefrnjymo'].clone().set_position(12, 21),
            sprites['slefrnjymo'].clone().set_position(24, 21),
            sprites['tddzizwhzf'].clone().set_position(15, 21),
            sprites['tddzizwhzf'].clone().set_position(33, 15),
            sprites['tddzizwhzf'].clone().set_position(30, 18),
            sprites['tddzizwhzf'].clone().set_position(15, 3),
            sprites['tddzizwhzf'].clone().set_position(27, 21),
            sprites['zpxgvxwdex'].clone().set_position(10, 24),
        ],
        grid_size=(39, 31),
        data={'StepCounter': 80, 'level_name': 'vvnbesozdj'},
    ),
    # Level 4
    Level(
        sprites=[
            sprites['ahdesifykt'].clone().set_position(51, 11),
            sprites['ahdesifykt'].clone().set_position(21, 11),
            sprites['ahdesifykt'].clone().set_position(21, 41),
            sprites['ahdesifykt'].clone().set_position(51, 41),
            sprites['aydooxtcli'].clone().set_position(45, 12),
            sprites['aydooxtcli'].clone().set_position(42, 39),
            sprites['aydooxtcli'].clone().set_position(12, 15),
            sprites['aydooxtcli'].clone().set_position(15, 42),
            sprites['aydooxtcli'].clone().set_position(39, 42),
            sprites['aydooxtcli'].clone().set_position(42, 12),
            sprites['bghvgbtwcb'].clone().set_position(35, 41),
            Sprite(
                pixels=[
                [-1, 14, 14, -1],
                [14, 14, 14, 14],
                [14, -1, -1, 14],
            ],
                name='dvvacwfchj',
                x=41,
                y=2,
                blocking=BlockingMode.PIXEL_PERFECT,
                interaction=InteractionMode.TANGIBLE,
                tags=['button_B_R', 'sys_click'],
            ),
            Sprite(
                pixels=[
                [-1, 14, 14, -1],
                [14, 14, 14, 14],
                [14, -1, -1, 14],
            ],
                name='dvvacwfchj',
                x=11,
                y=2,
                blocking=BlockingMode.PIXEL_PERFECT,
                interaction=InteractionMode.TANGIBLE,
                tags=['button_B_R', 'sys_click'],
            ),
            Sprite(
                pixels=[
                [-1, 14, 14, -1],
                [14, 14, 14, 14],
                [14, -1, -1, 14],
            ],
                name='dvvacwfchj',
                x=41,
                y=32,
                blocking=BlockingMode.PIXEL_PERFECT,
                interaction=InteractionMode.TANGIBLE,
                tags=['button_B_R', 'sys_click'],
            ),
            Sprite(
                pixels=[
                [-1, 14, 14, -1],
                [14, 14, 14, 14],
                [14, -1, -1, 14],
            ],
                name='dvvacwfchj',
                x=11,
                y=32,
                blocking=BlockingMode.PIXEL_PERFECT,
                interaction=InteractionMode.TANGIBLE,
                tags=['button_B_R', 'sys_click'],
            ),
            sprites['ekpijbeoel'].clone().set_position(42, 48),
            sprites['ekpijbeoel'].clone().set_position(42, 36),
            sprites['ekpijbeoel'].clone().set_position(12, 39),
            sprites['ekpijbeoel'].clone().set_position(36, 42),
            sprites['ekpijbeoel'].clone().set_position(12, 18),
            sprites['ekpijbeoel'].clone().set_position(12, 6),
            sprites['ekpijbeoel'].clone().set_position(45, 42),
            sprites['fdgmtkfrxl'].clone().set_position(17, 41),
            sprites['hfikqtizdo'].clone().set_position(6, 42),
            sprites['kisflvfvsy'].clone().set_position(12, 42),
            sprites['kisflvfvsy'].clone().set_position(12, 9),
            sprites['kisflvfvsy'].clone().set_position(9, 12),
            sprites['kisflvfvsy'].clone().set_position(42, 15),
            sprites['kisflvfvsy'].clone().set_position(15, 12),
            sprites['kisflvfvsy'].clone().set_position(12, 12),
            sprites['kisflvfvsy'].clone().set_position(12, 48),
            sprites['odkpvwbihk'].clone().set_position(18, 12),
            Sprite(
                pixels=[
                [8, -1, -1, 8],
                [8, 8, 8, 8],
                [-1, 8, 8, -1],
            ],
                name='peuddygayw',
                x=41,
                y=21,
                blocking=BlockingMode.PIXEL_PERFECT,
                interaction=InteractionMode.TANGIBLE,
                tags=['button_B_L', 'sys_click'],
            ),
            Sprite(
                pixels=[
                [8, -1, -1, 8],
                [8, 8, 8, 8],
                [-1, 8, 8, -1],
            ],
                name='peuddygayw',
                x=11,
                y=51,
                blocking=BlockingMode.PIXEL_PERFECT,
                interaction=InteractionMode.TANGIBLE,
                tags=['button_B_L', 'sys_click'],
            ),
            Sprite(
                pixels=[
                [8, -1, -1, 8],
                [8, 8, 8, 8],
                [-1, 8, 8, -1],
            ],
                name='peuddygayw',
                x=11,
                y=21,
                blocking=BlockingMode.PIXEL_PERFECT,
                interaction=InteractionMode.TANGIBLE,
                tags=['button_B_L', 'sys_click'],
            ),
            Sprite(
                pixels=[
                [8, -1, -1, 8],
                [8, 8, 8, 8],
                [-1, 8, 8, -1],
            ],
                name='peuddygayw',
                x=41,
                y=51,
                blocking=BlockingMode.PIXEL_PERFECT,
                interaction=InteractionMode.TANGIBLE,
                tags=['button_B_L', 'sys_click'],
            ),
            sprites['slefrnjymo'].clone().set_position(12, 36),
            sprites['slefrnjymo'].clone().set_position(42, 6),
            sprites['slefrnjymo'].clone().set_position(42, 9),
            sprites['slefrnjymo'].clone().set_position(39, 12),
            sprites['slefrnjymo'].clone().set_position(6, 12),
            sprites['slefrnjymo'].clone().set_position(48, 42),
            sprites['slefrnjymo'].clone().set_position(12, 45),
            sprites['slefrnjymo'].clone().set_position(42, 45),
            sprites['tddzizwhzf'].clone().set_position(18, 42),
            sprites['tddzizwhzf'].clone().set_position(42, 42),
            sprites['tddzizwhzf'].clone().set_position(9, 42),
            sprites['tddzizwhzf'].clone().set_position(36, 12),
            sprites['tddzizwhzf'].clone().set_position(42, 18),
            sprites['tddzizwhzf'].clone().set_position(48, 12),
            sprites['zpxgvxwdex'].clone().set_position(32, 11),
            sprites['zpxgvxwdex'].clone().set_position(2, 41),
            sprites['zpxgvxwdex'].clone().set_position(32, 41),
            sprites['zpxgvxwdex'].clone().set_position(2, 11),
        ],
        grid_size=(57, 57),
        data={'StepCounter': 150, 'level_name': 'ihpokmcrjm'},
    ),
    # Level 5
    Level(
        sprites=[
            sprites['ahdesifykt'].clone().set_position(21, 17),
            sprites['aydooxtcli'].clone().set_position(12, 9),
            sprites['aydooxtcli'].clone().set_position(9, 3),
            sprites['aydooxtcli'].clone().set_position(18, 15),
            sprites['aydooxtcli'].clone().set_position(12, 15),
            sprites['bghvgbtwcb'].clone().set_position(17, 5),
            sprites['bghvgbtwcb'].clone().set_position(14, 26),
            sprites['dvvacwfchj'].clone().set_position(1, 2),
            sprites['ekpijbeoel'].clone().set_position(15, 21),
            sprites['ekpijbeoel'].clone().set_position(12, 21),
            sprites['ekpijbeoel'].clone().set_position(18, 9),
            sprites['ekpijbeoel'].clone().set_position(12, 12),
            sprites['ekpijbeoel'].clone().set_position(18, 6),
            sprites['ekpijbeoel'].clone().set_position(12, 3),
            sprites['ekpijbeoel'].clone().set_position(15, 27),
            sprites['kisflvfvsy'].clone().set_position(12, 27),
            sprites['kisflvfvsy'].clone().set_position(15, 9),
            sprites['kisflvfvsy'].clone().set_position(15, 15),
            sprites['odkpvwbihk'].clone().set_position(18, 21),
            sprites['odkpvwbihk'].clone().set_position(18, 18),
            sprites['peuddygayw'].clone().set_position(22, 2),
            sprites['slefrnjymo'].clone().set_position(12, 24),
            sprites['slefrnjymo'].clone().set_position(6, 3),
            sprites['tddzizwhzf'].clone().set_position(18, 3),
            sprites['tddzizwhzf'].clone().set_position(15, 3),
            sprites['tddzizwhzf'].clone().set_position(18, 27),
            sprites['zpxgvxwdex'].clone().set_position(8, 17),
        ],
        grid_size=(27, 32),
        data={'StepCounter': 80, 'level_name': 'qibynbipmw'},
    ),
    # Level 6
    Level(
        sprites=[
            sprites['aoibinevrm'].clone().set_position(2, 14),
            Sprite(
                pixels=[
                [-1, 14, 14, -1],
                [14, 14, 14, 14],
                [14, -1, -1, 14],
            ],
                name='aqwhbtzcfg',
                x=5,
                y=54,
                blocking=BlockingMode.PIXEL_PERFECT,
                interaction=InteractionMode.TANGIBLE,
                tags=['button_27_R', 'sys_click'],
            ),
            sprites['auxglvwwep'].clone().set_position(17, 44),
            sprites['avazowxmej'].clone().set_position(17, 44),
            sprites['aydooxtcli'].clone().set_position(30, 48),
            sprites['aydooxtcli'].clone().set_position(24, 6),
            sprites['aydooxtcli'].clone().set_position(36, 15),
            sprites['aydooxtcli'].clone().set_position(18, 18),
            sprites['aydooxtcli'].clone().set_position(21, 9),
            sprites['aydooxtcli'].clone().set_position(24, 15),
            sprites['aydooxtcli'].clone().set_position(51, 9),
            sprites['aydooxtcli'].clone().set_position(27, 45),
            sprites['aydooxtcli'].clone().set_position(42, 15),
            sprites['aydooxtcli'].clone().set_position(33, 45),
            sprites['aydooxtcli'].clone().set_position(6, 6),
            sprites['azkpmswird'].clone().set_position(32, 14),
            sprites['bbxrzomunc'].clone().set_position(2, 14),
            sprites['bghvgbtwcb'].clone().set_position(44, 8),
            sprites['bghvgbtwcb'].clone().set_position(20, 14),
            sprites['bghvgbtwcb'].clone().set_position(29, 41),
            sprites['cfhhkdewbs'].clone().set_position(32, 14),
            sprites['cgkbezvpdp'].clone().set_position(2, 14),
            sprites['cjcssvobei'].clone().set_position(29, 57),
            sprites['cyqncaekpb'].clone().set_position(32, 14),
            sprites['djepopdkpm'].clone().set_position(32, 14),
            sprites['dvvacwfchj'].clone().set_position(44, 27),
            sprites['ekpijbeoel'].clone().set_position(27, 48),
            sprites['ekpijbeoel'].clone().set_position(15, 21),
            sprites['ekpijbeoel'].clone().set_position(39, 54),
            sprites['ekpijbeoel'].clone().set_position(15, 9),
            sprites['ekpijbeoel'].clone().set_position(6, 24),
            sprites['ekpijbeoel'].clone().set_position(15, 24),
            sprites['ekpijbeoel'].clone().set_position(27, 42),
            sprites['ekpijbeoel'].clone().set_position(30, 39),
            sprites['ekpijbeoel'].clone().set_position(30, 33),
            sprites['ekpijbeoel'].clone().set_position(48, 15),
            sprites['ekpijbeoel'].clone().set_position(36, 45),
            sprites['ekpijbeoel'].clone().set_position(21, 54),
            sprites['ekpijbeoel'].clone().set_position(36, 39),
            sprites['gknuimaglj'].clone().set_position(17, 44),
            sprites['hiictjojxg'].clone().set_position(32, 14),
            sprites['hvgvgpuasf'].clone().set_position(14, 27),
            sprites['icgyrqkqpc'].clone().set_position(2, 14),
            sprites['ikgydmjteo'].clone().set_position(2, 14),
            sprites['isjrkszgff'].clone().set_position(17, 44),
            sprites['jxibbjkyqn'].clone().set_position(2, 14),
            sprites['kcuuamovad'].clone().set_position(17, 44),
            sprites['kisflvfvsy'].clone().set_position(39, 15),
            sprites['kisflvfvsy'].clone().set_position(12, 15),
            sprites['kisflvfvsy'].clone().set_position(45, 24),
            sprites['kisflvfvsy'].clone().set_position(45, 18),
            sprites['kisflvfvsy'].clone().set_position(30, 51),
            sprites['kisflvfvsy'].clone().set_position(54, 6),
            sprites['kisflvfvsy'].clone().set_position(39, 36),
            sprites['kisflvfvsy'].clone().set_position(42, 12),
            sprites['kisflvfvsy'].clone().set_position(27, 27),
            sprites['kisflvfvsy'].clone().set_position(39, 21),
            sprites['kisflvfvsy'].clone().set_position(48, 12),
            sprites['kisflvfvsy'].clone().set_position(21, 36),
            sprites['kisflvfvsy'].clone().set_position(36, 51),
            sprites['kisflvfvsy'].clone().set_position(21, 21),
            sprites['kisflvfvsy'].clone().set_position(18, 12),
            sprites['kisflvfvsy'].clone().set_position(21, 15),
            sprites['kisflvfvsy'].clone().set_position(51, 15),
            sprites['kisflvfvsy'].clone().set_position(30, 42),
            sprites['kisflvfvsy'].clone().set_position(51, 21),
            sprites['lfcynjbowf'].clone().set_position(32, 14),
            sprites['lnnponqnto'].clone().set_position(32, 14),
            sprites['lqtjzsqwtz'].clone().set_position(17, 44),
            sprites['odkpvwbihk'].clone().set_position(33, 27),
            sprites['odkpvwbihk'].clone().set_position(24, 24),
            sprites['odkpvwbihk'].clone().set_position(24, 45),
            sprites['qfmlfsmppb'].clone().set_position(2, 14),
            sprites['reafrgzfwk'].clone().set_position(44, 27),
            sprites['rhyksubvjk'].clone().set_position(17, 44),
            sprites['sbogwsxcvo'].clone().set_position(14, 27),
            sprites['slefrnjymo'].clone().set_position(9, 15),
            sprites['slefrnjymo'].clone().set_position(45, 12),
            sprites['slefrnjymo'].clone().set_position(24, 51),
            sprites['slefrnjymo'].clone().set_position(21, 45),
            sprites['slefrnjymo'].clone().set_position(9, 9),
            sprites['slefrnjymo'].clone().set_position(12, 18),
            sprites['slefrnjymo'].clone().set_position(36, 6),
            sprites['slefrnjymo'].clone().set_position(48, 18),
            sprites['slefrnjymo'].clone().set_position(45, 21),
            sprites['slefrnjymo'].clone().set_position(54, 24),
            sprites['slefrnjymo'].clone().set_position(45, 6),
            sprites['slefrnjymo'].clone().set_position(12, 12),
            sprites['slefrnjymo'].clone().set_position(39, 45),
            sprites['slefrnjymo'].clone().set_position(24, 39),
            sprites['slefrnjymo'].clone().set_position(33, 42),
            sprites['tcweaqkrko'].clone().set_position(2, 14),
            sprites['tddzizwhzf'].clone().set_position(15, 6),
            sprites['tddzizwhzf'].clone().set_position(36, 24),
            sprites['tddzizwhzf'].clone().set_position(15, 12),
            sprites['tddzizwhzf'].clone().set_position(33, 48),
            sprites['tddzizwhzf'].clone().set_position(30, 54),
            sprites['tddzizwhzf'].clone().set_position(15, 18),
            sprites['tddzizwhzf'].clone().set_position(42, 18),
            sprites['tddzizwhzf'].clone().set_position(45, 9),
            sprites['tddzizwhzf'].clone().set_position(39, 9),
            sprites['tddzizwhzf'].clone().set_position(6, 15),
            sprites['tddzizwhzf'].clone().set_position(18, 15),
            sprites['tddzizwhzf'].clone().set_position(9, 21),
            sprites['tddzizwhzf'].clone().set_position(54, 15),
            sprites['tddzizwhzf'].clone().set_position(30, 36),
            sprites['uqipjzobpp'].clone().set_position(14, 27),
            sprites['vdjpajqpny'].clone().set_position(17, 44),
            sprites['xtxayxwyfn'].clone().set_position(29, 57),
            sprites['ypbsjakojf'].clone().set_position(32, 14),
            sprites['zdlwfpeyyd'].clone().set_position(29, 57),
            sprites['zpxgvxwdex'].clone().set_position(44, 27),
            Sprite(
                pixels=[
                [-1, 14, 14, -1],
                [14, 14, 14, 14],
                [14, -1, -1, 14],
            ],
                name='zrzovwqbcx',
                x=5,
                y=54,
                blocking=BlockingMode.PIXEL_PERFECT,
                interaction=InteractionMode.TANGIBLE,
                tags=['button_25_R', 'sys_click'],
            ),
            Sprite(
                pixels=[
                [-1, 14, 14, -1],
                [14, 14, 14, 14],
                [14, -1, -1, 14],
            ],
                name='zseotqksli',
                x=5,
                y=54,
                blocking=BlockingMode.PIXEL_PERFECT,
                interaction=InteractionMode.TANGIBLE,
                tags=['button_26_R', 'sys_click'],
            ),
        ],
        grid_size=(60, 64),
        data={'StepCounter': 80, 'level_name': 'ksgcbuhgwz'},
    ),
    # Level 7
    Level(
        sprites=[
            sprites['ahdesifykt'].clone().set_position(24, 27),
            sprites['aydooxtcli'].clone().set_position(24, 24),
            sprites['aydooxtcli'].clone().set_position(33, 12),
            sprites['bghvgbtwcb'].clone().set_position(17, 8),
            sprites['bghvgbtwcb'].clone().set_position(20, 23),
            Sprite(
                pixels=[
                [-1, 14, 14, -1],
                [14, 14, 14, 14],
                [14, -1, -1, 14],
            ],
                name='dvvacwfchj',
                x=32,
                y=5,
                blocking=BlockingMode.PIXEL_PERFECT,
                interaction=InteractionMode.TANGIBLE,
                tags=['button_B_R', 'sys_click'],
            ),
            sprites['ekpijbeoel'].clone().set_position(21, 9),
            sprites['ekpijbeoel'].clone().set_position(15, 9),
            sprites['ekpijbeoel'].clone().set_position(24, 9),
            sprites['hvgvgpuasf'].clone().set_position(20, 27),
            sprites['kisflvfvsy'].clone().set_position(18, 9),
            sprites['odkpvwbihk'].clone().set_position(24, 21),
            sprites['odkpvwbihk'].clone().set_position(33, 9),
            sprites['oqsumsdlyg'].clone().set_position(24, 27),
            Sprite(
                pixels=[
                [8, -1, -1, 8],
                [8, 8, 8, 8],
                [-1, 8, 8, -1],
            ],
                name='peuddygayw',
                x=32,
                y=18,
                blocking=BlockingMode.PIXEL_PERFECT,
                interaction=InteractionMode.TANGIBLE,
                tags=['button_B_L', 'sys_click'],
            ),
            sprites['slefrnjymo'].clone().set_position(12, 9),
            sprites['slefrnjymo'].clone().set_position(30, 9),
            sprites['tddzizwhzf'].clone().set_position(21, 24),
            sprites['tddzizwhzf'].clone().set_position(27, 9),
            sprites['tddzizwhzf'].clone().set_position(21, 21),
            sprites['tddzizwhzf'].clone().set_position(33, 15),
            sprites['zpxgvxwdex'].clone().set_position(20, 27),
        ],
        grid_size=(48, 36),
        data={'StepCounter': 80, 'level_name': 'yzzznxxvju'},
    ),
    # Level 8
    Level(
        sprites=[
            sprites['ahdesifykt'].clone().set_position(8, 23),
            sprites['aydooxtcli'].clone().set_position(42, 15),
            sprites['aydooxtcli'].clone().set_position(33, 6),
            sprites['aydooxtcli'].clone().set_position(33, 9),
            sprites['aydooxtcli'].clone().set_position(45, 21),
            sprites['aydooxtcli'].clone().set_position(21, 12),
            sprites['aydooxtcli'].clone().set_position(15, 15),
            sprites['aydooxtcli'].clone().set_position(21, 30),
            sprites['aydooxtcli'].clone().set_position(15, 21),
            sprites['aydooxtcli'].clone().set_position(21, 27),
            sprites['aydooxtcli'].clone().set_position(30, 18),
            sprites['aydooxtcli'].clone().set_position(33, 36),
            sprites['aydooxtcli'].clone().set_position(15, 36),
            sprites['aydooxtcli'].clone().set_position(27, 36),
            sprites['aydooxtcli'].clone().set_position(15, 45),
            sprites['aydooxtcli'].clone().set_position(21, 51),
            sprites['aydooxtcli'].clone().set_position(33, 39),
            sprites['aydooxtcli'].clone().set_position(15, 51),
            sprites['bghvgbtwcb'].clone().set_position(47, 8),
            sprites['bghvgbtwcb'].clone().set_position(44, 20),
            sprites['bghvgbtwcb'].clone().set_position(35, 20),
            sprites['dvvacwfchj'].clone().set_position(4, 28),
            sprites['ekpijbeoel'].clone().set_position(27, 30),
            sprites['ekpijbeoel'].clone().set_position(27, 12),
            sprites['ekpijbeoel'].clone().set_position(33, 24),
            sprites['ekpijbeoel'].clone().set_position(15, 18),
            sprites['ekpijbeoel'].clone().set_position(30, 27),
            sprites['ekpijbeoel'].clone().set_position(48, 9),
            sprites['hvgvgpuasf'].clone().set_position(21, 56),
            sprites['kisflvfvsy'].clone().set_position(21, 15),
            sprites['kisflvfvsy'].clone().set_position(21, 18),
            sprites['kisflvfvsy'].clone().set_position(21, 45),
            sprites['kisflvfvsy'].clone().set_position(21, 33),
            sprites['kisflvfvsy'].clone().set_position(15, 27),
            sprites['kisflvfvsy'].clone().set_position(24, 24),
            sprites['kisflvfvsy'].clone().set_position(15, 33),
            sprites['kisflvfvsy'].clone().set_position(27, 33),
            sprites['kisflvfvsy'].clone().set_position(33, 42),
            sprites['kisflvfvsy'].clone().set_position(54, 12),
            sprites['kisflvfvsy'].clone().set_position(27, 39),
            sprites['kisflvfvsy'].clone().set_position(33, 15),
            sprites['kisflvfvsy'].clone().set_position(15, 42),
            sprites['kisflvfvsy'].clone().set_position(51, 6),
            sprites['kisflvfvsy'].clone().set_position(51, 15),
            sprites['kisflvfvsy'].clone().set_position(21, 9),
            sprites['lfimxyubtw'].clone().set_position(26, 56),
            sprites['odkpvwbihk'].clone().set_position(27, 45),
            sprites['odkpvwbihk'].clone().set_position(27, 51),
            sprites['odkpvwbihk'].clone().set_position(48, 18),
            sprites['oqsumsdlyg'].clone().set_position(26, 56),
            sprites['peuddygayw'].clone().set_position(8, 28),
            sprites['reafrgzfwk'].clone().set_position(4, 33),
            sprites['sbogwsxcvo'].clone().set_position(21, 56),
            sprites['sjummcsymu'].clone().set_position(26, 56),
            sprites['slefrnjymo'].clone().set_position(27, 48),
            sprites['slefrnjymo'].clone().set_position(39, 9),
            sprites['slefrnjymo'].clone().set_position(33, 48),
            sprites['slefrnjymo'].clone().set_position(45, 12),
            sprites['slefrnjymo'].clone().set_position(21, 21),
            sprites['slefrnjymo'].clone().set_position(21, 42),
            sprites['slefrnjymo'].clone().set_position(15, 24),
            sprites['slefrnjymo'].clone().set_position(42, 24),
            sprites['slefrnjymo'].clone().set_position(33, 33),
            sprites['slefrnjymo'].clone().set_position(21, 36),
            sprites['slefrnjymo'].clone().set_position(36, 12),
            sprites['slefrnjymo'].clone().set_position(18, 48),
            sprites['slefrnjymo'].clone().set_position(21, 48),
            sprites['tddzizwhzf'].clone().set_position(33, 45),
            sprites['tddzizwhzf'].clone().set_position(15, 12),
            sprites['tddzizwhzf'].clone().set_position(27, 15),
            sprites['tddzizwhzf'].clone().set_position(33, 51),
            sprites['tddzizwhzf'].clone().set_position(36, 21),
            sprites['tddzizwhzf'].clone().set_position(15, 30),
            sprites['tddzizwhzf'].clone().set_position(27, 42),
            sprites['tddzizwhzf'].clone().set_position(39, 18),
            sprites['tddzizwhzf'].clone().set_position(39, 27),
            sprites['tddzizwhzf'].clone().set_position(15, 39),
            sprites['tddzizwhzf'].clone().set_position(36, 30),
            sprites['tddzizwhzf'].clone().set_position(21, 39),
            sprites['tddzizwhzf'].clone().set_position(15, 48),
            sprites['tddzizwhzf'].clone().set_position(27, 21),
            sprites['uqipjzobpp'].clone().set_position(21, 56),
            sprites['ymwkwkfxct'].clone().set_position(8, 33),
            sprites['zpxgvxwdex'].clone().set_position(4, 23),
        ],
        grid_size=(63, 63),
        data={'StepCounter': 80, 'level_name': 'hmzsasouat'},
    ),
]
izutyjcpih = {
    'kdrsqrvpwb': {
        'A': [
            [-1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, 7, 6, 5, 4, 3, 2, 1],
            [-1, -1, 8, -1, -1, -1, -1, -1, 20],
            [-1, -1, 9, -1, -1, -1, -1, -1, 19],
            [-1, -1, 10, -1, -1, -1, -1, -1, 18],
            [-1, -1, 11, 12, 13, 14, 15, 16, 17],
        ],
    },
    'cecdsipmha': {
        'A': [
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, 5, 4, 3, 2, 1],
            [-1, -1, -1, -1, -1, 6, -1, -1, -1, 26],
            [-1, -1, -1, -1, -1, 7, -1, -1, -1, 25],
            [-1, -1, -1, -1, -1, 8, -1, -1, -1, 24],
            [-1, -1, -1, -1, -1, 9, -1, -1, -1, 23],
            [-1, -1, -1, -1, -1, 10, -1, -1, -1, 22],
            [-1, -1, -1, -1, -1, 11, -1, -1, -1, 21],
            [-1, -1, -1, -1, -1, 12, -1, -1, -1, 20],
            [-1, -1, -1, -1, -1, 13, -1, -1, -1, 19],
            [-1, -1, -1, -1, -1, 14, 15, 16, 17, 18],
        ],
        'B': [
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1],
        ],
        'C': [
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1],
        ],
    },
    'qibynbipmw': {
        'A': [
            [-1, -1, -1, -1, -1, -1, -1],
            [-1, -1, 21, 20, 19, 18, 17],
            [-1, -1, -1, -1, -1, -1, 16],
            [-1, -1, -1, -1, 13, 14, 15],
            [-1, -1, -1, -1, 12, -1, -1],
            [-1, -1, -1, -1, 11, 10, 9],
            [-1, -1, -1, -1, -1, -1, 8],
            [-1, -1, -1, -1, 5, 6, 7],
            [-1, -1, -1, -1, 4, -1, -1],
            [-1, -1, -1, -1, 3, 2, 1],
        ],
        'B': [
            [-1, -1, -1, -1, -1, -1, -1],
            [-1, -1, 5, 4, 3, 2, 1],
        ],
    },
    'asymmetry': {
        'A': [
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, 8, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, 7, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, 6, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, 5, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, 4, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, 3, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, 2, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, 1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
        ],
        'B': [
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, 1, 2, 3, 4, 5, 6, -1, -1],
            [-1, -1, 16, -1, -1, -1, -1, 7, -1, -1],
            [-1, -1, 15, -1, -1, -1, -1, 8, -1, -1],
            [-1, -1, 14, 13, 12, 11, 10, 9, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
        ],
    },
    'vvnbesozdj': {
        'A': [
            [-1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, 3, 2, 1, -1, -1],
            [-1, -1, 4, -1, -1, -1, 16, -1],
            [-1, 5, -1, -1, -1, -1, -1, 15],
            [-1, 6, -1, -1, -1, -1, -1, 14],
            [-1, 7, -1, -1, -1, -1, -1, 13],
            [-1, -1, 8, -1, -1, -1, 12, -1],
            [-1, -1, -1, 9, 10, 11, -1, -1],
        ],
        'B': [
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, 3, 2, 1, -1, -1],
            [-1, -1, -1, -1, -1, -1, 4, -1, -1, -1, 16, -1],
            [-1, -1, -1, -1, -1, 5, -1, -1, -1, -1, -1, 15],
            [-1, -1, -1, -1, -1, 6, -1, -1, -1, -1, -1, 14],
            [-1, -1, -1, -1, -1, 7, -1, -1, -1, -1, -1, 13],
            [-1, -1, -1, -1, -1, -1, 8, -1, -1, -1, 12, -1],
            [-1, -1, -1, -1, -1, -1, -1, 9, 10, 11, -1, -1],
        ],
    },
    'ihpokmcrjm': {
        'A': [
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, 10, 9, 8, 7, 6, -1, -1, -1, -1, -1, 5, 4, 3, 2, 1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, 20, 19, 18, 17, 16, -1, -1, -1, -1, -1, 15, 14, 13, 12, 11],
        ],
        'B': [
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, 10, -1, -1, -1, -1, -1, -1, -1, -1, -1, 20],
            [-1, -1, -1, -1, 9, -1, -1, -1, -1, -1, -1, -1, -1, -1, 19],
            [-1, -1, -1, -1, 8, -1, -1, -1, -1, -1, -1, -1, -1, -1, 18],
            [-1, -1, -1, -1, 7, -1, -1, -1, -1, -1, -1, -1, -1, -1, 17],
            [-1, -1, -1, -1, 6, -1, -1, -1, -1, -1, -1, -1, -1, -1, 16],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, 5, -1, -1, -1, -1, -1, -1, -1, -1, -1, 15],
            [-1, -1, -1, -1, 4, -1, -1, -1, -1, -1, -1, -1, -1, -1, 14],
            [-1, -1, -1, -1, 3, -1, -1, -1, -1, -1, -1, -1, -1, -1, 13],
            [-1, -1, -1, -1, 2, -1, -1, -1, -1, -1, -1, -1, -1, -1, 12],
            [-1, -1, -1, -1, 1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 11],
        ],
    },
    'concentric': {
        'A': [
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, 1, 2, 3, 4, 5, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, 28, -1, -1, -1, -1, -1, 6, -1, -1, -1, -1, -1],
            [-1, -1, -1, 27, -1, -1, -1, -1, -1, -1, -1, 7, -1, -1, -1, -1],
            [-1, -1, 26, -1, -1, -1, -1, -1, -1, -1, -1, -1, 8, -1, -1, -1],
            [-1, -1, 25, -1, -1, -1, -1, -1, -1, -1, -1, -1, 9, -1, -1, -1],
            [-1, -1, 24, -1, -1, -1, -1, -1, -1, -1, -1, -1, 10, -1, -1, -1],
            [-1, -1, 23, -1, -1, -1, -1, -1, -1, -1, -1, -1, 11, -1, -1, -1],
            [-1, -1, 22, -1, -1, -1, -1, -1, -1, -1, -1, -1, 12, -1, -1, -1],
            [-1, -1, -1, 21, -1, -1, -1, -1, -1, -1, -1, 13, -1, -1, -1, -1],
            [-1, -1, -1, -1, 20, -1, -1, -1, -1, -1, 14, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, 19, 18, 17, 16, 15, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
        ],
        'B': [
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, 1, 2, 3, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, 16, -1, -1, -1, 4, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, 15, -1, -1, -1, -1, -1, 5, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, 14, -1, -1, -1, -1, -1, 6, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, 13, -1, -1, -1, -1, -1, 7, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, 12, -1, -1, -1, 8, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, 11, 10, 9, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
        ],
        'C': [
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
        ],
    },
    'metronome': {
        'A': [
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, 1, 2, 3, 4, 5, 6, 7, 8, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
        ],
        'B': [
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, 3, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, 2, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, 1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
        ],
        'C': [
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, 1, 2, 3, 4, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
        ],
        'D': [
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, 1, 2, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, 4, 3, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
        ],
    },
    'yzzznxxvju': {
        'A': [
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, 8, 7, 6, 5, 4, 3, 2, 1],
        ],
        'B': [
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 3],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 2],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 1],
        ],
        'C': [
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, 4, 3, 2, 1],
        ],
        'D': [
            [-1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, 2, 1],
            [-1, -1, -1, -1, -1, -1, -1, 3, 4],
        ],
    },
    'hmzsasouat': {
        'A': [
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 2, -1],
        ],
        'B': [
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 2, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 3, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 4, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 5, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 6, -1, -1, -1, -1, -1],
        ],
        'C': [
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 2, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 3, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 4, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 5, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 6, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 7, -1, -1, -1, -1, -1, -1],
        ],
        'D': [
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 2, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 3, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 4, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 5, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 6, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 7, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 8, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 9, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 10, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 11, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 12, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 13, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 14, -1, -1, -1, -1, -1, -1, -1],
        ],
        'E': [
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 2, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 3, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 4, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 5, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 6, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 7, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 8, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, 9, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, 10, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, 11, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, 12, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, 13, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, 14, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, 15, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, 16, -1, -1, -1, -1, -1, -1, -1, -1],
        ],
        'F': [
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 2, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 3, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 4, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, 5, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, 6, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, 7, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, 8, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, 9, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, 10, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, 11, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, 12, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, 13, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, 14, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, 15, -1, -1, -1, -1, -1, -1],
        ],
    },
    'ksgcbuhgwz': {
        'A': [
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 7, 8, 1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 6, -1, 2],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 5, 4, 3],
        ],
        'B': [
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 7, -1, 8, -1, 1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 6, -1, -1, -1, 2],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 5, -1, 4, -1, 3],
        ],
        'C': [
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 7, -1, -1, 8, -1, -1, 1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 6, -1, -1, -1, -1, -1, 2],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 5, -1, -1, 4, -1, -1, 3],
        ],
        'D': [
            [-1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, 7, 8, 1],
            [-1, -1, -1, -1, 6, -1, 2],
            [-1, -1, -1, -1, 5, 4, 3],
        ],
        'E': [
            [-1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, 7, -1, 8, -1, 1],
            [-1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, 6, -1, -1, -1, 2],
            [-1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, 5, -1, 4, -1, 3],
        ],
        'F': [
            [-1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, 7, -1, -1, 8, -1, -1, 1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, 6, -1, -1, -1, -1, -1, 2],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, 5, -1, -1, 4, -1, -1, 3],
        ],
        'G': [
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, 7, 8, 1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, 6, -1, 2],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, 5, 4, 3],
        ],
        'H': [
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, 7, -1, 8, -1, 1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, 6, -1, -1, -1, 2],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, 5, -1, 4, -1, 3],
        ],
        'I': [
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, 7, -1, -1, 8, -1, -1, 1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, 6, -1, -1, -1, -1, -1, 2],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, 5, -1, -1, 4, -1, -1, 3],
        ],
        '1': [
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 3, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 2, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 1],
        ],
        '2': [
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 3, 2, 1],
        ],
        '3': [
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 2, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 3, -1, -1],
        ],
        '4': [
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 2],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 3],
        ],
        '5': [
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 2, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 3],
        ],
        '6': [
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 1, 2, 3],
        ],
        '7': [
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 3],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 2, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 1, -1, -1],
        ],
        '8': [
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 3],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 2],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 1],
        ],
        '9': [
            [-1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1],
            [-1, -1, 3, -1, -1],
            [-1, -1, -1, 2, -1],
            [-1, -1, -1, -1, 1],
        ],
        '10': [
            [-1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1],
            [-1, -1, 3, 2, 1],
        ],
        '11': [
            [-1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1],
            [-1, -1, -1, -1, 1],
            [-1, -1, -1, 2, -1],
            [-1, -1, 3, -1, -1],
        ],
        '12': [
            [-1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, 1],
            [-1, -1, -1, -1, -1, 2],
            [-1, -1, -1, -1, -1, 3],
        ],
        '13': [
            [-1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, 1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, 2, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, 3],
        ],
        '14': [
            [-1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, 1, 2, 3],
        ],
        '15': [
            [-1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, 3],
            [-1, -1, -1, -1, -1, -1, -1, 2, -1],
            [-1, -1, -1, -1, -1, -1, 1, -1, -1],
        ],
        '16': [
            [-1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, 3],
            [-1, -1, -1, -1, -1, 2],
            [-1, -1, -1, -1, -1, 1],
        ],
        '17': [
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, 3, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, 2, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, 1],
        ],
        '18': [
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, 3, 2, 1],
        ],
        '19': [
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, 1],
            [-1, -1, -1, -1, -1, -1, -1, -1, 2, -1],
            [-1, -1, -1, -1, -1, -1, -1, 3, -1, -1],
        ],
        '20': [
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 2],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 3],
        ],
        '21': [
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 2, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 3],
        ],
        '22': [
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 1, 2, 3],
        ],
        '23': [
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 3],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 2, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 1, -1, -1],
        ],
        '24': [
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 3],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 2],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 1],
        ],
        '25': [
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 2, -1],
        ],
        '26': [
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, 1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, 2],
        ],
        '27': [
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 2],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 1],
        ],
    },
}
BACKGROUND_COLOR = 4
PADDING_COLOR = 3
urckwqnpen = -1
pfoodymmkh = 0
uokijcngum = 1
njzkvaczgr = 2
cnucahvrqo = 3
agaegydzug = 4
sayxoyjqpt = 5
mgjravlcbp = 6
qgzzunqqsz = 7
civwkpzhyp = 8
anazyoqymy = 9
vdsneyyubb = 10
hgqsismneu = 11
klwzynitxb = 12
icheixzpyv = 13
cqizedfwrl = 14
jxejtkmohi = 15
crxpafuiwp = 3


class rnbcvtkqiw(NamedTuple):
    """."""

    y: int
    x: int


class thembpsuoz(TypedDict):
    """."""

    qcmzcjocmj: Dict[int, rnbcvtkqiw]
    oxbwsencfv: int


def qfvvosdkqr(
    wcbywgdovp: Dict[str, Dict[str, List[List[int]]]],
) -> Dict[str, Dict[str, thembpsuoz]]:
    """."""
    zzdjlqxdnf: Dict[str, Dict[str, thembpsuoz]] = {}
    for uwtopyjnbz, vpuoorisew in wcbywgdovp.items():
        ccqkbwunoh: Dict[str, thembpsuoz] = {}
        for ihcexiqgys, axevtouupo in vpuoorisew.items():
            qcmzcjocmj: Dict[int, rnbcvtkqiw] = {}
            oxbwsencfv = 0
            for y, pxycedmqtn in enumerate(axevtouupo):
                for x, rchyrnavey in enumerate(pxycedmqtn):
                    if rchyrnavey != -1:
                        if rchyrnavey in qcmzcjocmj:
                            raise ValueError(f"Duplicate number {rchyrnavey} in map '{ihcexiqgys}' of level '{uwtopyjnbz}'")
                        qcmzcjocmj[rchyrnavey] = rnbcvtkqiw(y, x)
                        if rchyrnavey > oxbwsencfv:
                            oxbwsencfv = rchyrnavey
            ccqkbwunoh[ihcexiqgys] = {"qcmzcjocmj": qcmzcjocmj, "oxbwsencfv": oxbwsencfv}
        zzdjlqxdnf[uwtopyjnbz] = ccqkbwunoh
    return zzdjlqxdnf


def chmfaflqhy(
    uwtopyjnbz: str,
    ihcexiqgys: str,
    kiofvrbmju: bool,
    uopmnplcnv: Dict[str, Dict[str, thembpsuoz]],
) -> List[Tuple[rnbcvtkqiw, rnbcvtkqiw]]:
    """."""
    gdmraryfrp: thembpsuoz = uopmnplcnv[uwtopyjnbz][ihcexiqgys]
    qcmzcjocmj: Dict[int, rnbcvtkqiw] = gdmraryfrp["qcmzcjocmj"]
    oxbwsencfv: int = gdmraryfrp["oxbwsencfv"]
    if oxbwsencfv <= 1:
        return []
    nvjnzzyham: List[Tuple[rnbcvtkqiw, rnbcvtkqiw]] = []
    for acnxhwymfw, pmpudfwvhx in qcmzcjocmj.items():
        ibwabdeure: int
        if kiofvrbmju:
            ibwabdeure = 1 if acnxhwymfw == oxbwsencfv else acnxhwymfw + 1
        else:
            ibwabdeure = oxbwsencfv if acnxhwymfw == 1 else acnxhwymfw - 1
        kvtywzwzuc: rnbcvtkqiw = qcmzcjocmj[ibwabdeure]
        nvjnzzyham.append((pmpudfwvhx, kvtywzwzuc))
    return nvjnzzyham


class fonypcnqmf(RenderableUserDisplay):
    """."""

    rrhqvpezjr: List[Tuple[int, int]]

    def __init__(self, bnlfrvxkob: int, zigwldrikf: int = 1, level_index: int = 0):
        self.bnlfrvxkob = bnlfrvxkob
        self.current_steps = bnlfrvxkob
        self.zigwldrikf = max(1, zigwldrikf)
        self.level_index = level_index
        self.rrhqvpezjr = self.xuyldyuchy()

    def octblyaxjq(self, tozynaoupn: int) -> None:
        self.current_steps = max(0, min(tozynaoupn, self.bnlfrvxkob))

    def xsfawdkqoi(self) -> bool:
        if self.current_steps > 0:
            self.current_steps -= 1
        return self.current_steps > 0

    def xkzycpirhl(self) -> None:
        self.current_steps = self.bnlfrvxkob

    def yjpcfoxhmx(self, zigwldrikf: int, level_index: int) -> None:
        self.zigwldrikf = max(1, zigwldrikf)
        self.level_index = min(level_index - 1, zigwldrikf - 1)

    @staticmethod
    def xuyldyuchy() -> List[Tuple[int, int]]:
        """."""
        cbymhlqajy: List[Tuple[int, int]] = []
        for y in range(0, 64):
            cbymhlqajy.append((63, y))
        return cbymhlqajy

    def render_interface(self, frame: np.ndarray) -> np.ndarray:
        if self.bnlfrvxkob == 0:
            return frame
        vhemackyeq = (self.bnlfrvxkob - self.current_steps) / self.bnlfrvxkob
        mvinexidwb = round(len(self.rrhqvpezjr) * vhemackyeq)
        for bgneslizza, (x, y) in enumerate(self.rrhqvpezjr):
            frame[y, x] = sayxoyjqpt if bgneslizza < mvinexidwb else cqizedfwrl
        for i in range(self.zigwldrikf):
            start_x = 10 + i * 5
            start_y = 62
            for sbgijpvxnc in range(4):
                frame[start_y, start_x + sbgijpvxnc] = cqizedfwrl if i <= self.level_index else sayxoyjqpt
        return frame


class _Ly85Rules(ARCBaseGame):
    def __init__(self) -> None:
        kccdfjnrxn = levels[0].get_data("StepCounter") if levels else 0
        bnlfrvxkob = kccdfjnrxn if kccdfjnrxn else 0
        self.toxpunyqe = fonypcnqmf(bnlfrvxkob, zigwldrikf=len(levels), level_index=0)
        self.uopmnplcnv = qfvvosdkqr(izutyjcpih)
        qroguobpp = Camera(
            width=16,
            height=16,
            background=BACKGROUND_COLOR,
            letter_box=PADDING_COLOR,
            interfaces=[self.toxpunyqe],
        )
        super().__init__(game_id="lp85", levels=levels, camera=qroguobpp, available_actions=[6])
        self.izmredwten()

    def izmredwten(self) -> None:
        """."""
        nolvdnrgxa = self.current_level.get_data("StepCounter")
        if nolvdnrgxa:
            self.toxpunyqe.bnlfrvxkob = nolvdnrgxa
            self.toxpunyqe.xkzycpirhl()

    def on_set_level(self, level: Level) -> None:
        """."""
        self.izmredwten()
        isjnflak = self.current_level.grid_size
        if isjnflak is not None:
            self.kshrbnrfkopq = isjnflak[0]
            self.papamfmeoa = isjnflak[1]
        self.toxpunyqe.yjpcfoxhmx(zigwldrikf=len(levels), level_index=self.level_index)
        self.ucybisahh = self.current_level.get_data("level_name")
        self.afhycvvjg = self.current_level.get_sprites_by_tag("sys_click")
        qsdpkqvbun: set[tuple[int, int]] = set()
        for s in self.afhycvvjg:
            if (s.x, s.y) in qsdpkqvbun:
                s.tags.remove("sys_click")
            else:
                qsdpkqvbun.add((s.x, s.y))

    def ttawusezqc(self, x: int, y: int) -> Sprite | None:
        for sprite in self.current_level._sprites:
            if sprite.x == x and sprite.y == y:
                return sprite
        return None

    def pubeyzotzr(self, x: int, y: int) -> List[Sprite] | None:
        sprites = []
        for sprite in self.current_level._sprites:
            if x >= sprite.x and y >= sprite.y and (x < sprite.x + sprite.width) and (y < sprite.y + sprite.height):
                sprites.append(sprite)
        if len(sprites) > 0:
            return sprites
        return None

    def step(self) -> None:
        vctdsvnwjd = False
        if self.action.id == GameAction.ACTION6:
            x = self.action.data.get("x", 0)
            y = self.action.data.get("y", 0)
            vshsqyfvro = self.camera.display_to_grid(x, y)
            if vshsqyfvro:
                yrtwgqlvm, ejftlnclv = vshsqyfvro
                cwpawmamb = self.pubeyzotzr(yrtwgqlvm, ejftlnclv)
                if cwpawmamb is not None:
                    for pnrmgmcmh in cwpawmamb:
                        if pnrmgmcmh is not None and pnrmgmcmh.tags is not None and ("button" in pnrmgmcmh.tags[0]):
                            vctdsvnwjd = True
                            qrjqfnfrjr = pnrmgmcmh.tags[0].split("_")
                            if len(qrjqfnfrjr) == 3:
                                racnaqksms = qrjqfnfrjr[1]
                                weskkxahis = qrjqfnfrjr[2]
                                kypahuoyom = True if weskkxahis == "R" else False
                                dshozwexhv = chmfaflqhy(
                                    self.ucybisahh,
                                    racnaqksms,
                                    kypahuoyom,
                                    self.uopmnplcnv,
                                )
                                cywbpycapt = []
                                for pmpudfwvhx, kvtywzwzuc in dshozwexhv:
                                    dbonbayerv = self.ttawusezqc(
                                        pmpudfwvhx.x * crxpafuiwp,
                                        pmpudfwvhx.y * crxpafuiwp,
                                    )
                                    if dbonbayerv:
                                        cywbpycapt.append((dbonbayerv, kvtywzwzuc))
                                for rpuvbbtfbq, ckyxhqnvtd in cywbpycapt:
                                    rpuvbbtfbq.set_position(
                                        ckyxhqnvtd.x * crxpafuiwp,
                                        ckyxhqnvtd.y * crxpafuiwp,
                                    )
        if not vctdsvnwjd:
            self.complete_action()
            return
        if self.khartslnwa():
            self.next_level()
            self.complete_action()
            return
        if not self.toxpunyqe.xsfawdkqoi():
            self.lose()
        self.complete_action()

    def khartslnwa(self) -> bool:
        ngnionqsbv = self.current_level.get_sprites_by_tag("bghvgbtwcb")
        for praflotbfn in ngnionqsbv:
            if self.current_level.get_sprite_at(praflotbfn.x + 1, praflotbfn.y + 1, "goal") is None:
                return False
        ngnionqsbv = self.current_level.get_sprites_by_tag("fdgmtkfrxl")
        for praflotbfn in ngnionqsbv:
            if self.current_level.get_sprite_at(praflotbfn.x + 1, praflotbfn.y + 1, "goal-o") is None:
                return False
        return True


# ── copycat layer ───────────────────────────────────────────────────────────────
# Colour assignment for this copycat: displayed colour = _CC_PALETTE[engine colour].
# Applied to the camera's final 64x64 output only, so the game's own rules (some of which
# read sprite colours) are untouched.
_CC_PALETTE = np.array([12, 4, 10, 2, 0, 1, 7, 11, 15, 3, 5, 8, 9, 6, 13, 14], dtype=np.int8)


class _CcCamera(Camera):
    def render(self, sprites):
        frame = super().render(sprites)
        frame = np.asarray(frame)
        out = frame.copy()
        mask = (frame >= 0) & (frame <= 15)
        out[mask] = _CC_PALETTE[frame[mask].astype(np.int64)]
        return out


class Ly85(_Ly85Rules):
    def __init__(self) -> None:
        super().__init__()
        if type(self._camera) is Camera:
            self._camera.__class__ = _CcCamera
        if not isinstance(self._camera, _CcCamera):
            raise RuntimeError("copycat palette camera not installed")
        self._game_id = 'ly85'

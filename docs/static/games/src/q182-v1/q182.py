"""q182 Borrowed Floor -- tiles used now disappear from a later room."""

from __future__ import annotations
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

CELL,OX,TOP,BOTTOM,W,H=5,14,5,35,7,5
BG,NOW,LATER,WALL,PLAYER,GOAL,BORROWED,MISSING,BAD=6,11,9,3,10,14,12,8,13
DIRS={1:(0,-1),2:(0,1),3:(-1,0),4:(1,0)}
LEVELS=[
 {"name":"Save One Tile","first":["#######","#S.a.G#","#.....#","#######","#######"],"later":["#######","#S.a.G#","#######","#######","#######"],"budget":22},
 {"name":"Long Route First","first":["#######","#S.abG#","#.....#","#######","#######"],"later":["#######","#S.abG#","#.###.#","#.....#","#######"],"budget":28},
 {"name":"Shared Material","first":["#######","#S.a.G#","#.#.#.#","#..b..#","#######"],"later":["#######","#S.b.G#","#.#.#.#","#..a..#","#######"],"budget":32},
 {"name":"Floor Ledger","first":["#######","#S.abc#","#....G#","#######","#######"],"later":["#######","#S...G#","#.abc.#","#.....#","#######"],"budget":35},
 {"name":"Conserve the Bridge","first":["#######","#S.a..#","#.#.#G#","#..b..#","#######"],"later":["#######","#S.b.G#","#.#.#.#","#..a..#","#######"],"budget":38},
 {"name":"Borrowed Floor","first":["#######","#S.ab.#","#.#.#G#","#..c..#","#######"],"later":["#######","#S.c.G#","#.#.#.#","#.ab..#","#######"],"budget":42},
]


def locate(grid,ch):
 for y,row in enumerate(grid):
  for x,v in enumerate(row):
   if v==ch:return x,y
 raise ValueError(ch)


class Display(RenderableUserDisplay):
 def __init__(self,game):self.game=game
 @staticmethod
 def room(frame,grid,oy,color,used,pos,active):
  frame[oy-2:oy+H*CELL+2,OX-2:OX+W*CELL+2]=0 if active else color
  for y,row in enumerate(grid):
   for x,ch in enumerate(row):
    px,py=OX+x*CELL,oy+y*CELL;c=WALL if ch=="#" else color
    if ch in used:c=MISSING
    frame[py:py+CELL,px:px+CELL]=c
    if ch in "abc":frame[py+1:py+4,px+1:px+4]=BORROWED
    elif ch=="G":frame[py+1:py+4,px+1:px+4]=GOAL
  px,py=OX+pos[0]*CELL,oy+pos[1]*CELL;frame[py+1:py+4,px+1:px+4]=PLAYER
 def render_interface(self,frame:np.ndarray)->np.ndarray:
  g=self.game;frame[:,:]=BG;self.room(frame,g.first,TOP,NOW,set(),g.pos if g.phase==0 else locate(g.first,"G"),g.phase==0);self.room(frame,g.later,BOTTOM,LATER,g.used,g.pos if g.phase==1 else locate(g.later,"S"),g.phase==1)
  if g.failed:frame[31:34,25:39]=BAD
  return frame


class Q182(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.first=self.later=[];self.used=set();self.pos=(0,0);self.phase=self.budget_left=0;self.failed=False
  levels=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS]
  super().__init__("q182",levels,Camera(0,0,64,64,BG,BG,[self.display]),False,len(levels),[1,2,3,4])
 def on_set_level(self,level):
  s=LEVELS[self.level_index];self.first=list(s["first"]);self.later=list(s["later"]);self.used=set();self.phase=0;self.pos=locate(self.first,"S");self.budget_left=s["budget"];self.failed=False
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  self.budget_left-=1
  if a not in DIRS:self.failed=True;self.lose();self.complete_action();return
  dx,dy=DIRS[a];grid=self.first if self.phase==0 else self.later;nxt=(self.pos[0]+dx,self.pos[1]+dy)
  if 0<=nxt[0]<W and 0<=nxt[1]<H and grid[nxt[1]][nxt[0]]!="#" and not(self.phase==1 and grid[nxt[1]][nxt[0]] in self.used):self.pos=nxt
  ch=grid[self.pos[1]][self.pos[0]]
  if self.phase==0 and ch in "abc":self.used.add(ch)
  if self.pos==locate(grid,"G"):
   if self.phase==0:self.phase=1;self.pos=locate(self.later,"S")
   else:self.next_level()
  elif self.budget_left<=0:self.failed=True;self.lose()
  self.complete_action()

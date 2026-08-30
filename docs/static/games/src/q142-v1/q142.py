"""q142 Ghost Alternatives -- spend scarce previews before committing movement."""

from __future__ import annotations
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

CELL,OX,OY,SIZE=9,9,10,5
BG,FLOOR,WALL,PLAYER,GOAL,TRAP,GHOST,CURSOR,BAD=1,10,3,6,14,8,7,11,13
DIRS={1:(0,-1),2:(0,1),3:(-1,0),4:(1,0)}
LEVELS=[
 {"name":"One Preview","start":(1,2),"goal":(3,2),"walls":[],"traps":[(2,1)],"previews":2,"budget":8},
 {"name":"Choose the Ghost","start":(0,4),"goal":(4,0),"walls":[(2,3)],"traps":[(1,3),(3,1)],"previews":3,"budget":18},
 {"name":"Sparse Preview","start":(0,2),"goal":(4,2),"walls":[(2,2)],"traps":[(1,1),(3,3)],"previews":2,"budget":21},
 {"name":"Delayed Choice","start":(4,4),"goal":(0,0),"walls":[(3,2),(1,2)],"traps":[(2,3),(2,1)],"previews":3,"budget":24},
 {"name":"Preview Budget","start":(0,4),"goal":(4,0),"walls":[(2,2),(3,2)],"traps":[(1,3),(3,1),(4,1)],"previews":3,"budget":28},
 {"name":"Ghost Alternatives","start":(0,2),"goal":(4,2),"walls":[(2,1),(2,3)],"traps":[(1,2),(3,2)],"previews":4,"budget":30},
]


class Display(RenderableUserDisplay):
 def __init__(self,game):self.game=game
 @staticmethod
 def fill(f,c,color,inset=0):
  x,y=c;px,py=OX+x*CELL,OY+y*CELL;f[py+inset:py+CELL-inset,px+inset:px+CELL-inset]=color
 def render_interface(self,frame:np.ndarray)->np.ndarray:
  g=self.game;frame[:,:]=BG
  for y in range(SIZE):
   for x in range(SIZE):self.fill(frame,(x,y),FLOOR,1)
  for w in g.walls:self.fill(frame,w,WALL,1)
  for t in g.traps:self.fill(frame,t,TRAP,3)
  self.fill(frame,g.goal,GOAL,1);self.fill(frame,g.goal,FLOOR,3);self.fill(frame,g.pos,PLAYER,1)
  if g.ghost is not None and 0<=g.ghost[0]<SIZE and 0<=g.ghost[1]<SIZE:self.fill(frame,g.ghost,GHOST,2)
  for i in range(g.previews_left):frame[3:6,8+i*8:14+i*8]=GHOST
  frame[59:63,8+g.cursor*10:15+g.cursor*10]=CURSOR
  if g.failed:frame[59:63,25:39]=BAD
  return frame


class Q142(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.pos=self.goal=(0,0);self.walls=self.traps=set();self.cursor=self.previews_left=self.budget_left=0;self.ghost=None;self.failed=False
  levels=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS]
  super().__init__("q142",levels,Camera(0,0,64,64,BG,BG,[self.display]),False,len(levels),[3,4,5,6])
 def on_set_level(self,level):
  s=LEVELS[self.level_index];self.pos=tuple(s["start"]);self.goal=tuple(s["goal"]);self.walls=set(map(tuple,s["walls"]));self.traps=set(map(tuple,s["traps"]));self.cursor=1;self.previews_left=s["previews"];self.budget_left=s["budget"];self.ghost=None;self.failed=False
 def candidate(self):
  dx,dy=DIRS[self.cursor];return self.pos[0]+dx,self.pos[1]+dy
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  self.budget_left-=1
  if a==3:self.cursor=4 if self.cursor==1 else self.cursor-1;self.ghost=None
  elif a==4:self.cursor=1 if self.cursor==4 else self.cursor+1;self.ghost=None
  elif a==5 and self.previews_left:self.ghost=self.candidate();self.previews_left-=1
  elif a==6:
   nxt=self.candidate()
   if not(0<=nxt[0]<SIZE and 0<=nxt[1]<SIZE) or nxt in self.walls or nxt in self.traps:self.failed=True;self.lose()
   else:self.pos=nxt;self.ghost=None
  else:self.failed=True;self.lose()
  if self.pos==self.goal:self.next_level()
  elif self.budget_left<=0:self.failed=True;self.lose()
  self.complete_action()

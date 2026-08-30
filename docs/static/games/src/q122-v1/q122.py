"""q122 Feint -- display an intent that moves a guard before executing the real move."""

from __future__ import annotations
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

CELL,OX,OY,SIZE=9,9,10,5
BG,FLOOR,WALL,PLAYER,GUARD,INTENT,GOAL,BAD=7,0,13,9,8,12,14,3
DIRS={1:(0,-1),2:(0,1),3:(-1,0),4:(1,0)}
LEVELS=[
 {"name":"Show Left Go Right","start":(1,2),"guard":(3,2),"goal":(4,2),"walls":[],"budget":12},
 {"name":"Corner Feint","start":(0,4),"guard":(2,2),"goal":(4,0),"walls":[],"budget":18},
 {"name":"Guarded Gap","start":(0,2),"guard":(2,2),"goal":(4,2),"walls":[(2,1),(2,3)],"budget":16},
 {"name":"Double Bluff","start":(4,4),"guard":(2,2),"goal":(0,0),"walls":[(3,2),(1,2)],"budget":22},
 {"name":"Narrow Intent","start":(0,4),"guard":(2,3),"goal":(4,0),"walls":[(1,2),(2,2),(3,1)],"budget":26},
 {"name":"Feint","start":(0,2),"guard":(3,2),"goal":(4,2),"walls":[(1,1),(2,1),(2,3),(3,3)],"budget":28},
]


def toward(pos,target):
 dx=target[0]-pos[0];dy=target[1]-pos[1]
 if abs(dx)>=abs(dy) and dx:return pos[0]+(1 if dx>0 else -1),pos[1]
 if dy:return pos[0],pos[1]+(1 if dy>0 else -1)
 return pos


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
  self.fill(frame,g.goal,GOAL,1);self.fill(frame,g.goal,FLOOR,3);self.fill(frame,g.pos,PLAYER,1);self.fill(frame,g.guard,GUARD,1)
  if g.stage:self.fill(frame,g.intent_cell,INTENT,3)
  if g.failed:frame[59:63,25:39]=BAD
  return frame


class Q122(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.pos=self.guard=self.goal=self.intent_cell=(0,0);self.walls=set();self.stage=self.budget_left=0;self.failed=False
  levels=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS]
  super().__init__("q122",levels,Camera(0,0,64,64,BG,BG,[self.display]),False,len(levels),[1,2,3,4])
 def on_set_level(self,level):
  s=LEVELS[self.level_index];self.pos=tuple(s["start"]);self.guard=tuple(s["guard"]);self.goal=tuple(s["goal"]);self.walls=set(map(tuple,s["walls"]));self.intent_cell=self.pos;self.stage=0;self.budget_left=s["budget"];self.failed=False
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  self.budget_left-=1
  if a not in DIRS:self.failed=True;self.lose();self.complete_action();return
  dx,dy=DIRS[a]
  if self.stage==0:
   self.intent_cell=(self.pos[0]+dx,self.pos[1]+dy);candidate=toward(self.guard,self.intent_cell)
   if candidate not in self.walls:self.guard=candidate
   self.stage=1
  else:
   nxt=(self.pos[0]+dx,self.pos[1]+dy)
   if not(0<=nxt[0]<SIZE and 0<=nxt[1]<SIZE) or nxt in self.walls or nxt==self.guard:self.failed=True;self.lose()
   else:self.pos=nxt;self.stage=0
  if self.pos==self.goal:self.next_level()
  elif self.budget_left<=0:self.failed=True;self.lose()
  self.complete_action()

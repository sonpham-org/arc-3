"""q162 Claim or Explore -- spend turns revealing policy or advancing irreversibly."""

from __future__ import annotations
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,CORRIDOR,UNKNOWN,CLUE,PLAYER,GOAL,PROBE,BAD=13,1,3,11,9,14,15,8
DIRS={1:(0,-1),2:(0,1),3:(-1,0),4:(1,0)}
LEVELS=[
 {"name":"Probe Then Act","route":[4,4],"span":1,"budget":5},
 {"name":"One Clue Two Steps","route":[1,4,4],"span":2,"budget":6},
 {"name":"Alternating Evidence","route":[3,1,4,2],"span":1,"budget":9},
 {"name":"Stop Exploring","route":[1,1,4,2,4],"span":3,"budget":8},
 {"name":"Sparse Claims","route":[4,1,3,2,4,1],"span":2,"budget":10},
 {"name":"Claim or Explore","route":[1,4,2,3,1,4,4],"span":3,"budget":11},
]


class Display(RenderableUserDisplay):
 def __init__(self,game):self.game=game
 def render_interface(self,frame:np.ndarray)->np.ndarray:
  g=self.game;frame[:,:]=BG;frame[8:56,5:59]=CORRIDOR
  for i in range(len(g.route)):frame[18:27,8+i*7:14+i*7]=GOAL if i<g.index else UNKNOWN
  frame[34:44,8+g.index*7:14+g.index*7]=PLAYER
  for offset in range(g.revealed):
   if g.index+offset<len(g.route):
    a=g.route[g.index+offset];dx,dy=DIRS[a];x=11+(g.index+offset)*7;frame[49+dy*3:53+dy*3,x+dx*3-1:x+dx*3+2]=CLUE
  frame[3:6,25:39]=PROBE if g.revealed else UNKNOWN
  if g.failed:frame[59:63,25:39]=BAD
  return frame


class Q162(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.route=[];self.index=self.span=self.revealed=self.budget_left=0;self.failed=False
  levels=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS]
  super().__init__("q162",levels,Camera(0,0,64,64,BG,BG,[self.display]),False,len(levels),[1,2,3,4,5])
 def on_set_level(self,level):
  s=LEVELS[self.level_index];self.route=list(s["route"]);self.index=0;self.span=s["span"];self.revealed=0;self.budget_left=s["budget"];self.failed=False
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  self.budget_left-=1
  if a==5:self.revealed=max(self.revealed,min(self.span,len(self.route)-self.index))
  elif a in DIRS:
   if a!=self.route[self.index]:self.failed=True;self.lose()
   else:self.index+=1;self.revealed=max(0,self.revealed-1)
  else:self.failed=True;self.lose()
  if self.index==len(self.route):self.next_level()
  elif self.budget_left<=0:self.failed=True;self.lose()
  self.complete_action()

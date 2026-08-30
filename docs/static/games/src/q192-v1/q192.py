"""q192 Nested Clocks -- synchronize fast local cycles with a slow global cycle."""

from __future__ import annotations
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,FACE,FAST,SLOW,TARGET,CAPTURE,BAD=8,1,9,15,14,11,13
LEVELS=[
 {"name":"One Rollover","fast":3,"slow":2,"targets":[(2,0)],"budget":4},
 {"name":"Two Hands","fast":4,"slow":3,"targets":[(1,0),(0,1)],"budget":7},
 {"name":"Nested Period","fast":5,"slow":3,"targets":[(3,0),(1,1)],"budget":10},
 {"name":"Slow Boundary","fast":4,"slow":4,"targets":[(2,1),(0,3)],"budget":15},
 {"name":"Clock Phrase","fast":6,"slow":3,"targets":[(2,0),(5,1),(1,2)],"budget":18},
 {"name":"Nested Clocks","fast":7,"slow":4,"targets":[(3,0),(0,1),(5,2),(2,3)],"budget":28},
]


class Display(RenderableUserDisplay):
 def __init__(self,game):self.game=game
 def render_interface(self,frame:np.ndarray)->np.ndarray:
  g=self.game;frame[:,:]=BG;frame[8:56,6:58]=FACE
  for i in range(g.fast_n):frame[18:24,10+i*7:15+i*7]=FAST if i==g.fast else 3
  for i in range(g.slow_n):frame[36:45,14+i*10:21+i*10]=SLOW if i==g.slow else 3
  if g.index<len(g.targets) and (g.fast,g.slow)==g.targets[g.index]:frame[27:34,27:37]=TARGET
  for i in range(len(g.targets)):frame[3:6,7+i*10:13+i*10]=CAPTURE if i<g.index else 3
  if g.failed:frame[59:63,25:39]=BAD
  return frame


class Q192(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.fast_n=self.slow_n=self.fast=self.slow=self.index=self.budget_left=0;self.targets=[];self.failed=False
  levels=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS]
  super().__init__("q192",levels,Camera(0,0,64,64,BG,BG,[self.display]),False,len(levels),[5,6])
 def on_set_level(self,level):
  s=LEVELS[self.level_index];self.fast_n=s["fast"];self.slow_n=s["slow"];self.targets=list(map(tuple,s["targets"]));self.fast=self.slow=self.index=0;self.budget_left=s["budget"];self.failed=False
 def tick(self):
  self.fast+=1
  if self.fast==self.fast_n:self.fast=0;self.slow=(self.slow+1)%self.slow_n
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  self.budget_left-=1
  if a==6:
   if (self.fast,self.slow)!=self.targets[self.index]:self.failed=True;self.lose();self.complete_action();return
   self.index+=1
   if self.index==len(self.targets):self.next_level();self.complete_action();return
  elif a!=5:self.failed=True;self.lose();self.complete_action();return
  self.tick()
  if self.budget_left<=0:self.failed=True;self.lose()
  self.complete_action()

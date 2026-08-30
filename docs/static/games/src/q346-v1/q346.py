"""q346 Crossing Survey -- alternate marked observers to cover disjoint dock attributes."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,FERRY,DOCK,PASSENGER,SEEN,MARK,NEED,BAD=0,13,9,12,10,15,14,8
LEVELS=[
 {"name":"Two Observers","n":5,"masks":[[3,6],[12,17]],"plan":[1,3],"budget":2},
 {"name":"Disjoint Attributes","n":6,"masks":[[5,10],[20,33]],"plan":[2,4],"budget":2},
 {"name":"Persistent Mark","n":6,"masks":[[3,12],[24,34]],"plan":[1,4,2],"budget":3},
 {"name":"Capacity Dock","n":7,"masks":[[7,14],[28,81]],"plan":[4,2,1],"budget":3},
 {"name":"Alternating Control","n":8,"masks":[[9,34],[68,145]],"plan":[1,4,2,3],"budget":4},
 {"name":"Crossing Survey","n":8,"masks":[[7,25],[98,164]],"plan":[3,1,4,2],"budget":4}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=FERRY
  for i in range(g.n):x=7+i*(50//g.n);f[17:33,x:x+6]=DOCK;f[37:42,x:x+6]=SEEN if g.seen&(1<<i) else PASSENGER;f[45:49,x:x+6]=NEED if g.need&(1<<i) else FERRY
  f[3:6,8:30]=MARK if g.marked else FERRY
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q346(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.n=self.budget=self.used=self.controller=self.seen=self.need=0;self.masks=[];self.marked=self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q346",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,5,6])
 def on_set_level(self,l):
  s=LEVELS[self.level_index];self.n=s["n"];self.budget=s["budget"];self.masks=[list(x) for x in s["masks"]];self.used=self.controller=self.seen=0;self.marked=False;need=0;c=1
  for a in s["plan"]:need|=self.masks[c][(a-1)%2];c=1-c
  self.need=need;self.failed=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z in (1,2,3,4) and self.marked and self.used<self.budget:self.seen|=self.masks[self.controller][(z-1)%2];self.used+=1;self.marked=False
  elif z==5 and not self.marked:self.marked=True;self.controller=1-self.controller
  elif z==6:
   if (self.seen&self.need)==self.need and self.used<=self.budget:self.next_level()
   else:self.failed=True;self.lose()
  else:self.failed=True;self.lose()
  self.complete_action()

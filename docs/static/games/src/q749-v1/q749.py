"""q749 Strata Obligation -- repay an identity-bound debt after undoing its cause."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,QUARRY,ORE,DEPTH,DEBT,MEMORY,CURSOR,BAD=9,11,13,14,15,10,12,8
LEVELS=[
 {"name":"Borrowed Pick","identity":1,"delay":1},{"name":"Buried Promise","identity":2,"delay":2},
 {"name":"Undo the Shaft","identity":1,"delay":3},{"name":"Persistent Debt","identity":2,"delay":4},
 {"name":"Long Credit","identity":2,"delay":5},{"name":"Strata Obligation","identity":1,"delay":6}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;l=LEVELS[g.level_index];f[:,:]=BG;f[4:60,6:58]=QUARRY
  for i in range(l["delay"]):y=49-i*6;f[y:y+4,18:46]=ORE if i<g.depth else DEPTH
  f[8:13,10:10+g.stage*10]=CURSOR
  if g.obligation:f[15:22,12+g.obligation*12:20+g.obligation*12]=DEBT
  if g.memory:f[25:32,12+g.memory*12:20+g.memory*12]=MEMORY
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q749(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.stage=self.depth=0;self.obligation=self.memory=None;self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q749",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,5])
 def on_set_level(self,l):self.stage=self.depth=0;self.obligation=self.memory=None;self.bad=False
 def fail(self):self.bad=True;self.lose()
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  l=LEVELS[self.level_index]
  if self.stage==0 and z in (1,2):self.obligation=z;self.stage=1
  elif self.stage==1 and z==3 and self.depth<l["delay"]:self.depth+=1
  elif self.stage==1 and z==5 and self.depth==l["delay"]:self.memory=self.obligation;self.stage=2
  elif self.stage==2 and z==4 and self.depth>0:
   self.depth-=1
   if self.depth==0:self.stage=3
  elif self.stage==3 and z in (1,2):
   if z==self.memory==l["identity"]:self.next_level()
   else:self.fail()
  else:self.fail()
  self.complete_action()

"""q752 Lockwater Obligation -- repay causal identity after a delayed appearance exchange."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,CANAL,BARGE,WATER,DEBT,SWAP,REWARD,BAD=2,7,13,10,15,12,6,8
LEVELS=[{"name":n,"identity":i,"delay":d} for n,i,d in [("Borrowed Barge",1,1),("Water Debt",2,2),("Appearance Swap",1,3),("Delayed Reward",2,4),("Causal Owner",2,5),("Lockwater Obligation",1,6)]]
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=CANAL;f[15:28,9:23]=BARGE;f[15:28,41:55]=BARGE;f[32:37,8:56]=WATER;f[42:46,8:8+g.depth*7]=REWARD
  if g.identity:f[49:54,9+g.identity*16:20+g.identity*16]=DEBT
  if g.swapped:f[54:58,42:56]=SWAP
  if g.bad:f[61:64,22:42]=BAD
  return f
class Q752(ARCBaseGame):
 def __init__(self):self.display=D(self);self.stage=self.depth=0;self.identity=None;self.swapped=self.bad=False;ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q752",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5])
 def on_set_level(self,l):self.stage=self.depth=0;self.identity=None;self.swapped=self.bad=False
 def step(self):
  z=self.action.id.value;x=LEVELS[self.level_index]
  if z==0:self.complete_action();return
  if self.stage==0 and z in (1,2):self.identity=z;self.stage=1
  elif self.stage==1 and z==3 and self.depth<x["delay"]:self.depth+=1
  elif self.stage==1 and self.depth==x["delay"] and z==4:self.swapped=True;self.stage=2
  elif self.stage==2 and z==5:self.stage=3
  elif self.stage==3 and z in (1,2):
   if self.swapped and z==self.identity==x["identity"]:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()

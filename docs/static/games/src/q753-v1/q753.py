"""q753 Murmuration Obligation -- delayed identity debt guarded by redundant parity."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,AVIARY,BIRD,WAKE,DEBT,REWARD,PARITY,BAD=3,7,13,10,15,12,6,8
LEVELS=[{"name":n,"identity":i,"delay":d,"signals":s,"bad":b} for n,i,d,s,b in [("Borrowed Marker",1,1,[1,0,1],1),("Wind Debt",2,2,[0,1,1],2),("Misleading Bird",1,3,[1,1,0,1],0),("Delayed Reward",2,4,[0,1,0,1],3),("Causal Flock",2,5,[1,0,1,1,0],4),("Murmuration Obligation",1,6,[1,1,0,1,0,0],2)]]
def parity(x):return sum(v^(i==x["bad"]) for i,v in enumerate(x["signals"]))%2
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,5:59]=AVIARY;f[14:24,8:56]=BIRD;f[29:34,8:56]=WAKE;f[40:44,8:8+g.depth*7]=REWARD;f[49:53,8:8+g.claim*18]=PARITY
  if g.identity:f[54:58,42:56]=DEBT
  if g.badstate:f[61:64,22:42]=BAD
  return f
class Q753(ARCBaseGame):
 def __init__(self):self.display=D(self);self.stage=self.depth=self.claim=0;self.identity=None;self.badstate=False;ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q753",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5])
 def on_set_level(self,l):self.stage=self.depth=self.claim=0;self.identity=None;self.badstate=False
 def step(self):
  z=self.action.id.value;x=LEVELS[self.level_index]
  if z==0:self.complete_action();return
  if self.stage==0 and z in (1,2):self.identity=z;self.stage=1
  elif self.stage==1 and z==3 and self.depth<x["delay"]:self.depth+=1
  elif self.stage==1 and z==4:self.claim=1-self.claim
  elif self.stage==1 and z==5 and self.depth==x["delay"] and self.claim==parity(x):self.stage=2
  elif self.stage==2 and z in (1,2):
   if z==self.identity==x["identity"]:self.next_level()
   else:self.badstate=True;self.lose()
  else:self.badstate=True;self.lose()
  self.complete_action()

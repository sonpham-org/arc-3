"""q267 Canopy Probe -- buffer causal interventions through a narrow evidence store."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,ORCHARD,SEED,SHADE,PROBE,STORE,EVIDENCE,BAD=7,11,13,10,14,15,6,8
LEVELS=[{"name":n,"model":m,"need":p,"cap":c} for n,m,p,c in [("Direct Shade",0,[1,2],2),("Shared Season",1,[1,3],1),("Coincident Seed",2,[2,3],2),("Narrow Store",1,[1,2],1),("Finite Probe",2,[2,3],1),("Canopy Probe",0,[1,2],2)]]
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,5:59]=ORCHARD;f[13:18,8:56]=SHADE;f[24:33,9:20]=SEED;f[39:43,8:8+len(g.store)*10]=STORE;f[48:52,8:8+g.seen*7]=EVIDENCE
  if g.bad:f[61:64,22:42]=BAD
  return f
class Q267(ARCBaseGame):
 def __init__(self):self.display=D(self);self.store=[];self.seen=self.candidate=0;self.bad=False;ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q267",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):self.store=[];self.seen=self.candidate=0;self.bad=False
 def step(self):
  z=self.action.id.value;x=LEVELS[self.level_index]
  if z==0:self.complete_action();return
  if z in (1,2,3) and len(self.store)<x["cap"]:self.store.append(z)
  elif z==4 and self.store:
   for p in self.store:self.seen|=1<<(p-1)
   self.store=[]
  elif z==5 and not self.store:self.candidate=(self.candidate+1)%3
  elif z==6:
   if not self.store and all(self.seen&(1<<(i-1)) for i in x["need"]) and self.candidate==x["model"]:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()

"""q567 Canopy Counter -- chunk a shaping pattern through a bounded store."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,ORCHARD,SEED,SHADE,STORE,HISTORY,READY,BAD=7,11,13,10,14,15,6,8
LEVELS=[{"name":n,"pattern":p,"cap":c} for n,p,c in [("Recent Seed",[1,1],2),("Shade Response",[1,2],1),("Chunked Pattern",[2,3,2],2),("Narrow Store",[3,1,2],1),("Deadlock Risk",[1,3,2,1],2),("Canopy Counter",[2,1,3,2],1)]]
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,5:59]=ORCHARD;f[13:18,8:56]=SHADE
  for i in range(g.store):f[25:32,8+i*11:17+i*11]=STORE
  f[39:43,8:8+len(g.history)*8]=HISTORY
  if g.stage:f[49:55,38:56]=READY
  if g.bad:f[61:64,22:42]=BAD
  return f
class Q567(ARCBaseGame):
 def __init__(self):self.display=D(self);self.pending=[];self.history=[];self.store=self.stage=self.tactic=0;self.bad=False;ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q567",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5])
 def on_set_level(self,l):self.pending=[];self.history=[];self.store=self.stage=self.tactic=0;self.bad=False
 def step(self):
  z=self.action.id.value;x=LEVELS[self.level_index]
  if z==0:self.complete_action();return
  if z in (1,2,3) and not self.stage and self.store<x["cap"]:self.pending.append(z);self.store+=1
  elif z==4 and not self.stage and self.store:self.history+=self.pending;self.pending=[];self.store=0
  elif z==5 and not self.stage:
   if not self.store and self.history[-len(x["pattern"]):]==x["pattern"]:self.tactic=(sum(x["pattern"])-1)%3+1;self.stage=1
   else:self.bad=True;self.lose()
  elif z in (1,2,3) and self.stage:
   if z==self.tactic%3+1:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()

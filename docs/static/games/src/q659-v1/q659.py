"""q659 Strata Analogy -- transfer a route after a reversible physical probe."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,QUARRY,ORE,FAULT,SOURCE,TARGET,KNOWLEDGE,BAD=9,11,13,14,15,10,6,8
BASE=[1,3,2,4]
LEVELS=[{"name":n,"source":s,"target":t} for n,s,t in [
 ("Fault Route",[1,2,3,4],[2,3,4,1]),("Ore Transfer",[2,4,1,3],[4,1,3,2]),("Undo Probe",[3,1,4,2],[1,4,2,3]),
 ("Relational Seam",[4,2,3,1],[3,1,4,2]),("Causal Structure",[2,3,1,4],[4,2,1,3]),("Strata Analogy",[3,4,2,1],[2,1,3,4])]]
def route(m):return[m[x-1] for x in BASE]
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,5:59]=QUARRY;f[13:20,8:56]=FAULT;f[25:32,8:56]=ORE;f[38:43,8:8+g.index*10]=SOURCE if not g.probed else TARGET
  if g.physical:f[47:53,9:21]=KNOWLEDGE
  if g.evidence:f[47:53,43:55]=KNOWLEDGE
  if g.bad:f[61:64,22:42]=BAD
  return f
class Q659(ARCBaseGame):
 def __init__(self):self.display=D(self);self.phase=self.index=0;self.probed=self.physical=self.evidence=self.bad=False;ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q659",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):self.phase=self.index=0;self.probed=self.physical=self.evidence=self.bad=False
 def step(self):
  z=self.action.id.value;x=LEVELS[self.level_index]
  if z==0:self.complete_action();return
  if not self.probed and z in (1,2,3,4):
   if z==route(x["source"])[self.index]:self.index+=1
   else:self.bad=True;self.lose()
  elif not self.probed and self.index==4 and z==5:self.probed=self.physical=self.evidence=True;self.index=0
  elif self.physical and z==6:self.physical=False
  elif self.probed and not self.physical and z in (1,2,3,4):
   if z==route(x["target"])[self.index]:self.index+=1
   else:self.bad=True;self.lose()
   if self.index==4:self.next_level()
  else:self.bad=True;self.lose()
  self.complete_action()

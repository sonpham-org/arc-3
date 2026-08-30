"""q359 Strata Rig -- assemble quarry modules, probe them, then undo physically."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,QUARRY,ORE,FAULT,PART,MODULE,KNOWLEDGE,BAD=9,11,13,14,15,12,10,8
LEVELS=[{"name":n,"modules":m} for n,m in [("Ore Redirect",[[1,2]]),("Fault Join",[[2,3],[1,2]]),("Support Span",[[3,1],[2,3]]),("Two Effects",[[2,1,3],[1,2]]),("Reusable Rig",[[1,3,2],[3,1],[2,3]]),("Strata Rig",[[3,2,1],[1,2,3],[2,1]])]]
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,5:59]=QUARRY;f[12:17,8:56]=FAULT
  for i in range(len(g.store)):f[24:32,8+i*13:18+i*13]=PART
  f[39:44,8:8+g.progress*12]=MODULE
  if g.physical:f[48:54,9:21]=ORE
  if g.evidence:f[48:54,43:55]=KNOWLEDGE
  if g.bad:f[61:64,22:42]=BAD
  return f
class Q359(ARCBaseGame):
 def __init__(self):self.display=D(self);self.store=[];self.progress=0;self.physical=self.evidence=self.bad=False;ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q359",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):self.store=[];self.progress=0;self.physical=self.evidence=self.bad=False
 def step(self):
  z=self.action.id.value;x=LEVELS[self.level_index]
  if z==0:self.complete_action();return
  if z in (1,2,3) and len(self.store)<3:self.store.append(z)
  elif z==4:
   if self.progress<len(x["modules"]) and self.store==x["modules"][self.progress]:self.progress+=1;self.store=[]
   else:self.bad=True;self.lose()
  elif z==5 and self.progress==len(x["modules"]) and not self.store:self.physical=self.evidence=True
  elif z==6 and self.physical and self.evidence:self.physical=False;self.next_level()
  else:self.bad=True;self.lose()
  self.complete_action()

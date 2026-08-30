"""q419 Strata Revision -- identify a worn rule while irreversible knowledge outlives undo."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,QUARRY,ORE,FAULT,WEAR,PROBE,KNOWLEDGE,BAD=9,11,13,14,15,12,10,8
LAW=[1,3,2]
LEVELS=[
 {"name":"Wear Boundary","rule":0,"boundary":1},{"name":"Inverted Law","rule":1,"boundary":2},
 {"name":"Rotated Law","rule":2,"boundary":3},{"name":"Undo the Probe","rule":1,"boundary":4},
 {"name":"Persistent Knowledge","rule":2,"boundary":5},{"name":"Strata Revision","rule":0,"boundary":6}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;l=LEVELS[g.level_index];f[:,:]=BG;f[5:59,5:59]=QUARRY
  for i in range(l["boundary"]):f[48-i*6:52-i*6,12:52]=ORE if i<g.wear else FAULT
  f[9:13,8:8+g.wear*7]=WEAR
  if g.world:f[24:34,9:20]=PROBE
  if g.evidence is not None:f[24:34,44:55]=KNOWLEDGE
  if g.bad:f[61:64,22:42]=BAD
  return f
class Q419(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.wear=self.world=self.candidate=0;self.evidence=None;self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q419",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,3,4,5,6])
 def on_set_level(self,l):self.wear=self.world=self.candidate=0;self.evidence=None;self.bad=False
 def fail(self):self.bad=True;self.lose()
 def step(self):
  z=self.action.id.value;l=LEVELS[self.level_index]
  if z==0:self.complete_action();return
  if z==3 and not self.world:self.wear+=1
  elif z==1 and self.wear==l["boundary"] and not self.world:self.world=1;self.evidence=LAW[l["rule"]]
  elif z==4 and self.world:self.world=0;self.wear=max(0,self.wear-1)
  elif z==5 and not self.world:self.candidate=(self.candidate+1)%3
  elif z==6:
   if self.evidence is not None and not self.world and self.candidate==l["rule"]:self.next_level()
   else:self.fail()
  else:self.fail()
  self.complete_action()

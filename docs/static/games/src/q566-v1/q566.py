"""q566 Palimpsest Counter -- shape an adaptive archive opponent with an exact causal pattern."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,ARCHIVE,TILE,TRACE,PATTERN,READY,FAILED,BAD=6,10,12,15,14,11,3,8
LEVELS=[{"name":n,"pattern":p} for n,p in [("Recent Trace",[1,1]),("Failed Twin",[1,2]),("Three Marks",[2,3,2]),("Causal Pattern",[3,1,2]),("Near Miss",[1,3,2,1]),("Palimpsest Counter",[2,1,3,2])]]
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,5:59]=ARCHIVE
  for i,z in enumerate(g.history[-4:]):f[18:28,9+i*12:19+i*12]=TILE;f[30:34,9+i*12:9+i*12+z*3]=TRACE
  f[40:44,8:8+len(g.history)*8]=PATTERN
  if g.stage:f[49:55,38:56]=READY
  f[55:58,8:28]=FAILED
  if g.bad:f[61:64,22:42]=BAD
  return f
class Q566(ARCBaseGame):
 def __init__(self):self.display=D(self);self.history=[];self.stage=self.tactic=0;self.bad=False;ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q566",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4])
 def on_set_level(self,l):self.history=[];self.stage=self.tactic=0;self.bad=False
 def step(self):
  z=self.action.id.value;p=LEVELS[self.level_index]["pattern"]
  if z==0:self.complete_action();return
  if z in (1,2,3) and not self.stage:self.history.append(z)
  elif z==4 and not self.stage:
   if self.history[-len(p):]==p:self.tactic=(sum(p)-1)%3+1;self.stage=1
   else:self.bad=True;self.lose()
  elif z in (1,2,3) and self.stage:
   if z==self.tactic%3+1:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()

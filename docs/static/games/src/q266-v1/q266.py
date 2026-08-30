"""q266 Palimpsest Probe -- causal diagnosis against a visible near-miss example."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,ARCHIVE,TILE,TRACE,PROBE,HYPOTHESIS,FAILED,BAD=6,10,12,15,14,11,3,8
SIG=[[0,1,0],[1,1,0],[1,0,1]]
LEVELS=[{"name":n,"model":m,"need":p} for n,m,p in [("Direct Trace",0,[1,2]),("Shared Shelf",1,[1,3]),("Coincident Tile",2,[2,3]),("Failed Twin",1,[1,2]),("Finite Probe",2,[2,3]),("Palimpsest Probe",0,[1,2])]]
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,5:59]=ARCHIVE
  for x in (9,26,43):f[14:27,x:x+11]=TILE
  f[32:36,8:56]=TRACE;f[41:45,8:8+g.seen*7]=PROBE;f[49:54,8+g.candidate*15:19+g.candidate*15]=HYPOTHESIS;f[55:58,43:56]=FAILED
  if g.bad:f[61:64,22:42]=BAD
  return f
class Q266(ARCBaseGame):
 def __init__(self):self.display=D(self);self.seen=self.candidate=0;self.bad=False;ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q266",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5])
 def on_set_level(self,l):self.seen=self.candidate=0;self.bad=False
 def step(self):
  z=self.action.id.value;x=LEVELS[self.level_index]
  if z==0:self.complete_action();return
  if z in (1,2,3):self.seen|=1<<(z-1)
  elif z==4:self.candidate=(self.candidate+1)%3
  elif z==5:
   if all(self.seen&(1<<(i-1)) for i in x["need"]) and self.candidate==x["model"]:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()

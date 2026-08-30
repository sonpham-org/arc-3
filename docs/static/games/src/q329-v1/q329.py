"""q329 Strata Survey -- reversible quarry probes with persistent set-cover evidence."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,QUARRY,ORE,FAULT,PROBE,EVIDENCE,BUDGET,BAD=9,11,13,14,15,10,6,8
LEVELS=[{"name":n,"masks":m,"need":q,"solution":s} for n,m,q,s in [("Fault Slice",[1,2,4,3],7,[1,2,3]),("Ore Union",[3,6,12,9],15,[1,3]),("Undo Probe",[5,10,3,12],15,[1,2]),("Persistent Trace",[9,18,36,27],63,[1,2,3]),("Route Evidence",[7,24,42,49],63,[1,2,4]),("Strata Survey",[11,21,38,56],63,[1,3,4])]]
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,5:59]=QUARRY;f[13:18,8:56]=FAULT;f[25:34,9:20]=ORE
  if g.physical:f[39:45,9:21]=PROBE
  f[49:53,8:8+bin(g.seen).count("1")*7]=EVIDENCE
  if g.bad:f[61:64,22:42]=BAD
  return f
class Q329(ARCBaseGame):
 def __init__(self):self.display=D(self);self.seen=self.used=0;self.physical=self.bad=False;ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q329",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):self.seen=self.used=0;self.physical=self.bad=False
 def step(self):
  z=self.action.id.value;x=LEVELS[self.level_index]
  if z==0:self.complete_action();return
  if z in (1,2,3,4) and not self.physical and not self.used&(1<<(z-1)):self.physical=True;self.seen|=x["masks"][z-1];self.used|=1<<(z-1)
  elif z==5 and self.physical:self.physical=False
  elif z==6:
   if not self.physical and self.seen&x["need"]==x["need"]:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()

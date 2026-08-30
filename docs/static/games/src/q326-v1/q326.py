"""q326 Palimpsest Survey -- allocate bounded observations to overwritten traces."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,ARCHIVE,SHELF,TRACE,OBSERVED,BUDGET,FAILED,BAD=6,10,12,14,15,11,3,8
LEVELS=[
 {"name":"Trace Slice","masks":[1,2,4,3],"need":7,"budget":3},
 {"name":"Overwritten Shelf","masks":[3,6,12,9],"need":15,"budget":2},
 {"name":"Failed Example","masks":[5,10,3,12],"need":15,"budget":2},
 {"name":"Bounded Union","masks":[9,18,36,27],"need":63,"budget":3},
 {"name":"Route Question","masks":[7,24,42,49],"need":63,"budget":3},
 {"name":"Palimpsest Survey","masks":[11,21,38,56],"need":63,"budget":3}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;l=LEVELS[g.level_index];f[:,:]=BG;f[5:59,5:59]=ARCHIVE
  for i,m in enumerate(l["masks"]):x=8+i*13;f[14:26,x:x+9]=SHELF;f[27:31,x:x+bin(m).count("1")]=TRACE if not g.used&(1<<i) else OBSERVED
  f[40:45,8:8+g.budget*10]=BUDGET;f[49:53,8:31]=FAILED
  if g.bad:f[61:64,22:42]=BAD
  return f
class Q326(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.seen=self.used=self.budget=0;self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q326",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,5])
 def on_set_level(self,l):self.seen=self.used=0;self.budget=LEVELS[self.level_index]["budget"];self.bad=False
 def fail(self):self.bad=True;self.lose()
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  l=LEVELS[self.level_index]
  if z in (1,2,3,4) and self.budget>0 and not self.used&(1<<(z-1)):self.seen|=l["masks"][z-1];self.used|=1<<(z-1);self.budget-=1
  elif z==5:
   if self.seen&l["need"]==l["need"]:self.next_level()
   else:self.fail()
  else:self.fail()
  self.complete_action()

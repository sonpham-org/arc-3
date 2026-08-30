"""q408 Escapement Delegation -- diagnose a fault before alternating complementary views."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,TOWER,WEIGHT,GEAR,MARK,PROBE,DONE,BAD=7,3,9,12,15,10,6,8
LEVELS=[
 {"name":"Probe the Fault","fault":0,"pairs":[[1,2],[2,1]]},{"name":"Complementary Gears","fault":1,"pairs":[[2,2],[1,1],[2,1]]},
 {"name":"Alternating Control","fault":0,"pairs":[[1,2],[2,2],[1,1],[2,1]]},{"name":"Persistent Mark","fault":1,"pairs":[[2,1],[1,2],[2,2],[1,1],[2,1]]},
 {"name":"Exclusive Outcome","fault":0,"pairs":[[1,1],[2,1],[1,2],[2,2],[1,1],[2,2]]},{"name":"Escapement Delegation","fault":1,"pairs":[[2,2],[1,2],[2,1],[1,1],[2,2],[1,1],[2,1]]}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=TOWER;f[15:29,8:22]=WEIGHT if g.controller==0 else GEAR;f[15:29,42:56]=GEAR if g.controller==0 else WEIGHT;f[34:39,8:8+(g.mark or 0)*10]=MARK;f[43:48,8:8+g.index*7]=DONE
  if g.probed:f[50:54,34:56]=PROBE
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q408(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.fault=self.index=self.controller=0;self.pairs=[];self.mark=None;self.probed=self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q408",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,5,6])
 def on_set_level(self,l):self.fault=LEVELS[self.level_index]["fault"];self.pairs=[list(x) for x in LEVELS[self.level_index]["pairs"]];self.index=self.controller=0;self.mark=None;self.probed=self.failed=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z==5 and not self.probed:self.probed=True
  elif z in (1,2) and self.probed and self.index<len(self.pairs):
   expected=((self.pairs[self.index][self.controller]-1+self.fault)%2)+1
   if z!=expected:self.failed=True;self.lose()
   elif self.controller==0:self.mark=z
   elif self.mark is None:self.failed=True;self.lose()
   else:self.index+=1;self.mark=None
  elif z==3 and self.probed:
   if (self.controller==0 and self.mark is not None) or (self.controller==1 and self.mark is None):self.controller=1-self.controller
   else:self.failed=True;self.lose()
  elif z==6:
   if self.probed and self.index==len(self.pairs):self.next_level()
   else:self.failed=True;self.lose()
  else:self.failed=True;self.lose()
  self.complete_action()

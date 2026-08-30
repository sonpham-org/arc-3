"""q676 Crossing Analogy -- transfer dock structure through alternating marked controllers."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,FERRY,DOCK,PASSENGER,MARK,CONTROLLER,DONE,BAD=0,13,9,12,15,10,6,8
BASE=[1,3,2,4]
LEVELS=[
 {"name":"Dock Relation","dock":[1,2,3,4],"actor":[2,4,1,3]},
 {"name":"Alternate Controller","dock":[2,1,4,3],"actor":[3,1,4,2]},
 {"name":"Persistent Mark","dock":[4,2,1,3],"actor":[1,3,2,4]},
 {"name":"Capacity Structure","dock":[3,4,2,1],"actor":[4,2,3,1]},
 {"name":"Surface Independence","dock":[2,3,1,4],"actor":[3,2,4,1]},
 {"name":"Crossing Analogy","dock":[4,1,3,2],"actor":[2,4,3,1]}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=FERRY
  for i in range(4):x=9+i*13;f[15:25,x:x+8]=DOCK;f[30:42,x:x+8]=PASSENGER;f[46:50,x:x+8]=DONE if i<g.progress else FERRY
  f[3:6,8:30]=MARK if g.marked else CONTROLLER
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q676(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.routes=[];self.phase=self.progress=self.controller=0;self.marked=self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q676",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,5])
 def on_set_level(self,l):
  s=LEVELS[self.level_index];self.routes=[[s[k][i-1] for i in BASE] for k in ("dock","actor")];self.phase=self.progress=self.controller=0;self.marked=self.failed=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z==5 and not self.marked:self.marked=True
  elif z in (1,2,3,4) and self.marked:
   if z!=self.routes[self.phase][self.progress]:self.failed=True;self.lose()
   else:
    self.progress+=1;self.controller=1-self.controller;self.marked=False
    if self.progress==4:
     if self.phase==0:self.phase=1;self.progress=0
     else:self.next_level()
  else:self.failed=True;self.lose()
  self.complete_action()

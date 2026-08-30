"""q074 Drift Law -- recalibrate as the directional transformation rotates."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,FIELD,CAL,ROUTE,DONE,DRIFT,BAD=11,0,12,9,14,10,8
LEVELS=[
 {"name":"First Drift","rot":1,"route":[1,4],"cal":1}, {"name":"Old Mapping","rot":2,"route":[2,3,1],"cal":1},
 {"name":"Sparse Calibration","rot":3,"route":[4,1,2,3],"cal":1}, {"name":"Rotating Rule","rot":1,"route":[3,2,4,1,3],"cal":1},
 {"name":"Long Expiry","rot":2,"route":[1,4,2,3,1,2],"cal":1}, {"name":"Drift Law","rot":3,"route":[4,2,1,3,4,1,2],"cal":1}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[7:56,4:60]=FIELD
  for i,a in enumerate(g.route):x=7+i*8;f[29:37,x:x+6]=DONE if i<g.progress else ROUTE;f[31:34,x:x+a+1]=DRIFT
  if g.seen:f[13:18,26+g.rot*3:34+g.rot*3]=CAL
  if g.failed:f[59:63,25:39]=BAD
  return f
class Q074(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.rot=self.progress=self.cal=0;self.route=[];self.seen=False;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q074",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,5])
 def on_set_level(self,l):s=LEVELS[self.level_index];self.rot=s["rot"];self.route=list(s["route"]);self.progress=0;self.cal=s["cal"];self.seen=False;self.failed=False
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a==5 and self.cal:self.cal-=1;self.seen=True
  elif 1<=a<=4:
   expected=(self.route[self.progress]-1-self.rot)%4+1
   if not self.seen or a!=expected:self.failed=True;self.lose()
   else:
    self.progress+=1
    if self.progress==len(self.route):self.next_level()
  else:self.failed=True;self.lose()
  self.complete_action()

"""q666 Backstage Analogy -- transfer sightline structure to actors under a quantity threshold."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,THEATER,SIGHT,ACTOR,METER,THRESHOLD,DONE,BAD=10,2,9,12,15,14,6,8
BASE=[1,3,2,4]
LEVELS=[
 {"name":"Sightline Rule","sight":[1,2,3,4],"actor":[2,4,1,3],"weights":[1,2,1,2]},
 {"name":"Actor Analogy","sight":[2,1,4,3],"actor":[3,1,4,2],"weights":[2,1,2,1]},
 {"name":"Conserved Relation","sight":[4,2,1,3],"actor":[1,3,2,4],"weights":[1,3,1,2]},
 {"name":"Accumulated Influence","sight":[3,4,2,1],"actor":[4,2,3,1],"weights":[2,1,3,1]},
 {"name":"Surface Independence","sight":[2,3,1,4],"actor":[3,2,4,1],"weights":[3,1,2,2]},
 {"name":"Backstage Analogy","sight":[4,1,3,2],"actor":[2,4,3,1],"weights":[2,3,1,2]}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=THEATER
  for i in range(4):x=9+i*13;f[15:24,x:x+8]=SIGHT;f[29:42,x:x+8]=ACTOR;f[45:49,x:x+8]=DONE if i<g.progress else THEATER
  f[3:6,8:8+g.meter*3]=METER
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q666(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.routes=[];self.weights=[];self.phase=self.progress=self.meter=0;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q666",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4])
 def on_set_level(self,l):
  s=LEVELS[self.level_index];self.routes=[[s[k][i-1] for i in BASE] for k in ("sight","actor")];self.weights=list(s["weights"]);self.phase=self.progress=self.meter=0;self.failed=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z!=self.routes[self.phase][self.progress]:self.failed=True;self.lose()
  else:
   self.meter+=self.weights[self.progress];self.progress+=1
   if self.progress==4:
    if self.phase==0:self.phase=1;self.progress=0
    elif self.meter==2*sum(self.weights):self.next_level()
    else:self.failed=True;self.lose()
  self.complete_action()

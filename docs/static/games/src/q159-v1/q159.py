"""q159 Cross-Scale Transfer -- preserve a causal order from tiles to regions."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,WORLD,SMALL,LARGE,EDGE,ACTIVE,DONE,BAD=8,3,9,12,15,10,14,6
BASE=[1,3,4,2]
LEVELS=[
 {"name":"Tile to Region","local":[1,2,3,4],"global":[2,4,1,3]},
 {"name":"Scale Shift","local":[2,1,4,3],"global":[3,1,2,4]},
 {"name":"Preserve the Graph","local":[4,2,1,3],"global":[1,3,4,2]},
 {"name":"Nested Analogy","local":[3,4,2,1],"global":[4,1,3,2]},
 {"name":"Appearance Independence","local":[2,3,1,4],"global":[3,2,4,1]},
 {"name":"Cross-Scale Transfer","local":[4,1,3,2],"global":[2,4,3,1]}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=WORLD
  for i in range(4):x=8+i*13;f[14:21,x:x+7]=ACTIVE if g.phase==0 and i<g.progress else SMALL;f[29:43,x:x+10]=ACTIVE if g.phase==1 and i<g.progress else LARGE;f[23:26,x+2:x+6]=EDGE
  f[49:53,8:30 if g.phase else 17]=DONE
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q159(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.routes=[];self.phase=self.progress=0;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q159",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4])
 def on_set_level(self,l):
  s=LEVELS[self.level_index];self.routes=[[s[k][i-1] for i in BASE] for k in ("local","global")];self.phase=self.progress=0;self.failed=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z not in (1,2,3,4) or z!=self.routes[self.phase][self.progress]:self.failed=True;self.lose()
  else:
   self.progress+=1
   if self.progress==len(BASE):
    if self.phase==0:self.phase=1;self.progress=0
    else:self.next_level()
  self.complete_action()

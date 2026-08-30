"""q179 Field Alignment -- align local vectors to steer integrated global drift."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,FIELD,VECTOR,CURSOR,TARGET,DRIFT,DONE,BAD=10,7,12,9,14,15,6,8
LEVELS=[
 {"name":"Align Two Vectors","initial":[0,2],"targets":[1]},
 {"name":"Integrated Direction","initial":[3,1,2],"targets":[0]},
 {"name":"Local Rotation","initial":[1,3,0,2],"targets":[2,3]},
 {"name":"Field Reorientation","initial":[0,2,1,3],"targets":[3,1]},
 {"name":"Repeated Drift","initial":[2,0,3,1,2],"targets":[1,2,0]},
 {"name":"Field Alignment","initial":[3,1,0,2,3,1],"targets":[2,0,3]}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=FIELD;n=len(g.vectors)
  for i,v in enumerate(g.vectors):x=8+i*(48//n);h=5+v*3;f[35-h:36,x:x+7]=VECTOR;f[42:46,x:x+7]=CURSOR if i==g.cursor else FIELD
  f[3:6,8:8+g.targets[min(g.phase,len(g.targets)-1)]*8]=TARGET;f[50:53,8:8+g.phase*10]=DONE
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q179(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.vectors=self.targets=[];self.cursor=self.phase=0;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q179",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,5])
 def on_set_level(self,l):
  s=LEVELS[self.level_index];self.vectors=list(s["initial"]);self.targets=list(s["targets"]);self.cursor=self.phase=0;self.failed=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z==1:self.vectors[self.cursor]=(self.vectors[self.cursor]+1)%4
  elif z==2:self.vectors[self.cursor]=(self.vectors[self.cursor]-1)%4
  elif z==3:self.cursor=(self.cursor-1)%len(self.vectors)
  elif z==4:self.cursor=(self.cursor+1)%len(self.vectors)
  elif z==5:
   if any(v!=self.targets[self.phase] for v in self.vectors):self.failed=True;self.lose()
   else:
    self.phase+=1
    if self.phase==len(self.targets):self.next_level()
    else:self.vectors=[(v+1+(i%2))%4 for i,v in enumerate(self.vectors)]
  self.complete_action()

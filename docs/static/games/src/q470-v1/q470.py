"""q470 Workbench Lineage -- recover a helper identity through reversible tool transforms."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,WORKSHOP,TOOL,FIXTURE,TRAIL,MEMORY,DEBT,BAD=9,4,12,10,15,6,14,8
LEVELS=[
 {"name":"Helper Trail","ops":[1],"helper":1},{"name":"Appearance Exchange","ops":[2,1],"helper":2},
 {"name":"Split and Rotate","ops":[1,2,1],"helper":3},{"name":"Reversible Fixture","ops":[2,1,2,1],"helper":1},
 {"name":"Identity Debt","ops":[1,1,2,1,2],"helper":2},{"name":"Workbench Lineage","ops":[2,1,2,2,1,2],"helper":3}]
def transform(p,op):
 p=list(p)
 if op==1:p[0],p[1]=p[1],p[0]
 else:p=p[1:]+p[:1]
 return p
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=WORKSHOP
  for i in range(3):x=9+i*17;f[17:32,x:x+11]=TOOL;f[36:40,x:x+11]=MEMORY if i==g.cursor else TRAIL
  f[44:49,8:8+len(g.history)*8]=FIXTURE
  if g.remembered is not None:f[3:6,8:30]=DEBT
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q470(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.ops=[];self.helper=self.progress=self.cursor=self.phase=0;self.perm=[1,2,3];self.history=[];self.remembered=None;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q470",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,5,6])
 def on_set_level(self,l):
  s=LEVELS[self.level_index];self.ops=list(s["ops"]);self.helper=s["helper"];self.progress=self.cursor=self.phase=0;self.perm=[1,2,3];self.history=[];self.remembered=None;self.failed=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z in (1,2) and self.phase==0:
   if self.progress>=len(self.ops) or z!=self.ops[self.progress]:self.failed=True;self.lose()
   else:self.history.append(list(self.perm));self.perm=transform(self.perm,z);self.progress+=1
  elif z==3 and self.phase==0 and self.progress==len(self.ops):self.cursor=(self.cursor+1)%3
  elif z==5 and self.phase==0 and self.progress==len(self.ops):self.remembered=self.perm[self.cursor];self.phase=1
  elif z==4 and self.phase==1 and self.history:self.perm=self.history.pop()
  elif z==6:
   if self.phase==1 and not self.history and self.remembered==self.helper:self.next_level()
   else:self.failed=True;self.lose()
  else:self.failed=True;self.lose()
  self.complete_action()

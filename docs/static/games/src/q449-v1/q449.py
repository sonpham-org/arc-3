"""q449 Strata Lineage -- follow causal identity through reversible transformations."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,QUARRY,ORE,TRAIL,PROBE,MEMORY,GATE,BAD=3,11,9,15,10,14,6,8
LEVELS=[
 {"name":"Track One Ancestor","ops":[1],"target":0},{"name":"Appearance Exchange","ops":[2,1],"target":2},
 {"name":"Split and Rotate","ops":[1,2,1],"target":3},{"name":"Reversible World","ops":[2,1,2,1],"target":1},
 {"name":"Persistent Knowledge","ops":[1,1,2,1,2],"target":2},{"name":"Strata Lineage","ops":[2,1,2,2,1,2],"target":3}]
def transform(p,op):
 p=list(p)
 if op==1:p[0],p[1]=p[1],p[0];p[2],p[3]=p[3],p[2]
 else:p=p[1:]+p[:1]
 return p
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=QUARRY
  for i,v in enumerate(g.perm):x=8+i*13;f[18:33,x:x+9]=ORE;f[36:40,x:x+9]=PROBE if i==g.cursor else TRAIL
  f[44:49,8:8+len(g.history)*8]=TRAIL
  if g.remembered is not None:f[3:6,8:30]=MEMORY
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q449(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.ops=[];self.target=self.progress=self.cursor=self.phase=0;self.perm=list(range(4));self.history=[];self.remembered=None;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q449",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,5,6])
 def on_set_level(self,l):
  s=LEVELS[self.level_index];self.ops=list(s["ops"]);self.target=s["target"];self.progress=self.cursor=self.phase=0;self.perm=list(range(4));self.history=[];self.remembered=None;self.failed=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z in (1,2) and self.phase==0:
   if self.progress>=len(self.ops) or z!=self.ops[self.progress]:self.failed=True;self.lose()
   else:self.history.append(list(self.perm));self.perm=transform(self.perm,z);self.progress+=1
  elif z==3 and self.phase==0 and self.progress==len(self.ops):self.cursor=(self.cursor+1)%4
  elif z==5 and self.phase==0 and self.progress==len(self.ops):self.remembered=self.perm[self.cursor];self.phase=1
  elif z==4 and self.phase==1 and self.history:self.perm=self.history.pop()
  elif z==6:
   if self.phase==1 and not self.history and self.remembered==self.target:self.next_level()
   else:self.failed=True;self.lose()
  else:self.failed=True;self.lose()
  self.complete_action()

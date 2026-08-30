"""q463 Impeller Lineage -- follow ancestors through splitting wakes and changing blade masks."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,TURBINE,BLADE,MASK,WAKE,CLAIM,COST,BAD=11,10,15,14,12,9,13,8
LEVELS=[
 {"name":"First Wake","ancestor":0,"ops":(1,)},{"name":"Split Rider","ancestor":1,"ops":(2,3)},
 {"name":"Merged Trail","ancestor":2,"ops":(4,1,2)},{"name":"Counter Rotation","ancestor":3,"ops":(3,2,1,4)},
 {"name":"Costly Sample","ancestor":1,"ops":(2,4,3,1,2)},{"name":"Impeller Lineage","ancestor":2,"ops":(1,3,4,2,3,1)}]
def transform(lineages,masks,a):
 o=[set(v) for v in lineages];s=list(masks)
 if a==1:o[0],o[-1]=o[-1],o[0]
 elif a==2:o[1]|=o[0];o=o[1:]+o[:1]
 elif a==3:o=o[-1:]+o[:-1];s=s[1:]+s[:1]
 else:o[1],o[2]=o[2],o[1];s[0],s[3]=s[3],s[0]
 return tuple(frozenset(v) for v in o),tuple(s)
def result(x):
 o=tuple(frozenset((i,)) for i in range(4));s=(0,1,2,3)
 for a in x["ops"]:o,s=transform(o,s,a)
 return min(i for i,v in enumerate(o) if x["ancestor"] in v)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=TURBINE
  for i,(lineage,mask) in enumerate(zip(g.lineages,g.masks)):
   x=7+i*14;f[13:27,x:x+10]=BLADE;f[16:23,x+3:x+7]=MASK if mask%2 else WAKE
   for j,_ in enumerate(sorted(lineage)):f[29+j*3:31+j*3,x:x+10]=WAKE
  f[45:50,7+g.claim*14:17+g.claim*14]=CLAIM;f[54:58,7:7+g.samples*10]=COST
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q463(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.lineages=tuple(frozenset((i,)) for i in range(4));self.masks=(0,1,2,3);self.claim=self.samples=0;self.target=0;self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q463",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):
  self.lineages=tuple(frozenset((i,)) for i in range(4));self.masks=(0,1,2,3);self.claim=self.samples=0;self.target=result(LEVELS[self.level_index]);self.bad=False
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3,4):self.lineages,self.masks=transform(self.lineages,self.masks,a)
  elif a==5:self.claim=(self.claim+1)%4;self.samples+=1
  elif a==6:
   if x["ancestor"] in self.lineages[self.claim] and self.claim==self.target and self.samples<=4:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()

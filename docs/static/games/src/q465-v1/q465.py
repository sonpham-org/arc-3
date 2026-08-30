"""q465 Vivarium Lineage -- track ancestors through strata while partner favor follows the helped identity."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,VIVARIUM,FAUNA,STRATA,ANCESTOR,FAVOR,CLAIM,BAD=11,14,15,12,10,9,13,8
LEVELS=[
 {"name":"First Help","ancestor":0,"ops":(4,)},{"name":"Split Stratum","ancestor":1,"ops":(2,4,1)},
 {"name":"Merged Habitat","ancestor":2,"ops":(3,4,2,1)},{"name":"Reciprocal Lineage","ancestor":3,"ops":(1,3,4,2,3)},
 {"name":"Delayed Favor","ancestor":1,"ops":(2,4,3,1,2,3)},{"name":"Vivarium Lineage","ancestor":2,"ops":(1,3,2,4,1,2,3)}]
def transform(o,a):
 o=[set(v) for v in o]
 if a==1:o[0],o[-1]=o[-1],o[0]
 elif a==2:o[1]|=o[0];o=o[1:]+o[:1]
 elif a==3:o=o[-1:]+o[:-1]
 return tuple(frozenset(v) for v in o)
def result(x):
 o=tuple(frozenset((i,)) for i in range(4));favor=0
 for a in x["ops"]:
  if a in (1,2,3):o=transform(o,a)
  else:favor=(favor+x["ancestor"]+o.index(next(v for v in o if x["ancestor"] in v)))%3
 return o,min(i for i,v in enumerate(o) if x["ancestor"] in v),favor
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=VIVARIUM
  for i,lineage in enumerate(g.lineages):
   x=7+i*14;f[12:27,x:x+10]=FAUNA
   for j,_ in enumerate(sorted(lineage)):f[29+j*3:31+j*3,x:x+10]=ANCESTOR
  f[43:47,8:8+g.favor*14]=FAVOR;f[52:57,7+g.claim*14:17+g.claim*14]=CLAIM
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q465(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.lineages=tuple(frozenset((i,)) for i in range(4));self.favor=self.claim=0;self.target=(self.lineages,0,0);self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q465",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):self.lineages=tuple(frozenset((i,)) for i in range(4));self.favor=self.claim=0;self.target=result(LEVELS[self.level_index]);self.bad=False
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3):self.lineages=transform(self.lineages,a)
  elif a==4:self.favor=(self.favor+x["ancestor"]+min(i for i,v in enumerate(self.lineages) if x["ancestor"] in v))%3
  elif a==5:self.claim=(self.claim+1)%4
  elif a==6:
   if self.lineages==self.target[0] and self.claim==self.target[1] and self.favor==self.target[2]:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()

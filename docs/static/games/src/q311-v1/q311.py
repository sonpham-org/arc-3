"""q311 Pollen Ledger -- conserve pollen while a visible wear boundary complements transfers."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,MEADOW,BLOOM,POLLEN,WEAR,LEDGER,GOAL,BAD=3,14,11,15,12,10,9,8
LEVELS=[
 {"name":"First Transfer","stock":4,"boundary":1,"plan":(1,)},{"name":"Complement Wind","stock":5,"boundary":1,"plan":(1,2)},
 {"name":"Worn Ledger","stock":6,"boundary":2,"plan":(2,3,1)},{"name":"Global Bloom","stock":7,"boundary":2,"plan":(1,3,2,1)},
 {"name":"Conserved Revision","stock":8,"boundary":3,"plan":(2,1,3,2,1)},{"name":"Pollen Ledger","stock":9,"boundary":3,"plan":(1,2,3,1,3,2)}]
def advance(s,a,boundary):
 bins,wear=s;b=list(bins);src=a-1;dst=(src+1)%3 if wear<boundary else (src+2)%3
 if b[src]:b[src]-=1;b[dst]+=1
 return tuple(b),wear+1
def target(x):
 s=((x["stock"],0,0),0)
 for a in x["plan"]:s=advance(s,a,x["boundary"])
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=MEADOW
  for i,v in enumerate(g.bins):
   x=8+i*17;f[10:39,x:x+11]=BLOOM;f[36-v*3:37,x+2:x+9]=POLLEN
  f[44:48,8:8+g.wear*6]=WEAR;f[51:55,8:8+sum(g.bins)*4]=LEDGER;f[57:60,8:8+sum(g.target[0])*4]=GOAL
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q311(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bins=(4,0,0);self.wear=0;self.target=((4,0,0),0);self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q311",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):
  x=LEVELS[self.level_index];self.bins=(x["stock"],0,0);self.wear=0;self.target=target(x);self.bad=False
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3):self.bins,self.wear=advance((self.bins,self.wear),a,x["boundary"])
  elif a==4:self.wear+=1
  elif a==5:self.wear=max(0,self.wear-1)
  elif a==6:
   if (self.bins,self.wear)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()

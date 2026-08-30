"""q247 Catalyst Pact -- infer a social convention whose offers store orientations for later execution."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,REFINERY,BEAD,PIPE,OFFER,MEMORY,ROLE,BAD=1,12,15,11,14,10,13,8
LEVELS=[
 {"name":"First Offer","role":0,"plan":(1,4)},{"name":"Recency Pipe","role":1,"plan":(2,4,1,4)},
 {"name":"Reciprocal Bead","role":2,"plan":(1,2,4,3,4)},{"name":"Stored Pact","role":1,"plan":(3,4,2,4,1,4)},
 {"name":"Hidden Convention","role":0,"plan":(1,4,2,3,4,1,4)},{"name":"Catalyst Pact","role":2,"plan":(2,4,1,3,4,2,1,4)}]
def simulate(x):
 o=[0,1,2];stored=[None]*3;selected=0
 for a in x["plan"]:
  if a in (1,2,3):selected=a-1;stored[selected]=(o[selected]+x["role"]+a)%4
  else:o[selected]=(o[selected]+stored[selected]+1)%4;stored[selected]=None
 return tuple(o)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=REFINERY
  for i,v in enumerate(g.orientation):
   x=9+i*17;f[11:28,x:x+11]=PIPE;f[15+v*2:21+v*2,x+3:x+8]=BEAD
   if g.stored[i] is not None:f[30:34,x:x+11]=MEMORY
  f[42:47,9+g.selected*17:20+g.selected*17]=OFFER;f[53:57,8:8+g.role*14]=ROLE
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q247(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.orientation=[0,1,2];self.stored=[None]*3;self.selected=self.role=0;self.history=[];self.target=(0,1,2);self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q247",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):self.orientation=[0,1,2];self.stored=[None]*3;self.selected=self.role=0;self.history=[];self.target=simulate(LEVELS[self.level_index]);self.bad=False
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3):self.selected=a-1;self.stored[self.selected]=(self.orientation[self.selected]+x["role"]+a)%4;self.history.append(a)
  elif a==4:
   if self.stored[self.selected] is not None:self.orientation[self.selected]=(self.orientation[self.selected]+self.stored[self.selected]+1)%4;self.stored[self.selected]=None;self.history.append(a)
   else:self.bad=True;self.lose()
  elif a==5:self.role=(self.role+1)%3
  elif a==6:
   if tuple(self.history)==x["plan"] and tuple(self.orientation)==self.target and self.role==x["role"]:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()

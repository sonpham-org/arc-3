"""q277 Catalyst Probe -- observations store orientations that execute only after hiding."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,REFINERY,PIPE,BEAD,LOOK,MEMORY,MODEL,BAD=2,9,11,15,14,12,10,8
LEVELS=[
 {"name":"First Memory","model":0,"plan":(1,4)},{"name":"Hidden Turn","model":1,"plan":(2,4,1,4)},
 {"name":"Shared Pipe","model":2,"plan":(1,2,4,3,4)},{"name":"Temperature Gate","model":3,"plan":(3,4,2,4,1,4)},
 {"name":"Stored Contrast","model":4,"plan":(1,4,2,3,4,1,4)},{"name":"Catalyst Probe","model":5,"plan":(2,4,1,3,4,2,1,4)}]
def simulate(x):
 o=[0,1,2];stored=[None]*3;selected=0
 for a in x["plan"]:
  if a in (1,2,3):selected=a-1;stored[selected]=o[selected]
  else:o[selected]=(o[selected]+stored[selected]+x["model"]+1)%4;stored[selected]=None
 return tuple(o)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=REFINERY
  for i,v in enumerate(g.orientation):
   x=9+i*17;f[11:28,x:x+11]=PIPE;f[15+v*2:21+v*2,x+3:x+8]=BEAD
   if g.stored[i] is not None:f[30:34,x:x+11]=MEMORY
  f[42:47,9+g.selected*17:20+g.selected*17]=LOOK;f[53:57,8:8+g.candidate*8]=MODEL
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q277(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.orientation=[0,1,2];self.stored=[None]*3;self.selected=self.candidate=0;self.history=[];self.target=(0,1,2);self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q277",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):
  self.orientation=[0,1,2];self.stored=[None]*3;self.selected=self.candidate=0;self.history=[];self.target=simulate(LEVELS[self.level_index]);self.bad=False
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3):self.selected=a-1;self.stored[self.selected]=self.orientation[self.selected];self.history.append(a)
  elif a==4:
   if self.stored[self.selected] is not None:self.orientation[self.selected]=(self.orientation[self.selected]+self.stored[self.selected]+x["model"]+1)%4;self.stored[self.selected]=None;self.history.append(a)
   else:self.bad=True;self.lose()
  elif a==5:self.candidate=(self.candidate+1)%6
  elif a==6:
   if tuple(self.history)==x["plan"] and tuple(self.orientation)==self.target and self.candidate==x["model"]:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()

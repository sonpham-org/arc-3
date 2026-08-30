"""q389 Strata Delegation -- integrate reversible probes from complementary quarry views."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,QUARRY,ORE,FAULT,MARK,PROBE,CONTROL,BAD=9,11,13,14,15,12,10,8
LEVELS=[
 {"name":"Complementary Faults","clues":[0,1]},{"name":"Reversible Probe","clues":[1,1]},
 {"name":"Persistent Mark","clues":[1,0]},{"name":"Alternating Control","clues":[0,0]},
 {"name":"Integrated Action","clues":[1,0]},{"name":"Strata Delegation","clues":[0,1]}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[5:59,5:59]=QUARRY;f[14:26,8:22]=ORE;f[14:26,42:56]=FAULT
  for i in range(4):
   if g.evidence&(1<<i):f[34:39,8+i*12:17+i*12]=MARK
  if g.physical:f[42:48,25:39]=PROBE
  f[51:56,8+g.controller*32:24+g.controller*32]=CONTROL
  if g.bad:f[61:64,22:42]=BAD
  return f
class Q389(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.controller=self.evidence=self.physical=self.stage=self.candidate=0;self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q389",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,5,6])
 def on_set_level(self,l):self.controller=self.evidence=self.physical=self.stage=self.candidate=0;self.bad=False
 def fail(self):self.bad=True;self.lose()
 def step(self):
  z=self.action.id.value;clues=LEVELS[self.level_index]["clues"]
  if z==0:self.complete_action();return
  if z==1 and not self.physical:self.physical=1;self.evidence|=1<<(self.controller*2+clues[self.controller])
  elif z==2 and self.physical:self.physical=0
  elif z==3 and not self.physical:self.controller=1-self.controller
  elif z==4 and not self.physical and all(self.evidence&(1<<(i*2+clues[i])) for i in range(2)) and self.stage<2:self.stage+=1
  elif z==5 and not self.physical:self.candidate=1-self.candidate
  elif z==6:
   if not self.physical and self.stage==2 and self.candidate==(clues[0]^clues[1]):self.next_level()
   else:self.fail()
  else:self.fail()
  self.complete_action()

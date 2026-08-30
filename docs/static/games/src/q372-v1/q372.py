"""q372 Semaphore Rig -- assemble flag hardware only after both miniature systems agree."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,CLIFF,FLAG,RIG,PHASE,SYSTEM,DONE,BAD=6,12,15,14,11,10,9,8
LEVELS=[
 {"name":"First Redirect","mod":3,"recipe":((1,0),)},
 {"name":"Dual Join","mod":4,"recipe":((2,1),(1,0))},{"name":"Beam Support","mod":5,"recipe":((3,2),(2,4))},
 {"name":"Test Geometry","mod":5,"recipe":((1,4),(3,2),(2,4))},{"name":"Reusable Semaphore","mod":6,"recipe":((2,3),(1,2),(3,5),(2,0))},
 {"name":"Semaphore Rig","mod":7,"recipe":((3,5),(1,5),(2,1),(3,0),(1,0))}]
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;x=LEVELS[g.level_index];f[:,:]=BG;f[5:59,4:60]=CLIFF
  for i,c in enumerate(x["recipe"]):
   y=9+i*8;f[y:y+5,8:25]=DONE if i<len(g.built) else FLAG;f[y+1:y+4,10:10+c[0]*3]=RIG
  f[14:18,38:38+g.phase*3]=PHASE;f[27:32,38+g.system*12:49+g.system*12]=SYSTEM;f[43:48,38:38+g.tested*8]=SYSTEM;f[50:55,38:38+g.selected*5]=RIG
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q372(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.phase=self.system=self.tested=self.selected=0;self.built=[];self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q372",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):self.phase=self.system=self.tested=self.selected=0;self.built=[];self.bad=False
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3):self.selected=a;self.tested|=1<<self.system
  elif a==5:self.phase=(self.phase+1)%x["mod"]
  elif a==6:self.system^=1
  elif a==4:
   need=x["recipe"][len(self.built)] if len(self.built)<len(x["recipe"]) else None
   if need==(self.selected,self.phase) and self.tested==3:
    self.built.append(self.selected);self.phase=(self.phase+self.selected+1)%x["mod"];self.tested=0
    if len(self.built)==len(x["recipe"]):self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()

"""q660 Spore Analogy -- transfer a relation while two colony clocks advance."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,GREENHOUSE,SPORE,HUMIDITY,SOURCE,TARGET,CLOCK,BAD=10,2,13,12,15,14,6,8
BASE=[1,3,2,4]
LEVELS=[{"name":n,"source":s,"target":t,"mods":m} for n,s,t,m in [("Humidity Rule",[1,2,3,4],[2,3,4,1],[3,4]),("Colony Transfer",[2,4,1,3],[4,1,3,2],[4,5]),("Unequal Actors",[3,1,4,2],[1,4,2,3],[5,6]),("Sparse Event",[4,2,3,1],[3,1,4,2],[6,7]),("Conserved Relation",[2,3,1,4],[4,2,1,3],[7,8]),("Spore Analogy",[3,4,2,1],[2,1,3,4],[8,9])]]
def route(m):return[m[x-1] for x in BASE]
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,5:59]=GREENHOUSE;f[13:25,8:22]=SPORE;f[13:25,42:56]=SPORE;f[30:35,8:56]=HUMIDITY;f[41:45,8:8+g.index*10]=SOURCE if g.phase==0 else TARGET;f[51:55,8:8+sum(g.clocks)*4]=CLOCK
  if g.bad:f[61:64,22:42]=BAD
  return f
class Q660(ARCBaseGame):
 def __init__(self):self.display=D(self);self.phase=self.index=0;self.clocks=[0,0];self.bad=False;ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q660",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5])
 def on_set_level(self,l):self.phase=self.index=0;self.clocks=[0,0];self.bad=False
 def step(self):
  z=self.action.id.value;x=LEVELS[self.level_index];expected=route(x["source"] if self.phase==0 else x["target"])
  if z==0:self.complete_action();return
  if z in (1,2,3,4) and z==expected[self.index]:self.index+=1;self.clocks=[(self.clocks[i]+i+1)%x["mods"][i] for i in range(2)]
  elif z==5 and self.phase==0 and self.index==4:self.phase=1;self.index=0
  else:self.bad=True;self.lose()
  if self.phase==1 and self.index==4:self.next_level()
  self.complete_action()

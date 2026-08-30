"""q360 Spore Rig -- assemble reusable modules only at sparse shared events."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,GREENHOUSE,SPORE,HUMIDITY,PART,MODULE,CLOCK,BAD=10,2,13,12,15,14,6,8
LEVELS=[{"name":n,"modules":m,"mods":c} for n,m,c in [("Spore Redirect",[[1,2]],[2,3]),("Humidity Join",[[2,3],[1,2]],[3,4]),("Shared Event",[[3,1],[2,3]],[4,5]),("Unequal Actors",[[2,1,3],[1,2]],[5,6]),("Two Effects",[[1,3,2],[3,1],[2,3]],[6,7]),("Spore Rig",[[3,2,1],[1,2,3],[2,1]],[7,8])]]
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,5:59]=GREENHOUSE;f[13:25,8:22]=SPORE;f[13:25,42:56]=SPORE;f[30:35,8:56]=HUMIDITY
  for i in range(len(g.store)):f[39:46,8+i*11:17+i*11]=PART
  f[49:53,8:8+g.progress*11]=MODULE;f[54:57,35:35+sum(g.phase)*4]=CLOCK
  if g.bad:f[61:64,22:42]=BAD
  return f
class Q360(ARCBaseGame):
 def __init__(self):self.display=D(self);self.store=[];self.progress=0;self.phase=[0,0];self.bad=False;ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q360",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):self.store=[];self.progress=0;self.phase=[0,0];self.bad=False
 def step(self):
  z=self.action.id.value;x=LEVELS[self.level_index]
  if z==0:self.complete_action();return
  if z in (1,2,3) and self.phase==[0,0] and len(self.store)<3:self.store.append(z);self.phase=[1%x["mods"][0],2%x["mods"][1]]
  elif z==5:self.phase[0]=(self.phase[0]+1)%x["mods"][0]
  elif z==6:self.phase[1]=(self.phase[1]+1)%x["mods"][1]
  elif z==4:
   if self.progress<len(x["modules"]) and self.store==x["modules"][self.progress]:self.progress+=1;self.store=[]
   else:self.bad=True;self.lose()
   if self.progress==len(x["modules"]):self.next_level()
  else:self.bad=True;self.lose()
  self.complete_action()

"""q327 Canopy Survey -- buffer scarce shade observations without deadlocking."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,ORCHARD,LEAF,SHADE,STORE,SEEN,BUDGET,BAD=7,11,13,10,14,15,12,8
LEVELS=[
 {"name":"Shade Slice","masks":[1,2,4,3],"need":7,"budget":3,"capacity":2},
 {"name":"Seed Union","masks":[3,6,12,9],"need":15,"budget":2,"capacity":2},
 {"name":"Narrow Store","masks":[5,10,3,12],"need":15,"budget":2,"capacity":1},
 {"name":"Route Evidence","masks":[9,18,36,27],"need":63,"budget":3,"capacity":2},
 {"name":"Deadlock Order","masks":[7,24,42,49],"need":63,"budget":3,"capacity":2},
 {"name":"Canopy Survey","masks":[11,21,38,56],"need":63,"budget":3,"capacity":1}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;l=LEVELS[g.level_index];f[:,:]=BG;f[5:59,5:59]=ORCHARD
  for i,m in enumerate(l["masks"]):x=8+i*13;f[14:26,x:x+9]=LEAF;f[28:32,x:x+bin(m).count("1")]=SHADE
  for i in range(len(g.store)):f[38:44,8+i*11:17+i*11]=STORE
  f[48:52,8:8+bin(g.seen).count("1")*7]=SEEN;f[54:57,8:8+g.budget*9]=BUDGET
  if g.bad:f[61:64,22:42]=BAD
  return f
class Q327(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.seen=self.used=self.budget=0;self.store=[];self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q327",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,5,6])
 def on_set_level(self,l):self.seen=self.used=0;self.budget=LEVELS[self.level_index]["budget"];self.store=[];self.bad=False
 def fail(self):self.bad=True;self.lose()
 def step(self):
  z=self.action.id.value;l=LEVELS[self.level_index]
  if z==0:self.complete_action();return
  if z in (1,2,3,4) and self.budget>0 and len(self.store)<l["capacity"] and not self.used&(1<<(z-1)):self.store.append(l["masks"][z-1]);self.used|=1<<(z-1);self.budget-=1
  elif z==5 and self.store:
   for mask in self.store:self.seen|=mask
   self.store=[]
  elif z==6:
   if not self.store and self.seen&l["need"]==l["need"]:self.next_level()
   else:self.fail()
  else:self.fail()
  self.complete_action()

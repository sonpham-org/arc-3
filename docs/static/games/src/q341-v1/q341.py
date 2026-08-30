"""q341 Pollen Survey -- collect finite bloom evidence across a visible complement change."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,MEADOW,BLOOM,POLLEN,KNOWN,WEAR,ROUTE,BAD=4,14,11,15,10,12,9,8
MASKS=(0b001101011,0b110010101,0b101110000)
LEVELS=[
 {"name":"First Bloom","plan":(1,),"boundary":1,"route":0},{"name":"Complement Wind","plan":(2,1),"boundary":1,"route":1},
 {"name":"Worn Survey","plan":(3,2,1),"boundary":2,"route":2},{"name":"Bounded Meadow","plan":(1,3,2,1),"boundary":2,"route":1},
 {"name":"Sparse Recheck","plan":(2,1,3,2,1),"boundary":3,"route":2},{"name":"Pollen Survey","plan":(3,1,2,3,1,2),"boundary":3,"route":0}]
def simulate(x):
 known=wear=0
 for a in x["plan"]:
  idx=(a-1)%3;mask=MASKS[idx] if wear<x["boundary"] else (~MASKS[idx])&0x1ff;known|=mask;wear+=1
 return known,wear
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=MEADOW
  for i in range(3):f[10:24,9+i*17:20+i*17]=BLOOM
  for i in range(9):
   x=8+(i%3)*17;y=29+(i//3)*6;f[y:y+4,x:x+9]=KNOWN if g.known&(1<<i) else POLLEN
  f[49:53,8:8+g.wear*6]=WEAR;f[54:58,8:8+g.route*14]=ROUTE
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q341(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.known=self.wear=self.route=0;self.history=[];self.target=(0,0);self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q341",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):self.known=self.wear=self.route=0;self.history=[];self.target=simulate(LEVELS[self.level_index]);self.bad=False
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3):
   idx=a-1;mask=MASKS[idx] if self.wear<x["boundary"] else (~MASKS[idx])&0x1ff;self.known|=mask;self.wear+=1;self.history.append(a)
  elif a==4:self.route=(self.route+1)%3
  elif a==5:self.wear+=1
  elif a==6:
   if tuple(self.history)==x["plan"] and (self.known,self.wear)==self.target and self.route==x["route"]:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()

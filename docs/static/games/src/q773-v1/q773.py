"""q773 Ember Rhythm -- interrupt autonomous heat routines while observation and repair share fuel."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,KILN,VESSEL,HEAT,FUEL,WINDOW,CLAIM,BAD=11,12,15,14,10,9,13,8
LEVELS=[
 {"name":"First Beat","period":4,"plan":(1,2),"claim":1},{"name":"Scaled Heat","period":5,"plan":(4,1),"claim":2},
 {"name":"Repair Window","period":6,"plan":(2,3,1),"claim":3},{"name":"Shared Fuel","period":7,"plan":(1,4,3,2),"claim":2},
 {"name":"Interrupted Routine","period":8,"plan":(4,2,1,3,2),"claim":4},{"name":"Ember Rhythm","period":9,"plan":(1,4,3,2,4,1),"claim":5}]
DELTA={1:1,2:2,3:1,4:3}
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=KILN
  for i in range(4):f[11:27,8+i*13:18+i*13]=VESSEL if i==g.phase%4 else HEAT
  f[34:39,8:8+g.fuel*4]=FUEL;f[43:48,8:8+g.phase*5]=WINDOW;f[52:57,8:8+g.claim*7]=CLAIM
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q773(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.phase=self.claim=0;self.fuel=12;self.history=[];self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q773",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):self.phase=self.claim=0;self.fuel=12;self.history=[];self.bad=False
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3,4):
   if self.fuel:self.phase=(self.phase+DELTA[a])%x["period"];self.fuel-=1;self.history.append(a)
   else:self.bad=True;self.lose()
  elif a==5:self.claim=(self.claim+1)%6
  elif a==6:
   target=sum(DELTA[v] for v in x["plan"])%x["period"]
   if tuple(self.history)==x["plan"] and self.phase==target and self.claim==x["claim"]:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()

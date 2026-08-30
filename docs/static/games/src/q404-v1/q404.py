"""q404 Tessera Delegation -- alternate controller marks and interrupt a compressed seam routine."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,MOSAIC,TESSERA,SEAM,CONTROL,WINDOW,CLAIM,BAD=7,6,15,12,10,11,13,8
LEVELS=[
 {"name":"First Relay","period":4,"window":3,"plan":(1,6,2,4),"claim":1},{"name":"Compressed Seam","period":5,"window":4,"plan":(3,6,1,4),"claim":2},
 {"name":"Alternating Fold","period":6,"window":4,"plan":(1,6,2,1,4),"claim":3},{"name":"Shared Mosaic","period":7,"window":6,"plan":(2,3,6,1,4),"claim":2},
 {"name":"State Window","period":8,"window":7,"plan":(3,1,6,2,1,4),"claim":3},{"name":"Tessera Delegation","period":9,"window":0,"plan":(1,3,6,2,1,2,4),"claim":1}]
DELTA={1:1,2:2,3:3}
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=MOSAIC
  for i in range(4):f[11:27,8+i*13:18+i*13]=WINDOW if i==g.phase%4 else TESSERA
  f[34:38,8:8+g.phase*5]=SEAM;f[42:46,8+g.controller*31:25+g.controller*31]=CONTROL;f[48:52,8:8+g.seen*12]=CONTROL;f[54:58,8:8+g.claim*10]=CLAIM
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q404(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.phase=self.controller=self.seen=self.claim=0;self.caught=False;self.history=[];self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q404",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):self.phase=self.controller=self.seen=self.claim=0;self.caught=False;self.history=[];self.bad=False
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3):self.phase=(self.phase+DELTA[a])%x["period"];self.seen|=1<<self.controller;self.history.append(a)
  elif a==4:
   if tuple(self.history)==x["plan"] and self.caught:
    if self.seen==3 and self.claim==x["claim"]:self.next_level()
    else:self.bad=True;self.lose()
   else:self.caught|=self.phase==x["window"];self.history.append(a)
  elif a==6:self.controller^=1;self.history.append(a)
  elif a==5:self.claim=(self.claim+1)%4
  else:self.bad=True;self.lose()
  self.complete_action()

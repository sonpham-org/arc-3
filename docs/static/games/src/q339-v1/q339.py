"""q339 Reedbed Survey -- collect bounded salinity evidence while every sample rewires access."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,MARSH,REED,SAMPLE,KNOWN,LINK,ROUTE,BAD=4,10,11,15,14,12,9,8
MASKS=(0b001011001,0b110100010,0b100010111)
LEVELS=[
 {"name":"First Reed","plan":(1,),"route":0},{"name":"Flood Link","plan":(2,1),"route":1},
 {"name":"Rewired Sample","plan":(4,3,1),"route":2},{"name":"Bounded Union","plan":(2,4,1,3),"route":1},
 {"name":"Obstructed Route","plan":(3,1,4,2,3),"route":2},{"name":"Reedbed Survey","plan":(4,2,1,4,3,2),"route":0}]
def simulate(plan):
 known=link=0
 for a in plan:
  if a in (1,2,3):known|=MASKS[(a-1+link)%3];link=(link+a)%3
  else:link=(link+1)%3
 return known,link
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=MARSH
  for i in range(3):
   x=9+i*17;f[10:25,x:x+11]=REED
  for i in range(9):
   x=8+(i%3)*17;y=29+(i//3)*6;f[y:y+4,x:x+9]=KNOWN if g.known&(1<<i) else SAMPLE
  f[49:53,8:8+g.link*14]=LINK;f[54:58,8:8+g.route*14]=ROUTE
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q339(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.known=self.link=self.route=0;self.history=[];self.target=(0,0);self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q339",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):self.known=self.link=self.route=0;self.history=[];self.target=simulate(LEVELS[self.level_index]["plan"]);self.bad=False
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3):self.known|=MASKS[(a-1+self.link)%3];self.link=(self.link+a)%3;self.history.append(a)
  elif a==4:self.link=(self.link+1)%3;self.history.append(a)
  elif a==5:self.route=(self.route+1)%3
  elif a==6:
   if tuple(self.history)==x["plan"] and (self.known,self.link)==self.target and self.route==x["route"]:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()

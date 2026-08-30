"""q045 Scout Drones -- allocate disposable launches to preserve enough corridor evidence."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,MAP,HIDDEN,REVEAL,DRONE,TARGET,CURSOR,BAD=4,1,3,10,9,14,11,8
LEVELS=[
 {"name":"One Scout","rays":[1,2],"target":1,"bank":1}, {"name":"Choose Launch","rays":[3,4,1],"target":5,"bank":2},
 {"name":"Blocked Ray","rays":[3,12,5],"target":15,"bank":2}, {"name":"Map Fragments","rays":[7,24,9,18],"target":31,"bank":3},
 {"name":"Sparse Drones","rays":[3,12,48,17,34],"target":63,"bank":3}, {"name":"Scout Drones","rays":[7,24,96,65,18,36],"target":127,"bank":4}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[7:56,4:60]=MAP
  for i in range(7):x=7+i*7;f[18:39,x:x+5]=REVEAL if g.seen&(1<<i) else HIDDEN;f[13:16,x:x+5]=TARGET if g.target&(1<<i) else MAP
  for i in range(len(g.rays)):f[44:49,7+i*8:13+i*8]=CURSOR if i==g.cursor else DRONE
  f[51:54,7:7+g.bank*8]=DRONE
  if g.failed:f[59:63,25:39]=BAD
  return f
class Q045(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.rays=[];self.target=self.bank=self.cursor=self.seen=0;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q045",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[3,4,5,6])
 def on_set_level(self,l):s=LEVELS[self.level_index];self.rays=list(s["rays"]);self.target=s["target"];self.bank=s["bank"];self.cursor=self.seen=0;self.failed=False
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a==3:self.cursor=(self.cursor-1)%len(self.rays)
  elif a==4:self.cursor=(self.cursor+1)%len(self.rays)
  elif a==5 and self.bank:self.seen|=self.rays[self.cursor];self.bank-=1
  elif a==6:
   if self.seen&self.target==self.target:self.next_level()
   else:self.failed=True;self.lose()
  else:self.failed=True;self.lose()
  self.complete_action()

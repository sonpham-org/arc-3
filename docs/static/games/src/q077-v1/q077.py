"""q077 Aging Tools -- tool effects change after known use thresholds."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,BENCH,TOOLA,TOOLB,WEAR,STATE,TARGET,BAD=8,3,10,12,6,9,14,13
LEVELS=[
 {"name":"Second Use Changes","start":0,"target":3,"mod":7,"a":[1,2],"b":[-1]},
 {"name":"Worn Hammer","start":2,"target":0,"mod":8,"a":[2,1],"b":[-1,-2]},
 {"name":"Plan the Wear","start":1,"target":7,"mod":9,"a":[1,3,2],"b":[-2,-1]},
 {"name":"Crossing Lifetimes","start":5,"target":2,"mod":10,"a":[2,4,1],"b":[-1,-3,2]},
 {"name":"Functional Aging","start":3,"target":9,"mod":11,"a":[3,1,-2,2],"b":[-2,4,-1]},
 {"name":"Aging Tools","start":7,"target":4,"mod":12,"a":[1,4,-1,3],"b":[-3,2,5,-2]}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=BENCH;f[15:34,9:25]=TOOLA;f[15:34,39:55]=TOOLB
  f[37:41,9:9+g.agea*5]=WEAR;f[37:41,39:39+g.ageb*5]=WEAR;f[45:50,8:8+g.value*4]=STATE;f[52:55,8:8+g.target*4]=TARGET
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q077(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.value=self.target=self.mod=self.agea=self.ageb=0;self.a=self.b=[];self.budget=20;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q077",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,6])
 def on_set_level(self,l):
  s=LEVELS[self.level_index];self.value=s["start"];self.target=s["target"];self.mod=s["mod"];self.a=list(s["a"]);self.b=list(s["b"]);self.agea=self.ageb=0;self.budget=20;self.failed=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  self.budget-=1
  if z==1:self.value=(self.value+self.a[min(self.agea,len(self.a)-1)])%self.mod;self.agea=min(self.agea+1,len(self.a)-1)
  elif z==2:self.value=(self.value+self.b[min(self.ageb,len(self.b)-1)])%self.mod;self.ageb=min(self.ageb+1,len(self.b)-1)
  elif z==6:
   if self.value==self.target:self.next_level()
   else:self.failed=True;self.lose()
  else:self.failed=True;self.lose()
  if self.budget<=0:self.failed=True;self.lose()
  self.complete_action()

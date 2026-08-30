"""q187 Echo Cost -- early action repetition changes each action's later effect."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,HALL,ACTIONA,ACTIONB,COST,STATE,TARGET,BAD=6,1,9,12,8,10,14,15
LEVELS=[
 {"name":"Second Use Costs","start":0,"target":3,"mod":7,"a":[1,2],"b":[-1]},
 {"name":"Diversify Early","start":2,"target":0,"mod":8,"a":[2,-1],"b":[1,-2]},
 {"name":"Delayed Effect","start":1,"target":7,"mod":9,"a":[1,3,-1],"b":[-2,2]},
 {"name":"Repetition Debt","start":5,"target":2,"mod":10,"a":[2,-2,3],"b":[-1,4,-2]},
 {"name":"Long Echo","start":3,"target":9,"mod":11,"a":[3,1,-3,2],"b":[-2,4,1]},
 {"name":"Echo Cost","start":7,"target":4,"mod":12,"a":[1,4,-2,3],"b":[-3,2,5,-1]}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=HALL;f[15:32,9:25]=ACTIONA;f[15:32,39:55]=ACTIONB;f[35:39,9:9+g.ca*5]=COST;f[35:39,39:39+g.cb*5]=COST;f[44:49,8:8+g.value*4]=STATE;f[51:54,8:8+g.target*4]=TARGET
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q187(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.value=self.target=self.mod=self.ca=self.cb=0;self.a=self.b=[];self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q187",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,6])
 def on_set_level(self,l):
  s=LEVELS[self.level_index];self.value=s["start"];self.target=s["target"];self.mod=s["mod"];self.a=list(s["a"]);self.b=list(s["b"]);self.ca=self.cb=0;self.failed=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z==1:self.value=(self.value+self.a[min(self.ca,len(self.a)-1)])%self.mod;self.ca=min(self.ca+1,len(self.a)-1)
  elif z==2:self.value=(self.value+self.b[min(self.cb,len(self.b)-1)])%self.mod;self.cb=min(self.cb+1,len(self.b)-1)
  elif z==6:
   if self.value==self.target:self.next_level()
   else:self.failed=True;self.lose()
  else:self.failed=True;self.lose()
  self.complete_action()

"""q089 Persistent Passenger -- track one passenger through visible carrier changes."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,DEPOT,VEHICLE,PASSENGER,GATE,HANDOFF,FLOW,BAD=11,7,10,15,14,12,9,8
LEVELS=[
 {"name":"Carrier Change","count":3,"gate":2,"handoffs":1}, {"name":"Track Passenger","count":4,"gate":1,"handoffs":2},
 {"name":"Rotating Vehicles","count":4,"gate":3,"handoffs":1}, {"name":"Two Transfers","count":5,"gate":2,"handoffs":3},
 {"name":"Hidden Rider","count":6,"gate":4,"handoffs":2}, {"name":"Persistent Passenger","count":7,"gate":5,"handoffs":4}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=DEPOT;n=len(g.vehicles)
  for i,v in enumerate(g.vehicles):x=7+i*(50//n);f[24:39,x:x+8]=VEHICLE+(v%3);f[19:22,x:x+8]=PASSENGER if v==g.passenger and g.revealed else DEPOT
  x=7+g.gate*(50//n);f[43:49,x:x+8]=GATE;f[3:6,8:8+g.handoffs*7]=HANDOFF
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q089(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.vehicles=[];self.passenger=self.gate=self.handoffs=self.done=0;self.revealed=self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q089",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,5,6])
 def on_set_level(self,l):
  s=LEVELS[self.level_index];self.vehicles=list(range(s["count"]));self.passenger=0;self.gate=s["gate"];self.handoffs=s["handoffs"];self.done=0;self.revealed=self.failed=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z==1:self.vehicles=self.vehicles[1:]+self.vehicles[:1]
  elif z==2:self.vehicles=self.vehicles[-1:]+self.vehicles[:-1]
  elif z==3:
   i=self.vehicles.index(self.passenger);self.passenger=self.vehicles[(i+1)%len(self.vehicles)];self.done+=1;self.revealed=False
  elif z==5:self.revealed=True
  elif z==6:
   if self.vehicles[self.gate]==self.passenger and self.done==self.handoffs:self.next_level()
   else:self.failed=True;self.lose()
  self.complete_action()

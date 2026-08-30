"""q047 Sensor Auction -- buy a sufficient, budget-respecting evidence set."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,MARKET,SENSOR,BOUGHT,YES,NO,CAND,CURSOR,BAD=7,1,10,14,9,8,12,11,13
LEVELS=[
 {"name":"Cheapest Distinction","candidates":[0,1],"target":1,"costs":[1,2],"budget":1},
 {"name":"Range or Material","candidates":[0,1,2],"target":2,"costs":[2,1],"budget":1},
 {"name":"Two Clues","candidates":[0,1,2,3],"target":3,"costs":[1,1],"budget":2},
 {"name":"Unequal Prices","candidates":[0,1,2,4,7],"target":4,"costs":[1,3,1],"budget":2},
 {"name":"Connectivity Bid","candidates":[1,2,4,8,11,13],"target":5,"costs":[2,1,2,1],"budget":4},
 {"name":"Sensor Auction","candidates":[0,3,5,6,9,10,12,15],"target":6,"costs":[1,3,2,2],"budget":6}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[7:57,4:60]=MARKET
  for i,c in enumerate(g.costs):
   x=8+i*12;f[13:24,x:x+9]=BOUGHT if i in g.bought else SENSOR;f[9:12,x:x+9]=CURSOR if i==g.sensor else MARKET;f[26:29,x:x+c*2]=NO
   if i in g.bought:f[31:35,x:x+9]=YES if g.candidates[g.target]&(1<<i) else NO
  for i in range(len(g.candidates)):
   x=7+i*7;f[43:50,x:x+5]=CAND;f[52:55,x:x+5]=CURSOR if i==g.hyp else MARKET
  f[3:6,7:7+g.remaining*6]=YES
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q047(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.candidates=self.costs=[];self.target=self.sensor=self.hyp=self.remaining=0;self.bought=set();self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q047",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,5,6])
 def on_set_level(self,l):
  s=LEVELS[self.level_index];self.candidates=list(s["candidates"]);self.costs=list(s["costs"]);self.target=s["target"];self.remaining=s["budget"];self.sensor=self.hyp=0;self.bought=set();self.failed=False
 def identified(self):
  t=self.candidates[self.target];return all(i==self.target or any(((t>>b)&1)!=((v>>b)&1) for b in self.bought) for i,v in enumerate(self.candidates))
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a==1:self.sensor=(self.sensor-1)%len(self.costs)
  elif a==2:self.sensor=(self.sensor+1)%len(self.costs)
  elif a==3:self.hyp=(self.hyp-1)%len(self.candidates)
  elif a==4:self.hyp=(self.hyp+1)%len(self.candidates)
  elif a==5:
   if self.sensor not in self.bought and self.costs[self.sensor]<=self.remaining:self.remaining-=self.costs[self.sensor];self.bought.add(self.sensor)
   else:self.failed=True;self.lose()
  elif a==6:
   if self.hyp==self.target and self.identified():self.next_level()
   else:self.failed=True;self.lose()
  self.complete_action()

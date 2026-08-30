"""q264 Honeycomb Probe -- diagnose hidden transmission across nested clocks."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,HIVE,CELL,NECTAR,PROBE,CLOCK,HYPOTHESIS,BAD=4,11,9,12,14,15,6,8
RESP=[[0,1],[1,1],[1,0]]
LEVELS=[
 {"name":"Direct Scent","model":0,"cycle":2,"budget":4},{"name":"Shared Cause","model":1,"cycle":3,"budget":5},
 {"name":"Coincident Flight","model":2,"cycle":2,"budget":6},{"name":"Outer Clock","model":1,"cycle":4,"budget":5},
 {"name":"Budgeted Repair","model":2,"cycle":3,"budget":6},{"name":"Honeycomb Probe","model":0,"cycle":5,"budget":4}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[5:59,4:60]=HIVE
  for y in (14,27):
   for x in (10,24,38):f[y:y+9,x:x+10]=CELL
  f[42:47,8:8+g.seen*10]=PROBE;f[49:53,8:8+g.outer*9]=CLOCK;f[49:55,42+g.candidate*5:47+g.candidate*5]=HYPOTHESIS
  if g.bad:f[61:64,22:42]=BAD
  return f
class Q264(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.model=self.cycle=self.budget=self.local=self.outer=self.seen=self.candidate=0;self.evidence=[];self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q264",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,5])
 def on_set_level(self,l):x=LEVELS[self.level_index];self.model=x["model"];self.cycle=x["cycle"];self.budget=x["budget"];self.local=self.outer=self.seen=self.candidate=0;self.evidence=[];self.bad=False
 def tick(self):
  self.local+=1
  if self.local==self.cycle:self.local=0;self.outer=(self.outer+1)%3
 def fail(self):self.bad=True;self.lose()
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  self.budget-=1
  if self.budget<0:self.fail()
  elif z in (1,2):self.evidence.append((RESP[self.model][z-1]+self.outer)%3);self.seen|=1<<(z-1);self.tick()
  elif z==3:self.candidate=(self.candidate+1)%3;self.tick()
  elif z==5:
   if self.seen==3 and self.candidate==self.model:self.next_level()
   else:self.fail()
  else:self.fail()
  self.complete_action()

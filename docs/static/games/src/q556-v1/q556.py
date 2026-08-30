"""q556 Crossing Lesson -- infer a conditional demonstration across alternating partial controllers."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,RIVER,DOCK,PASSENGER,MARK,CONTROL,POLICY,BAD=1,7,11,15,14,12,13,8
LEVELS=[
 {"name":"First Lesson","demo":(1,4,2),"policy":0},{"name":"Ineffective Gesture","demo":(2,4,3,1),"policy":1},
 {"name":"Capacity Switch","demo":(1,2,4,3,2),"policy":2},{"name":"Conditional Ferry","demo":(3,4,1,2,4,3),"policy":3},
 {"name":"Disjoint Views","demo":(2,1,4,3,4,1,2),"policy":2},{"name":"Crossing Lesson","demo":(1,4,3,2,4,1,3,2),"policy":1}]
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=RIVER;f[11:24,8:25]=DOCK;f[11:24,39:56]=DOCK
  for i,a in enumerate(g.history[-6:]):f[29+i*4:32+i*4,8:8+a*10]=PASSENGER
  f[49:53,8:8+g.marks[0]*6]=MARK;f[54:58,8:8+g.marks[1]*6]=MARK;f[8:11,8+g.controller*31:25+g.controller*31]=CONTROL
  f[59:62,8:8+g.policy*11]=POLICY
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q556(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.controller=self.policy=0;self.marks=[0,0];self.history=[];self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q556",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):self.controller=self.policy=0;self.marks=[0,0];self.history=[];self.bad=False
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3):self.marks[self.controller]|=1<<((a+self.controller)%3);self.history.append(a)
  elif a==4:self.controller^=1;self.history.append(a)
  elif a==5:self.policy=(self.policy+1)%4
  elif a==6:
   if tuple(self.history)==x["demo"] and all(self.marks) and self.policy==x["policy"]:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()

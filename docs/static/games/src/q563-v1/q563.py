"""q563 Ember Counter -- shape an opponent within a shared action budget."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,KILN,VESSEL,HEAT,TACTIC,RESOURCE,READY,BAD=3,13,9,14,15,10,6,8
LEVELS=[
 {"name":"Shared Budget","desired":1,"window":2,"budget":4},{"name":"Recent Heat","desired":2,"window":2,"budget":4},
 {"name":"Three-Step Counter","desired":3,"window":3,"budget":5},{"name":"Shape Then Exploit","desired":1,"window":3,"budget":5},
 {"name":"Repair Tradeoff","desired":2,"window":4,"budget":6},{"name":"Ember Counter","desired":3,"window":4,"budget":6}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=KILN
  for i in range(3):x=9+i*17;f[16:31,x:x+11]=TACTIC if i+1==g.current else VESSEL
  f[35:40,8:8+len(g.history)*6]=HEAT;f[44:48,8:8+g.resource*8]=RESOURCE;f[50:54,34:56]=READY if g.stage else KILN
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q563(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.desired=self.window=self.resource=self.current=self.stage=0;self.history=[];self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q563",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4])
 def on_set_level(self,l):
  s=LEVELS[self.level_index];self.desired=s["desired"];self.window=s["window"];self.resource=s["budget"];self.current=1;self.stage=0;self.history=[];self.failed=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  self.resource-=1
  if self.resource<0:self.failed=True;self.lose()
  elif z in (1,2,3) and self.stage==0:self.history.append(z);self.current=self.history[-1]
  elif z==4 and self.stage==0:
   if len(self.history)>=self.window and len(set(self.history[-self.window:]))==1 and self.current==self.desired:self.stage=1
   else:self.failed=True;self.lose()
  elif z in (1,2,3) and self.stage==1:
   if z==(self.current%3)+1:self.next_level()
   else:self.failed=True;self.lose()
  else:self.failed=True;self.lose()
  self.complete_action()

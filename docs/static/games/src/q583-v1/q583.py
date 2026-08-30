"""q583 Impeller Counter -- shape a stable opponent tactic and stop sampling safely."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,TURBINE,BLADE,WAKE,TACTIC,SAMPLE,STOP,BAD=2,11,9,12,15,10,6,8
LEVELS=[
 {"name":"Stable Tactic","desired":1,"window":2},{"name":"Recent Wake","desired":2,"window":2},
 {"name":"Three Samples","desired":3,"window":3},{"name":"Stop When Certain","desired":1,"window":3},
 {"name":"Costly Extra Sample","desired":2,"window":4},{"name":"Impeller Counter","desired":3,"window":4}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=TURBINE
  for i in range(3):x=9+i*17;f[16:31,x:x+11]=TACTIC if i+1==g.current else BLADE
  f[35:40,8:8+len(g.history)*6]=WAKE;f[44:49,8:8+g.cost*8]=SAMPLE;f[50:54,34:56]=STOP if g.stage else TURBINE
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q583(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.desired=self.window=self.current=self.cost=self.stage=0;self.history=[];self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q583",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,5])
 def on_set_level(self,l):
  s=LEVELS[self.level_index];self.desired=s["desired"];self.window=s["window"];self.current=1;self.cost=self.stage=0;self.history=[];self.failed=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z in (1,2,3) and self.stage==0:self.history.append(z);self.current=self.history[-1]
  elif z==5 and self.stage==0:self.cost+=1;self.history.append(self.history[-1] if self.history else 1);self.current=self.history[-1]
  elif z==4 and self.stage==0:
   if len(self.history)>=self.window and len(set(self.history[-self.window:]))==1 and self.current==self.desired:self.stage=1
   else:self.failed=True;self.lose()
  elif z in (1,2,3) and self.stage==1:
   if z==(self.current%3)+1:self.next_level()
   else:self.failed=True;self.lose()
  else:self.failed=True;self.lose()
  self.complete_action()

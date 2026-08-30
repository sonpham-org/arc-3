"""q127 Policy Mirror -- defeated opponents adopt the successful strategy transformation."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,ARENA,OPPONENT,POLICY,STRATEGY,SHIFT,DONE,BAD=13,1,12,15,9,10,14,8
LEVELS=[
 {"name":"Adopt the Winner","route":[1,2]}, {"name":"Second Strategy","route":[2,4,1]},
 {"name":"Mirror Policy","route":[3,1,4,2]}, {"name":"Transfer Again","route":[1,3,2,4,1]},
 {"name":"No Brute Persistence","route":[4,2,1,3,4,2]}, {"name":"Policy Mirror","route":[2,4,1,3,2,1,4]}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=ARENA;f[16:34,8:24]=OPPONENT;f[20:26,31:31+g.policy*6]=POLICY
  for i in range(len(g.route)):x=8+i*7;f[42:49,x:x+5]=DONE if i<g.progress else STRATEGY
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q127(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.route=[];self.progress=self.policy=0;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q127",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4])
 def on_set_level(self,l):self.route=list(LEVELS[self.level_index]["route"]);self.progress=self.policy=0;self.failed=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z!=self.route[self.progress] or z==self.policy:self.failed=True;self.lose()
  else:
   self.policy=z;self.progress+=1
   if self.progress==len(self.route):self.next_level()
  self.complete_action()

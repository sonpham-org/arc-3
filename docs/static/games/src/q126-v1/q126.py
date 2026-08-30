"""q126 Copycat Trap -- use a rival's one-turn delayed imitation as an actuator."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,ARENA,PLAYER,RIVAL,TARGET,ACTUATOR,DONE,BAD=13,1,9,12,14,10,6,8
LEVELS=[
 {"name":"Delayed Copy","target":[1,4]}, {"name":"Prime the Rival","target":[2,3,1]},
 {"name":"Remote Actuator","target":[4,1,3,2]}, {"name":"Exploit Imitation","target":[1,3,2,4,1]},
 {"name":"Delayed Control","target":[3,1,4,2,3,1]}, {"name":"Copycat Trap","target":[2,4,1,3,2,1,4]}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=ARENA;f[17:29,8:21]=PLAYER;f[35:47,8:21]=RIVAL;f[20:25,28:28+g.previous*5]=ACTUATOR
  for i,t in enumerate(g.target):x=28+i*4;f[36:43,x:x+3]=DONE if i<g.progress else TARGET
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q126(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.target=[];self.progress=self.previous=0;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q126",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4])
 def on_set_level(self,l):self.target=list(LEVELS[self.level_index]["target"]);self.progress=self.previous=0;self.failed=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if self.previous:
   if self.previous!=self.target[self.progress]:self.failed=True;self.lose()
   else:
    self.progress+=1
    if self.progress==len(self.target):self.next_level();self.complete_action();return
  self.previous=z;self.complete_action()

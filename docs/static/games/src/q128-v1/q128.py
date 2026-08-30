"""q128 Adaptive Patrol -- recent visits diffuse patrol density toward repeated regions."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,FIELD,PLAYER,PATROL,RECENT,GOAL,DONE,BAD=13,1,9,8,15,14,10,6
LEVELS=[
 {"name":"Patrol Learns","route":[1,2]}, {"name":"Vary the Route","route":[1,3,2]},
 {"name":"Density Shift","route":[2,4,1,3]}, {"name":"Avoid Repetition","route":[1,3,2,4,1]},
 {"name":"Diffuse Attention","route":[4,2,1,3,4,2]}, {"name":"Adaptive Patrol","route":[2,4,1,3,2,1,4]}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=FIELD;f[17:31,8:22]=PLAYER
  for i,d in enumerate(g.density):x=29+i*7;f[38-d*4:40,x:x+5]=PATROL;f[43:47,x:x+5]=RECENT if i+1==g.last else FIELD
  for i in range(len(g.route)):x=8+i*7;f[49:54,x:x+5]=DONE if i<g.progress else GOAL
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q128(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.route=[];self.density=[0]*4;self.progress=self.last=0;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q128",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4])
 def on_set_level(self,l):self.route=list(LEVELS[self.level_index]["route"]);self.density=[0]*4;self.progress=self.last=0;self.failed=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z not in (1,2,3,4):self.failed=True;self.lose();self.complete_action();return
  self.density=[max(0,d-1) for d in self.density];self.density[z-1]=min(3,self.density[z-1]+2);self.last=z
  if z!=self.route[self.progress] or self.density[z-1]>=3:self.failed=True;self.lose()
  else:
   self.progress+=1
   if self.progress==len(self.route):self.next_level()
  self.complete_action()

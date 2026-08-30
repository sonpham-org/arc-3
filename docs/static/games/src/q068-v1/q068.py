"""q068 Blind Captain -- limited observer pulses guide an instrument-only controller."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,BRIDGE,CAPTAIN,OBSERVER,SIGNAL,DONE,BUDGET,BAD=7,2,9,14,12,10,11,8
LEVELS=[
 {"name":"One Pulse","route":[4,4],"pulses":1}, {"name":"Remember Heading","route":[1,1,4],"pulses":2},
 {"name":"Terrain Report","route":[2,2,4,4],"pulses":2}, {"name":"Sparse Signals","route":[3,3,1,1,4],"pulses":3},
 {"name":"Instrument Memory","route":[4,4,2,2,3,3],"pulses":3}, {"name":"Blind Captain","route":[1,1,4,4,2,2,3,3],"pulses":4}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=BRIDGE;f[16:31,8:22]=OBSERVER;f[35:50,8:22]=CAPTAIN
  f[20:26,29:29+g.signal*6]=SIGNAL if g.signal else BRIDGE
  for i in range(len(g.route)):x=30+i*4;f[39:45,x:x+3]=DONE if i<g.progress else CAPTAIN
  f[3:6,7:7+g.pulses*8]=BUDGET
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q068(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.route=[];self.progress=self.pulses=self.signal=0;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q068",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,5])
 def on_set_level(self,l):
  s=LEVELS[self.level_index];self.route=list(s["route"]);self.progress=0;self.pulses=s["pulses"];self.signal=0;self.failed=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z==5:
   if self.pulses:self.pulses-=1;self.signal=self.route[self.progress]
   else:self.failed=True;self.lose()
  elif z in (1,2,3,4):
   if z!=self.route[self.progress]:self.failed=True;self.lose()
   else:
    self.progress+=1;self.signal=0
    if self.progress==len(self.route):self.next_level()
  self.complete_action()

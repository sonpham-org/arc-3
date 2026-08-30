"""q066 Beacon Relay -- position local observers to transmit one global direction."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,FIELD,BEACON,AGENT,SIGNAL,DONE,BAD=14,1,12,9,10,6,8
LEVELS=[
 {"name":"Nearest Beacon","signals":[1,4]}, {"name":"Two Agents","signals":[2,4,1]},
 {"name":"Relay Turn","signals":[3,1,4,2]}, {"name":"Local Views","signals":[4,2,3,1,4]},
 {"name":"Long Relay","signals":[1,3,2,4,1,2]}, {"name":"Beacon Relay","signals":[2,4,1,3,2,1,4]}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:55,4:60]=FIELD
  for i,s in enumerate(g.signals):x=7+i*8;f[15:23,x:x+6]=BEACON;f[28:36,x:x+6]=AGENT;f[30:33,x:x+s]=SIGNAL;f[42:48,x:x+6]=DONE if i<g.progress else SIGNAL
  if g.failed:f[59:63,25:39]=BAD
  return f
class Q066(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.signals=[];self.progress=0;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q066",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4])
 def on_set_level(self,l):self.signals=list(LEVELS[self.level_index]["signals"]);self.progress=0;self.failed=False
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a!=self.signals[self.progress]:self.failed=True;self.lose()
  else:
   self.progress+=1
   if self.progress==len(self.signals):self.next_level()
  self.complete_action()

"""q134 Relay Syntax -- compose learnable local signal transforms across agents."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,CHANNEL,AGENT,SIGNAL,OUTPUT,DONE,BAD=7,10,12,9,6,14,8
LEVELS=[
 {"name":"One Relay","rules":[1],"signals":[0,1]}, {"name":"Two Relays","rules":[1,3],"signals":[0,2,3]},
 {"name":"Canceling Rules","rules":[1,1,2],"signals":[1,3,0,2]}, {"name":"Relay Chain","rules":[3,1,2],"signals":[0,1,2,3,1]},
 {"name":"Local Syntax","rules":[2,3,1,1],"signals":[3,0,2,1,3,2]}, {"name":"Relay Syntax","rules":[1,2,3,1,2],"signals":[0,3,1,2,0,2,3]}]
def relay(x,rules):
 for r in rules:x=(x+r)%4
 return x+1
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[7:56,4:60]=CHANNEL
  for i,r in enumerate(g.rules):x=10+i*10;f[13:23,x:x+7]=AGENT;f[16:19,x:x+r+2]=SIGNAL
  for i,s in enumerate(g.signals):x=7+i*8;f[38:46,x:x+6]=DONE if i<g.progress else OUTPUT;f[40:43,x:x+s+2]=SIGNAL
  if g.failed:f[59:63,25:39]=BAD
  return f
class Q134(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.rules=self.signals=[];self.progress=0;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q134",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4])
 def on_set_level(self,l):s=LEVELS[self.level_index];self.rules=list(s["rules"]);self.signals=list(s["signals"]);self.progress=0;self.failed=False
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a!=relay(self.signals[self.progress],self.rules):self.failed=True;self.lose()
  else:
   self.progress+=1
   if self.progress==len(self.signals):self.next_level()
  self.complete_action()

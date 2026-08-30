"""q573 Murmuration Counter -- shape a legible adaptive tactic and verify parity."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,AVIARY,FLOCK,WIND,TACTIC,PARITY,READY,BAD=7,14,9,12,15,10,6,8
LEVELS=[
 {"name":"Shape the Opponent","desired":1,"window":2},{"name":"Recent Treatment","desired":2,"window":2},
 {"name":"Three-Step Memory","desired":3,"window":3},{"name":"Misleading Observation","desired":1,"window":3},
 {"name":"Redundant Parity","desired":2,"window":4},{"name":"Murmuration Counter","desired":3,"window":4}]
def tactic(history,window):return(sum(history[-window:])%3)+1
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=AVIARY
  for i in range(3):x=9+i*17;f[17:30,x:x+11]=TACTIC if i+1==g.current else FLOCK
  f[34:39,8:8+len(g.history)*6]=WIND;f[43:48,8:24]=PARITY if g.parity else AVIARY;f[49:53,34:56]=READY if g.stage else AVIARY
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q573(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.desired=self.window=self.current=self.parity=self.stage=0;self.history=[];self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q573",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,5])
 def on_set_level(self,l):
  s=LEVELS[self.level_index];self.desired=s["desired"];self.window=s["window"];self.current=1;self.parity=self.stage=0;self.history=[];self.failed=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z in (1,2,3) and self.stage==0:self.history.append(z);self.current=tactic(self.history,self.window)
  elif z==4 and self.stage==0:self.parity=1-self.parity
  elif z==5 and self.stage==0:
   if len(self.history)>=self.window and self.current==self.desired and self.parity==sum(self.history)%2:self.stage=1
   else:self.failed=True;self.lose()
  elif z in (1,2,3) and self.stage==1:
   if z==(self.current%3)+1:self.next_level()
   else:self.failed=True;self.lose()
  else:self.failed=True;self.lose()
  self.complete_action()

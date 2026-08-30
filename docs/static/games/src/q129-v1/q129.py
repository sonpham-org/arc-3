"""q129 Decoy Learner -- teach an adaptive guard a false preference before committing."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,GARDEN,OBJECT,DECOY,TARGET,GUARD,LEARNED,BAD=13,10,12,9,14,8,15,6
LEVELS=[
 {"name":"Teach a Decoy","target":1,"lessons":1},{"name":"False Preference","target":2,"lessons":2},
 {"name":"Break the Tie","target":3,"lessons":3},{"name":"Delayed Commitment","target":4,"lessons":4},
 {"name":"Adaptive Protection","target":2,"lessons":5},{"name":"Decoy Learner","target":3,"lessons":6}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=GARDEN
  for i in range(4):x=8+i*13;f[20:33,x:x+9]=TARGET if i+1==g.target else OBJECT;h=min(10,g.attention[i]*2);f[37-h:39,x+2:x+7]=LEARNED
  if g.stage:f[43:49,8+(g.protected-1)*13:17+(g.protected-1)*13]=GUARD
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q129(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.target=self.lessons=self.stage=self.protected=0;self.attention=[0]*4;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q129",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,5])
 def on_set_level(self,l):
  s=LEVELS[self.level_index];self.target=s["target"];self.lessons=s["lessons"];self.stage=0;self.protected=1;self.attention=[0]*4;self.failed=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z in (1,2,3,4) and self.stage==0:self.attention[z-1]+=1
  elif z==5 and self.stage==0:
   if sum(self.attention)<self.lessons:self.failed=True;self.lose()
   else:self.protected=max(range(4),key=lambda i:(self.attention[i],-i))+1;self.stage=1
  elif z in (1,2,3,4) and self.stage==1:
   if z==self.target and z!=self.protected:self.next_level()
   else:self.failed=True;self.lose()
  else:self.failed=True;self.lose()
  self.complete_action()

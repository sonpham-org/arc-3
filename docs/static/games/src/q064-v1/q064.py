"""q064 Scout Gestures -- ground returning scouts' motion patterns as hidden findings."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,CAMP,SCOUT,GESTURE,BRANCH,DONE,BAD=14,1,9,12,10,6,8
LEVELS=[
 {"name":"One Gesture","mapping":[2,1,4,3],"reports":[0,1]}, {"name":"Hidden Branches","mapping":[3,4,1,2],"reports":[2,0,3]},
 {"name":"Scout Pair","mapping":[4,2,3,1],"reports":[1,3,0,2]}, {"name":"Motion Phrase","mapping":[1,3,2,4],"reports":[3,2,0,1,3]},
 {"name":"Remote Findings","mapping":[2,4,3,1],"reports":[0,2,1,3,2,0]}, {"name":"Scout Gestures","mapping":[3,1,4,2],"reports":[2,0,3,1,2,3,0]}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[7:56,4:60]=CAMP
  for i,v in enumerate(g.mapping):x=9+i*13;f[13:20,x:x+7]=SCOUT;f[22:26,x:x+v+2]=GESTURE
  for i,r in enumerate(g.reports):x=7+i*8;f[37:44,x:x+6]=BRANCH;f[46:51,x:x+6]=DONE if i<g.progress else GESTURE;f[47:50,x:x+r+2]=SCOUT
  if g.failed:f[59:63,25:39]=BAD
  return f
class Q064(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.mapping=[];self.reports=[];self.progress=0;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q064",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4])
 def on_set_level(self,l):s=LEVELS[self.level_index];self.mapping=list(s["mapping"]);self.reports=list(s["reports"]);self.progress=0;self.failed=False
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a!=self.mapping[self.reports[self.progress]]:self.failed=True;self.lose()
  else:
   self.progress+=1
   if self.progress==len(self.reports):self.next_level()
  self.complete_action()

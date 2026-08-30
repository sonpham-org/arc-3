"""q196 Event Order -- causal event boundaries transfer despite changing animation durations."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,STAGE,EVENT,DURATION,SELECTED,DONE,BOUNDARY,BAD=2,7,9,12,15,14,10,8
LEVELS=[
 {"name":"Ignore Duration","events":[1,4],"durations":[3,1]}, {"name":"Event Boundary","events":[2,3,1],"durations":[1,4,2]},
 {"name":"Order Transfer","events":[4,1,3,2],"durations":[4,1,3,2]}, {"name":"Variable Animation","events":[1,3,2,4,1],"durations":[2,5,1,4,3]},
 {"name":"Causal Sequence","events":[3,1,4,2,3,1],"durations":[5,1,2,4,1,3]}, {"name":"Event Order","events":[2,4,1,3,2,1,4],"durations":[1,5,2,4,3,1,5]}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=STAGE;k=min(g.progress,len(g.events)-1);f[17:29,8:8+g.events[k]*9]=EVENT;f[33:38,8:8+g.durations[k]*7]=DURATION;f[41:45,8:56]=SELECTED if g.selected else BOUNDARY
  for i in range(len(g.events)):x=8+i*7;f[49:54,x:x+5]=DONE if i<g.progress else EVENT
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q196(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.events=self.durations=[];self.progress=self.selected=0;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q196",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,5])
 def on_set_level(self,l):
  s=LEVELS[self.level_index];self.events=list(s["events"]);self.durations=list(s["durations"]);self.progress=self.selected=0;self.failed=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z in (1,2,3,4):self.selected=z
  elif z==5:
   if self.selected!=self.events[self.progress]:self.failed=True;self.lose()
   else:
    self.progress+=1;self.selected=0
    if self.progress==len(self.events):self.next_level()
  self.complete_action()

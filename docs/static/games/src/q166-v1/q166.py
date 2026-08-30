"""q166 Checkpoint Choice -- preserve state at a calibrated point before risky experiments."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,PATH,SAFE,RISK,CHECKPOINT,GOAL,DONE,BAD=7,1,10,8,15,14,6,12
LEVELS=[
 {"name":"Before the Risk","route":[1,2],"checkpoint":1}, {"name":"Not Too Early","route":[1,1,2],"checkpoint":2},
 {"name":"Confidence Placement","route":[2,1,2,2],"checkpoint":2}, {"name":"Preserve Evidence","route":[1,2,1,2,1],"checkpoint":3},
 {"name":"One Saved State","route":[2,2,1,2,1,1],"checkpoint":4}, {"name":"Checkpoint Choice","route":[1,2,2,1,2,1,1],"checkpoint":5}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=PATH
  for i,a in enumerate(g.route):x=7+i*7;f[25:38,x:x+5]=DONE if i<g.progress else RISK if a==2 else SAFE;f[17:21,x:x+5]=CHECKPOINT if g.saved==i else PATH
  f[44:49,48:57]=GOAL
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q166(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.route=[];self.required=self.progress=0;self.saved=-1;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q166",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,5,6])
 def on_set_level(self,l):
  s=LEVELS[self.level_index];self.route=list(s["route"]);self.required=s["checkpoint"];self.progress=0;self.saved=-1;self.failed=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z==5:
   if self.saved<0:self.saved=self.progress
   else:self.failed=True;self.lose()
  elif z in (1,2):
   if self.progress>=len(self.route) or z!=self.route[self.progress]:self.failed=True;self.lose()
   else:self.progress+=1
  elif z==6:
   if self.progress==len(self.route) and self.saved==self.required:self.next_level()
   else:self.failed=True;self.lose()
  self.complete_action()

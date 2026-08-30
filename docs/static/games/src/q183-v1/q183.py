"""q183 Delayed Escort -- early assistance changes a companion's later policy."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,HALL,ROOM,HELP,IGNORE,ESCORT,GOAL,BAD=1,10,3,14,8,9,6,13
LEVELS=[
 {"name":"Help Returns","choices":[1],"need":1}, {"name":"Do Not Overhelp","choices":[1,0],"need":1},
 {"name":"Delayed Policy","choices":[0,1,1],"need":2}, {"name":"False Reward","choices":[1,0,1,0],"need":2},
 {"name":"Long Escort","choices":[0,1,1,0,1],"need":3}, {"name":"Delayed Escort","choices":[1,0,1,1,0,1],"need":4}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:55,4:60]=HALL
  for i,c in enumerate(g.choices):
   x=7+i*8;f[18:31,x:x+6]=ROOM;f[35:43,x:x+6]=ESCORT if i>=g.stage else HELP if c else IGNORE
  f[47:52,7:7+g.helped*7]=GOAL
  if g.failed:f[59:63,25:39]=BAD
  return f
class Q183(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.choices=[];self.need=self.stage=self.helped=0;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q183",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,6])
 def on_set_level(self,l):s=LEVELS[self.level_index];self.choices=list(s["choices"]);self.need=s["need"];self.stage=self.helped=0;self.failed=False
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if self.stage<len(self.choices) and a in (1,2):
   choice=a==1
   if choice!=bool(self.choices[self.stage]):self.failed=True;self.lose()
   else:self.helped+=choice;self.stage+=1
  elif a==6 and self.stage==len(self.choices):
   if self.helped==self.need:self.next_level()
   else:self.failed=True;self.lose()
  else:self.failed=True;self.lose()
  self.complete_action()

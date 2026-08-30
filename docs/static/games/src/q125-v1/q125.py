"""q125 Escalation Ladder -- alternate retreat and counter to control adaptive aggression."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,ARENA,LADDER,AGGRESS,COUNTER,TARGET,DONE,BAD=8,1,3,13,9,14,10,5
LEVELS=[
 {"name":"One Escalation","windows":[1]}, {"name":"Controlled Retreat","windows":[2,1]},
 {"name":"Alternating Counter","windows":[1,2,1]}, {"name":"Escalation Steps","windows":[2,1,2,1]},
 {"name":"Avoid Panic","windows":[1,2,2,1,2]}, {"name":"Escalation Ladder","windows":[2,1,2,2,1,2]}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:55,4:60]=ARENA
  for i,w in enumerate(g.windows):x=7+i*8;f[16:27,x:x+6]=DONE if i<g.progress else LADDER;f[31:35,x:x+w*3]=TARGET
  f[43:49,8:8+g.aggression*12]=AGGRESS
  if g.failed:f[59:63,25:39]=BAD
  return f
class Q125(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.windows=[];self.progress=self.aggression=0;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q125",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3])
 def on_set_level(self,l):self.windows=list(LEVELS[self.level_index]["windows"]);self.progress=self.aggression=0;self.failed=False
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a==1:self.aggression=min(3,self.aggression+1)
  elif a==3:self.aggression=max(0,self.aggression-1)
  elif a==2:
   if self.aggression==self.windows[self.progress]:
    self.progress+=1;self.aggression=0
    if self.progress==len(self.windows):self.next_level()
   else:self.failed=True;self.lose()
  else:self.failed=True;self.lose()
  self.complete_action()

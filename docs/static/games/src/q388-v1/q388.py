"""q388 Breakwater Delegation -- merge complementary marked views before a dormant effect."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,HARBOR,SKIFF,CHANNEL,MARK,CONTROL,SUBGOAL,BAD=8,10,12,14,15,13,6,3
LEVELS=[
 {"name":"Complementary Views","clues":[0,1]},{"name":"Persistent Marks","clues":[1,1]},
 {"name":"Alternating Control","clues":[1,0]},{"name":"Dormant Gate","clues":[0,0]},
 {"name":"Two Subgoals","clues":[1,0]},{"name":"Breakwater Delegation","clues":[0,1]}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[5:59,4:60]=HARBOR;f[14:25,8:23]=SKIFF;f[14:25,41:56]=SKIFF;f[29:34,8:56]=CHANNEL
  for i in range(4):
   if g.marks&(1<<i):f[39:44,8+i*12:17+i*12]=MARK
  f[48:53,8+g.controller*32:24+g.controller*32]=CONTROL;f[55:58,8:8+g.stage*15]=SUBGOAL
  if g.bad:f[61:64,22:42]=BAD
  return f
class Q388(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.controller=self.marks=self.stage=self.candidate=0;self.first=None;self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q388",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,5,6])
 def on_set_level(self,l):self.controller=self.marks=self.stage=self.candidate=0;self.first=None;self.bad=False
 def fail(self):self.bad=True;self.lose()
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  clues=LEVELS[self.level_index]["clues"]
  if z in (1,2):
   value=clues[self.controller] if z==1 else 1-clues[self.controller];self.marks|=1<<(self.controller*2+value)
   if self.first is None:self.first=value
  elif z==3:self.controller=1-self.controller
  elif z==4 and all(self.marks&(1<<(i*2+clues[i])) for i in range(2)) and self.stage<2:self.stage+=1
  elif z==5:self.candidate=1-self.candidate
  elif z==6:
   if self.stage==2 and self.first==clues[0] and self.candidate==(clues[0]^clues[1]):self.next_level()
   else:self.fail()
  else:self.fail()
  self.complete_action()

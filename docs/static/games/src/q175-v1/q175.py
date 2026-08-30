"""q175 Pendulum Phase -- time transfers using both pendulum position and momentum phase."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,CHAMBER,ARC,BOB,MOMENTUM,PLATFORM,DONE,BAD=14,1,3,9,10,12,6,8
LEVELS=[
 {"name":"First Transfer","period":4,"windows":[1]}, {"name":"Return Swing","period":4,"windows":[3,1]},
 {"name":"Momentum Side","period":6,"windows":[2,5]}, {"name":"Moving Platforms","period":6,"windows":[4,1,5]},
 {"name":"Phase Sequence","period":8,"windows":[3,7,2]}, {"name":"Pendulum Phase","period":8,"windows":[6,1,5,2]}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[7:56,4:60]=CHAMBER;f[13:37,8:56]=ARC;x=10+(g.phase*42//max(1,g.period-1));f[28:37,x:x+7]=BOB;f[39:43,x-2:x+9]=MOMENTUM
  for i,w in enumerate(g.windows):f[46:51,8+i*12:17+i*12]=DONE if i<g.progress else PLATFORM
  if g.failed:f[59:63,25:39]=BAD
  return f
class Q175(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.period=self.phase=self.progress=0;self.windows=[];self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q175",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[5,6])
 def on_set_level(self,l):s=LEVELS[self.level_index];self.period=s["period"];self.windows=list(s["windows"]);self.phase=self.progress=0;self.failed=False
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a==5:self.phase=(self.phase+1)%self.period
  elif a==6:
   if self.phase==self.windows[self.progress]:
    self.progress+=1;self.phase=(self.phase+2)%self.period
    if self.progress==len(self.windows):self.next_level()
   else:self.failed=True;self.lose()
  else:self.failed=True;self.lose()
  self.complete_action()

"""q174 Resonant Steps -- accumulate oscillation with correctly phased pushes."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,CHAMBER,WAVE,BODY,PUSH,TARGET,BAD=14,1,10,3,9,6,8
LEVELS=[
 {"name":"First Resonance","period":2,"phase":0,"target":2}, {"name":"Wait for Phase","period":3,"phase":1,"target":2},
 {"name":"Three Pushes","period":3,"phase":2,"target":3}, {"name":"Long Cycle","period":4,"phase":1,"target":3},
 {"name":"Build Amplitude","period":5,"phase":3,"target":4}, {"name":"Resonant Steps","period":6,"phase":4,"target":4}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:55,4:60]=CHAMBER
  for i in range(g.period):f[15:21,8+i*8:14+i*8]=PUSH if i==g.phase else WAVE
  f[29:38,28-g.amp*3:36+g.amp*3]=BODY;f[44:49,8:8+g.target*10]=TARGET
  if g.failed:f[59:63,25:39]=BAD
  return f
class Q174(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.period=self.phase=self.target=self.t=self.amp=0;self.budget=50;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q174",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,5])
 def on_set_level(self,l):s=LEVELS[self.level_index];self.period=s["period"];self.phase=s["phase"];self.target=s["target"];self.t=self.amp=0;self.budget=50;self.failed=False
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  self.budget-=1
  if a==1:self.amp=self.amp+1 if self.t==self.phase else max(0,self.amp-1);self.t=(self.t+1)%self.period
  elif a==2:self.t=(self.t+1)%self.period
  elif a==5:
   if self.amp>=self.target:self.next_level()
   else:self.failed=True;self.lose()
  else:self.failed=True;self.lose()
  if self.budget<=0:self.failed=True;self.lose()
  self.complete_action()

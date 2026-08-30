"""q800 Workbench Rhythm -- chunk events, interrupt a window, and repay the helper."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,WORKSHOP,TOOL,FIXTURE,RHYTHM,WINDOW,DEBT,BAD=9,4,12,10,15,6,14,8
LEVELS=[
 {"name":"Event Window","helper":1,"period":4,"window":2},{"name":"Chunk the Routine","helper":2,"period":5,"window":4},
 {"name":"Scaled Interval","helper":1,"period":6,"window":1},{"name":"State Interrupt","helper":2,"period":7,"window":5},
 {"name":"Delayed Helper Debt","helper":1,"period":8,"window":6},{"name":"Workbench Rhythm","helper":2,"period":9,"window":7}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=WORKSHOP;f[16:31,8:22]=TOOL;f[16:31,42:56]=FIXTURE;f[35:40,8:8+g.phase*5]=RHYTHM;f[43:48,8:8+g.window*5]=WINDOW
  if g.obligation:f[50:54,34:56]=DEBT
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q800(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.helper=self.period=self.window=self.phase=self.stage=0;self.obligation=None;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q800",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,5])
 def on_set_level(self,l):
  s=LEVELS[self.level_index];self.helper=s["helper"];self.period=s["period"];self.window=s["window"];self.phase=self.stage=0;self.obligation=None;self.failed=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if self.stage==0 and z in (1,2):self.obligation=z;self.stage=1
  elif self.stage==1 and z==4:self.phase=(self.phase+3)%self.period
  elif self.stage==1 and z==5:self.phase=(self.phase+1)%self.period
  elif self.stage==1 and z==3:
   if self.phase==self.window:self.stage=2
   else:self.failed=True;self.lose()
  elif self.stage==2 and z in (1,2):
   if z==self.obligation==self.helper:self.next_level()
   else:self.failed=True;self.lose()
  else:self.failed=True;self.lose()
  self.complete_action()

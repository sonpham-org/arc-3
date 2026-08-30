"""q738 Escapement Gradient -- conserve a phased distribution after diagnosing one fault."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,TOWER,WEIGHT,GEAR,PROBE,PHASE,TARGET,BAD=7,3,9,12,15,10,14,8
LEVELS=[
 {"name":"Probe the Fault","start":[2,1,0],"target":[1,1,1],"phase":1,"fault":0},
 {"name":"Mutually Exclusive","start":[3,0,1],"target":[1,2,1],"phase":2,"fault":1},
 {"name":"Conserved Gradient","start":[1,3,0],"target":[2,1,1],"phase":1,"fault":0},
 {"name":"Nested Gear Phase","start":[4,0,1],"target":[1,2,2],"phase":3,"fault":1},
 {"name":"Capacity Threshold","start":[2,3,1],"target":[3,1,2],"phase":2,"fault":0},
 {"name":"Escapement Gradient","start":[5,1,1],"target":[2,3,2],"phase":3,"fault":1}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=TOWER
  for i,v in enumerate(g.values):x=9+i*17;f[17:40,x:x+11]=GEAR;f[35-v*4:38,x+3:x+8]=WEIGHT;f[44:48,x:x+11]=TARGET if v==g.target[i] else TOWER
  f[3:6,8:8+g.phase*10]=PHASE
  if g.probed:f[49:53,34:56]=PROBE
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q738(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.values=self.target=[];self.target_phase=self.fault=self.cursor=self.phase=0;self.probed=self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q738",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,5,6])
 def on_set_level(self,l):
  s=LEVELS[self.level_index];self.values=list(s["start"]);self.target=list(s["target"]);self.target_phase=s["phase"];self.fault=s["fault"];self.cursor=self.phase=0;self.probed=self.failed=False
 def step(self):
  z=self.action.id.value;nxt=(self.cursor+(2 if self.fault else 1))%3
  if z==0:self.complete_action();return
  if z==5:self.probed=True
  elif not self.probed:self.failed=True;self.lose()
  elif z==1 and self.values[self.cursor]>0:self.values[self.cursor]-=1;self.values[nxt]+=1
  elif z==2 and self.values[nxt]>0:self.values[nxt]-=1;self.values[self.cursor]+=1
  elif z==3:self.cursor=(self.cursor+1)%3
  elif z==4:self.phase=(self.phase+1)%4
  elif z==6:
   if self.values==self.target and self.phase==self.target_phase:self.next_level()
   else:self.failed=True;self.lose()
  else:self.failed=True;self.lose()
  self.complete_action()

"""q197 Phase Landmark -- anchor repetitive cycles on one distinctive configuration."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,STAGE,CYCLEA,CYCLEB,LANDMARK,TARGET,PHASE,BAD=2,7,9,12,14,15,10,8
LEVELS=[
 {"name":"Find the Landmark","mods":[3,4],"start":[0,0],"target":[1,2]},
 {"name":"Offset Cycles","mods":[4,5],"start":[1,3],"target":[3,1]},
 {"name":"Long Synchrony","mods":[5,6],"start":[2,4],"target":[0,3]},
 {"name":"Repetitive Phase","mods":[6,7],"start":[3,5],"target":[1,0]},
 {"name":"Landmark Anchor","mods":[7,8],"start":[4,6],"target":[0,5]},
 {"name":"Phase Landmark","mods":[8,9],"start":[5,7],"target":[2,0]}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=STAGE;f[17:34,8:26]=LANDMARK if g.phase[0]==0 else CYCLEA;f[17:34,38:56]=LANDMARK if g.phase[1]==0 else CYCLEB;f[38:42,8:8+g.phase[0]*5]=PHASE;f[45:49,8:8+g.phase[1]*5]=PHASE;f[52:55,8:8+sum(g.target)*3]=TARGET
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q197(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.mods=self.phase=self.target=[];self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q197",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,5,6])
 def on_set_level(self,l):
  s=LEVELS[self.level_index];self.mods=list(s["mods"]);self.phase=list(s["start"]);self.target=list(s["target"]);self.failed=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z==1:self.phase[0]=(self.phase[0]+1)%self.mods[0]
  elif z==2:self.phase[1]=(self.phase[1]+1)%self.mods[1]
  elif z==5:self.phase=[(p+1)%m for p,m in zip(self.phase,self.mods)]
  elif z==6:
   if self.phase==self.target:self.next_level()
   else:self.failed=True;self.lose()
  self.complete_action()

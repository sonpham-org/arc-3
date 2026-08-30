"""q178 Wave Junction -- align source phases so interference peaks at a receiver."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,LAB,SOURCEA,SOURCEB,WAVE,RECEIVER,TARGET,BAD=11,1,9,12,15,10,14,8
LEVELS=[
 {"name":"Phase Match","mods":[3,4],"start":[0,0],"target":[1,2]}, {"name":"Reflected Pulse","mods":[4,5],"start":[1,3],"target":[3,1]},
 {"name":"Junction Timing","mods":[5,6],"start":[2,4],"target":[0,3]}, {"name":"Interference Peak","mods":[6,7],"start":[3,5],"target":[1,0]},
 {"name":"Network Phase","mods":[7,8],"start":[4,6],"target":[0,5]}, {"name":"Wave Junction","mods":[8,9],"start":[5,7],"target":[2,0]}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=LAB;f[17:30,8:22]=SOURCEA;f[17:30,42:56]=SOURCEB;f[34:39,8:8+g.phase[0]*5]=WAVE;f[41:46,8:8+g.phase[1]*5]=WAVE;f[48:53,25:39]=RECEIVER;f[3:6,8:8+sum(g.target)*3]=TARGET
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q178(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.mods=self.phase=self.target=[];self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q178",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,5,6])
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

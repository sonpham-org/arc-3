"""q169 Uncertainty Routing -- preserve ambiguous cargo at a reversible hub."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,DEPOT,CARGO,HUB,LEFT,RIGHT,EVIDENCE,BAD=9,4,12,10,14,15,6,8
LEVELS=[
 {"name":"Wait for Evidence","target":1,"reveal":1,"deadline":3,"hub":False},
 {"name":"Reversible Hub","target":2,"reveal":2,"deadline":4,"hub":True},
 {"name":"Hold or Route","target":1,"reveal":3,"deadline":5,"hub":True},
 {"name":"One-Way Branch","target":2,"reveal":4,"deadline":6,"hub":True},
 {"name":"Delayed Confidence","target":1,"reveal":5,"deadline":7,"hub":True},
 {"name":"Uncertainty Routing","target":2,"reveal":6,"deadline":8,"hub":True}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=DEPOT;f[26:38,8:20]=CARGO;f[24:40,26:38]=HUB if g.at_hub else DEPOT;f[17:29,45:57]=LEFT;f[39:51,45:57]=RIGHT;f[3:6,8:8+g.time*6]=EVIDENCE
  if g.known:f[12:16,45:57]=LEFT if g.target==1 else RIGHT
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q169(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.target=self.reveal=self.deadline=self.time=0;self.require_hub=self.at_hub=self.known=self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q169",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4])
 def on_set_level(self,l):
  s=LEVELS[self.level_index];self.target=s["target"];self.reveal=s["reveal"];self.deadline=s["deadline"];self.require_hub=s["hub"];self.time=0;self.at_hub=self.known=self.failed=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z in (1,2):
   if z==2:self.at_hub=True
   self.time+=1;self.known=self.time>=self.reveal
   if self.time>self.deadline:self.failed=True;self.lose()
  elif z in (3,4):
   branch=z-2
   if self.known and branch==self.target and (self.at_hub or not self.require_hub):self.next_level()
   else:self.failed=True;self.lose()
  else:self.failed=True;self.lose()
  self.complete_action()

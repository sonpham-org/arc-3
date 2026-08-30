"""q420 Spore Revision -- recalibrate a worn law only at a shared clock event."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,GREENHOUSE,SPORE,HUMIDITY,WEAR,CLOCK,KNOWLEDGE,BAD=10,2,13,12,15,14,6,8
LEVELS=[
 {"name":"Wear Boundary","rule":0,"boundary":1,"mods":[2,3]},
 {"name":"Inverted Growth","rule":1,"boundary":2,"mods":[3,4]},
 {"name":"Rotated Colony","rule":2,"boundary":3,"mods":[4,5]},
 {"name":"Delayed Law","rule":1,"boundary":4,"mods":[5,6]},
 {"name":"Shared Event","rule":2,"boundary":5,"mods":[6,7]},
 {"name":"Spore Revision","rule":0,"boundary":6,"mods":[7,8]}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[5:59,5:59]=GREENHOUSE;f[15:29,9:23]=SPORE;f[15:29,41:55]=SPORE;f[33:38,8:56]=HUMIDITY
  f[42:46,8:8+g.wear*6]=WEAR;f[49:52,8:8+g.phase[0]*5]=CLOCK;f[54:57,8:8+g.phase[1]*5]=KNOWLEDGE if g.evidence is not None else CLOCK
  if g.bad:f[61:64,22:42]=BAD
  return f
class Q420(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.wear=self.candidate=0;self.phase=[0,0];self.evidence=None;self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q420",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,5,6])
 def on_set_level(self,l):self.wear=self.candidate=0;self.phase=[0,0];self.evidence=None;self.bad=False
 def fail(self):self.bad=True;self.lose()
 def step(self):
  z=self.action.id.value;l=LEVELS[self.level_index]
  if z==0:self.complete_action();return
  if z==1:self.phase[0]=(self.phase[0]+1)%l["mods"][0]
  elif z==2:self.phase[1]=(self.phase[1]+1)%l["mods"][1]
  elif z==4 and self.wear<l["boundary"]:self.wear+=1;self.phase=[(self.phase[0]+1)%l["mods"][0],(self.phase[1]+2)%l["mods"][1]]
  elif z==3 and self.wear==l["boundary"] and self.phase==[0,0]:self.evidence=l["rule"]
  elif z==5 and self.evidence is not None:self.candidate=(self.candidate+1)%3
  elif z==6:
   if self.evidence==l["rule"] and self.candidate==l["rule"]:self.next_level()
   else:self.fail()
  else:self.fail()
  self.complete_action()

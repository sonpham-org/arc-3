"""q137 Shared Convention -- feedback moves two partners toward one negotiated mapping."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,TABLE,PARTNERA,PARTNERB,PROPOSAL,FEEDBACK,TARGET,BAD=15,1,9,12,10,14,6,8
LEVELS=[
 {"name":"Agree on One Signal","start":[0,2],"target":1}, {"name":"Move Both Mappings","start":[3,1],"target":2},
 {"name":"Feedback Convention","start":[0,3],"target":2}, {"name":"Do Not Chase","start":[1,3],"target":0},
 {"name":"Stable Agreement","start":[2,0],"target":3}, {"name":"Shared Convention","start":[3,0],"target":1}]
def step_toward(value,target):
 if value==target:return value
 r=(target-value)%4;l=(value-target)%4;return(value+1)%4 if r<=l else(value-1)%4
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=TABLE;f[17:32,8:22]=PARTNERA;f[17:32,42:56]=PARTNERB;f[38:44,8:8+g.values[0]*9]=FEEDBACK;f[38:44,42:42+g.values[1]*4]=FEEDBACK;f[47:51,20:20+g.proposal*8]=PROPOSAL;f[3:6,8:8+g.target*10]=TARGET
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q137(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.values=[];self.target=self.proposal=0;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q137",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,5,6])
 def on_set_level(self,l):
  s=LEVELS[self.level_index];self.values=list(s["start"]);self.target=s["target"];self.proposal=0;self.failed=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z==1:self.proposal=(self.proposal-1)%4
  elif z==2:self.proposal=(self.proposal+1)%4
  elif z==5:self.values=[step_toward(v,self.proposal) for v in self.values]
  elif z==6:
   if self.values==[self.target,self.target] and self.proposal==self.target:self.next_level()
   else:self.failed=True;self.lose()
  self.complete_action()

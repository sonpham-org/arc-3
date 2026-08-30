"""q377 Spectrum Rig -- build a prism tool then reuse its relational algebra with agents."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,GALLERY,SLOT,REDIRECT,JOIN,SUPPORT,TRANSFER,BAD=6,2,9,12,10,14,15,8
BASE=[1,3,2,4]
LEVELS=[
 {"name":"Prism Geometry","tool":[1,2,1],"map":[1,2,3,4]},{"name":"Reusable Rig","tool":[2,1,3],"map":[2,4,1,3]},
 {"name":"Relational Transfer","tool":[3,1,2,1],"map":[3,1,4,2]},{"name":"Agent Surface","tool":[1,3,2,2],"map":[4,2,3,1]},
 {"name":"Two Functions","tool":[2,3,1,2,1],"map":[2,3,4,1]},{"name":"Spectrum Rig","tool":[3,2,1,3,2],"map":[3,4,2,1]}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=GALLERY;n=len(g.slots)
  for i,v in enumerate(g.slots):x=8+i*(48//n);f[17:33,x:x+8]=SLOT if not v else (REDIRECT,JOIN,SUPPORT)[v-1]
  f[39:44,8:8+len(g.result)*9]=TRANSFER;f[48:52,8:30]=TRANSFER if g.phase else GALLERY
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q377(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.tool=self.mapping=self.slots=self.result=[];self.cursor=self.phase=0;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q377",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,5,6])
 def on_set_level(self,l):
  s=LEVELS[self.level_index];self.tool=list(s["tool"]);self.mapping=list(s["map"]);self.slots=[0]*len(self.tool);self.result=[];self.cursor=self.phase=0;self.failed=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if self.phase==0 and z in (1,2,3):self.slots[self.cursor]=z
  elif self.phase==0 and z==4:self.cursor=(self.cursor+1)%len(self.slots)
  elif self.phase==0 and z==5:
   if self.slots==self.tool:self.phase=1
   else:self.failed=True;self.lose()
  elif self.phase==1 and z in (1,2,3,4):self.result.append(self.mapping[z-1])
  elif self.phase==1 and z==6:
   if self.result==BASE:self.next_level()
   else:self.failed=True;self.lose()
  else:self.failed=True;self.lose()
  self.complete_action()

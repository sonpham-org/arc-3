"""q176 Heat Diffusion -- local heat spreads and crosses visible material thresholds."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,CHAMBER,COLD,WARM,HOT,TARGET,CURSOR,BAD=11,1,10,12,8,14,15,6
LEVELS=[
 {"name":"One Diffusion","start":[0,3,0],"plan":[5]},
 {"name":"Heat a Neighbor","start":[0,1,0,0],"plan":[1,5]},
 {"name":"Threshold Field","start":[0,3,0,1],"plan":[4,1,5,5]},
 {"name":"Predict the Spread","start":[1,0,3,0,1],"plan":[4,4,2,5,3,5]},
 {"name":"Material Change","start":[0,2,0,3,0,1],"plan":[4,1,5,4,4,2,5]},
 {"name":"Heat Diffusion","start":[1,0,3,0,2,0],"plan":[4,4,1,5,4,4,2,5,5]}]
def diffuse(vals):return tuple((vals[max(0,i-1)]+2*v+vals[min(len(vals)-1,i+1)])//4 for i,v in enumerate(vals))
def derive(level):
 v=list(level["start"]);c=0
 for z in level["plan"]:
  if z==1:v[c]=min(4,v[c]+1)
  elif z==2:v[c]=max(0,v[c]-1)
  elif z==3:c=(c-1)%len(v)
  elif z==4:c=(c+1)%len(v)
  elif z==5:v=list(diffuse(v))
 return v
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=CHAMBER;n=len(g.values)
  for i,(v,t) in enumerate(zip(g.values,g.target)):x=7+i*(50//n);f[19:42,x:x+8]=COLD if v<2 else WARM if v<4 else HOT;f[34-v*4:38,x+2:x+6]=HOT;f[13:16,x:x+t*2]=TARGET;f[46:50,x:x+8]=CURSOR if i==g.cursor else CHAMBER
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q176(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.values=self.target=[];self.cursor=0;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q176",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,5,6])
 def on_set_level(self,l):
  s=LEVELS[self.level_index];self.values=list(s["start"]);self.target=derive(s);self.cursor=0;self.failed=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z==1:self.values[self.cursor]=min(4,self.values[self.cursor]+1)
  elif z==2:self.values[self.cursor]=max(0,self.values[self.cursor]-1)
  elif z==3:self.cursor=(self.cursor-1)%len(self.values)
  elif z==4:self.cursor=(self.cursor+1)%len(self.values)
  elif z==5:self.values=list(diffuse(self.values))
  elif z==6:
   if self.values==self.target:self.next_level()
   else:self.failed=True;self.lose()
  self.complete_action()

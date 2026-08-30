"""q202 Tide Veil -- schedule observation across coupled reversing currents."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,BASIN,SHELL,SEEN,HIDDEN,CURRENT,TARGET,BAD=2,11,9,15,12,14,6,8
LEVELS=[
 {"name":"Freeze One Pool","n":4,"start":[0,1],"plan":[2,1,2]},
 {"name":"Reversing Current","n":5,"start":[1,3],"plan":[2,2,1,2]},
 {"name":"Coupled Attention","n":6,"start":[2,0],"plan":[1,2,1,2,2]},
 {"name":"Unsafe Branch","n":7,"start":[3,5],"plan":[2,1,2,1,2,2]},
 {"name":"Delayed Seal","n":8,"start":[6,1],"plan":[1,2,2,1,2,1,2]},
 {"name":"Tide Veil","n":9,"start":[4,7],"plan":[2,1,2,2,1,2,1,2]}]
def tick(state,n):
 values,focus,tide=state;v=list(values);other=1-focus;v[other]=(v[other]+tide)%n;return tuple(v),focus,-tide
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[6:58,4:60]=BASIN
  for i,v in enumerate(g.values):x=9+i*32;f[15:31,x:x+14]=SEEN if i==g.focus else HIDDEN;f[34-v*2:38,x:x+14]=SHELL
  f[44:49,8:32 if g.tide>0 else 56]=CURRENT
  for i,v in enumerate(g.target):f[51:55,9+i*32:9+i*32+v*2]=TARGET
  if g.bad:f[60:63,22:42]=BAD
  return f
class Q202(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.n=1;self.values=(0,0);self.target=(0,0);self.focus=0;self.tide=1;self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q202",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,6])
 def on_set_level(self,l):
  x=LEVELS[self.level_index];self.n=x["n"];self.values=tuple(x["start"]);self.focus=0;self.tide=1;s=(self.values,0,1)
  for a in x["plan"]:
   if a==1:s=(s[0],1-s[1],s[2])
   else:s=tick(s,self.n)
  self.target=s[0];self.bad=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z==1:self.focus=1-self.focus
  elif z==2:self.values,self.focus,self.tide=tick((self.values,self.focus,self.tide),self.n)
  elif z==6:
   if self.values==self.target:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()

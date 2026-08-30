"""q296 Palimpsest Ledger -- conserve memory tiles while matching a causal trace."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,ARCHIVE,TILE,TRACE,CURSOR,TARGET,FAILED,BAD=6,10,12,15,14,11,3,8
LEVELS=[
 {"name":"Conserved Tiles","start":[3,0,0],"plan":[1,1]},
 {"name":"Overwritten Trace","start":[1,3,0],"plan":[3,1,2,1]},
 {"name":"Failed Twin","start":[0,2,3],"plan":[2,3,2,1,2]},
 {"name":"Global Ledger","start":[4,0,2],"plan":[1,3,1,2,3,1]},
 {"name":"Causal Distinction","start":[2,3,2],"plan":[3,2,1,3,1,2,1]},
 {"name":"Palimpsest Ledger","start":[0,4,4],"plan":[2,3,1,1,3,2,1,2]}]
def advance(state,z):
 values,cursor,trace=state;v=list(values);n=(cursor+1)%3
 if z==1 and v[cursor]:v[cursor]-=1;v[n]+=1;trace=(trace*3+cursor+1)%11
 elif z==2 and v[n]:v[n]-=1;v[cursor]+=1;trace=(trace*3+n+1)%11
 elif z==3:cursor=n;trace=(trace+5)%11
 else:return None
 return tuple(v),cursor,trace
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[5:59,5:59]=ARCHIVE
  for i,v in enumerate(g.values):x=8+i*18;f[15:47,x:x+12]=TILE;f[47-v*4:47,x:x+12]=TARGET
  f[50:55,8+g.cursor*18:20+g.cursor*18]=CURSOR;f[9:12,8:8+g.trace*4]=TRACE;f[55:58,42:56]=FAILED
  if g.bad:f[61:64,22:42]=BAD
  return f
class Q296(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.values=();self.cursor=self.trace=0;self.target=None;self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q296",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,6])
 def on_set_level(self,l):
  x=LEVELS[self.level_index];self.values=tuple(x["start"]);self.cursor=self.trace=0;s=(self.values,0,0)
  for z in x["plan"]:s=advance(s,z)
  self.target=(s[0],s[2]);self.bad=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z in (1,2,3):
   s=advance((self.values,self.cursor,self.trace),z)
   if s is None:self.bad=True;self.lose()
   else:self.values,self.cursor,self.trace=s
  elif z==6:
   if (self.values,self.trace)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()

"""q038 Balance Web -- redistribute conserved load through capacity-limited edges."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,FIELD,NODE,LOAD,TARGET,EDGE,CURSOR,BAD=9,0,10,12,14,3,11,8
LEVELS=[
 {"name":"One Edge","start":[3,0],"target":[1,2],"cap":[3,3],"edges":[(0,1)]},
 {"name":"Shared Sink","start":[2,2,0],"target":[1,1,2],"cap":[3,3,2],"edges":[(0,2),(1,2)]},
 {"name":"Capacity Detour","start":[4,0,1],"target":[1,2,2],"cap":[4,2,3],"edges":[(0,1),(1,2),(0,2)]},
 {"name":"Balance Cycle","start":[3,2,1,0],"target":[1,1,2,2],"cap":[3,3,3,2],"edges":[(0,1),(1,2),(2,3),(0,3)]},
 {"name":"Web Bottleneck","start":[5,0,1,0],"target":[1,2,1,2],"cap":[5,2,2,2],"edges":[(0,1),(1,2),(2,3),(0,3),(0,2)]},
 {"name":"Balance Web","start":[4,2,0,1,0],"target":[1,1,2,1,2],"cap":[4,3,2,2,2],"edges":[(0,1),(0,2),(1,3),(2,3),(3,4),(1,4)]}]
def move(vals,edge,reverse,cap):
 a,b=edge
 if reverse:a,b=b,a
 out=list(vals)
 if out[a]>0 and out[b]<cap[b]:out[a]-=1;out[b]+=1
 return tuple(out)
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[7:57,4:60]=FIELD;n=len(g.values)
  for i,(v,t) in enumerate(zip(g.values,g.target)):
   x=8+i*(48//n);f[19:43,x:x+9]=NODE;f[37-v*4:40,x+2:x+7]=LOAD;f[13:16,x:x+t*3]=TARGET
  for i in range(len(g.edges)):f[47:50,7+i*9:14+i*9]=CURSOR if i==g.cursor else EDGE
  f[3:6,48:57]=LOAD if g.reverse else EDGE
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q038(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.values=self.target=self.cap=();self.edges=[];self.cursor=0;self.reverse=False;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q038",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,3,4,5,6])
 def on_set_level(self,l):
  s=LEVELS[self.level_index];self.values=tuple(s["start"]);self.target=tuple(s["target"]);self.cap=tuple(s["cap"]);self.edges=list(map(tuple,s["edges"]));self.cursor=0;self.reverse=False;self.failed=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z==1:self.reverse=not self.reverse
  elif z==3:self.cursor=(self.cursor-1)%len(self.edges)
  elif z==4:self.cursor=(self.cursor+1)%len(self.edges)
  elif z==5:self.values=move(self.values,self.edges[self.cursor],self.reverse,self.cap)
  elif z==6:
   if self.values==self.target:self.next_level()
   else:self.failed=True;self.lose()
  self.complete_action()

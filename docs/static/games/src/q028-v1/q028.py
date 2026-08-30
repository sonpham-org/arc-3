"""q028 Causal Quilt -- sparse local probes identify boundaries between transformation laws."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,CLOTH,PATCH,LAW0,LAW1,LAW2,BOUNDARY,CURSOR,BAD=15,7,1,9,12,14,6,11,8
LEVELS=[
 {"name":"One Seam","laws":[0,0,1,1]}, {"name":"Probe Both Sides","laws":[0,0,2,2,2]},
 {"name":"Three Regions","laws":[1,1,0,2,2,2]}, {"name":"Short Middle Law","laws":[0,0,1,2,2,0,0]},
 {"name":"Alternating Patches","laws":[2,2,0,0,1,1,2,2]}, {"name":"Causal Quilt","laws":[0,0,1,2,2,1,1,0,2]}]
def seams(laws):return {i for i in range(len(laws)-1) if laws[i]!=laws[i+1]}
def regions(laws):
 out=[];start=0
 for i in range(1,len(laws)):
  if laws[i]!=laws[i-1]:out.append(set(range(start,i)));start=i
 out.append(set(range(start,len(laws))));return out
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=CLOTH;n=len(g.laws)
  for i,l in enumerate(g.laws):
   x=6+i*(53//n);f[19:42,x:x+7]=[LAW0,LAW1,LAW2][l] if i in g.observed else PATCH;f[13:16,x:x+7]=CURSOR if i==g.cursor else CLOTH
   if i in g.marks:f[44:50,x+5:x+8]=BOUNDARY
  f[3:6,7:7+g.paint*7]=LAW2
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q028(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.laws=[];self.cursor=self.paint=0;self.observed=self.marks=set();self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q028",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,6])
 def on_set_level(self,l):
  self.laws=list(LEVELS[self.level_index]["laws"]);self.cursor=0;self.paint=len(regions(self.laws));self.observed=set();self.marks=set();self.failed=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z==1:self.cursor=max(0,self.cursor-1)
  elif z==2:self.cursor=min(len(self.laws)-1,self.cursor+1)
  elif z==3:
   if self.paint:self.paint-=1;self.observed.add(self.cursor)
   else:self.failed=True;self.lose()
  elif z==4:
   if self.cursor in self.marks:self.marks.remove(self.cursor)
   else:self.marks.add(self.cursor)
  elif z==6:
   if self.marks==seams(self.laws) and all(self.observed&r for r in regions(self.laws)):self.next_level()
   else:self.failed=True;self.lose()
  self.complete_action()

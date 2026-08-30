"""q083 Unmarked Lineage -- select an identical descendant by its ancestry graph."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,PANEL,ROOT,CHILD,LINK,CURSOR,TARGET,BAD=8,1,12,10,3,11,14,5
LEVELS=[
 {"name":"Two Children","parents":[0,1],"target":0},
 {"name":"One Split","parents":[0,1,0],"target":2},
 {"name":"Crossed Family","parents":[0,1,0,1],"target":3},
 {"name":"Hidden Grandchild","parents":[0,1,0,1,2],"target":4},
 {"name":"Lineage Chain","parents":[0,1,0,2,1,4],"target":5},
 {"name":"Unmarked Lineage","parents":[0,1,0,1,2,3,5],"target":6}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[7:57,4:60]=PANEL;n=len(g.parents)
  xs=[8+i*(48//max(1,n-1)) for i in range(n)]
  for i,p in enumerate(g.parents):
   if i>=2:
    x0,x1=xs[p],xs[i]
    for t in range(11):x=round(x0+(x1-x0)*t/10);y=18+t*2;f[y:y+2,x:x+2]=LINK
   f[13:20,xs[i]-3:xs[i]+4]=ROOT if i<2 else CHILD;f[40:47,xs[i]-3:xs[i]+4]=CHILD
  f[49:53,xs[g.cursor]-4:xs[g.cursor]+5]=CURSOR;root=g.ancestor(g.target);f[2:5,8+root*12:17+root*12]=TARGET
  if g.failed:f[59:63,25:39]=BAD
  return f
class Q083(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.parents=[];self.target=self.cursor=0;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q083",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[3,4,6])
 def ancestor(self,i):
  while i>=2:i=self.parents[i]
  return i
 def on_set_level(self,l):s=LEVELS[self.level_index];self.parents=list(s["parents"]);self.target=s["target"];self.cursor=0;self.failed=False
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a==3:self.cursor=(self.cursor-1)%len(self.parents)
  elif a==4:self.cursor=(self.cursor+1)%len(self.parents)
  elif a==6:
   if self.cursor==self.target:self.next_level()
   else:self.failed=True;self.lose()
  else:self.failed=True;self.lose()
  self.complete_action()

"""q030 Antidote Network -- treatments suppress neighbors and strengthen distance-two nodes."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,CLINIC,NODE,SICK,HEALTHY,LINK,PROBE,CURSOR,BAD=13,1,3,8,14,10,9,11,6
LEVELS=[
 {"name":"Neighbor Suppression","start":[2,2,0],"edges":[(0,1),(1,2)],"plan":[5]},
 {"name":"Distance Two","start":[2,1,1,0],"edges":[(0,1),(1,2),(2,3)],"plan":[4,5]},
 {"name":"Fork Response","start":[2,2,1,0],"edges":[(0,1),(0,2),(2,3)],"plan":[5,4,4,5]},
 {"name":"Infer the Network","start":[2,1,2,1,0],"edges":[(0,1),(1,2),(1,3),(3,4)],"plan":[4,5,4,4,5]},
 {"name":"Preserve Distant Nodes","start":[2,2,1,1,0],"edges":[(0,1),(1,2),(2,3),(1,4)],"plan":[4,4,5,3,5]},
 {"name":"Antidote Network","start":[2,1,2,1,1,0],"edges":[(0,1),(1,2),(1,3),(3,4),(2,5)],"plan":[4,5,4,4,5,3,3,5]}]
def treat(vals,edges,node):
 adj={i:set() for i in range(len(vals))}
 for a,b in edges:adj[a].add(b);adj[b].add(a)
 near=adj[node];far=set().union(*(adj[n] for n in near))-near-{node};out=list(vals);out[node]=max(0,out[node]-1)
 for i in near:out[i]=max(0,out[i]-1)
 for i in far:out[i]=min(2,out[i]+1)
 return tuple(out)
def derive(level):
 v=tuple(level["start"]);cur=0
 for a in level["plan"]:
  if a==3:cur=(cur-1)%len(v)
  elif a==4:cur=(cur+1)%len(v)
  elif a==5:v=treat(v,level["edges"],cur)
 return v
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=CLINIC;n=len(g.values)
  for i,(v,t) in enumerate(zip(g.values,g.target)):
   x=7+i*(50//n);f[21:39,x:x+8]=NODE;f[34-v*5:37,x+2:x+6]=SICK if v else HEALTHY;f[14:17,x:x+t*3]=PROBE;f[44:48,x:x+8]=CURSOR if i==g.cursor else CLINIC
  if g.probed:f[3:6,8:56]=LINK
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q030(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.values=self.target=();self.edges=[];self.cursor=0;self.probed=self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q030",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,3,4,5,6])
 def on_set_level(self,l):
  s=LEVELS[self.level_index];self.values=tuple(s["start"]);self.target=derive(s);self.edges=list(map(tuple,s["edges"]));self.cursor=0;self.probed=self.failed=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z==1:self.probed=True
  elif z==3:self.cursor=(self.cursor-1)%len(self.values)
  elif z==4:self.cursor=(self.cursor+1)%len(self.values)
  elif z==5:self.values=treat(self.values,self.edges,self.cursor)
  elif z==6:
   if self.probed and self.values==self.target:self.next_level()
   else:self.failed=True;self.lose()
  self.complete_action()

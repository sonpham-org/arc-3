"""q039 Charge Pairs -- create and consume opposite charges with conserved net charge."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,LAB,NODE,POS,NEG,TARGET,CURSOR,BAD=6,0,3,9,12,14,11,8
LEVELS=[
 {"name":"Opposite Pair","start":[0,0],"target":[1,-1],"edges":[(0,1)]},
 {"name":"Net Not Count","start":[0,0,0],"target":[1,0,-1],"edges":[(0,1),(1,2),(0,2)]},
 {"name":"Annihilate Locally","start":[1,-1,0],"target":[0,1,-1],"edges":[(0,1),(1,2),(0,2)]},
 {"name":"Charge Routing","start":[0,0,0,0],"target":[2,-1,0,-1],"edges":[(0,1),(1,2),(2,3),(0,3)]},
 {"name":"Paired Gates","start":[1,0,-1,0],"target":[-1,1,1,-1],"edges":[(0,1),(1,2),(2,3),(0,3),(0,2)]},
 {"name":"Charge Pairs","start":[0,1,-1,0,0],"target":[2,-1,0,1,-2],"edges":[(0,1),(1,2),(2,3),(3,4),(0,4),(1,4)]}]
def pair(vals,edge,reverse,delta):
 a,b=edge
 if reverse:a,b=b,a
 out=list(vals);na,nb=out[a]+delta,out[b]-delta
 if -3<=na<=3 and -3<=nb<=3:out[a],out[b]=na,nb
 return tuple(out)
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[7:57,4:60]=LAB;n=len(g.values)
  for i,(v,t) in enumerate(zip(g.values,g.target)):
   x=8+i*(48//n);f[20:42,x:x+9]=NODE;f[29-v*4:33,x+2:x+7]=POS if v>=0 else NEG;f[13:17,x:x+abs(t)*3]=TARGET
  for i in range(len(g.edges)):f[47:50,7+i*8:13+i*8]=CURSOR if i==g.cursor else NODE
  f[3:6,49:57]=NEG if g.reverse else POS
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q039(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.values=self.target=();self.edges=[];self.cursor=0;self.reverse=self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q039",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,5,6])
 def on_set_level(self,l):
  s=LEVELS[self.level_index];self.values=tuple(s["start"]);self.target=tuple(s["target"]);self.edges=list(map(tuple,s["edges"]));self.cursor=0;self.reverse=self.failed=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z==1:self.values=pair(self.values,self.edges[self.cursor],self.reverse,1)
  elif z==2:self.values=pair(self.values,self.edges[self.cursor],self.reverse,-1)
  elif z==3:self.cursor=(self.cursor-1)%len(self.edges)
  elif z==4:self.cursor=(self.cursor+1)%len(self.edges)
  elif z==5:self.reverse=not self.reverse
  elif z==6:
   if self.values==self.target:self.next_level()
   else:self.failed=True;self.lose()
  self.complete_action()
